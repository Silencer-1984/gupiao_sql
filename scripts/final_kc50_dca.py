# -*- coding: utf-8 -*-
"""科创50定投最终方案（干净现金流模型）。

核心修正：
1. 期末估值用 start+months 当日收盘（不是最后一笔买入日）
2. 止盈卖出所得计入"落袋现金"，重启后新周期独立核算，不重复计份额
3. 最终价值 = 当前持仓市值 + 累计落袋现金
"""
import sqlite3
import numpy as np
import pandas as pd

c = sqlite3.connect('data/ashare.db')
e = pd.read_sql("select trade_date,open,close from px_etf_daily where etf_code='sh588000' order by trade_date", c)
e['trade_date'] = pd.to_datetime(e.trade_date).reset_index(drop=True)
DATES = e.trade_date
OPEN = dict(zip(e.trade_date, e.open))
CLOSE = dict(zip(e.trade_date, e.close))
pos = {d: i for i, d in enumerate(DATES)}


def xirr(flows):
    d0 = flows[0][0]
    if (flows[-1][0] - d0).days < 180: return np.nan
    amt = np.array([a for _, a in flows])
    yrs = np.array([(d - d0).days / 365.25 for d, _ in flows])
    def f(r): return np.sum(amt / (1 + r) ** yrs)
    def df(r): return np.sum(-yrs * amt / (1 + r) ** (yrs + 1))
    r = 0.1
    for _ in range(80):
        v, dv = f(r), df(r)
        if abs(dv) < 1e-12: break
        nr = r - v / dv
        if nr <= -0.99 or nr > 3: break
        if abs(nr - r) < 1e-8: r = nr; break
        r = nr
    return r if -0.99 < r < 3 else np.nan


def schedule(start, months, payday):
    end = start + pd.DateOffset(months=months)
    out = []
    for m in range(months):
        y = start.year + (start.month - 1 + m) // 12
        mo = (start.month - 1 + m) % 12 + 1
        target = pd.Timestamp(y, mo, 1) + pd.Timedelta(days=payday - 1)
        fut = DATES[DATES >= target]
        if len(fut) and fut.iloc[0] <= end: out.append(fut.iloc[0])
    return out, end


def run(buys, end, tp=None, debug=False):
    """干净现金流：每轮定投独立核算，止盈落袋后重启。"""
    flows = []
    realized = 0.0            # 累计落袋现金
    sh = 0.0                  # 当前持仓份额
    cycle_cost = 0.0          # 本轮累计投入
    total_invest = 0.0
    n_cycles = 1
    last_sell = None
    for k, d in enumerate(buys):
        p = OPEN[d]
        flows.append((d, -5000.0))
        sh += 5000.0 / p
        cycle_cost += 5000.0
        total_invest += 5000.0
        if tp:
            # 检查本轮自上次卖出以来是否达目标
            i0 = pos[d]
            fut_end = DATES[DATES >= end]
            end_actual = fut_end.iloc[0] if len(fut_end) else DATES.iloc[-1]
            i1 = pos[buys[k+1]] if k+1 < len(buys) else pos[end_actual]
            hit = None
            for i in range(i0, i1):
                dd = DATES[i]
                if sh * CLOSE[dd] >= cycle_cost * (1 + tp):
                    sell_d = DATES[min(i+1, len(DATES)-1)]
                    hit = (sell_d, OPEN[sell_d])
                    break
            if hit:
                sell_d, sell_px = hit
                realized += sh * sell_px
                flows.append((sell_d, sh * sell_px))
                sh, cycle_cost = 0.0, 0.0
                n_cycles += 1
                last_sell = (sell_d, realized)
                if debug: print(f"    止盈@{sell_d.date()} 落袋{realized:.0f}")
    # 期末日顺延到实际交易日
    fut = DATES[DATES >= end]
    end_actual = fut.iloc[0] if len(fut) else DATES.iloc[-1]
    end_px = CLOSE[end_actual]
    liquid = sh * end_px + realized
    flows.append((end_actual, liquid))
    ret = liquid / total_invest - 1
    if debug:
        print(f"    末日{end.date()} 持仓{sh:.0f}份×{end_px:.3f}={sh*end_px:.0f} + 落袋{realized:.0f} "
              f"= {liquid:.0f} / 投入{total_invest:.0f} = {ret*100:+.1f}%")
    return dict(ret=ret, xirr=xirr(flows), invest=total_invest, cycles=n_cycles, realized=realized)


# 单样本验证
print("=== 单样本验证（2021-06起36月，扣款25日） ===")
buys, end = schedule(pd.Timestamp('2021-06-15'), 36, 25)
print(f"买入{len(buys)}期 首{buys[0].date()} 末{buys[-1].date()} 期末{end.date()}")
for tp in [None, 0.30]:
    print(f"  止盈{tp}:")
    run(buys, end, tp, debug=True)

rng = np.random.default_rng(20261125)
lo, hi = pd.Timestamp('2021-01-01').toordinal(), pd.Timestamp('2023-11-01').toordinal()
params = [(pd.Timestamp.fromordinal(int(rng.integers(lo, hi))),
           int(rng.choice([24, 36, 60])), int(rng.integers(1, 29))) for _ in range(1200)]

print("\n" + "=" * 100)
print("最终方案：1200组随机定投，止盈后重启（T+1开盘，无前视）")
print("=" * 100)
print(f"{'方案':<18}{'收益中位':>11}{'收益均值':>11}{'正收益%':>9}{'XIRR中位':>10}{'XIRR 5%':>10}{'平均轮次':>9}")
res_store = {}
for tp in [None, 0.20, 0.30, 0.50]:
    res = []
    for start, months, payday in params:
        buys, end = schedule(start, months, payday)
        r = run(buys, end, tp)
        if r: res.append(r)
    d = pd.DataFrame(res)
    res_store[tp] = d
    label = f'止盈{tp*100:.0f}%重启' if tp else '不止盈(基准)'
    print(f"{label:<18}{d.ret.median()*100:>+10.2f}%{d.ret.mean()*100:>+10.2f}%{(d.ret>0).mean()*100:>8.1f}%"
          f"{d.xirr.median()*100:>+9.2f}%{d.xirr.quantile(.05)*100:>+9.2f}%{d.cycles.mean():>9.1f}")

print("\n" + "=" * 100)
print("固定3年 每月25日")
print("=" * 100)
for st in ['2021-01-01', '2022-01-01', '2023-01-01', '2024-01-01']:
    buys, end = schedule(pd.Timestamp(st), 36, 25)
    row = [f"{run(buys, end, tp)['ret']*100:+.1f}%" for tp in [None, 0.20, 0.30]]
    print(f"  {st[:7]}: 不止盈 {row[0]:>8}  止盈20% {row[1]:>8}  止盈30% {row[2]:>8}")
