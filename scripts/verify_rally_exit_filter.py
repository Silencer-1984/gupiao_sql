# -*- coding: utf-8 -*-
"""验证：两次大涨的顶部特征（过热/量比极值）能否作为提前离场信号改善策略。
复用权威口径：2020-11-24起，T日信号T+1开盘，双边成本0.05%。
"""
import sqlite3
import numpy as np
import pandas as pd

c = sqlite3.connect('data/ashare.db')
d = pd.read_sql("""
    select p.trade_date,p.open,p.close,p.amount,p.pct_chg,
           f.fear_composite,f.fear_rv_pct
    from px_index_daily_csi p left join mkt_fear_daily f
    on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688' and p.close!=1000 order by p.trade_date
""", c)
d['trade_date'] = pd.to_datetime(d.trade_date)
d = d.dropna(subset=['open', 'close']).reset_index(drop=True)
for w in [20, 60]:
    d[f'ma{w}'] = d.close.rolling(w, min_periods=w).mean()
d['ar20'] = d.amount / d.amount.rolling(20, min_periods=20).mean()
d['dist_ma20'] = d.close / d.ma20 - 1
d['ret20'] = d.close / d.close.shift(20) - 1

O, C = d.open.values, d.close.values
MA20 = d.ma20.values
S, E = pd.Timestamp('2020-11-24'), d.trade_date.iloc[-1]
mask = (d.trade_date >= S) & (d.trade_date <= E)


def bt(entry, extra_exit, name):
    # T日收盘判定信号 → T+1开盘成交（两端都shift，避免未来函数）
    base_exit = pd.Series(np.isfinite(MA20) & (C < np.where(np.isfinite(MA20), MA20, np.inf)), index=d.index)
    if extra_exit is not None:
        base_exit = base_exit | extra_exit.fillna(False)
    ee = entry.shift(1).fillna(False).values
    ex = base_exit.shift(1).fillna(False).values
    cash, sh, pos = 1.0, 0.0, False
    eq, ne = [], 0
    for i in range(len(d)):
        dt = d.trade_date.iloc[i]
        if dt < S or dt > E:
            continue
        if pos and ex[i]:
            cash = sh * O[i] * 0.9995
            pos, sh = False, 0.0
        if (not pos) and ee[i]:
            sh = cash / O[i] * 0.9995
            cash, pos = 0.0, True
            ne += 1
        eq.append(sh * C[i] + cash)
    nav = pd.Series(eq, index=d[mask].trade_date)
    f = nav.iloc[-1]
    ann = f ** (252 / len(nav)) - 1
    mdd = (nav / nav.cummax() - 1).min()
    r = nav.pct_change().dropna()
    shp = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
    print(f"{name:<36} 终值{f:.3f} 年化{ann*100:6.2f}% 回撤{mdd*100:6.2f}% 夏普{shp:5.2f} 进场{ne:3d}")


e10 = (d.close > d.ma20) & (d.ret20 > 0) & (d.ar20 > 0.9)
print("=== 离场过滤器（在破MA20基础上叠加提前离场） ===")
bt(e10, None, '基准 S10+破MA20')
bt(e10, d.dist_ma20 > 0.10, '+距MA20>10%提前走')
bt(e10, d.dist_ma20 > 0.15, '+距MA20>15%提前走')
bt(e10, d.ar20 > 2.0, '+量比>2提前走')
bt(e10, d.fear_composite > 75, '+fear>75提前走')
bt(e10, d.fear_rv_pct > 95, '+RV分位>95提前走')

print("\n=== 进场增强：放量突破（含/不含过热过滤） ===")
sig = (d.ar20 > 1.4) & (d.pct_chg > 3) & (d.close > d.ma20)
sig2 = sig & (d.dist_ma20 < 0.10) & (d.fear_rv_pct < 90)
bt(sig, None, '放量突破进场+破MA20')
bt(sig2, None, '放量突破+不过热+破MA20')
bt(e10 | sig2, None, 'S10 或 放量突破（合并）')

print("\n=== 纯事件驱动：只在放量突破日进场，持有到破MA20/T+10 ===")
# 固定持有10日的版本
ee = sig2.shift(1).fillna(False).values
eq = []
cash, sh, pos, hold = 1.0, 0.0, False, 0
for i in range(len(d)):
    dt = d.trade_date.iloc[i]
    if dt < S or dt > E:
        continue
    if pos and (hold >= 10 or (np.isfinite(MA20[i]) and C[i] < MA20[i])):
        cash = sh * O[i] * 0.9995
        pos, sh = False, 0.0
    if (not pos) and ee[i]:
        sh = cash / O[i] * 0.9995
        cash, pos, hold = 0.0, True, 0
    if pos:
        hold += 1
    eq.append(sh * C[i] + cash)
nav = pd.Series(eq, index=d[mask].trade_date)
f = nav.iloc[-1]
print(f"{'放量突破+最多持10日':<36} 终值{f:.3f} 年化{(f**(252/len(nav))-1)*100:6.2f}% 回撤{(nav/nav.cummax()-1).min()*100:6.2f}%")
