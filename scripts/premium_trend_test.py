# -*- coding: utf-8 -*-
"""
把「溢价水位上涨」这个变量单独拎出来验证：
所有回测里 A 跑赢 C，到底是品种优势，还是溢价单边抬升带来的账面收益？

做法：
  1) 覆盖 2015-09 至今（不只 2021 起），6 个月 / 12 个月两种持有期
  2) 每个窗口记录：A 收益、C 收益、买入加权溢价、卖出溢价
  3) 按「卖出溢价 − 买入溢价」分组，看 A−C 是否完全由它决定
  4) 分期：2015-2019（溢价无趋势）/ 2020-2024（小幅抬升）/ 2025-2026（快速抬升）
"""
import os, json, sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "premium_trend_test.json")
CSV = os.path.join(ROOT, "data", "premium_trend_windows.csv")
AMOUNT = 5000


def load():
    c = sqlite3.connect(DB)
    lof = pd.read_sql(
        "select trade_date, close_adj, nav_adj, premium_lag from px_lof_daily "
        "where fund_code='159941' and close_adj is not null and nav_adj is not null "
        "and premium_lag is not null order by trade_date", c, parse_dates=["trade_date"]).set_index("trade_date")
    ndx = pd.read_sql(
        "select trade_date, close from px_index_daily_us where index_code='.NDX' order by trade_date",
        c, parse_dates=["trade_date"]).set_index("trade_date")["close"].dropna()
    c.close()
    return lof, ndx


def dates_for(idx, m0, months):
    out = []
    for k in range(months):
        t = (m0 + pd.offsets.MonthBegin(k)).replace(day=15)
        cand = idx[idx >= t]
        if not len(cand):
            return None
        out.append(cand[0])
    return out


def window(lof, ndx, ds):
    sh_a = sh_c = 0.0
    prem = []
    for d in ds:
        sh_a += AMOUNT / lof.loc[d, "close_adj"]
        prem.append(lof.loc[d, "premium_lag"])
        prev = ndx.index[ndx.index < d]
        if len(prev):
            sh_c += AMOUNT / ndx.loc[prev[-1]]
    end = ds[-1]
    inv = AMOUNT * len(ds)
    v_a = sh_a * lof.loc[end, "close_adj"]
    v_c = sh_c * ndx.loc[ndx.index[ndx.index <= end][-1]]
    return {
        "ret_a": (v_a / inv - 1) * 100,
        "ret_c": (v_c / inv - 1) * 100,
        "diff": (v_a / inv - v_c / inv) * 100,
        "p_entry": float(np.mean(prem)),
        "p_exit": float(lof.loc[end, "premium_lag"]),
    }


def build(lof, ndx, months, start_min, start_max):
    rows = []
    for m0 in pd.date_range(start_min, start_max, freq="MS"):
        ds = dates_for(lof.index, m0, months)
        if ds is None or len(ds) != months:
            continue
        r = window(lof, ndx, ds)
        r.update({"start": ds[0].strftime("%Y-%m"), "end": ds[-1].strftime("%Y-%m"), "n": months})
        rows.append(r)
    return pd.DataFrame(rows)


def summarize(df, label):
    df = df.copy()
    df["dp"] = df.p_exit - df.p_entry
    buckets = [(-99, -2, "溢价↓ >2pp"), (-2, 2, "平稳 ±2pp"), (2, 5, "上行 2~5pp"), (5, 99, "上行 >5pp")]
    print(f"\n=== {label}（{len(df)} 个窗口，{df.n.iloc[0]} 个月）===")
    print(f"{'分组':<14}{'窗口数':>6}{'A均值':>9}{'C均值':>9}{'A−C均值':>10}{'A−C中位':>10}{'胜率':>7}")
    out = {}
    for lo, hi, name in buckets:
        g = df[(df.dp > lo) & (df.dp <= hi)]
        if len(g) < 3:
            continue
        print(f"{name:<14}{len(g):>6}{g.ret_a.mean():>8.2f}%{g.ret_c.mean():>8.2f}%"
              f"{g['diff'].mean():>+9.2f}pp{g['diff'].median():>+9.2f}pp{(g['diff'] > 0).mean() * 100:>6.0f}%")
        out[name] = {"n": int(len(g)), "diff_mean": round(float(g["diff"].mean()), 2),
                     "diff_median": round(float(g["diff"].median()), 2),
                     "win": round(float((g["diff"] > 0).mean() * 100), 0),
                     "ret_a": round(float(g.ret_a.mean()), 2), "ret_c": round(float(g.ret_c.mean()), 2)}
    slope, inter = np.polyfit(df.dp, df["diff"], 1)
    r = df.dp.corr(df["diff"])
    print(f"回归 A−C = {slope:+.3f}×Δ溢价 {inter:+.2f}　corr={r:.3f}　R²={r**2:.3f}")
    out["_reg"] = {"slope": round(float(slope), 3), "intercept": round(float(inter), 2),
                   "corr": round(float(r), 3), "r2": round(float(r ** 2), 3)}
    return out


def main():
    lof, ndx = load()
    d12 = build(lof, ndx, 12, "2015-09-01", "2025-12-01")
    d6 = build(lof, ndx, 6, "2015-09-01", "2026-05-01")
    all12 = pd.concat([d12, d6])
    all12.to_csv(CSV, index=False, encoding="utf-8-sig")

    res = {"windows_12m": summarize(d12, "全部 12 个月窗口 2015-2026"),
           "windows_6m": summarize(d6, "全部 6 个月窗口 2015-2026")}

    # 分期
    for lab, a, b in [("2015-2019", "2015-09", "2019-12"), ("2020-2024", "2020-01", "2024-12"),
                      ("2025-2026", "2025-01", "2025-12")]:
        g12 = d12[(d12.start >= a) & (d12.start <= b)]
        g6 = d6[(d6.start >= a) & (d6.start <= b)]
        if len(g12):
            res[f"period_{lab}_12m"] = summarize(g12, f"{lab} 12 个月窗口")
        if len(g6):
            res[f"period_{lab}_6m"] = summarize(g6, f"{lab} 6 个月窗口")

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n写出", OUT)


if __name__ == "__main__":
    main()
