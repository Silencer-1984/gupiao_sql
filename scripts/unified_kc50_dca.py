# -*- coding: utf-8 -*-
"""统一口径的最终定投对比：所有方案用同一引擎、同一批随机样本。

统一设定：
- 买入价：T日收盘（无未来函数，实盘可近似尾盘申购/场内买入）
- 期末估值：start+months 顺延到最近交易日收盘
- 随机：起点2021-01~2023-11，时长12/24/36/60月，扣款日1~28，种子20261125
- 数量：2000组
"""
import sqlite3
import numpy as np
import pandas as pd

c = sqlite3.connect('data/ashare.db')
e = pd.read_sql("select trade_date,open,close from px_etf_daily where etf_code='sh588000' order by trade_date", c)
e['trade_date'] = pd.to_datetime(e.trade_date)
e = e.reset_index(drop=True)
DATES = e.trade_date
CLOSE = dict(zip(e.trade_date, e.close))
pos = {d: i for i, d in enumerate(DATES)}
n = pd.read_sql("select trade_date,close_adj from px_lof_daily where fund_code='159941' and close_adj is not null order by trade_date", c)
n['trade_date'] = pd.to_datetime(n.trade_date)
NDATES = n.trade_date
NCLOSE = dict(zip(n.trade_date, n.close_adj))


def schedule(dates, start, months, payday):
    end = start + pd.DateOffset(months=months)
    out = []
    for m in range(months):
        y = start.year + (start.month - 1 + m) // 12
        mo = (start.month - 1 + m) % 12 + 1
        target = pd.Timestamp(y, mo, 1) + pd.Timedelta(days=payday - 1)
        fut = dates[dates >= target]
        if len(fut) and fut.iloc[0] <= end: out.append(fut.iloc[0])
    fut_end = dates[dates >= end]
    end_actual = fut_end.iloc[0] if len(fut_end) else dates.iloc[-1]
    return out, end_actual


def run(buys, end, price_map, dates, tp=None):
    if len(buys) < 6: return None
    realized, sh, cycle_cost, total = 0.0, 0.0, 0.0, 0.0
    idxmap = {d: i for i, d in enumerate(dates)}
    for k, d in enumerate(buys):
        p = price_map[d]
        sh += 5000.0 / p
        cycle_cost += 5000.0
        total += 5000.0
        if tp:
            i0 = idxmap[d]
            i1 = idxmap[buys[k+1]] if k+1 < len(buys) else idxmap[end]
            for i in range(i0, i1):
                dd = dates.iloc[i]
                if sh * price_map[dd] >= cycle_cost * (1 + tp):
                    sell_d = dates.iloc[min(i+1, len(dates)-1)]
                    realized += sh * price_map[sell_d]
                    sh, cycle_cost = 0.0, 0.0
                    break
    liquid = sh * price_map[end] + realized
    return dict(ret=liquid / total - 1, invest=total)


rng = np.random.default_rng(20261125)
lo = pd.Timestamp('2021-01-01').toordinal()
hi = pd.Timestamp('2023-11-01').toordinal()
params = [(pd.Timestamp.fromordinal(int(rng.integers(lo, hi))),
           int(rng.choice([12, 24, 36, 60])), int(rng.integers(1, 29))) for _ in range(2000)]

print("=" * 96)
print("统一口径：2000组随机定投，买入=当日收盘，卖出止盈=T+1收盘（无前视）")
print("=" * 96)
print(f"{'方案':<22}{'中位收益':>11}{'均值':>10}{'正收益%':>9}{'5%分位':>10}{'95%分位':>10}")
configs = [
    ('科创50ETF 不止盈', CLOSE, DATES, None),
    ('科创50ETF 止盈20%', CLOSE, DATES, 0.20),
    ('科创50ETF 止盈30%', CLOSE, DATES, 0.30),
    ('科创50ETF 止盈50%', CLOSE, DATES, 0.50),
    ('纳指159941 不止盈', NCLOSE, NDATES, None),
]
label_map = {}
for label, pm, dt, tp in configs:
    res = []
    for start, months, payday in params:
        if label.startswith('纳指'):
            if start < pd.Timestamp('2021-01-01'): continue
        buys, end = schedule(dt, start, months, payday)
        r = run(buys, end, pm, dt, tp)
        if r: res.append(r)
    d = pd.DataFrame(res)
    print(f"{label:<22}{d.ret.median()*100:>+10.2f}%{d.ret.mean()*100:>+9.2f}%{(d.ret>0).mean()*100:>8.1f}%"
          f"{d.ret.quantile(.05)*100:>+9.2f}%{d.ret.quantile(.95)*100:>+9.2f}%")
    label_map[label] = d

# 扣款日 & 频率（固定3年，4起点）
print("\n" + "=" * 96)
print("扣款日规律：固定3年，4个起点，收益率")
print("=" * 96)
print(f"{'扣款日':<10}{'2021起':>11}{'2022起':>11}{'2023起':>11}{'2024起':>11}{'均值':>10}")
for pd_ in [1, 5, 10, 15, 20, 25, 28]:
    row = []
    for st in ['2021-01-01', '2022-01-01', '2023-01-01', '2024-01-01']:
        buys, end = schedule(DATES, pd.Timestamp(st), 36, pd_)
        r = run(buys, end, CLOSE, DATES, None)
        row.append(r['ret'] if r else np.nan)
    print(f"{pd_:>3}日{'':<6}{row[0]*100:>+10.1f}%{row[1]*100:>+10.1f}%{row[2]*100:>+10.1f}%{row[3]*100:>+10.1f}%{np.nanmean(row)*100:>+9.1f}%")

# 周投 vs 月投（等金额，总投入对齐）
print("\n" + "=" * 96)
print("定投频率：固定3年，每月投5000 vs 每两周投2500（总投入相同）")
print("=" * 96)
for st in ['2021-01-01', '2022-01-01', '2023-01-01', '2024-01-01']:
    start = pd.Timestamp(st)
    # 月投
    buys_m, end = schedule(DATES, start, 36, 15)
    r_m = run(buys_m, end, CLOSE, DATES, None)
    # 双周投：每14个交易日一次，金额2500
    end_idx = pos[end]
    start_fut = DATES[DATES >= start]
    start_idx = pos[start_fut.iloc[0]] if len(start_fut) else 0
    buys_w = [d for i, d in enumerate(DATES) if start_idx <= i <= end_idx and (i - start_idx) % 10 == 0]
    sh_w = sum(2500 / CLOSE[d] for d in buys_w)
    r_w = sh_w * CLOSE[end] / (len(buys_w) * 2500) - 1
    print(f"  {st[:7]}: 月投{r_m['ret']*100:>+7.1f}%  双周投{r_w*100:>+7.1f}%  差值{(r_w-r_m['ret'])*100:>+6.1f}pp")
