# -*- coding: utf-8 -*-
"""
定投回测：159941（纳指ETF，场内、付溢价） vs 场外按净值 vs 纯纳指100。

设定（模仿一个"无脑定投"的投资者）：
  - 每月 15 日（遇非交易日顺延到当月下一个交易日）投入 5000 元
  - 不做择时、不止盈、不分批，期末按最后一日收盘/净值估值
  - 三个区间：近 5 年、近 3 年、今年 5 月起（QDII 限购收紧后）

三条轨：
  A 场内 159941：按当日收盘价买入（支付溢价）
  B 场外按净值：按当日单位净值买入（无溢价；限购时买不到，作理论对照）
  C 纯纳指100：按 A 股交易日前最近一个美股收盘买入（美元计价，无摩擦）

输出：累计投入 / 期末市值 / 总收益率 / XIRR / 买入时平均溢价 / 溢价损耗
"""
import os
import json
import sqlite3
import datetime as dt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "backtest_dca.json")

AMOUNT = 5000
WINDOWS = [
    ("近5年", "2021-11-01", "2026-11-21"),
    ("近3年", "2023-11-01", "2026-11-21"),
    ("今年5月起", "2026-05-01", "2026-11-21"),
]


def xirr(flows, guess=0.1):
    """flows: [(date, amount)]，投入为负、期末为正。二分法求年化。"""
    if not flows:
        return None
    d0 = flows[0][0]

    def npv(r):
        return sum(a / (1 + r) ** ((d - d0).days / 365.0) for d, a in flows)

    lo, hi = -0.9999, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def load():
    c = sqlite3.connect(DB)
    lof = pd.read_sql(
        # 用复权序列：159941 在 2022-07-05 做过 4:1 份额拆分，原始单位净值/价格不连续
        "select trade_date, close_adj as close, nav_adj as nav, premium_lag from px_lof_daily "
        "where fund_code='159941' and close_adj is not null and nav_adj is not null "
        "order by trade_date", c, parse_dates=["trade_date"])
    ndx = pd.read_sql(
        "select trade_date, close from px_index_daily_us where index_code='.NDX' order by trade_date",
        c, parse_dates=["trade_date"])
    c.close()
    return lof.set_index("trade_date"), ndx.set_index("trade_date")["close"]


def month_dates(lof, start, end):
    """每月 15 日起的第一个有 ETF 报价的交易日。"""
    idx = lof.index
    out = []
    cur = pd.Timestamp(start).replace(day=15)
    end = pd.Timestamp(end)
    while cur <= end:
        cand = idx[idx >= cur]
        if len(cand):
            d = cand[0]
            if d <= end and (not out or d != out[-1]):
                out.append(d)
        cur = (cur + pd.offsets.MonthBegin(1)).replace(day=15)
    return out


def run(lof, ndx, dates, mode):
    shares = 0.0
    invested = 0.0
    flows = []
    prem = []
    for d in dates:
        amt = AMOUNT
        invested += amt
        flows.append((d, -amt))
        if mode == "etf":
            px = float(lof.loc[d, "close"])
            if pd.notna(lof.loc[d, "premium_lag"]):
                prem.append(float(lof.loc[d, "premium_lag"]))
        elif mode == "nav":
            px = float(lof.loc[d, "nav"])
            if pd.notna(px) and px <= 0:
                continue
        else:  # ndx，用 A 股日之前最近的纳指收盘
            prev = ndx.index[ndx.index < d]
            if not len(prev):
                continue
            px = float(ndx.loc[prev[-1]])
        shares += amt / px
    last = dates[-1]
    if mode == "etf":
        end_px = float(lof["close"].dropna().iloc[-1])
        end_date = lof["close"].dropna().index[-1]
    elif mode == "nav":
        end_px = float(lof["nav"].dropna().iloc[-1])
        end_date = lof["nav"].dropna().index[-1]
    else:
        end_px = float(ndx.dropna().iloc[-1])
        end_date = ndx.dropna().index[-1]
    value = shares * end_px
    flows.append((end_date, value))
    return {
        "shares_raw": shares,
        "invested": round(invested, 0),
        "value": round(value, 0),
        "profit": round(value - invested, 0),
        "total_return": round((value / invested - 1) * 100, 2),
        "xirr": None if xirr(flows) is None else round(xirr(flows) * 100, 2),
        "shares": round(shares, 2),
        "end_price": round(end_px, 4),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "avg_premium": round(sum(prem) / len(prem), 2) if prem else None,
        "months": len(dates),
    }


def main():
    lof, ndx = load()
    result = {}
    for name, start, end in WINDOWS:
        dates = month_dates(lof, start, end)
        if not dates:
            continue
        a = run(lof, ndx, dates, "etf")
        b = run(lof, ndx, dates, "nav")
        c = run(lof, ndx, dates, "ndx")
        result[name] = {
            "range": [dates[0].strftime("%Y-%m-%d"), dates[-1].strftime("%Y-%m-%d")],
            "n_months": len(dates),
            "etf": a, "nav": b, "ndx": c,
            "diff_vs_nav_pct": round((a["value"] / b["value"] - 1) * 100, 2),
            "diff_vs_ndx_pct": round((a["value"] / c["value"] - 1) * 100, 2),
            "premium_now": None,
            "value_if_premium_median": None,
            "value_if_premium_zero": None,
            "premium_gain_pct": None,
        }
    # 溢价情景：期末若溢价回归历史中位/归零，A 轨还剩多少
    med = float(lof["premium_lag"].dropna().tail(1250).median()) / 100.0
    nav_last = float(lof["nav"].dropna().iloc[-1])
    close_last = float(lof["close"].dropna().iloc[-1])
    prem_now = close_last / nav_last - 1
    for name, r in result.items():
        sh = r["etf"]["shares_raw"]
        r["premium_now"] = round(prem_now * 100, 2)
        r["premium_median_5y"] = round(med * 100, 2)
        r["value_if_premium_median"] = round(sh * nav_last * (1 + med), 0)
        r["value_if_premium_zero"] = round(sh * nav_last, 0)
        r["premium_gain_pct"] = round((r["etf"]["value"] / (sh * nav_last) - 1) * 100, 2)

    # 卖出溢价敏感性：溢价从 0% 到当前水平的各档市值
    scen = [0.0, med, 0.05, 0.10, prem_now]
    for name, r in result.items():
        sh = r["etf"]["shares_raw"]
        r["sensitivity"] = [
            {"sell_premium": round(p * 100, 2),
             "value": round(sh * nav_last * (1 + p), 0),
             "total_return": round((sh * nav_last * (1 + p) / r["etf"]["invested"] - 1) * 100, 2)}
            for p in scen]

    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"每期投入 {AMOUNT} 元，每月 15 日（顺延到交易日）\n")
    for name, r in result.items():
        print(f"=== {name}  {r['range'][0]} ~ {r['range'][1]}  {r['n_months']} 期 ===")
        for k, label in [("etf", "A 场内159941"), ("nav", "B 场外按净值"), ("ndx", "C 纯纳指100")]:
            x = r[k]
            print(f"  {label:12s} 投入 {x['invested']:>7,.0f}  市值 {x['value']:>9,.0f}  "
                  f"收益 {x['profit']:>+9,.0f} ({x['total_return']:>+6.2f}%)  XIRR {str(x['xirr']):>7}%")
        print(f"  买入时平均溢价 {r['etf']['avg_premium']}%　当前溢价 {r['premium_now']}%")
        print(f"  A 相对 B（净值轨）{r['diff_vs_nav_pct']:+.2f}%　A 相对 C（纯指数）{r['diff_vs_ndx_pct']:+.2f}%")
        print(f"  若卖出时溢价回到 5 年中位 {r['premium_median_5y']}%：市值 {r['value_if_premium_median']:>9,.0f}"
              f"（比现在卖少 {r['value_if_premium_median'] - r['etf']['value']:>+9,.0f}）")
        print(f"  其中来自「溢价扩张」的部分：{r['premium_gain_pct']:+.2f}%\n")


if __name__ == "__main__":
    main()
