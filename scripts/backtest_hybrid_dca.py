# -*- coding: utf-8 -*-
"""
混合定投：当月若出现「溢价分位 < 20%」的交易日，就在那天买场内 ETF；
否则当月改买纳指 100。每月固定 5000，金额不变。

对比：无脑买 ETF / 无脑买纳指 / 阈值5%+等3月
区间：2021-01 起（按要求不回测 2021 年前）
"""
import os, json, sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "hybrid_dca.json")
CSV = os.path.join(ROOT, "data", "hybrid_dca_windows.csv")
BASE = 5000
PCT_THR = 20


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
    return lof, ndx


def ndx_price(ndx, d):
    prev = ndx.index[ndx.index <= d]
    return float(ndx.loc[prev[-1]]) if len(prev) else np.nan


def run_hybrid(lof, ndx, months_days, thr=PCT_THR):
    sh_e = sh_n = 0.0
    used_etf = 0
    prem = []
    for days in months_days:
        elig = [d for d in days if pd.notna(lof.loc[d, "pct"]) and lof.loc[d, "pct"] < thr]
        if elig:
            d = elig[0]
            sh_e += BASE / lof.loc[d, "close_adj"]
            prem.append(float(lof.loc[d, "premium_lag"]))
            used_etf += 1
        else:
            d = days[-1]
            sh_n += BASE / ndx_price(ndx, d)
    last = months_days[-1][-1]
    v = sh_e * lof.loc[last, "close_adj"] + sh_n * ndx_price(ndx, last)
    inv = BASE * len(months_days)
    return {"ret": (v / inv - 1) * 100, "etf_months": used_etf,
            "avg_prem": float(np.mean(prem)) if prem else None}


def run_flat_etf(lof, months_days):
    sh = 0.0
    for days in months_days:
        d = days[0] if len(days) else None
        # 固定每月第一个交易日买入（与混合策略同起点口径）
        sh += BASE / lof.loc[d, "close_adj"]
    last = months_days[-1][-1]
    return (sh * lof.loc[last, "close_adj"] / (BASE * len(months_days)) - 1) * 100


def run_flat_ndx(lof, ndx, months_days):
    sh = 0.0
    for days in months_days:
        sh += BASE / ndx_price(ndx, days[0])
    last = months_days[-1][-1]
    return (sh * ndx_price(ndx, last) / (BASE * len(months_days)) - 1) * 100


def run_thr(lof, months_days, thr=5, maxwait=3):
    cash = sh = 0.0
    consec = 0
    for days in months_days:
        d = days[0]
        cash += BASE
        p = float(lof.loc[d, "premium_lag"])
        if p <= thr or consec >= maxwait:
            sh += cash / lof.loc[d, "close_adj"]
            cash = 0.0
            consec = 0
        else:
            consec += 1
    last = months_days[-1][-1]
    v = sh * lof.loc[last, "close_adj"] + cash
    return v / (BASE * len(months_days)) * 100 - 100


def main():
    lof, ndx = load()
    idx = lof.index
    rows = []
    for m0 in pd.date_range("2021-01-01", "2025-12-01", freq="MS"):
        months_days = []
        ok = True
        for k in range(12):
            m = m0 + pd.offsets.MonthBegin(k)
            days = idx[(idx >= m) & (idx < m + pd.offsets.MonthBegin(1))]
            if not len(days):
                ok = False
                break
            months_days.append(list(days))
        if not ok:
            continue
        h = run_hybrid(lof, ndx, months_days)
        rec = {"start": months_days[0][0].strftime("%Y-%m"), "end": months_days[-1][-1].strftime("%Y-%m"),
               "混合": h["ret"], "ETF月数": h["etf_months"], "买入溢价": h["avg_prem"],
               "无脑ETF": run_flat_etf(lof, months_days),
               "无脑纳指": run_flat_ndx(lof, ndx, months_days),
               "阈值5+等3": run_thr(lof, months_days)}
        # 阈值 10 / 30 分位变体
        for thr in (10, 30):
            rec[f"混合{thr}"] = run_hybrid(lof, ndx, months_days, thr)["ret"]
        rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(CSV, index=False, encoding="utf-8-sig")

    print(f"{len(df)} 个一年期窗口（{df.start.min()} ~ {df.start.max()}），每期 5000，共 6 万\n")
    print(f"{'策略':<14}{'均值':>9}{'中位':>9}{'最差':>9}{'最好':>9}{'胜无脑ETF':>10}{'胜纳指':>8}")
    base = df["无脑ETF"]
    ndxb = df["无脑纳指"]
    for c in ["无脑ETF", "无脑纳指", "阈值5+等3", "混合", "混合10", "混合30"]:
        s = df[c]
        print(f"{c:<14}{s.mean():>8.2f}%{s.median():>8.2f}%{s.min():>8.2f}%{s.max():>8.2f}%"
              f"{(s > base).mean() * 100:>9.0f}%{(s > ndxb).mean() * 100:>7.0f}%")
    print(f"\n混合策略平均用 ETF 的月份数：{df['ETF月数'].mean():.1f}/12，买入时平均溢价 {df['买入溢价'].dropna().mean():.2f}%")
    print(f"混合 vs 无脑ETF：均值差 {df['混合'].mean() - base.mean():+.2f}pp，"
          f"中位差 {df['混合'].median() - base.median():+.2f}pp，最差 {df['混合'].min():.2f}% vs {base.min():.2f}%")
    print(f"混合 vs 无脑纳指：均值差 {df['混合'].mean() - ndxb.mean():+.2f}pp，"
          f"中位差 {df['混合'].median() - ndxb.median():+.2f}pp")

    res = {"n": len(df),
           "summary": {c: {"mean": round(float(df[c].mean()), 2), "median": round(float(df[c].median()), 2),
                           "min": round(float(df[c].min()), 2), "max": round(float(df[c].max()), 2)}
                       for c in ["无脑ETF", "无脑纳指", "阈值5+等3", "混合", "混合10", "混合30"]},
           "avg_etf_months": round(float(df["ETF月数"].mean()), 1)}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
