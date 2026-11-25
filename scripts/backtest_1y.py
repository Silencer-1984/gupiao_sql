# -*- coding: utf-8 -*-
"""
一年期定投对比：2021-01 ~ 2026-11 之间，随机（实际穷举）起点，持有 12 个月。

规则：
  - 每月 15 日（遇非交易日顺延）投入 5000 元，共 12 期（6 万）
  - 只比较两条：A 场内 159941 收盘价买入 / C 纳指100（美元）
  - 期末 = 第 12 次扣款当日收盘，含亏损

输出：全部可用窗口的对比 + 随机抽样的样例 + 分布统计
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "mc_1y.json")
CSV = os.path.join(ROOT, "data", "mc_1y_windows.csv")

AMOUNT = 5000
MONTHS = 12
START_MIN = "2021-01-01"
START_MAX = "2026-11-30"


def load():
    c = sqlite3.connect(DB)
    lof = pd.read_sql(
        "select trade_date, close_adj, nav_adj from px_lof_daily "
        "where fund_code='159941' and close_adj is not null and nav_adj is not null "
        "order by trade_date", c, parse_dates=["trade_date"]).set_index("trade_date")
    ndx = pd.read_sql(
        "select trade_date, close from px_index_daily_us where index_code='.NDX' order by trade_date",
        c, parse_dates=["trade_date"]).set_index("trade_date")["close"].dropna()
    c.close()
    lof["psame"] = lof.close_adj / lof.nav_adj - 1
    return lof, ndx


def dates_for(lof_index, start_month):
    out = []
    for k in range(MONTHS):
        target = (start_month + pd.offsets.MonthBegin(k)).replace(day=15)
        cand = lof_index[lof_index >= target]
        if not len(cand):
            return None
        out.append(cand[0])
    return out


def run_window(lof, ndx, ds):
    sh_a = sh_c = 0.0
    prem = []
    for d in ds:
        r = lof.loc[d]
        sh_a += AMOUNT / r.close_adj
        prem.append(r.psame)
        prev = ndx.index[ndx.index < d]
        if len(prev):
            sh_c += AMOUNT / ndx.loc[prev[-1]]
    end = ds[-1]
    r_end = lof.loc[end]
    v_a = sh_a * r_end.close_adj
    ndx_end = ndx.index[ndx.index <= end]
    v_c = sh_c * ndx.loc[ndx_end[-1]]
    inv = AMOUNT * MONTHS
    return {
        "start": ds[0].strftime("%Y-%m"),
        "end": end.strftime("%Y-%m"),
        "ret_a": (v_a / inv - 1) * 100,
        "ret_c": (v_c / inv - 1) * 100,
        "diff": (v_a / inv - v_c / inv) * 100,
        "p_entry": float(np.mean(prem)) * 100,
        "p_exit": float(r_end.psame) * 100,
    }


def main():
    lof, ndx = load()
    idx = lof.index
    months = pd.date_range(START_MIN, START_MAX, freq="MS")
    months = [m for m in months if m + pd.offsets.MonthBegin(MONTHS) <= pd.Timestamp("2026-12-01")]

    rows = []
    for m in months:
        ds = dates_for(idx, m)
        if ds is None or len(ds) != MONTHS:
            continue
        rows.append(run_window(lof, ndx, ds))
    df = pd.DataFrame(rows)
    df.to_csv(CSV, index=False, encoding="utf-8-sig")

    rng = np.random.default_rng(7)
    pick = df.sample(n=min(10, len(df)), random_state=7).sort_values("start")

    res = {
        "n_windows": int(len(df)),
        "range": [df.start.min(), df.start.max()],
        "ret_a": {"mean": round(df.ret_a.mean(), 2), "median": round(df.ret_a.median(), 2),
                  "min": round(df.ret_a.min(), 2), "max": round(df.ret_a.max(), 2)},
        "ret_c": {"mean": round(df.ret_c.mean(), 2), "median": round(df.ret_c.median(), 2),
                  "min": round(df.ret_c.min(), 2), "max": round(df.ret_c.max(), 2)},
        "diff": {"mean": round(df["diff"].mean(), 2), "median": round(df["diff"].median(), 2),
                 "min": round(df["diff"].min(), 2), "max": round(df["diff"].max(), 2)},
        "win_rate_a": round(float((df.ret_a > df.ret_c).mean() * 100), 1),
        "lose_rate_a": round(float((df.ret_a < df.ret_c).mean() * 100), 1),
        "corr_prem_change_vs_diff": round(float((df.p_exit - df.p_entry).corr(df["diff"])), 3),
        "samples": pick.round(2).to_dict("records"),
        "windows": df.round(2).to_dict("records"),
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"共 {len(df)} 个一年期窗口（起点 {df.start.min()} ~ {df.start.max()}）\n")
    print("随机抽 10 组：")
    print(f"{'起投':>8} {'卖出':>8} {'场内159941':>10} {'纳指100':>9} {'差值':>8} {'买溢价':>7} {'卖溢价':>7}")
    for _, r in pick.iterrows():
        print(f"{r.start:>8} {r.end:>8} {r.ret_a:>9.2f}% {r.ret_c:>8.2f}% {r['diff']:>+7.2f}pp "
              f"{r.p_entry:>6.2f}% {r.p_exit:>6.2f}%")

    print(f"\n{'':>8} {'均值':>9} {'中位':>9} {'最差':>9} {'最好':>9}")
    for k, lab in [("ret_a", "场内159941"), ("ret_c", "纳指100")]:
        s = df[k]
        print(f"{lab:>8} {s.mean():>8.2f}% {s.median():>8.2f}% {s.min():>8.2f}% {s.max():>8.2f}%")
    d = df["diff"]
    print(f"{'差值':>8} {d.mean():>8.2f}pp {d.median():>8.2f}pp {d.min():>8.2f}pp {d.max():>8.2f}pp")
    print(f"\n场内赢 {res['win_rate_a']}%　场内输 {res['lose_rate_a']}%")
    print(f"溢价变化 vs 差值 相关 {res['corr_prem_change_vs_diff']}")


if __name__ == "__main__":
    main()
