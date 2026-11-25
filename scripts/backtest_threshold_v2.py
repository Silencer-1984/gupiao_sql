# -*- coding: utf-8 -*-
"""修正版阈值策略：绝对阈值 vs 相对阈值（滚动中位+偏移） vs 下跌豁免。"""
import os, json, sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "thr_dca_v2.json")
AMOUNT, MONTHS = 5000, 12


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
    lof["pmed120"] = lof.premium_lag.rolling(120, min_periods=40).median()
    ndx20 = ndx / ndx.shift(20) - 1
    return lof, ndx, ndx20


def dates_for(idx, m0):
    out = []
    for k in range(MONTHS):
        t = (m0 + pd.offsets.MonthBegin(k)).replace(day=15)
        cand = idx[idx >= t]
        if not len(cand):
            return None
        out.append(cand[0])
    return out


def decide(lof, ndx20, d, rule, consec):
    p = lof.loc[d, "premium_lag"]
    pm = lof.loc[d, "pmed120"]
    d20 = ndx20.asof(d) * 100 if len(ndx20[:d]) else 0.0
    if rule["kind"] == "abs":
        return p <= rule["thr"]
    if rule["kind"] == "rel":
        if pd.isna(pm):
            return True
        return p <= pm + rule["thr"]
    if rule["kind"] == "abs_down":
        thr = rule["thr"]
        if d20 <= rule["dd"]:          # 跌市豁免：阈值放宽
            thr = rule["thr_wide"]
        return p <= thr
    return True


RULES = [
    ("无脑", {"kind": "none"}),
    ("绝对 5%", {"kind": "abs", "thr": 5}),
    ("绝对 5% + 等3月", {"kind": "abs", "thr": 5, "maxwait": 3}),
    ("相对中位+3pp", {"kind": "rel", "thr": 3}),
    ("相对中位+5pp", {"kind": "rel", "thr": 5}),
    ("绝对5%+跌市放宽15%", {"kind": "abs_down", "thr": 5, "dd": -8, "thr_wide": 15}),
]


def main():
    lof, ndx, ndx20 = load()
    idx = lof.index
    months = list(pd.date_range("2021-01-01", "2025-12-01", freq="MS"))
    rows = []
    for m0 in months:
        ds = dates_for(idx, m0)
        if ds is None or len(ds) != MONTHS:
            continue
        rec = {"start": ds[0].strftime("%Y-%m"), "end": ds[-1].strftime("%Y-%m")}
        for name, rule in RULES:
            cash = sh = 0.0
            paused = consec = 0
            prem = []
            for d in ds:
                cash += AMOUNT
                ok = decide(lof, ndx20, d, rule, consec)
                if not ok and rule.get("maxwait") and consec >= rule["maxwait"]:
                    ok = True
                if ok:
                    sh += cash / lof.loc[d, "close_adj"]
                    prem.append(lof.loc[d, "premium_lag"])
                    cash = 0.0
                    consec = 0
                else:
                    paused += 1
                    consec += 1
            v = sh * lof.loc[ds[-1], "close_adj"] + cash
            rec[name] = (v / (AMOUNT * MONTHS) - 1) * 100
            rec[name + "_pause"] = paused
            rec[name + "_idle"] = cash
        # 纳指基准
        shn = 0.0
        for d in ds:
            prev = ndx.index[ndx.index < d]
            if len(prev):
                shn += AMOUNT / ndx.loc[prev[-1]]
        rec["纳指"] = (shn * ndx.loc[ndx.index[ndx.index <= ds[-1]][-1]] / (AMOUNT * MONTHS) - 1) * 100
        rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ROOT, "data", "thr_dca_v2.csv"), index=False, encoding="utf-8-sig")

    print(f"{len(df)} 个一年期窗口\n")
    print(f"{'策略':<22}{'均值':>8}{'中位':>8}{'最差':>9}{'最好':>9}{'平均暂停':>8}{'平均闲置':>9}")
    base = df["无脑"]
    for name, _ in RULES:
        s = df[name]
        print(f"{name:<22}{s.mean():>7.2f}%{s.median():>7.2f}%{s.min():>8.2f}%{s.max():>8.2f}%"
              f"{df[name+'_pause'].mean():>8.2f}{df[name+'_idle'].mean():>9,.0f}")
    s = df["纳指"]
    print(f"{'纳指100':<22}{s.mean():>7.2f}%{s.median():>7.2f}%{s.min():>8.2f}%{s.max():>8.2f}%\n")

    print("相对无脑的改善（仅在 2025 起投窗口）：")
    d25 = df[df.start.str[:4] == "2025"]
    for name, _ in RULES:
        if name == "无脑":
            continue
        print(f"  {name:<22} 均值 {d25[name].mean() - d25['无脑'].mean():+.2f}pp  "
              f"胜率 {(d25[name] > d25['无脑']).mean() * 100:.0f}%")

    json.dump({"summary": {n: {"mean": round(float(df[n].mean()), 2),
                              "median": round(float(df[n].median()), 2)} for n, _ in RULES},
               "n": len(df)}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
