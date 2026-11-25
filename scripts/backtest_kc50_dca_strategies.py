# -*- coding: utf-8 -*-
"""科创50定投方案对比（配对随机抽样，同一批起点/时长/扣款日）。

基准 S0：每月固定日，无脑投5000
方案：
  S1 周投（等额拆分）
  S2 每月5日 vs 15日 vs 25日（扣款日规律）
  S3 PE分位加倍投（低分位多投，高分位少投）
  S4 MA200择时（上方正常/下方加倍）
  S5 恐慌度择时（高恐慌加倍）
  S6 目标收益止盈（浮盈达阈值全卖后重启）
  S7 组合：低PE+低均线加倍 + 止盈

输出：每方案在3000组配对样本上的收益率/XIRR/正收益占比，及相对基准的提升。
"""
import sqlite3
import numpy as np
import pandas as pd

pd.set_option('display.width', 240)
c = sqlite3.connect('data/ashare.db')

etf = pd.read_sql("select trade_date,open,close from px_etf_daily where etf_code='sh588000' order by trade_date", c)
etf['trade_date'] = pd.to_datetime(etf.trade_date)
idx = pd.read_sql("select trade_date,close,pe_ttm from px_index_daily_csi where index_code='000688' and close!=1000 order by trade_date", c)
idx['trade_date'] = pd.to_datetime(idx.trade_date)
fear = pd.read_sql("select trade_date,fear_composite,fear_rv_pct from mkt_fear_daily where index_code='000688' order by trade_date", c)
fear['trade_date'] = pd.to_datetime(fear.trade_date)

# 构造交易日历上的对齐信号（用ETF日期）
df = etf[['trade_date','close']].copy()
df = df.merge(idx[['trade_date','close','pe_ttm']].rename(columns={'close':'idx_close'}), on='trade_date', how='left')
df = df.merge(fear, on='trade_date', how='left')
df = df.sort_values('trade_date').reset_index(drop=True)
for w in [200]:
    df[f'ma{w}'] = df.idx_close.rolling(w, min_periods=w).mean()
df['pe_pct'] = df.pe_ttm.rolling(500, min_periods=200).apply(
    lambda s: (s[:-1] < s[-1]).mean() if len(s) > 1 else np.nan, raw=True)
df = df.fillna({'pe_pct': 0.5, 'fear_composite': 50, 'fear_rv_pct': 50})

PX = dict(zip(df.trade_date, df.close))
PE = dict(zip(df.trade_date, df.pe_pct))
MA = dict(zip(df.trade_date, df.ma200))
FR = dict(zip(df.trade_date, df.fear_rv_pct))
FC = dict(zip(df.trade_date, df.fear_composite))
dates_all = df.trade_date


def xirr(flows):
    if len(flows) < 2: return np.nan
    d0 = flows[0][0]
    amt = np.array([a for _, a in flows])
    yrs = np.array([(d - d0).days / 365.25 for d, _ in flows])
    def npv(r): return np.sum(amt / (1 + r) ** yrs)
    lo, hi = -0.9999, 10.0
    for _ in range(160):
        mid = (lo + hi) / 2
        if npv(mid) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def buy_dates(start, months, payday, freq='M'):
    end = start + pd.DateOffset(months=months)
    out = []
    if freq == 'M':
        for m in range(months):
            y = start.year + (start.month - 1 + m) // 12
            mo = (start.month - 1 + m) % 12 + 1
            target = pd.Timestamp(y, mo, 1) + pd.Timedelta(days=payday - 1)
            fut = dates_all[dates_all >= target]
            if len(fut) and fut.iloc[0] <= end: out.append(fut.iloc[0])
    else:
        cur = start
        while cur <= end:
            fut = dates_all[dates_all >= cur]
            if not len(fut): break
            d0 = fut.iloc[0]
            out.append(d0)
            cur = d0 + pd.Timedelta(days=7)
    return out


def run(buys, mode, base=5000, take_profit=None):
    """mode: 决定每期投入倍数；返回(收益率, xirr, 总投入)"""
    flows, sh, invest = [], 0.0, 0.0
    peak_since_reset = 0.0
    for d in buys:
        p = PX.get(d)
        if p is None: continue
        mult = 1.0
        if mode == 'pe_double':
            pe = PE.get(d, 0.5)
            mult = 2.0 if pe < 0.3 else (0.5 if pe > 0.8 else 1.0)
        elif mode == 'ma_double':
            ma = MA.get(d, np.nan)
            mult = 2.0 if (np.isfinite(ma) and p < ma) else 1.0
        elif mode == 'ma_pause':
            ma = MA.get(d, np.nan)
            if np.isfinite(ma) and p < ma: continue  # MA200下方暂停
        elif mode == 'fear_double':
            fr = FR.get(d, 50)
            mult = 2.0 if fr > 90 else (0.5 if fr < 30 else 1.0)
        elif mode == 'combo':
            pe = PE.get(d, 0.5); ma = MA.get(d, np.nan)
            if pe < 0.3 or (np.isfinite(ma) and p < ma): mult = 2.0
            elif pe > 0.8: mult = 0.5
        amt = base * mult
        flows.append((d, -amt)); invest += amt
        sh += amt / p
    if not flows: return None
    end = buys[-1]
    final_px = PX[end]
    val = sh * final_px
    # 止盈：在持有期内若曾达阈值，按该日价格卖出（近似：用最终日判断乐观偏差，故用逐日检查）
    if take_profit:
        start = buys[0]
        seg = df[(df.trade_date >= start) & (df.trade_date <= end)]
        hit = seg[seg.close >= seg.close.iloc[0] * (1 + take_profit)]
        if len(hit):
            sell_d = hit.trade_date.iloc[0]
            sell_px = hit.close.iloc[0]
            val = sh * sell_px
            end = sell_d
    flows.append((end, val))
    return dict(ret=val / invest - 1, xirr=xirr(flows), invest=invest, val=val, n=len(buys))


# 配对随机样本
rng = np.random.default_rng(20261125)
lo, hi = pd.Timestamp('2021-01-01').toordinal(), pd.Timestamp('2023-11-01').toordinal()
params = []
for _ in range(3000):
    start = pd.Timestamp.fromordinal(int(rng.integers(lo, hi)))
    months = int(rng.choice([12, 24, 36, 60]))
    payday = int(rng.integers(1, 29))
    params.append((start, months, payday))

configs = [
    ('S0 无脑月投15日', dict(payday=15, mode='none', freq='M')),
    ('S0b 无脑月投5日', dict(payday=5, mode='none', freq='M')),
    ('S0c 无脑月投25日', dict(payday=25, mode='none', freq='M')),
    ('S1 周投', dict(mode='none', freq='W')),
    ('S2 月投随机日', dict(mode='none', freq='M')),
    ('S3 PE分位加倍', dict(mode='pe_double', freq='M')),
    ('S4 MA200下方加倍', dict(mode='ma_double', freq='M')),
    ('S5 MA200下方暂停', dict(mode='ma_pause', freq='M')),
    ('S6 恐慌>90加倍', dict(mode='fear_double', freq='M')),
    ('S7 组合低PE+低MA加倍', dict(mode='combo', freq='M')),
]

print("=" * 108)
print("配对随机抽样 3000 组（起点2021-01~2023-11，时长12/24/36/60月）")
print("=" * 108)
print(f"{'方案':<24}{'收益率中位':>12}{'收益均值':>11}{'正收益%':>9}{'XIRR中位':>10}{'5%分位':>10}{'平均投入':>10}")
for name, cfg in configs:
    res = []
    for i, (start, months, payday0) in enumerate(params):
        pd_ = cfg.get('payday', payday0)
        buys = buy_dates(start, months, pd_, cfg['freq'])
        if len(buys) < 6: continue
        r = run(buys, cfg['mode'])
        if r: res.append(r)
    d = pd.DataFrame(res)
    print(f"{name:<24}{d.ret.median()*100:>+11.2f}%{d.ret.mean()*100:>+10.2f}%{(d.ret>0).mean()*100:>8.1f}%"
          f"{d.xirr.median()*100:>+9.2f}%{d.ret.quantile(.05)*100:>+9.2f}%{d.invest.mean():>10.0f}")

# 止盈测试（用S0扣款日，逐日检查）
print("\n" + "=" * 108)
print("止盈测试（月投15日，持期内浮盈达标即卖出；注意：此实现有轻微乐观偏差）")
print("=" * 108)
for tp in [None, 0.20, 0.30, 0.50, 0.80]:
    res = []
    for start, months, payday in params:
        buys = buy_dates(start, months, 15, 'M')
        if len(buys) < 6: continue
        r = run(buys, 'none', take_profit=tp)
        if r: res.append(r)
    d = pd.DataFrame(res)
    label = f"止盈{tp*100:.0f}%" if tp else "不止盈"
    print(f"{label:<24}{d.ret.median()*100:>+11.2f}%{d.ret.mean()*100:>+10.2f}%{(d.ret>0).mean()*100:>8.1f}%"
          f"{d.xirr.median()*100:>+9.2f}%{d.ret.quantile(.05)*100:>+9.2f}%")

# 固定3年窗口的方案对比（每月15日）
print("\n" + "=" * 108)
print("固定3年（2021-01 / 2022-01 / 2023-01 起点，每月15日）各方案收益率")
print("=" * 108)
print(f"{'方案':<24}{'2021-01起':>12}{'2022-01起':>12}{'2023-01起':>12}{'均值':>10}")
for name, cfg in configs:
    row = []
    for st in ['2021-01-01', '2022-01-01', '2023-01-01']:
        buys = buy_dates(pd.Timestamp(st), 36, cfg.get('payday', 15), cfg['freq'])
        r = run(buys, cfg['mode'])
        row.append(r['ret'] if r else np.nan)
    print(f"{name:<24}{row[0]*100:>+11.1f}%{row[1]*100:>+11.1f}%{row[2]*100:>+11.1f}%{np.mean(row)*100:>+9.1f}%")
