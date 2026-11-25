# -*- coding: utf-8 -*-
"""
阈值定投策略回测：溢价 > 阈值时暂停当月定投，积压现金等溢价回落再一次性补投。

对比：
  1) 无脑定投（每月必投）
  2) 阈值暂停（3% / 5% / 8% / 10%）—— 信号用当日可观测溢价 premium_lag，成交用当日收盘
  3) 直接买纳指100（每月必投）

区间：2021-01 ~ 2026-11，滚动一年（12 期），穷举全部起点，与上一篇口径完全一致。
期末未投出的现金计入总资产（不计息）。
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "thr_dca.json")
CSV = os.path.join(ROOT, "data", "thr_dca_windows.csv")

AMOUNT = 5000
MONTHS = 12
THRESHOLDS = [None, 3, 5, 8, 10]
HYBRIDS = [(5, 2), (5, 3), (8, 3)]   # (阈值, 最长连续暂停月数)


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
    return lof, ndx


def dates_for(idx, start_month):
    out = []
    for k in range(MONTHS):
        target = (start_month + pd.offsets.MonthBegin(k)).replace(day=15)
        cand = idx[idx >= target]
        if not len(cand):
            return None
        out.append(cand[0])
    return out


def run(lof, ndx, ds, thr, max_wait=None):
    """thr=None 表示无脑定投；max_wait 限制连续暂停月数，超时无条件买入。"""
    cash = 0.0
    shares = 0.0
    bought = 0.0          # 已投入金额
    prem = []             # 实际买入时的溢价
    paused = 0
    consec = 0
    for d in ds:
        cash += AMOUNT
        ok = thr is None or lof.loc[d, "premium_lag"] <= thr
        if not ok and max_wait is not None and consec >= max_wait:
            ok = True     # 空转超时，强制买入
        if ok:
            shares += cash / lof.loc[d, "close_adj"]
            bought += cash
            prem.append(lof.loc[d, "premium_lag"])
            cash = 0.0
            consec = 0
        else:
            paused += 1
            consec += 1
    end = ds[-1]
    v = shares * lof.loc[end, "close_adj"] + cash
    inv = AMOUNT * MONTHS
    return {
        "ret": (v / inv - 1) * 100,
        "value": v,
        "invested": bought,
        "idle_cash": cash,
        "paused": paused,
        "avg_prem": float(np.mean(prem)) if prem else None,
    }


def run_ndx(ndx, ds):
    sh = 0.0
    for d in ds:
        prev = ndx.index[ndx.index < d]
        if len(prev):
            sh += AMOUNT / ndx.loc[prev[-1]]
    end = ds[-1]
    e = ndx.index[ndx.index <= end]
    v = sh * ndx.loc[e[-1]]
    return {"ret": (v / (AMOUNT * MONTHS) - 1) * 100, "value": v}


def main():
    lof, ndx = load()
    idx = lof.index
    months = [m for m in pd.date_range("2021-01-01", "2025-12-01", freq="MS")]
    rows = []
    for m in months:
        ds = dates_for(idx, m)
        if ds is None or len(ds) != MONTHS:
            continue
        rec = {"start": ds[0].strftime("%Y-%m"), "end": ds[-1].strftime("%Y-%m")}
        for thr in THRESHOLDS:
            r = run(lof, ndx, ds, thr)
            tag = "dumb" if thr is None else f"t{thr}"
            rec[f"ret_{tag}"] = r["ret"]
            rec[f"paused_{tag}"] = r["paused"]
            rec[f"avgprem_{tag}"] = r["avg_prem"]
            rec[f"idle_{tag}"] = r["idle_cash"]
        for thr, mw in HYBRIDS:
            r = run(lof, ndx, ds, thr, max_wait=mw)
            tag = f"h{thr}_{mw}"
            rec[f"ret_{tag}"] = r["ret"]
            rec[f"paused_{tag}"] = r["paused"]
            rec[f"avgprem_{tag}"] = r["avg_prem"]
            rec[f"idle_{tag}"] = r["idle_cash"]
        rec["ret_ndx"] = run_ndx(ndx, ds)["ret"]
        rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(CSV, index=False, encoding="utf-8-sig")

    def agg(col):
        s = df[col]
        return {"mean": round(float(s.mean()), 2), "median": round(float(s.median()), 2),
                "min": round(float(s.min()), 2), "max": round(float(s.max()), 2)}

    res = {"n_windows": int(len(df)), "range": [df.start.min(), df.start.max()], "detail": {}}
    res["detail"]["ndx"] = agg("ret_ndx")
    all_tags = ["dumb"] + [f"t{t}" for t in THRESHOLDS if t] + [f"h{t}_{m}" for t, m in HYBRIDS] + ["ndx"]
    for tag in all_tags:
        if tag == "ndx":
            continue
        thr = None if tag == "dumb" else (int(tag[1:]) if tag.startswith("t") else int(tag[1:].split("_")[0]))
        d = df[f"ret_{tag}"] - df["ret_dumb"]
        n = df[f"ret_{tag}"] - df["ret_ndx"]
        res["detail"][tag] = {
            "thr": thr, **agg(f"ret_{tag}"),
            "vs_dumb_mean": round(float(d.mean()), 2),
            "vs_dumb_win": round(float((d > 0.01).mean() * 100), 1),
            "vs_ndx_mean": round(float(n.mean()), 2),
            "vs_ndx_win": round(float((n > 0).mean() * 100), 1),
            "avg_paused": round(float(df[f"paused_{tag}"].mean()), 2),
            "max_paused": int(df[f"paused_{tag}"].max()),
            "avg_buy_prem": round(float(df[f"avgprem_{tag}"].dropna().mean()), 2),
        }
        # 按起投年份
        g = df.assign(y=df.start.str[:4]).groupby("y")
        res["detail"][tag]["by_year"] = {
            y: {"mean": round(float(x[f"ret_{tag}"].mean()), 2),
                "vs_dumb_win": round(float((x[f"ret_{tag}"] > x["ret_dumb"]).mean() * 100), 0),
                "vs_ndx_win": round(float((x[f"ret_{tag}"] > x["ret_ndx"]).mean() * 100), 0)}
            for y, x in g}

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"{len(df)} 个一年期窗口 {df.start.min()} ~ {df.start.max()}\n")
    print(f"{'策略':<14}{'均值':>8}{'中位':>8}{'最差':>9}{'最好':>9}{'暂停次数':>8}{'买入溢价':>9}{'胜无脑':>7}{'胜纳指':>7}")
    labels = {"dumb": "无脑定投"}
    for thr in THRESHOLDS:
        if thr: labels[f"t{thr}"] = f"阈值 {thr}%"
    for thr, mw in HYBRIDS:
        labels[f"h{thr}_{mw}"] = f"阈值{thr}%+等{mw}月"
    for tag in all_tags:
        if tag == "ndx":
            continue
        x = res["detail"][tag]
        lab = labels[tag]
        print(f"{lab:<14}{x['mean']:>7.2f}%{x['median']:>7.2f}%{x['min']:>8.2f}%{x['max']:>8.2f}%"
              f"{x['avg_paused']:>8.2f}{x['avg_buy_prem']:>8.2f}%{x['vs_dumb_win']:>6.0f}%{x['vs_ndx_win']:>6.0f}%")
    x = res["detail"]["ndx"]
    print(f"{'纳指100':<14}{x['mean']:>7.2f}%{x['median']:>7.2f}%{x['min']:>8.2f}%{x['max']:>8.2f}%"
          f"{'-':>8}{'-':>9}{'-':>7}{'-':>7}")

    print("\n按起投年份（均值）：")
    for thr in [3, 5, 8, 10]:
        tag = f"t{thr}"
        by = res["detail"][tag]["by_year"]
        print(f"  阈值{thr}%: " + "  ".join(f"{y}:{v['mean']:+.2f}%" for y, v in by.items()))


if __name__ == "__main__":
    main()
