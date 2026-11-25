"""有色金属入场时机策略回测（纯本地）。

标的：000819 中证有色指数（信号+回测）；sh512400 有色ETF 作执行参照。
对比：000688 科创50、000300 沪深300。
输出：Markdown 报告 data/nonferrous_report.md（供 docs 报告引用）。
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "ashare.db"
OUT = ROOT / "data" / "nonferrous_report.md"
COST = 0.0002  # 单边万2，ETF 场内佣金近似

c = sqlite3.connect(DB)


def load_index(code):
    df = pd.read_sql(
        "select trade_date,close,pe_ttm,pct_chg,amount from px_index_daily_csi "
        "where index_code=? order by trade_date",
        c, params=[code],
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.set_index("trade_date")


def load_fear(code):
    df = pd.read_sql(
        "select trade_date,fear_composite,fear_rv_pct,rv20,dd60 from mkt_fear_daily "
        "where index_code=? order by trade_date",
        c, params=[code],
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.set_index("trade_date")


idx = load_index("000819")
fear = load_fear("000819")
df = idx.join(fear, how="left").dropna(subset=["close"])
df["ret"] = df["close"].pct_change()
df["ma200"] = df["close"].rolling(200, min_periods=200).mean()
df["ma60"] = df["close"].rolling(60, min_periods=60).mean()
df["dd120"] = df["close"] / df["close"].rolling(120, min_periods=120).max() - 1
df["pe_pct_5y"] = df["pe_ttm"].rolling(1250, min_periods=250).rank(pct=True)
df["fear_pct_5y"] = df["fear_composite"].rolling(1250, min_periods=250).rank(pct=True)
df = df.dropna(subset=["ma200", "dd120", "fear_pct_5y", "pe_pct_5y"]).copy()


def state_pos(buy, sell):
    """信号触发后持仓直到反向信号（状态机）。"""
    pos = []
    cur = 0
    for b, s in zip(buy, sell):
        if b:
            cur = 1
        elif s:
            cur = 0
        pos.append(cur)
    return np.array(pos)


# 策略信号（T 日收盘生成，T+1 日生效 → 用 shift(1)）
sig = pd.DataFrame(index=df.index)
sig["S0_buyhold"] = 1
sig["S1_trend200"] = (df["close"] > df["ma200"]).astype(int)
sig["S2_drawdown20"] = state_pos(df["dd120"] <= -0.20, df["dd120"] >= -0.05)
sig["S3_fear80"] = state_pos(df["fear_pct_5y"] >= 0.80, df["fear_pct_5y"] <= 0.50)
sig["S4_fear60_ma"] = (
    (df["close"] > df["ma200"]) & (df["fear_pct_5y"] >= 0.60)
).astype(int)
sig["S5_pe_low20"] = (df["pe_pct_5y"] <= 0.20).astype(int)


def metrics(pos, ret):
    pos = np.asarray(pos)
    ret = np.asarray(ret)
    turn_flags = np.abs(np.diff(np.r_[0, pos]))
    r = pos * ret - turn_flags * COST
    equity = np.cumprod(1 + r)
    years = len(r) / 252
    cum = equity[-1] - 1
    ann = (1 + cum) ** (1 / years) - 1
    mdd = (equity / np.maximum.accumulate(equity) - 1).min()
    # 每笔交易收益（持仓区间复利，忽略成本）
    trades = []
    in_trade = False
    start = 0
    for i, p in enumerate(pos):
        if p and not in_trade:
            in_trade = True
            start = i
        elif not p and in_trade:
            trades.append(np.prod(1 + ret[start:i]) - 1)
            in_trade = False
    if in_trade:
        trades.append(np.prod(1 + ret[start:]) - 1)
    win = np.mean([t > 0 for t in trades]) if trades else 0
    return dict(cum=cum, ann=ann, mdd=mdd, calmar=ann / abs(mdd) if mdd else 0,
                turns=int(turn_flags.sum()), win=win, ntr=len(trades))


rows = []
for col in sig.columns:
    pos = sig[col].shift(1).fillna(0).values
    m = metrics(pos, df["ret"].fillna(0).values)
    m["策略"] = col
    rows.append(m)
res = pd.DataFrame(rows).set_index("策略")

# 入场信号有效性：信号触发后未来 N 日收益（对比全样本基线）
fwd = {}
for n in (60, 120, 250):
    fwd[n] = df["close"].shift(-n) / df["close"] - 1
base = pd.DataFrame({f"基线_{n}D": [fwd[n].mean(), fwd[n].median(), (fwd[n] > 0).mean()]
                     for n in (60, 120, 250)},
                    index=["均值", "中位数", "胜率"])

signals = {
    "回撤≥20%": df["dd120"] <= -0.20,
    "恐慌≥80分位": df["fear_pct_5y"] >= 0.80,
    "恐慌≥80 & 趋势>MA200": (df["fear_pct_5y"] >= 0.80) & (df["close"] > df["ma200"]),
    "PE≤20分位": df["pe_pct_5y"] <= 0.20,
    "MA200上方": df["close"] > df["ma200"],
}
sig_rows = []
for name, mask in signals.items():
    row = {"信号": name, "样本数": int(mask.sum())}
    for n in (60, 120, 250):
        v = fwd[n][mask].dropna()
        row[f"{n}D均值"] = v.mean() if len(v) else np.nan
        row[f"{n}D胜率"] = (v > 0).mean() if len(v) else np.nan
    sig_rows.append(row)
sig_res = pd.DataFrame(sig_rows).set_index("信号")

# 当下读数
last = df.iloc[-1]
last_row = dict(日期=str(df.index[-1].date()), 收盘=last["close"],
                MA200=last["ma200"], 距MA200=last["close"]/last["ma200"]-1,
                回撤120=last["dd120"], 恐慌分位=last["fear_pct_5y"],
                PE=last["pe_ttm"], PE分位=last["pe_pct_5y"])

# 对比标的近况
compare = {}
for code, name in [("000819", "中证有色"), ("000688", "科创50"),
                   ("000300", "沪深300")]:
    d = load_index(code)
    for n, lbl in [(1, "近1年"), (3, "近3年")]:
        sub = d.tail(252 * n)
        if len(sub) > 1:
            compare[f"{name}_{lbl}"] = sub["close"].iloc[-1] / sub["close"].iloc[0] - 1

# 输出
lines = []
def w(s=""):
    lines.append(s)

w("# 有色金属策略回测（脚本原始输出）")
w(f"\n数据区间：{df.index[0].date()} → {df.index[-1].date()}（{len(df)} 交易日）\n")
w("## 策略对比（单边成本万2，信号 T 日 → T+1 生效）\n")
w("| 策略 | 累计 | 年化 | 最大回撤 | Calmar | 调仓次数 | 交易笔数 | 胜率 |")
w("|---|---:|---:|---:|---:|---:|---:|---:|")
for name, r in res.iterrows():
    w(f"| {name} | {r['cum']:.1%} | {r['ann']:.1%} | {r['mdd']:.1%} | "
      f"{r['calmar']:.2f} | {r['turns']:.0f} | {r['ntr']} | {r['win']:.0%} |")
w("\n## 入场信号有效性（信号后 N 日收益，全样本基线对照）\n")
w("| 基线 | 60D | 120D | 250D |")
w("|---|---:|---:|---:|")
for i, lbl in enumerate(["均值", "中位数", "胜率"]):
    w(f"| {lbl} | {base.iloc[i,0]:.2%} | {base.iloc[i,1]:.2%} | {base.iloc[i,2]:.2%} |")
w("")
w("| 信号 | 样本数 | 60D均值 | 60D胜率 | 120D均值 | 120D胜率 | 250D均值 | 250D胜率 |")
w("|---|---:|---:|---:|---:|---:|---:|---:|")
for name, r in sig_res.iterrows():
    w(f"| {name} | {r['样本数']} | {r['60D均值']:.2%} | {r['60D胜率']:.0%} | "
      f"{r['120D均值']:.2%} | {r['120D胜率']:.0%} | {r['250D均值']:.2%} | {r['250D胜率']:.0%} |")
w("\n## 当下读数\n")
w("| 指标 | 数值 |")
w("|---|---:|")
for k, v in last_row.items():
    w(f"| {k} | {v:.4f} |" if isinstance(v, float) else f"| {k} | {v} |")
w("\n## 相对表现\n")
w("| 标的 | 区间 | 收益 |")
w("|---|---|---:|")
for k, v in compare.items():
    w(f"| {k.replace('_',' ')} | | {v:.1%} |")
w("")
print("\n".join(lines))
