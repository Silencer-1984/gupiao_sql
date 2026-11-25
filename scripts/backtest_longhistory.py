# -*- coding: utf-8 -*-
"""把 2019+ 得出的择时策略放到全历史做随机检验，检验高胜率是否稳健。

数据：沪深300 PE/PB 月频 2005-04 ~ 2026-11（260 月）；10 年国债 2002+；恐慌度 2015+。
样本：
  FULL  2010-06 ~ 2026-11（5 年分位需要 60 月回溯，故从 2010 起）
  P2015 2015-01 ~ 2026-11（恐慌度可用）
  P2019 2019-01 ~ 2026-11（原研究样本，作为对照）
策略：
  B3/B5 基线：PE 分位<=20 买、>=80 卖
  E3/E5 加 ERP>=6.5pp
  P3/P5 加 ERP 分位>=80%（滚动 60 月，解决利率中枢变化问题）
  F3/F5 加 ERP>=6.5pp 且 恐慌度>=50（仅 P2015/P2019）
评价：随机起点 × 随机持有期(12/24/36/60月) vs 同期买入持有；滚动 60 月窗口胜率；全区间指标。
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from factor_timing_data import load_factor_panel, rolling_pct as rp
from backtest_pe_pct_2019 import apply_pos, perf, trades

OUT = os.path.join(ROOT, "data", "longhistory_validation.json")
SEED = 20261123
N_SIM = 3000
HORIZONS = [12, 24, 36, 60]
SAMPLES = {"FULL": "2010-06", "P2015": "2015-01", "P2019": "2019-01"}


def build_factors():
    f = load_factor_panel()
    f["pe_pct3"] = rp(f.pe, 36)
    f["pe_pct5"] = rp(f.pe, 60)
    f["erp_pct5"] = rp(f.erp, 60)
    return f


RULES = {
    "B3": lambda r: r.pe_pct3 <= 0.20,
    "B5": lambda r: r.pe_pct5 <= 0.20,
    "E3": lambda r: r.pe_pct3 <= 0.20 and r.erp >= 6.5,
    "E5": lambda r: r.pe_pct5 <= 0.20 and r.erp >= 6.5,
    "P3": lambda r: r.pe_pct3 <= 0.20 and r.erp_pct5 >= 0.80,
    "P5": lambda r: r.pe_pct5 <= 0.20 and r.erp_pct5 >= 0.80,
    "F3": lambda r: r.pe_pct3 <= 0.20 and r.erp >= 6.5 and r.fear_composite >= 50,
    "F5": lambda r: r.pe_pct5 <= 0.20 and r.erp >= 6.5 and r.fear_composite >= 50,
}


def rule_positions(f, y, buy_fn, lo, hi):
    p = f[f"pe_pct{y}"].values.astype(float)
    pos = np.zeros(len(f))
    s = 0.0
    for i in range(lo, hi + 1):
        if s == 0.0:
            if p[i] <= 0.20 and buy_fn(f.iloc[i]):
                s = 1.0
        elif p[i] >= 0.80:
            s = 0.0
        pos[i] = s
    return pos


def pos_matrix(f, y, buy_fn, lo, hi):
    pm = np.full((hi + 1, hi + 1), np.nan)
    p = f[f"pe_pct{y}"].values.astype(float)
    rows = [f.iloc[i] for i in range(hi + 1)]
    for a in range(lo, hi + 1):
        s = 0.0
        for i in range(a, hi + 1):
            if s == 0.0:
                if p[i] <= 0.20 and buy_fn(rows[i]):
                    s = 1.0
            elif p[i] >= 0.80:
                s = 0.0
            pm[a, i] = s
    return pm


def metrics(f, pos, lo, hi):
    close = f.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])
    r = apply_pos(pos[lo:hi + 1], ret[lo:hi + 1])
    m = perf(r)
    tst, segs = trades(pos[lo:hi + 1], ret[lo:hi + 1])
    m.update({"tim": round(float(pos[lo:hi + 1].mean()) * 100, 1),
              "ntr": tst["n"], "avg_trade": tst["avg"],
              "log": [{"in": str(f.index[lo + a]), "out": str(f.index[min(lo + b + 1, hi)]),
                       "months": L, "ret": round(float(np.prod(1 + np.nan_to_num(
                           ret[lo + a:lo + b + 1])) - 1) * 100, 2)} for a, b, L in segs]})
    return m


def mc(f, pm, ret, lo, hi, seed, n=N_SIM, horizons=HORIZONS):
    rng = np.random.default_rng(seed)
    win = {h: 0 for h in horizons}
    cnt = {h: 0 for h in horizons}
    delta = {h: [] for h in horizons}
    for _ in range(n):
        h = int(rng.choice(horizons))
        a = int(rng.integers(lo, hi - h + 1))
        b = min(a + h, hi)
        rs = apply_pos(pm[a, a:b + 1], ret[a:b + 1])
        s = float(np.prod(1 + rs))
        bh = float(np.prod(1 + np.nan_to_num(ret[a:b + 1])))
        win[h] += int(s > bh); cnt[h] += 1
        delta[h].append((s - bh) * 100)
    return {
        "win": {f"{h}m": round(win[h] / cnt[h] * 100, 1) for h in horizons},
        "all": round(sum(win.values()) / sum(cnt.values()) * 100, 1),
        "delta_pp": {f"{h}m": round(float(np.mean(delta[h])), 2) for h in horizons},
    }


def rolling_windows(f, pm, ret, lo, hi, win=60, step=6):
    out = []
    for a in range(lo, hi - win + 1, step):
        b = a + win
        s = float(np.prod(1 + apply_pos(pm[a, a:b + 1], ret[a:b + 1])))
        bh = float(np.prod(1 + np.nan_to_num(ret[a:b + 1])))
        out.append({"from": str(f.index[a]), "to": str(f.index[b]),
                    "strat": round((s - 1) * 100, 1), "bh": round((bh - 1) * 100, 1),
                    "win": bool(s > bh)})
    return out


def main():
    f = build_factors()
    ym = f.index.values.astype(str)
    close = f.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])
    res = {"meta": {"period_all": f"{ym[0]}~{ym[-1]}", "n_months": len(f),
                    "samples": SAMPLES, "n_sim": N_SIM, "seed": SEED,
                    "horizons": HORIZONS, "tc": 0.0005,
                    "note": "ERP=100/PE-TTM−10年国债；ERP分位为60月滚动；恐慌度2015前无数据"},
           "samples": {}, "curves": {}}
    for sname, sstart in SAMPLES.items():
        lo = int(np.searchsorted(ym, sstart)); hi = len(f) - 1
        block = {"from": sstart, "to": str(f.index[hi]), "months": hi - lo + 1,
                 "bh": perf(np.nan_to_num(ret[lo:hi + 1])), "rules": {}}
        if sname == "FULL":
            res["curves"]["ym"] = [str(x) for x in f.index[lo:hi + 1]]
            res["curves"]["bh"] = [round(float(x), 4) for x in np.cumprod(1 + np.nan_to_num(ret[lo:hi + 1]))]
        for key, fn in RULES.items():
            if key[0] == "F" and sname == "FULL":
                continue  # 恐慌度在 2015 前缺失
            y = int(key[1])
            pos = rule_positions(f, y, fn, lo, hi)
            pm = pos_matrix(f, y, fn, lo, hi)
            rw = rolling_windows(f, pm, ret, lo, hi)
            if sname == "FULL" and key in ("B5", "E5", "E3"):
                res["curves"][key] = [round(float(x), 4) for x in np.cumprod(1 + apply_pos(
                    pos[lo:hi + 1], ret[lo:hi + 1]))]
            block["rules"][key] = {
                "metrics": metrics(f, pos, lo, hi),
                "mc": mc(f, pm, ret, lo, hi, SEED + sum(ord(c) for c in key + sname)),
                "rolling60": rw,
                "subperiods": {
                    name: {
                        "mc": mc(f, pm, ret, a, b, SEED + sum(ord(c) for c in key + sname + name),
                                 n=800, horizons=[12, 24] if b - a < 60 else HORIZONS),
                        "metrics": metrics(f, pos, a, b),
                        "bh": perf(np.nan_to_num(ret[a:b + 1])),
                    }
                    for name, a, b in [("2010-2014", max(lo, int(np.searchsorted(ym, "2010-01"))),
                                        int(np.searchsorted(ym, "2014-12"))),
                                       ("2015-2018", max(lo, int(np.searchsorted(ym, "2015-01"))),
                                        int(np.searchsorted(ym, "2018-12"))),
                                       ("2019-2022", max(lo, int(np.searchsorted(ym, "2019-01"))),
                                        int(np.searchsorted(ym, "2022-12"))),
                                       ("2023-2026", max(lo, int(np.searchsorted(ym, "2023-01"))),
                                        hi)]
                    if b - a >= 26 and a >= lo and b <= hi
                },
            }
        res["samples"][sname] = block

    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)

    for sname, block in res["samples"].items():
        print(f"===== {sname}  {block['from']}~{block['to']}  {block['months']}月  "
              f"基准年化 {block['bh']['cagr']}% =====")
        print(f"{'策略':<5} {'年化':>7} {'回撤':>7} {'笔':>3} {'持仓':>6} {'MC总':>6} "
              f"{'12m':>6} {'24m':>6} {'36m':>6} {'60m':>6} {'滚动60胜':>9}")
        for key, v in block["rules"].items():
            m, mc_ = v["metrics"], v["mc"]
            rw = v["rolling60"]
            rw_win = round(sum(x["win"] for x in rw) / len(rw) * 100, 1) if rw else 0
            print(f"{key:<5} {m['cagr']:>7.2f} {m['max_dd']:>7.1f} {m['ntr']:>3} "
                  f"{m['tim']:>6.1f} {mc_['all']:>6.1f} {mc_['win']['12m']:>6.1f} "
                  f"{mc_['win']['24m']:>6.1f} {mc_['win']['36m']:>6.1f} "
                  f"{mc_['win']['60m']:>6.1f} {rw_win:>9.1f}")
        print()


if __name__ == "__main__":
    main()
