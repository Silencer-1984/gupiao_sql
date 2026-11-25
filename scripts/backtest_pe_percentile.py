# -*- coding: utf-8 -*-
"""
沪深300 PE 分位择时：1年 / 3年 / 5年 / 10年 四种回顾窗口的对比验证。

规则（用户给定）：
  - PE 分位 <= 20% 买入（满仓）
  - PE 分位 >= 80% 卖出（空仓）
  - 20%~80% 之间维持原仓位；从未触发买入则一直空仓

数据（全部来自 data/ashare.db，不调外部接口）：
  - val_index_pe_lg  沪深300 月度 PE-TTM(加权) + 指数收盘，2005-04 ~ 2026-11
  - px_index_daily_csi 沪深300 日频 PE-TTM + 收盘，2015-01 ~ 2026-11（稳健性对照）

口径要点：
  - 分位只用「截至当期」的历史，无未来函数
  - 月末出信号，次月收益生效（signal at close_t -> return of t+1）
  - 单边交易成本 5bp
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT_JSON = os.path.join(ROOT, "data", "pe_percentile_bt.json")
OUT_CSV = os.path.join(ROOT, "data", "pe_percentile_samples.csv")

WINDOWS = {1: 12, 3: 36, 5: 60, 10: 120}   # 年 -> 月
BUY_TH, SELL_TH = 0.20, 0.80
TC = 0.0005
SEED = 20261123
N_SIM = 4000
HORIZONS_M = [12, 36, 60, 120]


# ---------------- 数据 ----------------
def load_monthly():
    c = sqlite3.connect(DB)
    df = pd.read_sql(
        "select trade_date, index_close, pe_ttm from val_index_pe_lg "
        "where index_name='沪深300' order by trade_date", c,
        parse_dates=["trade_date"])
    c.close()
    df = df.dropna(subset=["index_close", "pe_ttm"]).reset_index(drop=True)
    df["ym"] = df.trade_date.dt.to_period("M")
    df = df.groupby("ym", as_index=False).last().sort_values("ym").reset_index(drop=True)
    return df


def load_daily():
    c = sqlite3.connect(DB)
    df = pd.read_sql(
        "select trade_date, close, pe_ttm from px_index_daily_csi "
        "where index_code='000300' order by trade_date", c,
        parse_dates=["trade_date"])
    c.close()
    df = df.dropna(subset=["close", "pe_ttm"]).drop_duplicates("trade_date").reset_index(drop=True)
    df["ym"] = df.trade_date.dt.to_period("M")
    # 每月取最后一个交易日的 PE 与收盘，与月度表同口径对齐
    return df.groupby("ym", as_index=False).last().sort_values("ym").reset_index(drop=True)


# ---------------- 分位 ----------------
def rolling_pct(pe: np.ndarray, win: int) -> np.ndarray:
    """滚动分位：pct[t] = 窗口内 <= pe[t] 的占比。前 win-1 个为 NaN。"""
    n = len(pe)
    out = np.full(n, np.nan)
    for t in range(win - 1, n):
        w = pe[t - win + 1: t + 1]
        out[t] = float((w <= pe[t]).mean())
    return out


# ---------------- 回测 ----------------
def run_rule(pct: np.ndarray, ret_next: np.ndarray, tc=TC):
    """返回逐期仓位（0/1）与策略/基准月度收益。"""
    n = len(pct)
    pos = np.zeros(n)
    state = 0.0
    for i in range(n):
        p = pct[i]
        if not np.isnan(p):
            if p <= BUY_TH:
                state = 1.0
            elif p >= SELL_TH:
                state = 0.0
        pos[i] = state            # 在 t 收盘持有，吃 t+1 的收益
    r = np.nan_to_num(ret_next, nan=0.0)
    prev = np.concatenate([[0.0], pos[:-1]])
    cost = np.abs(pos - prev) * tc
    r_strat = pos * r - cost
    return pos, r_strat, r, cost


def perf(r: np.ndarray, months_per_year=12):
    r = np.asarray(r, dtype=float)
    if len(r) == 0:
        return {}
    eq = np.cumprod(1 + r)
    total = eq[-1] - 1
    yrs = len(r) / months_per_year
    cagr = eq[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    vol = r.std(ddof=1) * np.sqrt(months_per_year) if len(r) > 2 else np.nan
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sharpe = (r.mean() * months_per_year) / vol if vol and vol > 0 else np.nan
    return {
        "total_ret": round(float(total) * 100, 1),
        "cagr": round(float(cagr) * 100, 2),
        "vol": round(float(vol) * 100, 2),
        "max_dd": round(dd * 100, 1),
        "sharpe_rf0": round(float(sharpe), 2),
        "calmar": round(float(cagr / abs(dd)), 2) if dd else np.nan,
    }


def trade_stats(pos, ret, cost):
    """按连续持仓段统计单笔交易。"""
    segs = []
    i = 0
    n = len(pos)
    while i < n:
        if pos[i] == 1 and (i == 0 or pos[i - 1] == 0):
            j = i
            while j + 1 < n and pos[j + 1] == 1:
                j += 1
            m = ret[i: j + 1]
            segs.append({"len": j - i + 1, "ret": float(np.prod(1 + m) - 1) * 100})
            i = j + 1
        else:
            i += 1
    if not segs:
        return {"n_trades": 0, "avg_len_m": 0, "win_rate": 0, "avg_ret": 0, "best": 0, "worst": 0}
    arr = np.array([s["ret"] for s in segs])
    ln = np.array([s["len"] for s in segs])
    return {
        "n_trades": len(segs),
        "avg_len_m": round(float(ln.mean()), 1),
        "win_rate": round(float((arr > 0).mean()) * 100, 1),
        "avg_ret": round(float(arr.mean()), 2),
        "median_ret": round(float(np.median(arr)), 2),
        "best": round(float(arr.max()), 2),
        "worst": round(float(arr.min()), 2),
    }


def spearman_ic(x, y):
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 30 or np.std(x[m]) == 0:
        return np.nan
    rx = pd.Series(x[m]).rank().values
    ry = pd.Series(y[m]).rank().values
    return float(np.corrcoef(rx, ry)[0, 1])


# ---------------- 主流程 ----------------
def main():
    m = load_monthly()
    d = load_daily()
    ym = m.ym.astype(str).values
    pe = m.pe_ttm.values.astype(float)
    close = m.index_close.values.astype(float)
    ret_next = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])  # ret_next[i] = r(i+1)

    # 各窗口分位
    pcts = {y: rolling_pct(pe, w) for y, w in WINDOWS.items()}

    # 共同可比区间：所有窗口都已有完整分位 -> 取 10 年窗口首个有效月
    first_valid = {y: int(np.argmax(~np.isnan(p))) + 1 for y, p in pcts.items()}
    common_start = max(first_valid[y] for y in WINDOWS)  # 下标（含）
    # 保证收益可取（最后一个月没有 next return）
    lo, hi = common_start, len(m) - 1

    res = {
        "meta": {
            "index": "沪深300", "pe_field": "PE-TTM(加权, 乐咕/val_index_pe_lg)",
            "source_table": "val_index_pe_lg",
            "freq": "月度(月内最后一个交易日)", "buy_th": BUY_TH, "sell_th": SELL_TH,
            "tc_oneway": TC, "seed": SEED, "n_sim": N_SIM,
            "full_sample": f"{ym[0]}~{ym[-1]}", "n_months": len(m),
            "common_window": f"{ym[lo]}~{ym[hi]}", "n_months_common": int(hi - lo + 1),
            "first_valid": {f"{y}y": ym[first_valid[y] - 1] for y in WINDOWS},
        },
        "common_window": {}, "own_window": {}, "montecarlo": {},
        "predictive": {}, "notes": [],
    }

    # --- 1. 共同区间：四标准同台 ---
    bh = perf(ret_next[lo:hi])
    res["common_window"]["buy_and_hold"] = {**bh, "months_in_market": round((hi - lo) / (hi - lo) * 100, 1)}
    for y in WINDOWS:
        pos, rs, rr, cost = run_rule(pcts[y][lo:hi], ret_next[lo:hi])
        tstat = trade_stats(pos, rr, cost)
        res["common_window"][f"{y}y"] = {
            **perf(rs),
            "time_in_market": round(float(pos.mean()) * 100, 1),
            "n_switches": int(np.abs(np.diff(np.concatenate([[0], pos]))).sum()),
            **tstat,
        }

    # --- 2. 各标准自身最长可用区间 ---
    for y in WINDOWS:
        s = first_valid[y] - 1
        pos, rs, rr, cost = run_rule(pcts[y][s:hi], ret_next[s:hi])
        res["own_window"][f"{y}y"] = {
            "period": f"{ym[s]}~{ym[hi]}",
            "months": int(hi - s),
            "strategy": perf(rs), "buy_hold": perf(ret_next[s:hi]),
            "time_in_market": round(float(np.mean(pos)) * 100, 1),
        }

    # --- 3. 预测力：分位 vs 未来收益 ---
    for y in WINDOWS:
        p = pcts[y]
        row = {}
        for fwd in (12, 36, 60):
            f = np.full(len(m), np.nan)
            for i in range(len(m) - fwd):
                f[i] = np.prod(1 + np.nan_to_num(ret_next[i:i + fwd])) - 1
            row[f"ic_{fwd}m"] = round(spearman_ic(p[lo:hi], f[lo:hi]), 3)
            # 分位 <=20 组 vs >=80 组的平均未来收益
            lo_g = np.nanmean(f[lo:hi][p[lo:hi] <= BUY_TH]) * 100 if np.any(p[lo:hi] <= BUY_TH) else np.nan
            hi_g = np.nanmean(f[lo:hi][p[lo:hi] >= SELL_TH]) * 100 if np.any(p[lo:hi] >= SELL_TH) else np.nan
            row[f"fwd{fwd}m_low20"] = round(float(lo_g), 1) if not np.isnan(lo_g) else None
            row[f"fwd{fwd}m_high80"] = round(float(hi_g), 1) if not np.isnan(hi_g) else None
            row[f"fwd{fwd}m_n_low"] = int(np.sum(p[lo:hi] <= BUY_TH))
            row[f"fwd{fwd}m_n_high"] = int(np.sum(p[lo:hi] >= SELL_TH))
        res["predictive"][f"{y}y"] = row

    # --- 4. 随机测试：随机起点 + 随机持有期，从空仓开始等待 ---
    rng = np.random.default_rng(SEED)
    samples = []
    for _ in range(N_SIM):
        y = int(rng.choice(list(WINDOWS)))
        H = int(rng.choice(HORIZONS_M))
        # 起点须让 [start, start+H] 落在 common 区间
        max_s = hi - H
        if max_s <= lo:
            continue
        s = int(rng.integers(lo, max_s))
        e = s + H
        # (a) 空仓起步，遵守规则等待
        posA, rA, _, _ = run_rule(pcts[y][s:e], ret_next[s:e])
        # (b) 全程运行（从 lo 起跑），只看窗口收益
        posB, rB, _, _ = run_rule(pcts[y][lo:e], ret_next[lo:e])
        rB_win = rB[s - lo:]
        bhA = ret_next[s:e]
        cagr = lambda r, h: (np.prod(1 + r) ** (12 / h) - 1) * 100
        samples.append({
            "win_y": y, "months": H,
            "start": ym[s], "end": ym[min(e, hi - 1)],
            "cagr_wait": cagr(rA, H),
            "cagr_cont": cagr(rB_win, H),
            "cagr_bh": cagr(np.nan_to_num(bhA), H),
            "time_in_market": float(posA.mean()) * 100,
            "n_trades": int(trade_stats(posA, rA, 0)["n_trades"]),
        })
    sdf = pd.DataFrame(samples)
    sdf.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    def q(s):
        return {
            "n": int(len(s)), "mean": round(float(s.mean()), 2),
            "median": round(float(s.median()), 2),
            "p05": round(float(s.quantile(0.05)), 2), "p25": round(float(s.quantile(0.25)), 2),
            "p75": round(float(s.quantile(0.75)), 2), "p95": round(float(s.quantile(0.95)), 2),
            "std": round(float(s.std()), 2),
        }

    for y in WINDOWS:
        for H in HORIZONS_M:
            g = sdf[(sdf.win_y == y) & (sdf.months == H)]
            if len(g) < 30:
                continue
            key = f"{y}y_{H}m"
            res["montecarlo"][key] = {
                "n": int(len(g)),
                "wait": q(g.cagr_wait), "cont": q(g.cagr_cont), "bh": q(g.cagr_bh),
                "win_vs_bh_wait": round(float((g.cagr_wait > g.cagr_bh).mean()) * 100, 1),
                "win_vs_bh_cont": round(float((g.cagr_cont > g.cagr_bh).mean()) * 100, 1),
                "median_excess_wait": round(float((g.cagr_wait - g.cagr_bh).median()), 2),
                "median_excess_cont": round(float((g.cagr_cont - g.cagr_bh).median()), 2),
                "avg_time_in_market": round(float(g.time_in_market.mean()), 1),
                "pct_no_trade": round(float((g.n_trades == 0).mean()) * 100, 1),
            }

    # --- 5. 日频稳健性（2015-2026，用中证官方 PE）---
    dym = d.ym.astype(str).values
    dpe = d.pe_ttm.values.astype(float)
    dclose = d.close.values.astype(float)
    dret = np.concatenate([dclose[1:] / dclose[:-1] - 1, [np.nan]])
    res["daily_robust"] = {"period": f"{dym[0]}~{dym[-1]}", "rows": int(len(d))}
    for y, w in WINDOWS.items():
        p = rolling_pct(dpe, w)
        s = int(np.argmax(~np.isnan(p)))
        if s < 1:
            continue
        pos, rs, _, _ = run_rule(p[s:len(d) - 1], dret[s:len(d) - 1])
        res["daily_robust"][f"{y}y"] = {
            "start": dym[s], **perf(rs),
            "time_in_market": round(float(pos.mean()) * 100, 1),
        }
    bh_d = perf(dret[s:len(d) - 1])
    res["daily_robust"]["buy_and_hold"] = bh_d

    res["notes"] = [
        "分位为滚动窗口内的百分位排名（窗口含当期），仅用历史数据",
        "月末信号、次月生效；单边成本 5bp；不含股息（沪深300 股息率约 2-3%，多头暴露越多越占优）",
        "10 年窗口需要 10 年历史，2015-04 之前无法计算，四标准可比区间因此从 2015 年起",
        "样本区间内含 2015 杠杆牛、2018 熊市、2021 高点、2022-24 熊市，但独立牛熊周期仅约 3 轮，统计功效有限",
    ]

    json.dump(res, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)

    # ---- 打印 ----
    print(f"样本 {res['meta']['full_sample']}  共 {len(m)} 月")
    print(f"四标准可比区间 {res['meta']['common_window']} ({res['meta']['n_months_common']} 月)\n")
    print("【可比区间】")
    hdr = f"{'标准':>8} {'总收益':>8} {'年化':>7} {'波动':>7} {'最大回撤':>8} {'夏普':>6} {'Calmar':>7} {'持仓%':>7} {'交易次数':>8} {'单笔均':>7} {'胜率':>6}"
    print(hdr)
    b = res["common_window"]["buy_and_hold"]
    print(f"{'买入持有':>8} {b['total_ret']:>7.1f}% {b['cagr']:>6.2f}% {b['vol']:>6.2f}% {b['max_dd']:>7.1f}% {b['sharpe_rf0']:>6.2f} {b['calmar']:>7.2f} {'100.0':>7} {0:>8} {'-':>7} {'-':>6}")
    for y in WINDOWS:
        v = res["common_window"][f"{y}y"]
        print(f"{str(y)+'年PE':>8} {v['total_ret']:>7.1f}% {v['cagr']:>6.2f}% {v['vol']:>6.2f}% {v['max_dd']:>7.1f}% "
              f"{v['sharpe_rf0']:>6.2f} {v['calmar']:>7.2f} {v['time_in_market']:>7.1f} {v['n_trades']:>8} "
              f"{v['avg_ret']:>6.2f}% {v['win_rate']:>5.1f}%")

    print("\n【各标准自身最长区间】")
    for y in WINDOWS:
        v = res["own_window"][f"{y}y"]
        print(f"{str(y)+'年PE':>8} {v['period']} {v['months']:>4}月  策略年化 {v['strategy']['cagr']:>6.2f}%  "
              f"基准 {v['buy_hold']['cagr']:>6.2f}%  回撤 {v['strategy']['max_dd']:>7.1f}%  持仓 {v['time_in_market']:>5.1f}%")

    print("\n【预测力：分位 vs 未来收益（Spearman IC，负值=低分位对应高收益，符合预期）】")
    for y in WINDOWS:
        r = res["predictive"][f"{y}y"]
        print(f"{str(y)+'年PE':>8}  IC1y {r['ic_12m']:>6.3f}  IC3y {r['ic_36m']:>6.3f}  IC5y {r['ic_60m']:>6.3f}"
              f"  | 低20%组未来1y {r['fwd12m_low20']}% vs 高80%组 {r['fwd12m_high80']}%"
              f"  (n={r['fwd12m_n_low']}/{r['fwd12m_n_high']})")

    print("\n【随机测试：随机起点+随机持有期，年化收益中位数 / 跑赢买入持有的概率】")
    print(f"{'标准':>7} {'持有':>5} {'n':>6} {'等待版中位':>10} {'连续版中位':>10} {'基准中位':>9} {'胜率(等待)':>10} {'胜率(连续)':>10} {'平均持仓%':>9} {'零交易%':>7}")
    for k, v in res["montecarlo"].items():
        y, H = k.split("_")
        print(f"{y:>7} {H:>5} {v['n']:>6} {v['wait']['median']:>9.2f}% {v['cont']['median']:>9.2f}% "
              f"{v['bh']['median']:>8.2f}% {v['win_vs_bh_wait']:>9.1f}% {v['win_vs_bh_cont']:>9.1f}% "
              f"{v['avg_time_in_market']:>8.1f}% {v['pct_no_trade']:>6.1f}%")

    print("\n【日频稳健性 2015-2026，中证官方 PE】")
    dr = res["daily_robust"]
    print(f"  买入持有 年化 {dr['buy_and_hold']['cagr']:>6.2f}%  回撤 {dr['buy_and_hold']['max_dd']:>7.1f}%")
    for y in WINDOWS:
        v = dr.get(f"{y}y")
        if v:
            print(f"  {str(y)+'年PE':>8} 起 {v['start']}  年化 {v['cagr']:>6.2f}%  回撤 {v['max_dd']:>7.1f}%  持仓 {v['time_in_market']:>5.1f}%")
    print(f"\n输出: {OUT_JSON}")
    print(f"      {OUT_CSV}")


if __name__ == "__main__":
    main()
