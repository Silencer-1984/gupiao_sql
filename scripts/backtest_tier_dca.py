# -*- coding: utf-8 -*-
"""
按溢价分档加码的定投策略（只能买场内 ETF 的人）。

规则：
  - 每月固定 5000 元充入现金池（钱不会少，只是择时投出去）
  - 按当日可观测溢价 p 决定本月买多少（倍数是相对 5000）
  - 低溢价加码（用池子里的钱补），高溢价缩量或暂停
  - 现金池超过 3 期（15000）的部分，无条件立即投出 → 防止资金长期停摆

对比：无脑定投 / 阈值5%+等3月 / 纳指100
区间：2021-2026（60 个一年期窗口）+ 2015-2026（124 个窗口）
"""
import os, json, sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "tier_dca.json")
CSV = os.path.join(ROOT, "data", "tier_dca_windows.csv")

BASE = 5000


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


# 档位：(溢价上限, 倍数)
TIERS = {
    "V1 温和(4/2/1/0.5/0)": [(1, 4), (3, 2), (8, 1), (15, 0.5), (999, 0)],
    "V2 中等(3/2/1/0.5/0)": [(2, 3), (5, 2), (8, 1), (15, 0.5), (999, 0)],
    "V3 简单(2/1/0.5/0)": [(3, 2), (8, 1), (15, 0.5), (999, 0)],
    "V4 只暂停(1/0.5/0)": [(8, 1), (15, 0.5), (999, 0)],
    "V5 对称(2/1/0.5/0)": [(2, 2), (5, 1), (10, 0.5), (999, 0)],
}
# 分位档（按滚动 250 日溢价分位，而不是绝对值）
PCT_TIERS = {
    "P1 分位档 30/70/90": [(30, 2.0), (70, 1.0), (90, 0.5), (101, 0.0)],
    "P2 分位档 20/60/85": [(20, 3.0), (60, 1.0), (85, 0.5), (101, 0.0)],
    "P3 只加不减 30": [(30, 2.0), (101, 1.0)],
}
CASH_CAP = 3 * BASE      # 池子超过 3 期就强制投


def mult(p, tiers):
    for hi, m in tiers:
        if p <= hi:
            return m
    return 0


def run_pct(lof, ds, tiers):
    cash = sh = 0.0
    prem = []
    forced = 0
    for d in ds:
        cash += BASE
        pct = lof.loc[d, "pct250"]
        if pd.isna(pct):
            m = 1.0
        else:
            m = next(mm for hi, mm in tiers if pct <= hi)
        want = BASE * m
        if cash > CASH_CAP:
            want = max(want, cash - CASH_CAP + want)
            forced += 1
        buy = min(cash, max(want, 0))
        if buy > 0:
            sh += buy / lof.loc[d, "close_adj"]
            cash -= buy
            prem.append(float(lof.loc[d, "premium_lag"]))
    v = sh * lof.loc[ds[-1], "close_adj"] + cash
    return {"ret": (v / (BASE * len(ds)) - 1) * 100, "idle": cash,
            "avg_prem": float(np.mean(prem)) if prem else None, "forced": forced}


def run_tier(lof, ds, tiers):
    cash = sh = 0.0
    prem = []
    forced = paused = 0
    for d in ds:
        cash += BASE
        p = float(lof.loc[d, "premium_lag"])
        want = BASE * mult(p, tiers)
        # 池子超限 → 强制把超出部分投掉
        if cash > CASH_CAP:
            want = max(want, cash - CASH_CAP + want)
            forced += 1
        buy = min(cash, max(want, 0))
        if buy > 0:
            sh += buy / lof.loc[d, "close_adj"]
            cash -= buy
            prem.append(p)
            if buy > 0:
                pass
        if buy == 0:
            paused += 1
    v = sh * lof.loc[ds[-1], "close_adj"] + cash
    return {"ret": (v / (BASE * len(ds)) - 1) * 100, "idle": cash,
            "avg_prem": float(np.mean(prem)) if prem else None,
            "paused": paused, "forced": forced}


def run_flat(lof, ds):
    sh = sum(BASE / lof.loc[d, "close_adj"] for d in ds)
    return {"ret": (sh * lof.loc[ds[-1], "close_adj"] / (BASE * len(ds)) - 1) * 100, "idle": 0.0}


def run_thr(lof, ds, thr=5, maxwait=3):
    cash = sh = 0.0
    consec = 0
    for d in ds:
        cash += BASE
        p = float(lof.loc[d, "premium_lag"])
        ok = p <= thr or consec >= maxwait
        if ok:
            sh += cash / lof.loc[d, "close_adj"]
            cash = 0.0
            consec = 0
        else:
            consec += 1
    return {"ret": (sh * lof.loc[ds[-1], "close_adj"] + cash) / (BASE * len(ds)) * 100 - 100, "idle": cash}


def run_ndx(ndx, ds):
    sh = 0.0
    for d in ds:
        prev = ndx.index[ndx.index < d]
        if len(prev):
            sh += BASE / ndx.loc[prev[-1]]
    return (sh * ndx.loc[ndx.index[ndx.index <= ds[-1]][-1]] / (BASE * len(ds)) - 1) * 100


def dates_for(idx, m0, months):
    out = []
    for k in range(months):
        t = (m0 + pd.offsets.MonthBegin(k)).replace(day=15)
        cand = idx[idx >= t]
        if not len(cand):
            return None
        out.append(cand[0])
    return out


def evaluate(start_min, start_max, months, label):
    lof, ndx = load()
    lof["pct250"] = lof.premium_lag.rolling(250, min_periods=100).apply(
        lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)
    idx = lof.index
    rows = []
    for m0 in pd.date_range(start_min, start_max, freq="MS"):
        ds = dates_for(idx, m0, months)
        if ds is None or len(ds) != months:
            continue
        rec = {"start": ds[0].strftime("%Y-%m"), "end": ds[-1].strftime("%Y-%m")}
        rec["无脑"] = run_flat(lof, ds)["ret"]
        rec["阈值5+等3"] = run_thr(lof, ds)["ret"]
        rec["纳指"] = run_ndx(ndx, ds)
        for name, tiers in TIERS.items():
            r = run_tier(lof, ds, tiers)
            rec[name] = r["ret"]
            rec[name + "_idle"] = r["idle"]
            rec[name + "_prem"] = r["avg_prem"]
            rec[name + "_forced"] = r["forced"]
            rec[name + "_paused"] = r["paused"]
        for name, tiers in PCT_TIERS.items():
            r = run_pct(lof, ds, tiers)
            rec[name] = r["ret"]
            rec[name + "_idle"] = r["idle"]
            rec[name + "_prem"] = r["avg_prem"]
        rows.append(rec)
    df = pd.DataFrame(rows)
    print(f"\n===== {label}（{len(df)} 个窗口，{months} 个月）=====")
    print(f"{'策略':<22}{'均值':>8}{'中位':>8}{'最差':>9}{'最好':>9}{'平均闲置':>9}{'买入溢价':>9}{'胜无脑':>7}")
    base = df["无脑"]
    out = {}
    for name in ["无脑", "阈值5+等3"] + list(TIERS) + list(PCT_TIERS) + ["纳指"]:
        s = df[name]
        idle = df[name + "_idle"].mean() if name + "_idle" in df else 0
        prem = df[name + "_prem"].dropna().mean() if name + "_prem" in df else np.nan
        win = (s > base).mean() * 100 if name not in ("无脑", "纳指") else np.nan
        print(f"{name:<22}{s.mean():>7.2f}%{s.median():>7.2f}%{s.min():>8.2f}%{s.max():>8.2f}%"
              f"{idle:>9,.0f}{prem:>8.2f}%{'' if np.isnan(win) else f'{win:>6.0f}%'}")
        out[name] = {"mean": round(float(s.mean()), 2), "median": round(float(s.median()), 2),
                     "min": round(float(s.min()), 2), "max": round(float(s.max()), 2),
                     "idle": round(float(idle), 0),
                     "prem": None if np.isnan(prem) else round(float(prem), 2),
                     "win_vs_dumb": None if np.isnan(win) else round(float(win), 0)}
    if "V2 中等(3/2/1/0.5/0)_forced" in df:
        out["_forced_avg"] = round(float(df["V2 中等(3/2/1/0.5/0)_forced"].mean()), 2)
    return df, out


def main():
    res = {}
    d1, r1 = evaluate("2021-01-01", "2025-12-01", 12, "2021-2026 一年期")
    d2, r2 = evaluate("2015-09-01", "2025-12-01", 12, "2015-2026 一年期（含无溢价年代）")
    res = {"2021_2026": r1, "2015_2026": r2}
    d1.to_csv(CSV, index=False, encoding="utf-8-sig")
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n写出", OUT, "/", CSV)


if __name__ == "__main__":
    main()
