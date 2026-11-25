# -*- coding: utf-8 -*-
"""
随机定投蒙特卡洛：随机起点 + 随机时长 + 随机扣款日，抹掉「现在溢价 21%」这个终点偏差。

对每个模拟投资者：
  - 随机起点（2015-07 ~ 2024-11 之间）
  - 随机时长（12 / 24 / 36 / 60 个月）
  - 随机扣款日（每月 1~28 日中随机一天，遇非交易日顺延）
  - 每期 5000 元，不做任何择时

三条轨：A 场内 159941（收盘价） / B 场外按净值 / C 纯纳指100
输出分布（胜率、均值、中位、分位）+ 溢价贡献的归因，以及「按 5 年中位溢价结算」的公平版。
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "mc_dca.json")

AMOUNT = 5000
N_SIM = 3000
HORIZONS = [12, 24, 36, 60]
SEED = 20261123


def load():
    c = sqlite3.connect(DB)
    lof = pd.read_sql(
        "select trade_date, close_adj, nav_adj from px_lof_daily "
        "where fund_code='159941' and close_adj is not null and nav_adj is not null "
        "order by trade_date", c, parse_dates=["trade_date"])
    ndx = pd.read_sql(
        "select trade_date, close from px_index_daily_us where index_code='.NDX' order by trade_date",
        c, parse_dates=["trade_date"])
    c.close()
    lof = lof.set_index("trade_date")
    lof["psame"] = lof.close_adj / lof.nav_adj - 1
    ndx = ndx.set_index("trade_date")["close"].dropna()
    return lof, ndx


def buy_dates(lof_index, start_month, months, day):
    """每月 day 号 → 当月第一个 >= 该日的交易日。"""
    out = []
    for k in range(months):
        m = (start_month + pd.offsets.MonthBegin(k)).replace(day=1)
        target = m.replace(day=min(day, 28))
        cand = lof_index[lof_index >= target]
        if not len(cand):
            return None
        out.append(cand[0])
    return out


def main():
    lof, ndx = load()
    idx = lof.index
    rng = np.random.default_rng(SEED)
    sims = []

    months_all = pd.date_range(idx.min(), idx.max(), freq="MS")
    for _ in range(N_SIM):
        months = int(rng.choice(HORIZONS))
        max_start_i = len(months_all) - months - 1
        if max_start_i < 1:
            continue
        start_month = months_all[rng.integers(1, max_start_i)]
        day = int(rng.integers(1, 29))
        ds = buy_dates(idx, start_month, months, day)
        if ds is None or len(ds) != months:
            continue
        exit_d = ds[-1]

        sh_a = sh_b = sh_c = 0.0
        prem_w = []
        for d in ds:
            r = lof.loc[d]
            sh_a += AMOUNT / r.close_adj
            sh_b += AMOUNT / r.nav_adj
            prem_w.append(r.psame)
            prev = ndx.index[ndx.index < d]
            if len(prev):
                sh_c += AMOUNT / ndx.loc[prev[-1]]

        r_end = lof.loc[exit_d]
        exit_ndx = ndx.index[ndx.index <= exit_d]
        p_exit = r_end.psame
        p_entry = sum(prem_w) / len(prem_w)

        v_a = sh_a * r_end.close_adj
        v_b = sh_b * r_end.nav_adj
        v_c = sh_c * ndx.loc[exit_ndx[-1]] if len(exit_ndx) else np.nan
        inv = AMOUNT * months

        sims.append({
            "months": months,
            "start": ds[0].strftime("%Y-%m-%d"),
            "end": exit_d.strftime("%Y-%m-%d"),
            "ret_a": (v_a / inv - 1) * 100,
            "ret_b": (v_b / inv - 1) * 100,
            "ret_c": (v_c / inv - 1) * 100,
            "p_entry": p_entry * 100,
            "p_exit": p_exit * 100,
            "v_a_norm": sh_a * r_end.nav_adj * (1 + 0.0149),   # 按 5 年中位溢价 1.49% 结算
            "inv": inv,
        })

    df = pd.DataFrame(sims)
    df["a_minus_c"] = df.ret_a - df.ret_c
    df["a_minus_b"] = df.ret_a - df.ret_b
    df["p_change"] = df.p_exit - df.p_entry
    df["ret_a_norm"] = (df.v_a_norm / df.inv - 1) * 100
    df["anorm_minus_c"] = df.ret_a_norm - df.ret_c

    def stat(s, pct=False):
        return {
            "n": int(len(s)),
            "mean": round(float(s.mean()), 2),
            "median": round(float(s.median()), 2),
            "p05": round(float(s.quantile(0.05)), 2),
            "p25": round(float(s.quantile(0.25)), 2),
            "p75": round(float(s.quantile(0.75)), 2),
            "p95": round(float(s.quantile(0.95)), 2),
        }

    res = {
        "n_sim": int(len(df)),
        "seed": SEED,
        "ranges": {"from": df.start.min(), "to": df.end.max()},
        "overall": {
            "ret_a": stat(df.ret_a), "ret_b": stat(df.ret_b), "ret_c": stat(df.ret_c),
            "win_rate_a_over_c": round(float((df.ret_a > df.ret_c).mean() * 100), 1),
            "win_rate_a_over_b": round(float((df.ret_a > df.ret_b).mean() * 100), 1),
            "a_minus_c": stat(df.a_minus_c),
            "a_minus_b": stat(df.a_minus_b),
            "p_entry": stat(df.p_entry), "p_exit": stat(df.p_exit),
        },
        "normalized": {
            "note": "A 轨按 5 年中位溢价 1.49% 结算，剔除当前极端溢价",
            "ret_a_norm": stat(df.ret_a_norm),
            "win_rate_over_c": round(float((df.ret_a_norm > df.ret_c).mean() * 100), 1),
            "win_rate_over_b": round(float((df.ret_a_norm > df.ret_b).mean() * 100), 1),
            "anorm_minus_c": stat(df.anorm_minus_c),
            "anorm_minus_b": stat(df.ret_a_norm - df.ret_b),
        },
        "by_horizon": {},
        "by_exit_premium": {},
        "corr": {
            "pchange_vs_aminusb": round(float(df.p_change.corr(df.a_minus_b)), 3),
            "pchange_vs_aminusc": round(float(df.p_change.corr(df.a_minus_c)), 3),
        },
    }
    for h in HORIZONS:
        g = df[df.months == h]
        res["by_horizon"][h] = {
            "n": int(len(g)),
            "ret_a": round(float(g.ret_a.mean()), 2),
            "ret_b": round(float(g.ret_b.mean()), 2),
            "ret_c": round(float(g.ret_c.mean()), 2),
            "win_a_over_c": round(float((g.ret_a > g.ret_c).mean() * 100), 1),
            "a_minus_c_median": round(float((g.ret_a - g.ret_c).median()), 2),
            "p_entry_median": round(float(g.p_entry.median()), 2),
            "p_exit_median": round(float(g.p_exit.median()), 2),
        }
    # 按退出溢价分组（越低越接近"溢价已回落"的情形）
    for lo, hi, lab in [(-99, 3, "退出溢价<3%"), (3, 8, "3~8%"), (8, 15, "8~15%"), (15, 999, ">15%")]:
        g = df[(df.p_exit > lo) & (df.p_exit <= hi)]
        if len(g) >= 20:
            res["by_exit_premium"][lab] = {
                "n": int(len(g)),
                "a_minus_c_median": round(float((g.ret_a - g.ret_c).median()), 2),
                "win_a_over_c": round(float((g.ret_a > g.ret_c).mean() * 100), 1),
                "anorm_minus_c_median": round(float((g.ret_a_norm - g.ret_c).median()), 2),
            }

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    df.to_csv(os.path.join(ROOT, "data", "mc_dca_samples.csv"), index=False, encoding="utf-8-sig")

    o = res["overall"]
    print(f"模拟 {res['n_sim']} 组，起点 {res['ranges']['from']} ~ {res['ranges']['to']}\n")
    for k, lab in [("ret_a", "A 场内159941"), ("ret_b", "B 场外净值"), ("ret_c", "C 纯纳指")]:
        s = o[k]
        print(f"  {lab:12s} 均值 {s['mean']:>6.2f}%  中位 {s['median']:>6.2f}%  5%~95% [{s['p05']:>6.1f}, {s['p95']:>6.1f}]")
    print(f"\n  A 胜 C 的概率 {o['win_rate_a_over_c']}%   A 胜 B 的概率 {o['win_rate_a_over_b']}%")
    print(f"  A−C 中位 {o['a_minus_c']['median']:+.2f}pp   A−B 中位 {o['a_minus_b']['median']:+.2f}pp")
    print(f"  买入溢价 中位 {o['p_entry']['median']:.2f}%   退出溢价 中位 {o['p_exit']['median']:.2f}%")
    n = res["normalized"]
    print(f"\n  [剔除当前极端溢价] A 按 1.49% 结算：均值 {n['ret_a_norm']['mean']:.2f}%  胜C {n['win_rate_over_c']}%  "
          f"A−C 中位 {n['anorm_minus_c']['median']:+.2f}pp")
    print("\n  按时长：")
    for h, v in res["by_horizon"].items():
        print(f"   {h:>2}月 A {v['ret_a']:>6.2f}%  B {v['ret_b']:>6.2f}%  C {v['ret_c']:>6.2f}%  "
              f"胜C {v['win_a_over_c']:>4.1f}%  A−C 中位 {v['a_minus_c_median']:+.2f}pp  "
              f"买入{v['p_entry_median']:.2f}%→退出{v['p_exit_median']:.2f}%")
    print("\n  按退出溢价：")
    for k, v in res["by_exit_premium"].items():
        print(f"   {k:12s} n={v['n']:>4d}  A−C 中位 {v['a_minus_c_median']:+.2f}pp  胜C {v['win_a_over_c']:>4.1f}%  "
              f"（按1.49%结算后 {v['anorm_minus_c_median']:+.2f}pp）")
    print("\n  相关：Δ溢价 vs (A−B)", res["corr"]["pchange_vs_aminusb"],
          " vs (A−C)", res["corr"]["pchange_vs_aminusc"])


if __name__ == "__main__":
    main()
