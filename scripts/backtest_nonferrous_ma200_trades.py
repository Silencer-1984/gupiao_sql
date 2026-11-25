"""MA200 完整交易闭环明细：站上买入、跌破全部卖出。

口径与 backtest_nonferrous.py 一致：T 日收盘信号，T+1 生效；单边成本万2。
输出每笔：进场日 / 离场日 / 持有交易日 / 指数区间涨幅 / 扣成本净收益。
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data" / "ashare.db")
COST = 0.0002

df = pd.read_sql(
    "select trade_date,close,pe_ttm from px_index_daily_csi "
    "where index_code='000819' order by trade_date", c)
df["trade_date"] = pd.to_datetime(df["trade_date"])
df = df.set_index("trade_date")
df["ret"] = df["close"].pct_change()
df["ma200"] = df["close"].rolling(200, min_periods=200).mean()
df["dd120"] = df["close"] / df["close"].rolling(120, min_periods=120).max() - 1
df["pe_pct"] = df["pe_ttm"].rolling(1250, min_periods=250).rank(pct=True)
fear = pd.read_sql(
    "select trade_date,fear_composite from mkt_fear_daily "
    "where index_code='000819' order by trade_date", c)
fear["trade_date"] = pd.to_datetime(fear["trade_date"])
fear = fear.set_index("trade_date")
df["fear_pct"] = fear["fear_composite"].rolling(1250, min_periods=250).rank(pct=True)
# 与主脚本 backtest_nonferrous.py 起点完全一致（2017-02-20 起）
df = df.dropna(subset=["ma200", "dd120", "pe_pct", "fear_pct"]).copy()

# T 日信号 → T+1 持仓
pos = (df["close"] > df["ma200"]).astype(int).shift(1).fillna(0).values
dates = df.index
ret = df["ret"].fillna(0).values
close = df["close"].values

# 提取连续持仓段
segments = []
i = 0
n = len(pos)
while i < n:
    if pos[i] == 1:
        j = i
        while j + 1 < n and pos[j + 1] == 1:
            j += 1
        gross = np.prod(1 + ret[i:j + 1]) - 1
        net = gross - 2 * COST
        segments.append(dict(
            entry=str(dates[i].date()), exit=str(dates[j].date()),
            days=j - i + 1,
            entry_px=close[i - 1],  # 信号日前收盘为买入基准
            exit_px=close[j],
            gross=gross, net=net,
            open_end=(j == n - 1),
        ))
        i = j + 1
    else:
        i += 1

tr = pd.DataFrame(segments)
tr["year"] = tr["entry"].str[:4]

print(f"总进场次数：{len(tr)}；完整闭环：{(~tr['open_end']).sum()} 笔；"
      f"样本末端仍持仓：{tr['open_end'].sum()} 笔\n")
print("| # | 进场日 | 离场日 | 持有交易日 | 进场点位 | 离场点位 | 指数涨幅 | 扣费净收益 | 状态 |")
print("|---:|---|---|---:|---:|---:|---:|---:|---|")
for k, r in tr.iterrows():
    tag = "持仓中" if r["open_end"] else ""
    print(f"| {k+1} | {r['entry']} | {r['exit']} | {r['days']} | "
          f"{r['entry_px']:.0f} | {r['exit_px']:.0f} | {r['gross']:+.1%} | "
          f"{r['net']:+.1%} | {tag} |")

closed = tr[~tr["open_end"]]
print(f"\n完整闭环统计（n={len(closed)}）：")
print(f"- 盈利笔数：{(closed['net']>0).sum()} / {len(closed)} = {(closed['net']>0).mean():.0%}")
print(f"- 单笔平均：{closed['net'].mean():+.2%}；中位数：{closed['net'].median():+.2%}")
print(f"- 最好：{closed['net'].max():+.1%}（{closed.loc[closed['net'].idxmax(),'entry']}）")
print(f"- 最差：{closed['net'].min():+.1%}（{closed.loc[closed['net'].idxmin(),'entry']}）")
print(f"- 全复利累计（含在持仓）：{np.prod(1+tr['net'].values)-1:+.1%}")
print("\n按年份分布（进场次数 / 正收益次数）：")
for y, g in tr.groupby("year"):
    print(f"- {y}: {len(g)} 次 / {(g['net']>0).sum()} 次正")
