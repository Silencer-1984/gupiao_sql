# -*- coding: utf-8 -*-
"""
长期定投测试：2021 年起投，持有 3 年（36 期）。
另做「相对高点进入 / 相对低点进入」的场景对比。

策略：
  1) 无脑 ETF（每月首个交易日买 159941）
  2) 无脑纳指 100
  3) 阈值 5% + 最多等 3 月（暂停时现金累积）
  4) 混合：当月出现「溢价分位<20%」就买 ETF，否则买纳指
  5) 分档加码 V2（低溢价加码、高溢价缩量、池子不超 3 期）
"""
import os, json, sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "long3y.json")
CSV = os.path.join(ROOT, "data", "long3y_windows.csv")
BASE = 5000
STRATS = ["无脑ETF", "无脑纳指", "阈值5+等3", "混合<20分位", "分档加码V2"]


def load():
    c = sqlite3.connect(DB)
    lof = pd.read_sql(
        "select trade_date, close_adj, premium_lag from px_lof_daily "
        "where fund_code='159941' and close_adj is not null and premium_lag is not null "
        "order by trade_date", c, parse_dates=["trade_date"]).set_index("trade_date")
    ndx = pd.read_sql(
        "select trade_date, close from px_index_daily_us where index_code='.NDX' order by trade_date",
        c, parse_dates=["trade_date"]).set_index("trade_date")["close"].dropna()
    c.close()
    lof["pct"] = lof.premium_lag.rolling(250, min_periods=100).apply(
        lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)
    ndx_pct = ndx.rolling(250, min_periods=100).apply(lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)
    return lof, ndx, ndx_pct


def ndx_px(ndx, d):
    p = ndx.index[ndx.index <= d]
    return float(ndx.loc[p[-1]]) if len(p) else np.nan


def months_of(idx, m0, n):
    out = []
    for k in range(n):
        m = m0 + pd.offsets.MonthBegin(k)
        days = idx[(idx >= m) & (idx < m + pd.offsets.MonthBegin(1))]
        if not len(days):
            return None
        out.append(list(days))
    return out


def s_etf(lof, md):
    sh = sum(BASE / lof.loc[d[0], "close_adj"] for d in md)
    return sh * lof.loc[md[-1][-1], "close_adj"]


def s_ndx(ndx, md):
    sh = sum(BASE / ndx_px(ndx, d[0]) for d in md)
    return sh * ndx_px(ndx, md[-1][-1])


def s_thr(lof, md, thr=5, maxwait=3):
    cash = sh = 0.0
    consec = 0
    for d in md:
        d0 = d[0]
        cash += BASE
        if float(lof.loc[d0, "premium_lag"]) <= thr or consec >= maxwait:
            sh += cash / lof.loc[d0, "close_adj"]
            cash = 0.0
            consec = 0
        else:
            consec += 1
    return sh * lof.loc[md[-1][-1], "close_adj"] + cash


def s_hybrid(lof, ndx, md, thr=20):
    se = sn = 0.0
    for d in md:
        elig = [x for x in d if pd.notna(lof.loc[x, "pct"]) and lof.loc[x, "pct"] < thr]
        if elig:
            se += BASE / lof.loc[elig[0], "close_adj"]
        else:
            sn += BASE / ndx_px(ndx, d[-1])
    return se * lof.loc[md[-1][-1], "close_adj"] + sn * ndx_px(ndx, md[-1][-1])


TIERS = [(2, 3), (5, 2), (8, 1), (15, 0.5), (999, 0)]


def s_tier(lof, md):
    cash = sh = 0.0
    for d in md:
        cash += BASE
        p = float(lof.loc[d[0], "premium_lag"])
        m = next(mm for hi, mm in TIERS if p <= hi)
        want = BASE * m
        if cash > 3 * BASE:
            want = max(want, cash - 3 * BASE + want)
        buy = min(cash, max(want, 0))
        if buy > 0:
            sh += buy / lof.loc[d[0], "close_adj"]
            cash -= buy
    return sh * lof.loc[md[-1][-1], "close_adj"] + cash


def main():
    lof, ndx, ndx_pct = load()
    idx = lof.index
    rows = []
    for m0 in pd.date_range("2021-01-01", "2023-11-01", freq="MS"):
        md = months_of(idx, m0, 36)
        if md is None:
            continue
        inv = BASE * 36
        r = {"start": md[0][0].strftime("%Y-%m"), "end": md[-1][-1].strftime("%Y-%m")}
        r["无脑ETF"] = (s_etf(lof, md) / inv - 1) * 100
        r["无脑纳指"] = (s_ndx(ndx, md) / inv - 1) * 100
        r["阈值5+等3"] = (s_thr(lof, md) / inv - 1) * 100
        r["混合<20分位"] = (s_hybrid(lof, ndx, md) / inv - 1) * 100
        r["分档加码V2"] = (s_tier(lof, md) / inv - 1) * 100
        # 起投时纳指所处位置（250 日分位）
        p = ndx_pct.asof(md[0][0])
        r["纳指起点分位"] = round(float(p), 0) if pd.notna(p) else np.nan
        r["起点溢价"] = round(float(lof.loc[md[0][0], "premium_lag"]), 2)
        r["终点溢价"] = round(float(lof.loc[md[-1][-1], "premium_lag"]), 2)
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(CSV, index=False, encoding="utf-8-sig")

    def table(d, label):
        print(f"\n===== {label}（{len(d)} 个窗口，各投 {BASE*36:,} 元）=====")
        print(f"{'策略':<14}{'均值':>9}{'中位':>9}{'最差':>9}{'最好':>9}{'胜无脑ETF':>10}{'胜纳指':>8}")
        b, c = d["无脑ETF"], d["无脑纳指"]
        for s in STRATS:
            x = d[s]
            print(f"{s:<14}{x.mean():>8.2f}%{x.median():>8.2f}%{x.min():>8.2f}%{x.max():>8.2f}%"
                  f"{(x > b).mean() * 100:>9.0f}%{(x > c).mean() * 100:>7.0f}%")
        return {s: {"mean": round(float(d[s].mean()), 2), "median": round(float(d[s].median()), 2),
                    "min": round(float(d[s].min()), 2), "max": round(float(d[s].max()), 2),
                    "win_etf": round(float((d[s] > b).mean() * 100), 0),
                    "win_ndx": round(float((d[s] > c).mean() * 100), 0)} for s in STRATS}

    res = {"all": table(df, "全部：2021-01 ~ 2023-11 起投，持有 3 年")}
    hi = df[df["纳指起点分位"] >= 70]
    lo = df[df["纳指起点分位"] <= 30]
    if len(hi):
        res["high_entry"] = {"n": len(hi), "starts": hi.start.tolist(), **table(hi, "场景A：纳指相对高点进入（分位≥70%）")}
    if len(lo):
        res["low_entry"] = {"n": len(lo), "starts": lo.start.tolist(), **table(lo, "场景B：纳指相对低点进入（分位≤30%）")}

    print("\n各起点明细：")
    show = ["start", "end", "纳指起点分位", "起点溢价", "终点溢价"] + STRATS
    print(df[show].round(2).to_string(index=False))
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
