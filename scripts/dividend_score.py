"""红利低波每日打分快照。

用法: uv run python scripts/dividend_score.py
只读本地库 data/ashare.db，不调外部接口。
每次运行把当日打分追加到 strategies/02_dividend/dividend_score_log.md。
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ashare.db"
LOG = ROOT / "strategies" / "02_dividend" / "dividend_score_log.md"

ETF = "sh512890"
INDEX = "H30269"
SPLIT_DATE = "2021-10-25"  # 2:1 份额拆分


def load() -> pd.DataFrame:
    c = sqlite3.connect(DB)
    e = pd.read_sql(
        f"select trade_date,close from px_etf_daily where etf_code='{ETF}' order by trade_date",
        c,
    )
    p = pd.read_sql(
        f"select trade_date,close px,pe_ttm from px_index_daily_csi "
        f"where index_code='{INDEX}' order by trade_date",
        c,
    )
    d = pd.read_sql(
        f"select trade_date,div_yield from val_index_dividend_yield "
        f"where index_code='{INDEX}' order by trade_date",
        c,
    )
    f = pd.read_sql(
        f"select trade_date,fear_composite from mkt_fear_daily "
        f"where index_code='{INDEX}' order by trade_date",
        c,
    )
    c.close()

    e["etf"] = pd.to_numeric(e.close, errors="coerce")
    # 拆分复权: 拆分日前价格 /2
    e.loc[e.trade_date < SPLIT_DATE, "etf"] /= 2

    df = (
        e.merge(p, on="trade_date")
        .merge(d, on="trade_date", how="left")
        .merge(f, on="trade_date", how="left")
        .dropna(subset=["div_yield"])
        .reset_index(drop=True)
    )
    df["px"] = pd.to_numeric(df.px, errors="coerce")
    df["ma250"] = df.px.rolling(250, min_periods=250).mean()
    df["px_vs_ma"] = (df.px / df.ma250 - 1) * 100
    df["mom1y"] = df.px / df.px.shift(252) - 1
    return df


def expanding_score(df: pd.DataFrame, row: pd.Series) -> dict:
    """按截至当日的全历史分位给分, 无前视偏差。"""
    out = {}
    specs = [
        ("div_yield", True, "股息率"),
        ("pe_ttm", False, "PE"),
        ("fear_composite", True, "恐慌度"),
        ("px_vs_ma", False, "均线偏离"),
        ("mom1y", False, "动量"),
    ]
    for col, higher_better, label in specs:
        v = df[col]  # 全历史序列；NaN 不参与比较（pandas 自动忽略）
        x = row[col]
        if pd.isna(x):
            out[label] = np.nan
            continue
        pct = (v < x).sum() / v.notna().sum()
        score = (pct if higher_better else 1 - pct) * 20
        out[label] = score
    out["总分"] = sum(v for v in out.values() if not np.isnan(v))
    return out


def action(total: float) -> str:
    if total >= 75:
        return "一次性投80%(或70%+30%机动)"
    if total >= 60:
        return "小仓/分批建仓"
    if total >= 45:
        return "等待或小仓试探"
    return "资金停泊债基,不买"


def main():
    df = load()
    cur = df.iloc[-1]
    s = expanding_score(df, cur)
    prev = df.iloc[-2]
    sp = expanding_score(df, prev) if len(df) > 1 else s

    # 拆分前已除以2复权，展示实际价需乘回2；拆分后是原始价
    actual_etf = cur.etf * (2 if cur.trade_date < SPLIT_DATE else 1)

    line = (
        f"| {cur.trade_date} | {cur.px:.0f} | {actual_etf:.3f} | "
        f"{cur.div_yield:.2f}% | {cur.pe_ttm:.2f} | "
        f"{s['股息率']:.1f} | {s['PE']:.1f} | {s['恐慌度']:.1f} | "
        f"{s['均线偏离']:.1f} | {s['动量']:.1f} | "
        f"**{s['总分']:.1f}** | {s['总分']-sp['总分']:+.1f} | "
        f"{action(s['总分'])} |"
    )

    if not LOG.exists():
        LOG.write_text(
            "# 红利低波每日打分日志\n\n"
            "> 由 `scripts/dividend_score.py` 自动生成。五因子各 0~20 分，总分 0~100。\n"
            "> ETF 价为 512890 实际价（已处理 2021-10-25 拆分）。\n\n"
            "| 日期 | 指数 | ETF价 | 股息率 | PE | 股息分 | PE分 | 恐慌分 | 均线分 | 动量化 | 总分 | 较前日 | 建议 |\n"
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n",
            encoding="utf-8",
        )

    content = LOG.read_text(encoding="utf-8")
    if f"| {cur.trade_date} |" in content:
        print(f"已存在 {cur.trade_date} 的打分记录，跳过。")
    else:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        print(f"已记录 {cur.trade_date}")

    print(f"\n当前打分 {s['总分']:.1f}/100  ->  {action(s['总分'])}")
    print(f"指数 {cur.px:.0f}  ETF实际价 {actual_etf:.3f}  股息 {cur.div_yield:.2f}%  PE {cur.pe_ttm:.2f}")
    for k in ["股息率", "PE", "恐慌度", "均线偏离", "动量"]:
        print(f"  {k}: {s[k]:.1f}/20")


if __name__ == "__main__":
    main()
