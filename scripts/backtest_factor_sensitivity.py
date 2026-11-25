# -*- coding: utf-8 -*-
"""因子阈值敏感性与组合检验：确认 ERP 与恐慌度是否有效，还是阈值偶然。"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from backtest_factor_filters import (build, sim_metrics, mc_test, start_position_matrix,
                                     positions_filtered, EXIT_RULES, FILTERS, START)
from backtest_pe_pct_2019 import apply_pos
from factor_timing_data import rolling_pct as rp

OUT = os.path.join(ROOT, "data", "factor_sensitivity.json")
WINDOWS = {3: 36, 5: 60}


def run(f, y, fn, lo, hi, sell=None):
    exit_rule = EXIT_RULES[sell] if sell else None
    pos = positions_filtered(f, y, fn, exit_rule=exit_rule)
    m = sim_metrics(f, y, pos, lo, hi)
    pm = start_position_matrix(f, y, fn, lo, hi) if sell is None else None
    mc = mc_test(f, y, fn, pm=pm, lo=lo, hi=hi) if sell is None else None
    return m, mc


def main():
    f = build()
    ym = f.index.values.astype(str)
    lo = int(np.searchsorted(ym, START))
    hi = len(f) - 1
    res = {"erp_sweep": {}, "combos": {}, "erp_bands": {}, "curves": {}, "meta": {
        "erp_def": "ERP = 100/PE-TTM(加权) - 10年国债收益率，单位百分点",
    }}

    close_arr = f.index_close.values.astype(float)
    ret_arr = np.concatenate([close_arr[1:] / close_arr[:-1] - 1, [np.nan]])
    res["curves"]["ym"] = [str(x) for x in f.index[lo:hi + 1]]
    res["curves"]["bh"] = [round(float(x), 4) for x in np.cumprod(1 + np.nan_to_num(ret_arr[lo:hi + 1]))]
    best = {
        "基线": lambda r, y: True,
        "ERP≥6.5且恐慌≥50": lambda r, y: r.erp >= 6.5 and r.fear_composite >= 50,
        "ERP≥6.5且恐慌≥50_卖90": lambda r, y: r.erp >= 6.5 and r.fear_composite >= 50,
    }
    for y in WINDOWS:
        for name, fn in best.items():
            sell = EXIT_RULES["PE≥90"] if name.endswith("卖90") else None
            pos = positions_filtered(f, y, fn, exit_rule=sell)[lo:hi + 1]
            rs = np.cumprod(1 + apply_pos(pos, ret_arr[lo:hi + 1]))
            res["curves"][f"{y}y_{name}"] = [round(float(x), 4) for x in rs]

    # ---------- 1. ERP 阈值敏感性 ----------
    for y in WINDOWS:
        rows = []
        for th in np.arange(5.0, 7.51, 0.25):
            th = round(float(th), 2)
            fn = lambda r, yy, t=th: r.erp >= t
            m, mc = run(f, y, fn, lo, hi)
            m2, _ = run(f, y, fn, lo, hi, sell="PE≥90")
            rows.append({"th": th, "cagr": m["cagr"], "mdd": m["max_dd"],
                         "ntr": m["ntr"], "tim": m["tim"],
                         "mc": round(float(np.mean(list(mc["win"].values()))), 1),
                         "cagr90": m2["cagr"], "mdd90": m2["max_dd"],
                         "ntr90": m2["ntr"]})
        res["erp_sweep"][f"{y}y"] = rows

    # ---------- 2. 组合规则 ----------
    combos = {
        "基线": lambda r, y: True,
        "ERP≥6.0": lambda r, y: r.erp >= 6.0,
        "ERP≥6.5": lambda r, y: r.erp >= 6.5,
        "ERP≥7.0": lambda r, y: r.erp >= 7.0,
        "PB分位≤20": lambda r, y: r[f"pb_pct{y}"] <= 0.20,
        "恐慌≥50": lambda r, y: r.fear_composite >= 50,
        "ERP≥6.5且PB分位≤20": lambda r, y: r.erp >= 6.5 and r[f"pb_pct{y}"] <= 0.20,
        "ERP≥6.5且恐慌≥50": lambda r, y: r.erp >= 6.5 and r.fear_composite >= 50,
        "ERP≥6.5或EPS>0": lambda r, y: r.erp >= 6.5 or r.eps_growth12 > 0,
        "ERP≥6.5或PB分位≤20": lambda r, y: r.erp >= 6.5 or r[f"pb_pct{y}"] <= 0.20,
        "ERP≥6.5且回撤≤-20": lambda r, y: r.erp >= 6.5 and r.dd36 <= -0.20,
        "EPS>0或恐慌≥50": lambda r, y: r.eps_growth12 > 0 or r.fear_composite >= 50,
    }
    for y in WINDOWS:
        res["combos"][f"{y}y"] = {}
        for name, fn in combos.items():
            m80, mc = run(f, y, fn, lo, hi)
            m90, _ = run(f, y, fn, lo, hi, sell="PE≥90")
            res["combos"][f"{y}y"][name] = {
                "sell80": m80, "sell90": m90,
                "mc": round(float(np.mean(list(mc["win"].values()))), 1),
            }

    # ---------- 3. ERP 分段的前瞻收益（全部 PE≤20 信号，按月聚类） ----------
    close = f.index_close.values.astype(float)
    for y in WINDOWS:
        p = f[f"pe_pct{y}"].values.astype(float)
        bands = [(0, 5.5), (5.5, 6.0), (6.0, 6.5), (6.5, 7.0), (7.0, 99)]
        out = []
        for a, b in bands:
            vals, months = [], []
            for i in range(lo, len(f) - 13):
                if not (p[i] <= 0.20 and a <= f.erp.iloc[i] < b):
                    continue
                vals.append(float(close[i + 13] / close[i + 1] - 1) * 100)
                months.append(str(f.index[i]))
            out.append({"band": f"{a}~{b}", "n": len(vals),
                        "mean": round(float(np.mean(vals)), 2) if vals else None,
                        "median": round(float(np.median(vals)), 2) if vals else None,
                        "win": round(float(np.mean(np.array(vals) > 0)) * 100, 1) if vals else None,
                        "months": months})
        res["erp_bands"][f"{y}y"] = out

    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)

    for y in WINDOWS:
        print(f"===== {y}y ERP 阈值（卖80 / 卖90）=====")
        for r in res["erp_sweep"][f"{y}y"]:
            print(f"  ERP≥{r['th']:<4} 卖80: {r['cagr']:>5.2f}% / {r['mdd']:>6.1f}% / {r['ntr']}笔 "
                  f"MC{r['mc']:>5.1f}   卖90: {r['cagr90']:>5.2f}% / {r['mdd90']:>6.1f}% / {r['ntr90']}笔")
        print(f"===== {y}y 组合（卖80 / 卖90）=====")
        for k, v in res["combos"][f"{y}y"].items():
            a, b = v["sell80"], v["sell90"]
            print(f"  {k:<22} 卖80 {a['cagr']:>5.2f}%/{a['max_dd']:>6.1f}%/{a['ntr']}笔 MC{v['mc']:>5.1f}"
                  f"   卖90 {b['cagr']:>5.2f}%/{b['max_dd']:>6.1f}%/{b['ntr']}笔")
        print(f"===== {y}y ERP 分段前瞻12月 =====")
        for r in res["erp_bands"][f"{y}y"]:
            print(f"  ERP {r['band']:<9} n={r['n']:<3} 均值 {r['mean']} 中位 {r['median']} 胜率 {r['win']}")
        print()


if __name__ == "__main__":
    main()
