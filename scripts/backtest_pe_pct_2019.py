# -*- coding: utf-8 -*-
"""
沪深300 PE 分位择时（2019 年之后样本）——1/3/5/10 年四个回顾窗口对比。

测试区间：2019-01 ~ 2026-11（不含 2019 年以前样本）
回溯窗口：1/3/5/10 年 PE 分位，仅用当期及以前数据（含 2019 前历史，但只作分母，不计收益）

规则：
  - 分位 <= 20% 买入满仓
  - 分位 >= 80% 卖出空仓
  - 20~80% 维持原仓位；始终未触发买入则一直空仓

随机测试：
  - 随机起点（2019-01 起）+ 随机持有期 12/24/36/60 月
  - 规则从起点空仓起步，与同窗口买入持有对比
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT_JSON = os.path.join(ROOT, "data", "pe_pct_2019.json")
OUT_CSV = os.path.join(ROOT, "data", "pe_pct_2019_samples.csv")

WINDOWS = {1: 12, 3: 36, 5: 60, 10: 120}
BUY_TH, SELL_TH = 0.20, 0.80
TC = 0.0005
SEED = 20261123
N_PER_CELL = 1500
HORIZONS = [12, 24, 36, 60]
START = "2019-01"


def load_monthly():
    c = sqlite3.connect(DB)
    df = pd.read_sql(
        "select trade_date, index_close, pe_ttm from val_index_pe_lg "
        "where index_name='沪深300' order by trade_date", c, parse_dates=["trade_date"])
    c.close()
    df = df.dropna(subset=["index_close", "pe_ttm"]).reset_index(drop=True)
    df["ym"] = df.trade_date.dt.to_period("M")
    return df.groupby("ym", as_index=False).last().sort_values("ym").reset_index(drop=True)


def rolling_pct(pe, win):
    n = len(pe)
    out = np.full(n, np.nan)
    for t in range(win - 1, n):
        w = pe[t - win + 1: t + 1]
        out[t] = float((w <= pe[t]).mean())
    return out


def positions(pct, buy=BUY_TH, sell=SELL_TH):
    pos = np.zeros(len(pct))
    s = 0.0
    for i in range(len(pct)):
        if not np.isnan(pct[i]):
            if pct[i] <= buy:
                s = 1.0
            elif pct[i] >= sell:
                s = 0.0
        pos[i] = s
    return pos


def apply_pos(pos, ret, tc=TC):
    ret = np.nan_to_num(ret, nan=0.0)
    prev = np.concatenate([[0.0], pos[:-1]])
    return pos * ret - np.abs(pos - prev) * tc


def perf(r):
    r = np.asarray(r, float)
    if len(r) < 2:
        return {}
    eq = np.cumprod(1 + r)
    yrs = len(r) / 12
    cagr = eq[-1] ** (1 / yrs) - 1
    vol = r.std(ddof=1) * np.sqrt(12)
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    return {
        "total_ret": round(float(eq[-1] - 1) * 100, 1),
        "cagr": round(float(cagr) * 100, 2),
        "vol": round(float(vol) * 100, 2),
        "max_dd": round(dd * 100, 1),
        "sharpe": round(float(cagr / vol), 2) if vol > 0 else None,
        "calmar": round(float(cagr / abs(dd)), 2) if dd else None,
    }


def trades(pos, ret):
    n, i, segs, dates = len(pos), 0, [], []
    while i < n:
        if pos[i] == 1 and (i == 0 or pos[i - 1] == 0):
            j = i
            while j + 1 < n and pos[j + 1] == 1:
                j += 1
            segs.append(float(np.prod(1 + np.nan_to_num(ret[i:j + 1])) - 1) * 100)
            dates.append((i, j, j - i + 1))
            i = j + 1
        else:
            i += 1
    if not segs:
        return {"n": 0, "avg": None, "win": None, "best": None, "worst": None}, []
    a = np.array(segs)
    return ({"n": len(segs), "avg": round(float(a.mean()), 2),
             "median": round(float(np.median(a)), 2),
             "win": round(float((a > 0).mean()) * 100, 1),
             "best": round(float(a.max()), 2), "worst": round(float(a.min()), 2)}, dates)


def q(s):
    return {"n": int(len(s)), "mean": round(float(s.mean()), 2),
            "median": round(float(s.median()), 2),
            "p05": round(float(s.quantile(0.05)), 2), "p25": round(float(s.quantile(0.25)), 2),
            "p75": round(float(s.quantile(0.75)), 2), "p95": round(float(s.quantile(0.95)), 2),
            "std": round(float(s.std()), 2)}


def main():
    m = load_monthly()
    ym = m.ym.astype(str).values
    pe = m.pe_ttm.values.astype(float)
    close = m.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])

    lo = int(np.searchsorted(ym, START))
    hi = len(m) - 1                      # 最后可计收益的月份下标
    pcts = {y: rolling_pct(pe, w) for y, w in WINDOWS.items()}
    for y, p in pcts.items():
        assert not np.isnan(p[lo]), f"{y}y 分位在 {ym[lo]} 缺失"

    res = {
        "meta": {
            "index": "沪深300", "pe": "PE-TTM 加权（val_index_pe_lg）",
            "period": f"{ym[lo]}~{ym[hi]}", "months": int(hi - lo),
            "buy_th": BUY_TH, "sell_th": SELL_TH, "tc": TC, "seed": SEED,
            "n_per_cell": N_PER_CELL, "horizons": HORIZONS,
            "rebalance": "月末信号、次月生效（close_t 出信号 -> t+1 月收益）",
        },
        "full_period": {}, "curves": {}, "mc": {}, "grid": {}, "exposure_year": {},
    }

    # ---------- 1. 2019 后全区间 ----------
    res["full_period"]["buy_and_hold"] = {**perf(ret[lo:hi]), "tim": 100.0}
    curve = {"ym": [ym[i] for i in range(lo, hi + 1)],
             "bh": [], "pe": [round(float(pe[i]), 2) for i in range(lo, hi + 1)]}
    eq_bh = np.concatenate([[1.0], np.cumprod(1 + np.nan_to_num(ret[lo:hi]))])
    curve["bh"] = [round(float(x), 4) for x in eq_bh]

    for y in WINDOWS:
        p = pcts[y]
        pos = positions(p[lo:hi])
        r = apply_pos(pos, ret[lo:hi])
        tstat, segs = trades(pos, ret[lo:hi])
        res["full_period"][f"{y}y"] = {
            **perf(r), "tim": round(float(pos.mean()) * 100, 1),
            "n_switch": int(np.abs(np.diff(np.concatenate([[0], pos]))).sum()),
            "trades": tstat,
            "trade_log": [{"from": ym[lo + a], "to": ym[min(lo + b + 1, hi)], "months": l,
                           "ret": round(float(np.prod(1 + np.nan_to_num(ret[lo + a:lo + b + 1])) - 1) * 100, 2)}
                          for a, b, l in segs],
            "pct_min": round(float(np.nanmin(p[lo:hi])) * 100, 1),
            "pct_max": round(float(np.nanmax(p[lo:hi])) * 100, 1),
            "pct_now": round(float(p[hi]) * 100, 1),
            "months_below20": int(np.nansum(p[lo:hi] <= BUY_TH)),
            "months_above80": int(np.nansum(p[lo:hi] >= SELL_TH)),
        }
        curve[f"{y}y"] = [round(float(x) * 100, 1) if not np.isnan(x) else None for x in p[lo:hi + 1]]
        eq = np.concatenate([[1.0], np.cumprod(1 + r)])
        curve[f"{y}y_eq"] = [round(float(x), 4) for x in eq]
    res["curves"] = curve

    # ---------- 2. 逐年敞口与收益 ----------
    for y in WINDOWS:
        pos = positions(pcts[y][lo:hi])
        r = apply_pos(pos, ret[lo:hi])
        df = pd.DataFrame({"ym": ym[lo:hi], "pos": pos, "r": r, "bh": np.nan_to_num(ret[lo:hi])})
        df["year"] = [x[:4] for x in df.ym]
        res["exposure_year"][f"{y}y"] = {
            k: {"tim": round(float(g.pos.mean()) * 100, 1),
                "ret": round(float((np.prod(1 + g.r) - 1) * 100), 1),
                "bh": round(float((np.prod(1 + g.bh) - 1) * 100), 1)}
            for k, g in df.groupby("year")}

    # ---------- 3. 随机测试 ----------
    rng = np.random.default_rng(SEED)
    rows = []
    for y in WINDOWS:
        p = pcts[y]
        for H in HORIZONS:
            for _ in range(N_PER_CELL):
                s = int(rng.integers(lo, hi - H + 1))
                e = s + H
                posA = positions(p[s:e])
                rA = apply_pos(posA, ret[s:e])
                # 连续版：规则自 2019-01 起持续运行，取同一窗口
                posB = positions(p[lo:e])
                rB = apply_pos(posB, ret[lo:e])[s - lo:]
                bh = np.nan_to_num(ret[s:e])
                f = lambda r: (np.prod(1 + r) ** (12 / H) - 1) * 100
                rows.append({
                    "win_y": y, "H": H, "start": ym[s], "end": ym[min(e, hi)],
                    "cagr_wait": f(rA), "cagr_cont": f(rB), "cagr_bh": f(bh),
                    "tim": float(posA.mean()) * 100,
                    "ntr": int(np.abs(np.diff(np.concatenate([[0], posA]))).sum()),
                })
    sdf = pd.DataFrame(rows)
    sdf.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    for (y, H), g in sdf.groupby(["win_y", "H"]):
        res["mc"][f"{y}y_{H}m"] = {
            "wait": q(g.cagr_wait), "cont": q(g.cagr_cont), "bh": q(g.cagr_bh),
            "win_wait": round(float((g.cagr_wait > g.cagr_bh).mean()) * 100, 1),
            "win_cont": round(float((g.cagr_cont > g.cagr_bh).mean()) * 100, 1),
            "exc_wait": round(float((g.cagr_wait - g.cagr_bh).median()), 2),
            "exc_cont": round(float((g.cagr_cont - g.cagr_bh).median()), 2),
            "tim": round(float(g.tim.mean()), 1),
            "no_trade": round(float((g.ntr == 0).mean()) * 100, 1),
            "realized": round(float((g.ntr > 0).mean()) * 100, 1),
        }
    # 全窗口汇总（跨持有期）
    for y in WINDOWS:
        g = sdf[sdf.win_y == y]
        res["mc"][f"{y}y_all"] = {
            "wait": q(g.cagr_wait), "cont": q(g.cagr_cont), "bh": q(g.cagr_bh),
            "win_wait": round(float((g.cagr_wait > g.cagr_bh).mean()) * 100, 1),
            "win_cont": round(float((g.cagr_cont > g.cagr_bh).mean()) * 100, 1),
            "exc_wait": round(float((g.cagr_wait - g.cagr_bh).median()), 2),
            "tim": round(float(g.tim.mean()), 1),
            "no_trade": round(float((g.ntr == 0).mean()) * 100, 1),
            "n": int(len(g)),
        }

    # ---------- 4. 阈值敏感性 ----------
    for y in WINDOWS:
        row = {}
        for bt in (0.10, 0.20, 0.30):
            for st in (0.70, 0.80, 0.90):
                if bt >= st:
                    continue
                pos = positions(pcts[y][lo:hi], bt, st)
                pf = perf(apply_pos(pos, ret[lo:hi]))
                row[f"{int(bt*100)}/{int(st*100)}"] = {
                    "cagr": pf["cagr"], "sharpe": pf["sharpe"], "max_dd": pf["max_dd"],
                    "tim": round(float(pos.mean()) * 100, 1)}
        res["grid"][f"{y}y"] = row

    json.dump(res, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)

    # ---------- 打印 ----------
    print(f"区间 {res['meta']['period']}  共 {res['meta']['months']} 个月\n")
    print("【全区间：2019-01 ~ 2026-11】")
    print(f"{'标准':>8} {'总收益':>8} {'年化':>7} {'波动':>6} {'回撤':>7} {'夏普':>6} {'持仓%':>6} {'交易':>4} {'分位区间':>12} {'<20月数':>7} {'>80月数':>7}")
    b = res["full_period"]["buy_and_hold"]
    print(f"{'买入持有':>8} {b['total_ret']:>7.1f}% {b['cagr']:>6.2f}% {b['vol']:>5.2f}% {b['max_dd']:>6.1f}% {b['sharpe']:>6.2f} {'100.0':>6} {0:>4} {'-':>12} {'-':>7} {'-':>7}")
    for y in WINDOWS:
        v = res["full_period"][f"{y}y"]
        print(f"{str(y)+'年PE':>8} {v['total_ret']:>7.1f}% {v['cagr']:>6.2f}% {v['vol']:>5.2f}% {v['max_dd']:>6.1f}% "
              f"{v['sharpe']:>6.2f} {v['tim']:>6.1f} {v['trades']['n']:>4} "
              f"{str(v['pct_min'])+'-'+str(v['pct_max']):>12} {v['months_below20']:>7} {v['months_above80']:>7}")

    print("\n【随机测试：年化收益中位数，括号内=跑赢买入持有的概率】")
    print(f"{'标准':>7} {'持有':>5} {'等待版':>16} {'连续版':>16} {'基准':>8} {'平均持仓%':>9} {'零交易%':>7}")
    for y in WINDOWS:
        for H in HORIZONS:
            v = res["mc"][f"{y}y_{H}m"]
            print(f"{y:>6}年 {H:>4}月 {v['wait']['median']:>7.2f}% ({v['win_wait']:>5.1f}%) "
                  f"{v['cont']['median']:>7.2f}% ({v['win_cont']:>5.1f}%) "
                  f"{v['bh']['median']:>7.2f}% {v['tim']:>8.1f}% {v['no_trade']:>6.1f}%")
        g = res["mc"][f"{y}y_all"]
        print(f"  ── 汇总 等待版中位 {g['wait']['median']:>6.2f}% 胜率 {g['win_wait']:>5.1f}%  "
              f"连续版中位 {g['cont']['median']:>6.2f}% 胜率 {g['win_cont']:>5.1f}%  "
              f"p05~p95 [{g['wait']['p05']:>6.1f},{g['wait']['p95']:>6.1f}]")

    print("\n【阈值敏感性 年化%】")
    for y in WINDOWS:
        print(f"{str(y)+'年':>5} " + "  ".join(f"{k}:{v['cagr']:>6.2f}" for k, v in res["grid"][f"{y}y"].items()))
    print(f"\n输出 {OUT_JSON}\n     {OUT_CSV}")


if __name__ == "__main__":
    main()
