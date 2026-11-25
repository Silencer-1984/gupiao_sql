# -*- coding: utf-8 -*-
"""PE 分位择时的多因子修正检验（2019 年后样本）

基线：3y/5y PE 分位 <=20% 买、>=80% 卖，月末信号次月生效，单边 5bp。
修正：买入侧加额外条件（PB 分位/绝对值、隐含 EPS 增速、股息率、ERP、恐慌度、
      价格回撤、两融同比、M1 同比、拥挤度）；卖出侧测试 PB 联合确认。
评价：全区间策略指标 + 信号月前瞻 12/24 月收益 + 随机起点窗口胜率。
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from backtest_pe_pct_2019 import rolling_pct, positions, apply_pos, perf, trades, q
from factor_timing_data import load_factor_panel, rolling_pct as rp

START = "2019-01"
TC = 0.0005
SEED = 20261123
N_SIM = 1200
HORIZONS = [12, 24, 36, 60]
OUT = os.path.join(ROOT, "data", "factor_filters.json")
OUT_CSV = os.path.join(ROOT, "data", "factor_filters_signals.csv")

WINDOWS = {3: 36, 5: 60}
BUY_TH, SELL_TH = 0.20, 0.80


def build():
    f = load_factor_panel()
    f["pe_pct3"] = rp(f.pe, 36)
    f["pe_pct5"] = rp(f.pe, 60)
    f["pb_pct3"] = rp(f.pb, 36)
    f["pb_pct5"] = rp(f.pb, 60)
    f["div_pct5"] = rp(f.div_yield, 60)
    f["erp_pct5"] = rp(f.erp, 60)
    f["fear_pct5"] = rp(f.fear_composite, 60)
    f["congestion_pct5"] = rp(f.congestion, 60)
    # 拥挤度有缺口，向前填充（仅用历史值）
    for col in ["congestion", "congestion_pct5"]:
        f[col] = f[col].ffill()
    return f


# 条件函数：输入一行 DataFrame Series，返回 bool
FILTERS = {
    "基线(仅PE)": lambda r, y: True,
    "PB分位≤20": lambda r, y: r[f"pb_pct{y}"] <= 0.20,
    "PB≤1.30": lambda r, y: r.pb_abs <= 1.30,
    "PB≤1.40": lambda r, y: r.pb_abs <= 1.40,
    "隐含EPS增速>0": lambda r, y: r.eps_growth12 > 0,
    "隐含EPS增速>5%": lambda r, y: r.eps_growth12 > 0.05,
    "股息率前20%": lambda r, y: r.div_pct5 >= 0.80,
    "ERP≥6.5%": lambda r, y: r.erp >= 6.5,
    "恐慌度≥50": lambda r, y: r.fear_composite >= 50,
    "恐慌度≥70": lambda r, y: r.fear_composite >= 70,
    "价格回撤≤-20%": lambda r, y: r.dd36 <= -0.20,
    "价格回撤≤-25%": lambda r, y: r.dd36 <= -0.25,
    "两融同比≤0": lambda r, y: r.margin_yoy <= 0,
    "M1同比≥5%": lambda r, y: r.m1_yoy >= 5,
    "拥挤度≤40%分位": lambda r, y: r.congestion_pct5 <= 0.40,
    "PB分位≤20且EPS>0": lambda r, y: r[f"pb_pct{y}"] <= 0.20 and r.eps_growth12 > 0,
    "回撤≤-20且EPS>0": lambda r, y: r.dd36 <= -0.20 and r.eps_growth12 > 0,
    "ERP≥6且恐慌≥50": lambda r, y: r.erp >= 6 and r.fear_composite >= 50,
    "PB≤1.35且EPS>0": lambda r, y: r.pb_abs <= 1.35 and r.eps_growth12 > 0,
}

EXIT_RULES = {
    "基线 PE≥80": lambda r, y: r[f"pe_pct{y}"] >= 0.80,
    "PE≥80或PB≥80": lambda r, y: r[f"pe_pct{y}"] >= 0.80 or r[f"pb_pct{y}"] >= 0.80,
    "PE≥80且PB≥60": lambda r, y: r[f"pe_pct{y}"] >= 0.80 and r[f"pb_pct{y}"] >= 0.60,
    "PE≥90": lambda r, y: r[f"pe_pct{y}"] >= 0.90,
}


def positions_filtered(f, y, filt, exit_rule=None, ym_lo=None):
    """生成仓位：买入需 PE<=20 且附加条件成立；卖出按 exit_rule（默认 PE>=80）。"""
    p = f[f"pe_pct{y}"].values.astype(float)
    ym = f.index.values.astype(str)
    if ym_lo is None:
        ym_lo = START
    lo = int(np.searchsorted(ym, ym_lo))
    exit_fn = exit_rule or EXIT_RULES["基线 PE≥80"]
    pos = np.zeros(len(f))
    s = 0.0
    rows = [f.iloc[i] for i in range(len(f))]
    for i in range(lo, len(f)):
        r = rows[i]
        if s == 0.0:
            if p[i] <= BUY_TH and filt(r, y):
                s = 1.0
        else:
            if exit_fn(r, y):
                s = 0.0
        pos[i] = s
    return pos


def start_position_matrix(f, y, filt, lo, hi):
    """pm[a, i] = 从 a 月空仓起步时 i 月仓位，供 MC 快速切片。"""
    pm = np.full((hi + 1, hi + 1), np.nan)
    p = f[f"pe_pct{y}"].values.astype(float)
    rows = [f.iloc[i] for i in range(hi + 1)]
    exit_fn = EXIT_RULES["基线 PE≥80"]
    for a in range(lo, hi + 1):
        s = 0.0
        for i in range(a, hi + 1):
            r = rows[i]
            if s == 0.0:
                if p[i] <= BUY_TH and filt(r, y):
                    s = 1.0
            elif exit_fn(r, y):
                s = 0.0
            pm[a, i] = s
    return pm


def sim_metrics(f, y, pos, lo, hi):
    close = f.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])
    r = apply_pos(pos[lo:hi + 1], ret[lo:hi + 1])
    m = perf(r)
    tst, segs = trades(pos[lo:hi + 1], ret[lo:hi + 1])
    m.update({"tim": round(float(pos[lo:hi + 1].mean()) * 100, 1),
              "ntr": tst["n"], "avg_hold_m": round(tst["n"] and
              (hi - lo) * pos[lo:hi + 1].mean() / tst["n"], 1),
              "avg_trade": tst["avg"]})
    m["log"] = [{"in": str(f.index[lo + a]), "out": str(f.index[min(lo + b + 1, hi)]),
                 "months": L, "ret": round(float(np.prod(1 + np.nan_to_num(
                     ret[lo + a:lo + b + 1])) - 1) * 100, 2)} for a, b, L in segs]
    return m


def signal_analysis(f, y, filt):
    """信号月前瞻收益：信号在 t 月末，次月起持有，统计 t+1 -> t+1+H 的指数收益。"""
    ym = f.index.values.astype(str)
    lo = int(np.searchsorted(ym, START))
    close = f.index_close.values.astype(float)
    p = f[f"pe_pct{y}"].values.astype(float)
    out = []
    for i in range(lo, len(f)):
        if not (p[i] <= BUY_TH and filt(f.iloc[i], y)):
            continue
        def rnd(col, n=3):
            v = f[col].iloc[i]
            return round(float(v), n) if pd.notna(v) else None
        row = {"ym": ym[i], "pe_pct": round(float(p[i]) * 100, 1),
               "pb": rnd("pb"), "eps_growth12": rnd("eps_growth12"),
               "dd36": rnd("dd36"), "div_yield": rnd("div_yield"),
               "erp": rnd("erp"), "fear": rnd("fear_composite"),
               "margin_yoy": rnd("margin_yoy"), "m1_yoy": rnd("m1_yoy", 1)}
        for h in (12, 24):
            j = min(i + h + 1, len(f) - 1)
            row[f"fwd{h}m"] = round(float(close[j] / close[i + 1] - 1) * 100, 2) if j > i + 1 else None
        out.append(row)
    return out


def mc_test(f, y, filt, pm=None, lo=None, hi=None):
    """随机起点 + 随机持有期：策略 vs 同期买入持有。"""
    ym = f.index.values.astype(str)
    lo = int(np.searchsorted(ym, START)) if lo is None else lo
    hi = len(f) - 1 if hi is None else hi
    if pm is None:
        pm = start_position_matrix(f, y, filt, lo, hi)
    close = f.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])
    rng = np.random.default_rng(SEED)
    wins = {h: 0 for h in HORIZONS}
    n = {h: 0 for h in HORIZONS}
    deltas = {h: [] for h in HORIZONS}
    for _ in range(N_SIM):
        h = int(rng.choice(HORIZONS))
        a = int(rng.integers(lo, hi - h + 1))
        b = min(a + h, hi)
        pos = pm[a, a:b + 1]
        rs = apply_pos(pos, ret[a:b + 1])
        rb = np.nan_to_num(ret[a:b + 1])
        s = float(np.prod(1 + rs)); bh = float(np.prod(1 + rb))
        n[h] += 1
        wins[h] += int(s > bh)
        deltas[h].append(round((s - bh) * 100, 2))
    return {"win": {f"{h}m": round(wins[h] / n[h] * 100, 1) for h in HORIZONS},
            "avg_delta_pp": {f"{h}m": round(float(np.mean(deltas[h])), 2) for h in HORIZONS},
            "n": sum(n.values())}


def main():
    f = build()
    ym = f.index.values.astype(str)
    lo = int(np.searchsorted(ym, START))
    hi = len(f) - 1
    res = {"meta": {"period": f"{ym[lo]}~{ym[hi]}", "months": hi - lo,
                    "source": "val_index_pe_lg / val_index_pb_lg / val_a_dividend_yield / "
                              "macro_bond_yield / mkt_fear_daily / flow_margin_sse / "
                              "macro_money_supply / val_congestion_lg",
                    "rule": "PE分位<=20%买且附加条件成立；PE分位>=80%卖；月末信号次月生效；单边5bp",
                    "tc": TC, "seed": SEED, "n_sim_per_horizon": N_SIM,
                    "note": "无未来函数：M1同比滞后1月；因子取月末最后可得值；分位用当期及历史"},
           "baseline": {}, "entry": {}, "exit": {}, "signals": {}, "mc": {},
           "factor_values": {}, "curves": {}}

    bh_close = f.index_close.values.astype(float)
    bh_ret = np.concatenate([bh_close[1:] / bh_close[:-1] - 1, [np.nan]])[lo:hi + 1]
    res["baseline"]["买入持有"] = perf(bh_ret)
    res["curves"]["bh"] = [round(float(x), 4) for x in np.cumprod(1 + np.nan_to_num(bh_ret))]

    for y in WINDOWS:
        base_pos = positions_filtered(f, y, FILTERS["基线(仅PE)"])
        res["baseline"][f"{y}y_PE20/80"] = sim_metrics(f, y, base_pos, lo, hi)
        res["curves"][f"{y}y"] = [round(float(x), 4) for x in np.cumprod(1 + apply_pos(
            base_pos[lo:hi + 1], np.concatenate([bh_close[1:] / bh_close[:-1] - 1, [np.nan]])[lo:hi + 1]))]

    # 因子在关键买点的取值（用于报告）
    for k in ["pb_abs", "pb_pct3", "pb_pct5", "eps_growth12", "div_yield", "erp",
              "fear_composite", "dd36", "margin_yoy", "m1_yoy", "congestion_pct5"]:
        res["factor_values"][k] = [{"ym": str(f.index[i]), "v": round(float(f[k].iloc[i]), 4)
                                    if pd.notna(f[k].iloc[i]) else None}
                                   for i in range(lo, hi + 1)]

    for y in WINDOWS:
        res["entry"][f"{y}y"] = {}
        res["signals"][f"{y}y"] = {}
        res["mc"][f"{y}y"] = {}
        for name, fn in FILTERS.items():
            pos = positions_filtered(f, y, fn)
            m = sim_metrics(f, y, pos, lo, hi)
            sig = signal_analysis(f, y, fn)
            fwd12 = [r["fwd12m"] for r in sig if r["fwd12m"] is not None]
            fwd24 = [r["fwd24m"] for r in sig if r["fwd24m"] is not None]
            res["entry"][f"{y}y"][name] = m
            res["signals"][f"{y}y"][name] = {
                "n_signal": len(sig),
                "fwd12_mean": round(float(np.mean(fwd12)), 2) if fwd12 else None,
                "fwd12_median": round(float(np.median(fwd12)), 2) if fwd12 else None,
                "fwd12_win": round(float(np.mean(np.array(fwd12) > 0)) * 100, 1) if fwd12 else None,
                "fwd24_mean": round(float(np.mean(fwd24)), 2) if fwd24 else None,
                "fwd24_win": round(float(np.mean(np.array(fwd24) > 0)) * 100, 1) if fwd24 else None,
                "list": sig,
            }
            res["mc"][f"{y}y"][name] = mc_test(f, y, fn,
                pm=start_position_matrix(f, y, fn, lo, hi), lo=lo, hi=hi)

    # 卖出侧修正（仅基线买入）
    for y in WINDOWS:
        res["exit"][f"{y}y"] = {}
        for name, fn in EXIT_RULES.items():
            pos = positions_filtered(f, y, FILTERS["基线(仅PE)"], exit_rule=fn)
            res["exit"][f"{y}y"][name] = sim_metrics(f, y, pos, lo, hi)

    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)
    rows = []
    for y in WINDOWS:
        for name, v in res["signals"][f"{y}y"].items():
            for r in v["list"]:
                rows.append({"window": f"{y}y", "filter": name, **r})
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    for y in WINDOWS:
        print(f"===== {y}y 买入侧因子 =====")
        print(f"{'条件':<20} {'年化':>7} {'回撤':>7} {'笔':>3} {'持仓%':>6} {'信号':>4} {'12月均':>7} {'胜率':>6} {'MC胜':>6}")
        for name in FILTERS:
            e = res["entry"][f"{y}y"][name]
            s = res["signals"][f"{y}y"][name]
            mc = res["mc"][f"{y}y"][name]
            allwin = round(float(np.mean([mc["win"][h] for h in mc["win"]])), 1)
            print(f"{name:<20} {e['cagr']:>7.2f} {e['max_dd']:>7.1f} {e['ntr']:>3} "
                  f"{e['tim']:>6.1f} {s['n_signal']:>4} {str(s['fwd12_mean']):>7} "
                  f"{str(s['fwd12_win']):>6} {allwin:>6.1f}")
        print(f"---- {y}y 卖出侧 ----")
        for name, v in res["exit"][f"{y}y"].items():
            print(f"  {name:<18} 年化 {v['cagr']:>6.2f}  回撤 {v['max_dd']:>6.1f}  笔 {v['ntr']}  持仓 {v['tim']}%")


if __name__ == "__main__":
    main()
