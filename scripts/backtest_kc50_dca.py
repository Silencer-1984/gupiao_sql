# -*- coding: utf-8 -*-
"""科创50 定投随机检验 + 方案对比（对齐纳指 backtest_mc.py 范式）。

数据：sh588000 ETF（2020-11-16起）+ 000688 指数（2020-01起）
方法：随机起点/时长/扣款日，3000组，每组无脑定投，计算总收益率与XIRR。
对比：ETF vs 指数 vs 同期纳指159941（若数据可得）。
"""
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

pd.set_option('display.width', 220)
c = sqlite3.connect('data/ashare.db')

# ---------- 载入 ----------
etf = pd.read_sql("select trade_date,open,close from px_etf_daily where etf_code='sh588000' order by trade_date", c)
etf['trade_date'] = pd.to_datetime(etf.trade_date)
idx = pd.read_sql("select trade_date,close,pe_ttm from px_index_daily_csi where index_code='000688' and close!=1000 order by trade_date", c)
idx['trade_date'] = pd.to_datetime(idx.trade_date)
ndx = pd.read_sql("select trade_date,close_adj from px_lof_daily where fund_code='159941' and close_adj is not null order by trade_date", c)
ndx['trade_date'] = pd.to_datetime(ndx.trade_date)

print("数据区间:")
for n, d in [('ETF sh588000', etf), ('指数 000688', idx), ('纳指 159941', ndx)]:
    print(f"  {n:<16} {d.trade_date.min().date()} ~ {d.trade_date.max().date()}  n={len(d)}")

# ETF 拆分检查（2020-11起应无拆分，但检查异常跳变）
etf['ret'] = etf.close.pct_change()
big = etf[etf.ret.abs() > 0.11]
print(f"ETF 单日涨跌>11%的交易日: {len(big)}", big[['trade_date', 'close', 'ret']].head().to_string(index=False) if len(big) else "")

# ---------- 定投引擎 ----------
def dca(series, dates, start, months, payday, amount=5000, freq='M'):
    """series=价格序列(pd.Series，index=dates)，每月payday号买入，返回(收益率, XIRR, 期数, 份额成本明细)"""
    start = pd.Timestamp(start)
    end = start + pd.DateOffset(months=months)
    mask = (dates >= start) & (dates <= end)
    sub = pd.Series(series.values[mask], index=dates[mask])
    if len(sub) < 10:
        return None
    buys = []  # (date, price)
    if freq == 'M':
        for m in range(months):
            y = start.year + (start.month - 1 + m) // 12
            mo = (start.month - 1 + m) % 12 + 1
            target = pd.Timestamp(y, mo, 1) + pd.Timedelta(days=payday - 1)
            fut = sub[sub.index >= target]
            if len(fut) and fut.index[0] <= end:
                buys.append((fut.index[0], fut.iloc[0]))
    else:  # 周投
        cur = start
        while cur <= end:
            fut = sub[sub.index >= cur]
            if not len(fut): break
            buys.append((fut.index[0], fut.iloc[0]))
            cur = fut.index[0] + pd.Timedelta(days=7)
    if len(buys) < 6:
        return None
    total_cost = len(buys) * amount
    shares = sum(amount / p for _, p in buys)
    final_px = sub.iloc[-1]
    final_val = shares * final_px
    ret = final_val / total_cost - 1
    # XIRR
    flows = [(d, -amount) for d, p in buys] + [(sub.index[-1], final_val)]
    try:
        xirr = xirr_calc(flows)
    except Exception:
        xirr = np.nan
    return dict(ret=ret, xirr=xirr, n=len(buys), cost=total_cost, val=final_val,
                buy_px=[p for _, p in buys], buy_dates=[d for d, _ in buys], end=sub.index[-1], end_px=final_px)


def xirr_calc(flows):
    d0 = flows[0][0]
    amounts = np.array([a for _, a in flows])
    yrs = np.array([(d - d0).days / 365.25 for d, _ in flows])
    def npv(r):
        return np.sum(amounts / (1 + r) ** yrs)
    lo, hi = -0.9999, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def sample_runs(series, dates, label, n=3000, seed=20261125, months_range=(12,24,36,60),
                start_range=('2021-01-01','2023-11-01')):
    rng = np.random.default_rng(seed)
    lo = pd.Timestamp(start_range[0]); hi = pd.Timestamp(start_range[1])
    lo_ord, hi_ord = lo.toordinal(), hi.toordinal()
    rows = []
    for _ in range(n):
        start = pd.Timestamp.fromordinal(int(rng.integers(lo_ord, hi_ord)))
        months = int(rng.choice(months_range))
        payday = int(rng.integers(1, 29))
        r = dca(series, dates, start, months, payday)
        if r:
            rows.append(r)
    dfres = pd.DataFrame(rows)
    if not len(dfres):
        print(f"{label}: 无有效样本"); return
    print(f"\n=== {label}  n={len(dfres)} ===")
    print(f"  收益率 均值{dfres.ret.mean()*100:+.2f}% 中位{dfres.ret.median()*100:+.2f}% "
          f"5%分位{dfres.ret.quantile(.05)*100:+.2f}% 95%分位{dfres.ret.quantile(.95)*100:+.2f}% "
          f"正收益占比{(dfres.ret>0).mean()*100:.1f}%")
    print(f"  XIRR  中位{dfres.xirr.median()*100:+.2f}%  5%分位{dfres.xirr.quantile(.05)*100:+.2f}%")
    return dfres


etf_s = etf.set_index('trade_date').close
idx_s = idx.set_index('trade_date').close
ndx_s = ndx.set_index('trade_date').close_adj

print("\n" + "="*90)
print("随机定投 3000 组（起点2021-01~2023-11，时长12/24/36/60月随机，扣款日1-28随机）")
print("="*90)
r_etf = sample_runs(etf_s, etf.trade_date, '科创50ETF sh588000')
r_idx = sample_runs(idx_s, idx.trade_date, '科创50指数 000688')
r_ndx = sample_runs(ndx_s, ndx.trade_date, '纳指ETF 159941(复权)')

# ---------- 固定3年/5年 ----------
print("\n" + "="*90)
print("固定窗口：每月15日，3年 / 5年")
print("="*90)
print(f"{'标的':<18}{'窗口':<10}{'起点':<12}{'期末':<12}{'收益率':>10}{'XIRR':>9}{'期数':>6}")
for start in ['2020-11-20', '2021-01-01', '2021-06-01', '2022-01-01', '2023-01-01']:
    for months in [36, 60]:
        for nm, s, dt in [('ETF', etf_s, etf.trade_date), ('指数', idx_s, idx.trade_date)]:
            r = dca(s, dt, start, months, 15)
            if r:
                print(f"{nm:<18}{months}月{'':<3}{start:<12}{r['end'].date().strftime('%Y-%m-%d'):<12}"
                      f"{r['ret']*100:>+9.1f}%{r['xirr']*100:>+8.1f}%{r['n']:>6}")
