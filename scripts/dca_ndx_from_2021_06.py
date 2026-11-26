"""纳指100(.NDX)定投：2021-06 起每月1w，算到数据末日的累计财富。

口径：
  - 标的=指数 .NDX；数据库无汇率表，忽略汇率（份额=10000/当日点位）
  - 扣款日可配（1/15/25/月末），遇非交易日取该月>=扣款日的首个交易日，月末规则取最后交易日
  - 收益=份额合计 × 数据末日点位；本金=期数×10000
  - 年化用 XIRR（二分法）
"""
import sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ashare.db"
AMOUNT = 10000.0
START = "2021-06"


def load():
    c = sqlite3.connect(DB)
    df = pd.read_sql(
        "select trade_date,close from px_index_daily_us "
        "where index_code='.NDX' order by trade_date", c)
    c.close()
    df["trade_date"] = pd.to_datetime(df.trade_date)
    df["ym"] = df.trade_date.dt.to_period("M")
    return df


def xirr(cashflows):
    """cashflows: list of (date, amount)，买入为负、期末市值为正。二分法求年化。"""
    def npv(r):
        return sum(amt / (1 + r) ** ((d - cashflows[0][0]).days / 365.0) for d, amt in cashflows)
    lo, hi = -0.9999, 10.0
    if npv(lo) * npv(hi) > 0:
        return np.nan
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def run():
    df = load()
    last_date = df.trade_date.iloc[-1]
    last_px = df.close.iloc[-1]
    months = pd.period_range(start=START, end=last_date.to_period("M"), freq="M")
    print(f"数据末日 {last_date.date()}  点位 {last_px:.2f}  月份 {months[0]}~{months[-1]} 共 {len(months)} 期\n")

    results = []
    for rule in [1, 15, 25, "month_end"]:
        shares, flows, buys = 0.0, [], []
        for m in months:
            sub = df[df.ym == m]
            if sub.empty:
                continue
            if rule == "month_end":
                row = sub.iloc[-1]
            else:
                cand = sub[sub.trade_date.dt.day >= rule]
                row = cand.iloc[0] if not cand.empty else sub.iloc[-1]
            shares += AMOUNT / row.close
            buys.append((row.trade_date, row.close))
            flows.append((row.trade_date, -AMOUNT))
        value = shares * last_px
        principal = len(buys) * AMOUNT
        flows.append((last_date, value))
        ann = xirr(flows)
        results.append((rule, len(buys), principal, value, value / principal - 1, ann,
                        buys[0][0].date(), buys[-1][0].date()))

    print(f"{'扣款日':>8} {'期数':>4} {'本金':>10} {'市值':>12} {'总收益':>9} {'年化XIRR':>9}  首末扣款")
    for rule, n, prin, val, ret, ann, d0, d1 in results:
        tag = "月末" if rule == "month_end" else f"{rule}日"
        print(f"{tag:>8} {n:>4} {prin:>10.0f} {val:>12.0f} {ret*100:>8.1f}% {ann*100:>8.2f}%  {d0}~{d1}")

    # 敏感性：若末日点位用前一日（核对异常跳变）
    prev_px = df.close.iloc[-2]
    print(f"\n末日前一日点位 {prev_px:.2f}（较末日 {(last_px/prev_px-1)*100:+.1f}%）")
    for rule, n, prin, val, ret, ann, d0, d1 in results:
        if rule == 25:
            print(f"用前一日点位：25日扣款市值 {val*prev_px/last_px:.0f}，总收益 {(val*prev_px/last_px/prin-1)*100:.1f}%")


if __name__ == "__main__":
    run()
