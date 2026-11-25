# -*- coding: utf-8 -*-
"""修正两处偏差 + 稳健性检验：
1. 止盈用逐日T+1开盘成交（无前视），止盈后重启定投
2. MA200暂停等方案保证最小期数，不丢弃样本
3. 多随机种子检验扣款日/方案优势是否稳健
"""
import sqlite3
import numpy as np
import pandas as pd

c = sqlite3.connect('data/ashare.db')
etf = pd.read_sql("select trade_date,open,close from px_etf_daily where etf_code='sh588000' order by trade_date", c)
etf['trade_date'] = pd.to_datetime(etf.trade_date)
idx = pd.read_sql("select trade_date,close,pe_ttm from px_index_daily_csi where index_code='000688' and close!=1000 order by trade_date", c)
idx['trade_date'] = pd.to_datetime(idx.trade_date)
df = etf[['trade_date','open','close']].merge(
    idx[['trade_date','pe_ttm']], on='trade_date', how='left').sort_values('trade_date').reset_index(drop=True)
df['ma200'] = df.close.rolling(200, min_periods=200).mean()
df['pe_pct'] = df.pe_ttm.rolling(500, min_periods=200).apply(
    lambda s: (s[:-1] < s[-1]).mean() if len(s) > 1 else np.nan, raw=True).fillna(0.5)

DATES = df.trade_date
OPEN = dict(zip(df.trade_date, df.open))
CLOSE = dict(zip(df.trade_date, df.close))
PEP = dict(zip(df.trade_date, df.pe_pct))
MA200 = dict(zip(df.trade_date, df.ma200))
pos = {d: i for i, d in enumerate(DATES)}


def xirr_fast(flows):
    d0 = flows[0][0]
    amt = np.array([a for _, a in flows])
    yrs = np.array([(d - d0).days / 365.25 for d, _ in flows])
    def npv(r): return np.sum(amt / (1 + r) ** yrs)
    lo, hi = -0.9999, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(mid) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def buy_dates(start, months, payday):
    end = start + pd.DateOffset(months=months)
    out = []
    for m in range(months):
        y = start.year + (start.month - 1 + m) // 12
        mo = (start.month - 1 + m) % 12 + 1
        target = pd.Timestamp(y, mo, 1) + pd.Timedelta(days=payday - 1)
        fut = DATES[DATES >= target]
        if len(fut) and fut.iloc[0] <= end: out.append(fut.iloc[0])
    return out


def dca_tp(buys, tp=None, restart=False):
    """逐日检查止盈；触发后T+1开盘卖出，可选重启。返回现金流与指标。"""
    if len(buys) < 6: return None
    flows, sh, invest = [], 0.0, 0.0
    cycle_start = buys[0]
    sell_dates = []
    i0 = pos[buys[0]]; i1 = pos[buys[-1]]
    cost_basis = 0.0
    for d in buys:
        p = OPEN[d]
        flows.append((d, -5000.0)); invest += 5000.0; cost_basis += 5000.0
        sh += 5000.0 / p
    if tp is None:
        flows.append((DATES[i1], sh * CLOSE[DATES[i1]]))
        return dict(ret=sh * CLOSE[DATES[i1]] / invest - 1, xirr=xirr_fast(flows), invest=invest)
    # 逐日检查：从建仓开始，首次触及目标收益的次日开盘卖出
    peak_check = cost_basis * (1 + tp)
    hit = None
    for i in range(i0 + 1, i1 + 1):
        d = DATES[i]
        if sh * CLOSE[d] >= peak_check:
            sell_d = DATES[i + 1] if i + 1 < len(DATES) else d
            hit = (sell_d, OPEN[sell_d])
            break
    if hit:
        sell_d, sell_px = hit
        flows.append((sell_d, sh * sell_px))
        final_val = sh * sell_px
        end_d = sell_d
    else:
        end_d = DATES[i1]
        final_val = sh * CLOSE[end_d]
        flows.append((end_d, final_val))
    return dict(ret=final_val / invest - 1, xirr=xirr_fast(flows), invest=invest,
                hit=hit is not None, final=end_d)


def sample(seed, n=1500):
    rng = np.random.default_rng(seed)
    lo, hi = pd.Timestamp('2021-01-01').toordinal(), pd.Timestamp('2023-11-01').toordinal()
    params = [(pd.Timestamp.fromordinal(int(rng.integers(lo, hi))),
               int(rng.choice([12, 24, 36, 60])), int(rng.integers(1, 29))) for _ in range(n)]
    return params


print("=" * 100)
print("止盈修正版（T+1开盘卖出，无前视）；1500组×3种子")
print("=" * 100)
for seed in [20261125, 20261126, 20261127]:
    params = sample(seed)
    print(f"\n种子 {seed}:")
    for tp in [None, 0.15, 0.20, 0.25, 0.30, 0.50]:
        res = []
        for start, months, payday in params:
            buys = buy_dates(start, months, payday)
            r = dca_tp(buys, tp)
            if r: res.append(r)
        d = pd.DataFrame(res)
        hit_rate = d['hit'].mean() * 100 if tp else 0
        print(f"  {f'止盈{tp*100:.0f}%' if tp else '不止盈':<10} n={len(d):4d} "
              f"收益中位{d.ret.median()*100:>+7.2f}% 均值{d.ret.mean()*100:>+7.2f}% "
              f"XIRR中位{d.xirr.median()*100:>+7.2f}% 正收益{(d.ret>0).mean()*100:>5.1f}% 触发{hit_rate:>5.1f}%")

print("\n" + "=" * 100)
print("扣款日稳健性：3种子 × 每月1/5/10/15/20/25日（3年起点固定）")
print("=" * 100)
print(f"{'扣款日':<8}{'2021起':>11}{'2022起':>11}{'2023起':>11}{'2024起':>11}{'均值':>10}")
for pd_ in [1, 5, 10, 15, 20, 25, 28]:
    row = []
    for st in ['2021-01-01', '2022-01-01', '2023-01-01', '2024-01-01']:
        buys = buy_dates(pd.Timestamp(st), 36, pd_)
        r = dca_tp(buys, None)
        row.append(r['ret'] if r else np.nan)
    print(f"{pd_:>3}日{'':<4}{row[0]*100:>+10.1f}%{row[1]*100:>+10.1f}%{row[2]*100:>+10.1f}%{row[3]*100:>+10.1f}%{np.nanmean(row)*100:>+9.1f}%")

print("\n" + "=" * 100)
print("PE分位/MA200 加码：固定3年，检验稳健性（ dosage 说明投入倍数不同，看XIRR）")
print("=" * 100)
def dca_mode(buys, mode):
    flows, sh, invest = [], 0.0, 0.0
    for d in buys:
        p = OPEN[d]; mult = 1.0
        if mode == 'pe_double':
            pe = PEP.get(d, 0.5)
            mult = 2.0 if pe < 0.3 else (0.5 if pe > 0.8 else 1.0)
        elif mode == 'ma_double':
            ma = MA200.get(d, np.nan)
            mult = 2.0 if (np.isfinite(ma) and OPEN[d] < ma) else 1.0
        amt = 5000 * mult
        flows.append((d, -amt)); invest += amt; sh += amt / p
    end = buys[-1]
    flows.append((end, sh * CLOSE[end]))
    return dict(ret=sh * CLOSE[end] / invest - 1, xirr=xirr_fast(flows), invest=invest)

print(f"{'方案':<16}{'2021起XIRR':>12}{'2022起XIRR':>12}{'2023起XIRR':>12}{'均值':>10}{'平均投入':>10}")
for mode in ['none', 'pe_double', 'ma_double']:
    xs, ivs = [], []
    for st in ['2021-01-01', '2022-01-01', '2023-01-01']:
        buys = buy_dates(pd.Timestamp(st), 36, 15)
        r = dca_mode(buys, mode)
        xs.append(r['xirr']); ivs.append(r['invest'])
    print(f"{mode:<16}{xs[0]*100:>+11.2f}%{xs[1]*100:>+11.2f}%{xs[2]*100:>+11.2f}%{np.mean(xs)*100:>+9.2f}%{np.mean(ivs):>10.0f}")
