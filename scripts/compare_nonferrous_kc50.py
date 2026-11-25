"""有色金属 vs 科创50：同口径对比（MA200 趋势 / 买入持有 / 当前读数）。

共同区间取两者都有真实行情的日期；科创50 过滤 close=1000 基期占位行。
T 日信号 T+1 生效，单边成本万2（两边一致）。
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data" / "ashare.db")
COST = 0.0002


def load(code):
    d = pd.read_sql(
        "select trade_date,close,pe_ttm from px_index_daily_csi "
        "where index_code=? and close!=1000 order by trade_date", c, params=[code])
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.set_index("trade_date")


def prep(d):
    x = d.copy()
    x["ret"] = x["close"].pct_change()
    x["ma200"] = x["close"].rolling(200, min_periods=200).mean()
    x["dd120"] = x["close"] / x["close"].rolling(120, min_periods=120).max() - 1
    x["pe_pct"] = x["pe_ttm"].rolling(750, min_periods=250).rank(pct=True)
    return x.dropna(subset=["ma200", "dd120", "pe_pct"])


def metrics(pos, ret):
    pos = np.asarray(pos)
    ret = np.asarray(ret)
    turns = np.abs(np.diff(np.r_[0, pos]))
    r = pos * ret - turns * COST
    eq = np.cumprod(1 + r)
    cum = eq[-1] - 1
    ann = (1 + cum) ** (252 / len(r)) - 1
    mdd = (eq / np.maximum.accumulate(eq) - 1).min()
    sharpe = (r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0
    # 闭环
    trades = []
    in_t = False
    s = 0
    for i, p in enumerate(pos):
        if p and not in_t:
            in_t = True
            s = i
        elif not p and in_t:
            trades.append(np.prod(1 + ret[s:i]) - 1)
            in_t = False
    if in_t:
        trades.append(np.prod(1 + ret[s:]) - 1)
    return dict(cum=cum, ann=ann, mdd=mdd, sharpe=sharpe,
                n=len(trades), win=np.mean([t > 0 for t in trades]) if trades else 0,
                med=np.median(trades) if trades else 0)


nf = prep(load("000819"))
kc = prep(load("000688"))
common = nf.index.intersection(kc.index)
nf, kc = nf.loc[common], kc.loc[common]
print(f"共同区间：{common[0].date()} → {common[-1].date()}（{len(common)} 交易日）\n")

res = {}
for name, x in [("有色金属000819", nf), ("科创50 000688", kc)]:
    ret = x["ret"].fillna(0).values
    res[name] = {
        "买入持有": metrics(np.ones(len(x)), ret),
        "MA200趋势": metrics((x["close"] > x["ma200"]).astype(int).shift(1).fillna(0).values, ret),
    }

print("| 标的 | 策略 | 累计 | 年化 | 最大回撤 | 夏普 | 进场次数 | 胜率 | 单笔中位 |")
print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
for name, d in res.items():
    for st, m in d.items():
        print(f"| {name} | {st} | {m['cum']:+.1%} | {m['ann']:+.1%} | {m['mdd']:.1%} | "
              f"{m['sharpe']:.2f} | {m['n']} | {m['win']:.0%} | {m['med']:+.2%} |")

# 信号有效性（共同区间）
print("\n## MA200 上方后 N 日收益（共同区间）")
print("| 标的 | 信号 | 60D均值 | 120D均值 | 250D均值/胜率 |")
print("|---|---|---:|---:|---:|")
for name, x in [("有色金属", nf), ("科创50", kc)]:
    mask = x["close"] > x["ma200"]
    row = [name, "站上MA200"]
    for n in (60, 120, 250):
        v = (x["close"].shift(-n) / x["close"] - 1)[mask].dropna()
        row.append(f"{v.mean():+.1%}")
    v250 = (x["close"].shift(-250) / x["close"] - 1)[mask].dropna()
    row.append(f"{v250.mean():+.1%} / {(v250>0).mean():.0%}")
    print("| " + " | ".join(row) + " |")

# 当前读数
print("\n## 当前读数（2026-11-20）")
print("| 指标 | 有色 | 科创50 |")
print("|---|---:|---:|")
rows = [
    ("收盘", lambda x: f"{x['close'].iloc[-1]:.0f}"),
    ("MA200", lambda x: f"{x['ma200'].iloc[-1]:.0f}"),
    ("距MA200", lambda x: f"{x['close'].iloc[-1]/x['ma200'].iloc[-1]-1:+.1%}"),
    ("120日回撤", lambda x: f"{x['dd120'].iloc[-1]:.1%}"),
    ("PE", lambda x: f"{x['pe_ttm'].iloc[-1]:.1f}"),
    ("PE分位(3y)", lambda x: f"{x['pe_pct'].iloc[-1]:.0%}"),
    ("MA200状态", lambda x: "上方✅" if x["close"].iloc[-1] > x["ma200"].iloc[-1] else "下方❌"),
]
for label, fn in rows:
    print(f"| {label} | {fn(nf)} | {fn(kc)} |")

# 年度收益对比
print("\n## 分年度收益（指数本身）")
print("| 年份 | 有色 | 科创50 | 谁赢 |")
print("|---|---:|---:|---|")
for y in sorted(set(nf.index.year)):
    a = nf[nf.index.year == y]["close"]
    b = kc[kc.index.year == y]["close"]
    ra = a.iloc[-1] / a.iloc[0] - 1
    rb = b.iloc[-1] / b.iloc[0] - 1
    print(f"| {y} | {ra:+.1%} | {rb:+.1%} | {'科创50' if rb>ra else '有色'} |")
