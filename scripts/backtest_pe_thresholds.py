# -*- coding: utf-8 -*-
"""
沪深300 PE 分位阈值优化 + 牛熊偏移检验（2019 年后样本）

1) 以 3 年 / 5 年 PE 分位为尺，网格搜索买/卖阈值，检验 20/80 是否过保守
2) 候选阈值随机测试（随机起点 + 随机持有期），验证「最大年化」是否稳健
3) 牛熊状态划分（事前可得：12 月均线 + 距历史峰值回撤），检验策略偏移
     - 上行/下行捕获率
     - 牛市参与率、熊市暴露率
     - 每段牛熊的前 3 个月参与率 vs 后期参与率
"""
import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from backtest_pe_pct_2019 import (load_monthly, rolling_pct, positions, apply_pos,
                                  perf, trades, q)

DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "data", "pe_threshold_regime.json")
OUT_CSV = os.path.join(ROOT, "data", "pe_threshold_samples.csv")
START = "2019-01"
SEED = 20261123
N_SIM = 1500
HORIZONS = [12, 24, 36, 60]
WINDOWS = {3: 36, 5: 60}
BUYS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
SELLS = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


def regime(close):
    """事前牛熊划分：36 月滚动峰值算回撤。
    close>MA12 且回撤>-15% = 牛市；回撤<=-20% = 熊市；其余震荡。
    """
    s = pd.Series(close)
    ma = s.rolling(12, min_periods=12).mean()
    peak = s.rolling(36, min_periods=12).max()
    dd = s / peak - 1
    reg = np.where(dd <= -0.20, "熊市", np.where((s > ma) & (dd > -0.15), "牛市", "震荡"))
    return reg, dd.values, ma.values


def main():
    m = load_monthly()
    ym = m.ym.astype(str).values
    pe = m.pe_ttm.values.astype(float)
    close = m.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])
    lo = int(np.searchsorted(ym, START))
    hi = len(m) - 1
    years = (hi - lo) / 12

    pcts = {y: rolling_pct(pe, w) for y, w in WINDOWS.items()}
    reg_all, dd_all, ma_all = regime(close)
    reg = reg_all[lo:hi]
    ym_eval = ym[lo:hi]
    bh = np.nan_to_num(ret[lo:hi])
    n = len(bh)

    res = {"meta": {
        "period": f"{ym[lo]}~{ym[hi]}", "months": n, "years": round(years, 1),
        "source": "val_index_pe_lg 沪深300 PE-TTM(加权)", "tc": 0.0005,
        "seed": SEED, "n_sim_per_cell": N_SIM,
        "regime_rule": "事前划分：36月滚动峰值算回撤；收盘>12月均线且回撤>-15% = 牛市；回撤<=-20% = 熊市；其余震荡",
    }, "grid": {}, "candidates": {}, "curves": {}, "mc": {},
        "regime": {}, "capture": {}, "episodes": {}}

    # ---------- 1. 阈值网格 ----------
    for y in WINDOWS:
        p = pcts[y][lo:hi]
        mat = {}
        flat = []
        for b in BUYS:
            col = {}
            for s in SELLS:
                if s - b < 0.20:
                    col[f"{int(s*100)}"] = None
                    continue
                pos = positions(p, b, s)
                pf = perf(apply_pos(pos, ret[lo:hi]))
                tst, _ = trades(pos, ret[lo:hi])
                cell = {"cagr": pf["cagr"], "mdd": pf["max_dd"], "sharpe": pf["sharpe"],
                        "calmar": pf["calmar"], "tim": round(float(pos.mean()) * 100, 1),
                        "ntr": tst["n"], "avg_trade": tst["avg"]}
                col[f"{int(s*100)}"] = cell
                flat.append((pf["cagr"], b, s, cell))
            mat[f"{int(b*100)}"] = col
        res["grid"][f"{y}y"] = {"matrix": mat,
                                "top10": [{"buy": round(b*100), "sell": round(s*100), **c}
                                          for _, b, s, c in sorted(flat, reverse=True)[:10]]}

    # ---------- 2. 候选阈值 ----------
    cands = [(0.20, 0.80), (0.25, 0.75), (0.30, 0.70), (0.35, 0.65)]
    for y in WINDOWS:
        top = res["grid"][f"{y}y"]["top10"][0]
        tcand = (top["buy"] / 100, top["sell"] / 100)
        if tcand not in cands:
            cands.append(tcand)
    cands = list(dict.fromkeys(cands))
    res["meta"]["candidates"] = [f"{int(b*100)}/{int(s*100)}" for b, s in cands]

    for y in WINDOWS:
        p = pcts[y][lo:hi]
        res["candidates"][f"{y}y"] = {}
        for b, s in cands:
            key = f"{int(b*100)}/{int(s*100)}"
            pos = positions(p, b, s)
            r = apply_pos(pos, ret[lo:hi])
            tst, segs = trades(pos, ret[lo:hi])
            pf = perf(r)
            res["candidates"][f"{y}y"][key] = {
                **pf, "tim": round(float(pos.mean()) * 100, 1),
                "ntr": tst["n"], "trades_per_year": round(tst["n"] / years, 2),
                "avg_hold_m": round(n * pos.mean() / tst["n"], 1) if tst["n"] else 0,
                "avg_trade": tst["avg"], "win_trade": tst["win"],
                "log": [{"in": ym[lo + a], "out": ym[min(lo + b + 1, hi)],
                         "months": L, "ret": round(float(np.prod(1 + np.nan_to_num(ret[lo + a:lo + b + 1])) - 1) * 100, 2)}
                        for a, b, L in segs],
            }

    # 净值曲线（全样本，含起点1）
    res["curves"] = {"ym": [ym[i] for i in range(lo, hi + 1)],
                     "bh": [1.0] + list(np.cumprod(1 + bh))}
    for key in res["meta"]["candidates"]:
        for y in WINDOWS:
            b, s = (int(x) / 100 for x in key.split("/"))
            pos = positions(pcts[y][lo:hi], b, s)
            eq = np.concatenate([[1.0], np.cumprod(1 + apply_pos(pos, ret[lo:hi]))])
            res["curves"][f"{y}y_{key}"] = eq
            res["curves"][f"{y}y_{key}_pos"] = np.concatenate([[0], pos])
    res["curves"] = {k: ([round(float(x), 4) for x in v] if k != "ym" else list(v))
                     for k, v in res["curves"].items()}

    # ---------- 3. 随机测试 ----------
    rng = np.random.default_rng(SEED)
    rows = []
    for y in WINDOWS:
        p = pcts[y]
        for b, s in cands:
            key = f"{int(b*100)}/{int(s*100)}"
            for H in HORIZONS:
                for _ in range(N_SIM):
                    st = int(rng.integers(lo, hi - H + 1))
                    en = st + H
                    pp = positions(p[st:en], b, s)
                    rr = apply_pos(pp, ret[st:en])
                    bb = np.nan_to_num(ret[st:en])
                    f = lambda x: (np.prod(1 + x) ** (12 / H) - 1) * 100
                    rows.append({"win": f"{y}y", "th": key, "H": H,
                                 "start": ym[st], "ret": f(rr), "bh": f(bb),
                                 "tim": float(pp.mean()) * 100,
                                 "ntr": int(np.abs(np.diff(np.concatenate([[0], pp]))).sum())})
    sdf = pd.DataFrame(rows)
    sdf.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    for (y, th), g in sdf.groupby(["win", "th"]):
        res["mc"][f"{y}_{th}"] = {
            "n": int(len(g)), "ret": q(g.ret), "bh": q(g.bh),
            "win": round(float((g.ret > g.bh).mean()) * 100, 1),
            "exc": round(float((g.ret - g.bh).median()), 2),
            "tim": round(float(g.tim.mean()), 1),
            "no_trade": round(float((g.ntr == 0).mean()) * 100, 1),
        }
    for (y, th, H), g in sdf.groupby(["win", "th", "H"]):
        res["mc"][f"{y}_{th}_{H}m"] = {
            "ret_med": round(float(g.ret.median()), 2),
            "bh_med": round(float(g.bh.median()), 2),
            "win": round(float((g.ret > g.bh).mean()) * 100, 1),
            "tim": round(float(g.tim.mean()), 1),
            "no_trade": round(float((g.ntr == 0).mean()) * 100, 1),
        }

    # ---------- 4. 牛熊偏移 ----------
    for y in WINDOWS:
        for b, s in cands:
            key = f"{int(b*100)}/{int(s*100)}"
            pos = positions(pcts[y][lo:hi], b, s)
            r = apply_pos(pos, ret[lo:hi])
            rr = {}
            for rg in ["牛市", "震荡", "熊市"]:
                mm = reg == rg
                if mm.sum() < 3:
                    continue
                rr[rg] = {
                    "months": int(mm.sum()),
                    "tim": round(float(pos[mm].mean()) * 100, 1),
                    "strat_m": round(float(r[mm].mean()) * 100, 2),
                    "bh_m": round(float(bh[mm].mean()) * 100, 2),
                    "strat_tot": round(float((np.prod(1 + r[mm]) - 1) * 100), 1),
                    "bh_tot": round(float((np.prod(1 + bh[mm]) - 1) * 100), 1),
                }
            up = bh > 0
            dn = bh < 0
            rr["up_capture"] = round(float(r[up].mean() / bh[up].mean()), 3)
            rr["down_capture"] = round(float(r[dn].mean() / bh[dn].mean()), 3)
            rr["up_participation"] = round(float(pos[up].mean()) * 100, 1)
            rr["down_participation"] = round(float(pos[dn].mean()) * 100, 1)
            res["capture"][f"{y}y_{key}"] = rr

    # ---------- 5. 牛熊段落：策略是否迟到/早退 ----------
    # 段落用 20/80 与 25/75 两个代表阈值
    for key in ["20/80", "25/75"]:
        b, s = (int(x) / 100 for x in key.split("/"))
        for y in WINDOWS:
            pos = positions(pcts[y][lo:hi], b, s)
            eps = []
            i = 0
            while i < n:
                j = i
                while j + 1 < n and reg[j + 1] == reg[i]:
                    j += 1
                L = j - i + 1
                if L >= 3 and reg[i] in ("牛市", "熊市"):
                    eps.append({
                        "type": reg[i], "from": ym_eval[i], "to": ym_eval[min(j + 1, n - 1)], "months": L,
                        "bh": round(float((np.prod(1 + bh[i:j+1]) - 1) * 100), 1),
                        "strat": round(float((np.prod(1 + apply_pos(pos[i:j+1], ret[lo+i:lo+j+1])) - 1) * 100), 1),
                        "tim_first3": round(float(pos[i:min(i+3, j+1)].mean()) * 100, 1),
                        "tim_rest": round(float(pos[min(i+3, j+1):j+1].mean()) * 100, 1) if L > 3 else None,
                        "tim_all": round(float(pos[i:j+1].mean()) * 100, 1),
                    })
                i = j + 1
            res["episodes"][f"{y}y_{key}"] = eps

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)

    # ---- 打印 ----
    print(f"区间 {res['meta']['period']} ({n}月 / {years:.1f}年)\n")
    for y in WINDOWS:
        g = res["grid"][f"{y}y"]
        print(f"【{y}年PE 阈值网格 — 年化%】  买\\卖 " + " ".join(f"{x:>6}" for x in SELLS))
        for b in BUYS:
            vals = [f"{g['matrix'][str(int(b*100))][str(int(s*100))]['cagr']:>6.2f}"
                    if g['matrix'][str(int(b*100))][str(int(s*100))] else "     -" for s in SELLS]
            print(f"   {int(b*100):>3}% " + " ".join(vals))
        print("  Top5:", [(f"{x['buy']}/{x['sell']}", x['cagr'], x['ntr']) for x in g['top10'][:5]])
        print("  候选 (年化/笔数/持仓):", {k: (v['cagr'], v['ntr'], v['tim']) for k, v in res["candidates"][f"{y}y"].items()})
        for k, v in res["candidates"][f"{y}y"].items():
            print(f"    {k}: ", [(x['in'], x['out'], x['months'], x['ret']) for x in v['log']])
        print()

    print("【随机测试（跨持有期）】")
    for k, v in res["mc"].items():
        if len(k.split("_")) == 2:
            print(f"  {k:>16} 中位 {v['ret']['median']:>6.2f}%  基准 {v['bh']['median']:>6.2f}%  "
                  f"胜率 {v['win']:>5.1f}%  超额中位 {v['exc']:>+6.2f}pp  持仓 {v['tim']:>5.1f}%  零交易 {v['no_trade']:>5.1f}%")

    print("\n【牛熊偏移 & 捕获率】")
    for k, v in res["capture"].items():
        print(f"  {k:>14} 上行捕获 {v['up_capture']:>5.2f} 下行捕获 {v['down_capture']:>5.2f} "
              f"| 牛市持仓 {v.get('牛市',{}).get('tim',0):>5.1f}% 熊市持仓 {v.get('熊市',{}).get('tim',0):>5.1f}% "
              f"| 牛市策略 {v.get('牛市',{}).get('strat_m',0):>+6.2f}%/月 基准 {v.get('牛市',{}).get('bh_m',0):>+6.2f}%/月")

    print("\n【代表性牛熊段落（5年PE，20/80 vs 25/75）】")
    for e in res["episodes"]["5y_20/80"]:
        print(f"  {e['type']} {e['from']}~{e['to']} {e['months']:>2}月 基准{e['bh']:>+6.1f}% "
              f"20/80:{e['strat']:>+6.1f}% (前3月持仓{e['tim_first3']:>5.1f}% 后期{e['tim_rest']})")
    print(f"\n输出 {OUT}\n     {OUT_CSV}")


if __name__ == "__main__":
    main()
