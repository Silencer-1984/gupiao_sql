# -*- coding: utf-8 -*-
"""
月内逢低加码：每月1号（顺延交易日）定投 5000 并记录买入价 P0；
之后本月内每个交易日，只要收盘价 < P0，就按规则补仓（100/200/300）。

补仓金额规则（用户要求：不固定 100，按偏离度和当日跌幅决定）：
  R0 基准      每月1号投5000，月内不补
  R1 固定100   低于P0就补100
  R2 固定200   低于P0就补200
  R3 偏离分档   低于P0：偏离≥1%补100、≥2%补200、≥3%补300
  R4 跌幅分档   低于P0 且当日跌：跌≥1%补100、≥2%补200、≥3%补300
  R5 组合分档   偏离pp + 当日跌幅pp：≥1补100、≥2补200、≥3补300

输出双口径：
  全成本收益 = 期末市值 / (5000×月数 + 累计补仓) − 1
  常规口径收益 = 期末市值 / (5000×月数) − 1   （补仓视作本来会花掉的钱）
并报总花费（累计投入）、补仓次数、平均补仓价 vs 基准价。

标的 .NDX，随机起点 + 5~9 年窗口，N=2000，seed=20261124。
输出：strategies/01_nasdaq_dca/backtest_intramonth_dip.md（单份报告）
"""
import os
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "strategies", "01_nasdaq_dca", "backtest_intramonth_dip.md")

BASE = 5000.0
N_SIM = 2000
HORIZONS = [60, 72, 84, 96, 108]
SEED = 20261124

NAMES = ["R0基准", "R1固定100", "R2固定200", "R3偏离分档", "R4跌幅分档", "R5组合分档"]


def load():
    c = sqlite3.connect(DB)
    df = pd.read_sql(
        "select trade_date, close from px_index_daily_us "
        "where index_code='.NDX' and close is not null order by trade_date",
        c, parse_dates=["trade_date"]).set_index("trade_date")["close"].astype(float)
    c.close()
    return df


def prep(s):
    df = pd.DataFrame({"px": s})
    df["ym"] = df.index.to_period("M")
    # 每月基准价 = 该月首个交易日收盘（即"1号"顺延后的买入价）
    df["p0"] = df.groupby("ym").px.transform("first")
    df["is_base"] = ~df.index.to_series().duplicated(keep="first").values | \
                    (df.index == df.groupby("ym").px.apply(lambda x: x.index[0]).reindex(df.index).values).astype(bool)
    # 上面的 is_base 复杂，直接用：当日是该月首个交易日
    first_idx = df.groupby("ym").apply(lambda g: g.index[0], include_groups=False)
    df["is_base"] = df.index.isin(first_idx.values)
    df["dev"] = (df.p0 / df.px - 1) * 100        # 低于基准的幅度（正=更便宜）
    df["dayret"] = df.px.pct_change() * 100       # 当日跌幅（负=跌）
    return df


def buy_months(idx, start_month, months):
    out = []
    for k in range(months):
        m = start_month + pd.offsets.MonthBegin(k)
        cand = idx[(idx >= m) & (idx < m + pd.offsets.MonthBegin(1))]
        if len(cand):
            out.append(cand[0])
    return out if len(out) == months else None


def topup_amount(st, dev, dayret):
    """返回本月补仓金额（元）；dev=低于P0幅度%，dayret=当日涨跌%。"""
    if st == 0 or dev <= 0:
        return 0.0
    if st == 1:
        return 100.0
    if st == 2:
        return 200.0
    if st == 3:
        if dev >= 3: return 300.0
        if dev >= 2: return 200.0
        if dev >= 1: return 100.0
        return 0.0
    if st == 4:
        drop = -dayret if dayret < 0 else 0.0
        if drop >= 3: return 300.0
        if drop >= 2: return 200.0
        if drop >= 1: return 100.0
        return 0.0
    if st == 5:
        drop = -dayret if dayret < 0 else 0.0
        score = dev + drop
        if score >= 3: return 300.0
        if score >= 2: return 200.0
        if score >= 1: return 100.0
        return 0.0
    return 0.0


def simulate(seg, n_base):
    """seg 为窗口内交易日 DataFrame。返回每条轨的结果 dict。"""
    px = seg.px.values
    dev = seg.dev.values
    dayret = np.nan_to_num(seg.dayret.values, nan=0.0)
    is_base = seg.is_base.values
    out = []
    for st in range(len(NAMES)):
        sh = 0.0
        topup_total = 0.0
        topup_cnt = 0
        topup_price_sum = 0.0
        for k in range(len(px)):
            if is_base[k]:
                sh += BASE / px[k]
            else:
                amt = topup_amount(st, dev[k], dayret[k])
                if amt > 0:
                    sh += amt / px[k]
                    topup_total += amt
                    topup_cnt += 1
                    topup_price_sum += px[k]
        cost_base = BASE * n_base
        v = sh * px[-1]
        out.append({
            "v": v,
            "ret_full": (v / (cost_base + topup_total) - 1) * 100,
            "ret_base": (v / cost_base - 1) * 100,
            "cost": cost_base + topup_total,
            "topup": topup_total,
            "cnt": topup_cnt,
            "avgpx": topup_price_sum / topup_cnt if topup_cnt else np.nan,
        })
    return out


def main():
    s = load()
    df = prep(s)
    idx = s.index
    months = pd.date_range(idx.min().normalize(), idx.max().normalize(), freq="MS")
    rng = np.random.default_rng(SEED)

    rows = []
    for _ in range(N_SIM):
        L = int(rng.choice(HORIZONS))
        if len(months) - L - 1 < 2:
            continue
        si = int(rng.integers(0, len(months) - L))
        bds = buy_months(idx, months[si], L)
        if bds is None:
            continue
        start, end = bds[0], bds[-1]
        seg = df[(df.index >= start) & (df.index <= end)]
        if len(seg) < L:
            continue
        res = simulate(seg, L)
        seg_px = seg.px.values
        peak = np.maximum.accumulate(seg_px)
        rec = {
            "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
            "months": L, "mkt_ret": (seg_px[-1] / seg_px[0] - 1) * 100,
            "mdd": (seg_px / peak - 1).min() * 100,
            "exit_dd": (seg_px[-1] / seg_px.max() - 1) * 100,
        }
        for st, r in enumerate(res):
            for k, v in r.items():
                rec[f"{k}{st}"] = v
        rows.append(rec)

    res = pd.DataFrame(rows).dropna(subset=["v0"])

    def stat(g, col):
        x = g[col].replace([np.inf, -np.inf], np.nan).dropna()
        return x.mean(), x.median()

    L = []
    L.append("# 月内逢低加码：每月1号定投 + 低于本月基准价就补仓\n")
    L.append(f"> 脚本 `scripts/backtest_intramonth_dip.py`　seed={SEED}　N={len(res)} 组，标的 .NDX\n")
    L.append("## 1. 规则\n")
    L.append("- 每月首个交易日（即「1号」顺延）投 **5000**，记该日收盘价为 P0")
    L.append("- 本月内之后每个交易日：若收盘价 **< P0**，按规则补仓；否则不动")
    L.append("- P0 每月重置；补仓金额不固定，按偏离度（P0/当日价−1）和当日跌幅决定\n")
    L.append("| 轨 | 补仓规则 |\n|---|---|")
    L.append("| R0 基准 | 不补仓 |")
    L.append("| R1 固定100 | 低于P0就补100 |")
    L.append("| R2 固定200 | 低于P0就补200 |")
    L.append("| R3 偏离分档 | 偏离≥1%补100、≥2%补200、≥3%补300 |")
    L.append("| R4 跌幅分档 | 当日跌≥1%补100、≥2%补200、≥3%补300（且需低于P0）|")
    L.append("| R5 组合分档 | 偏离pp+当日跌幅pp：≥1补100、≥2补200、≥3补300 |\n")
    L.append("**双口径**：全成本收益＝期末市值/(5000×月数+补仓)；常规口径＝期末市值/(5000×月数)（补仓视作本来会花掉的钱）。\n")

    def table(g, title):
        L.append(f"### {title}（n={len(g)}）\n")
        L.append("| 轨 | 全成本收益 | 常规口径收益 | 总花费(元) | 补仓额(元) | 补仓次数 | 补仓均价 |")
        L.append("|---|---:|---:|---:|---:|---:|---:|")
        for st, name in enumerate(NAMES):
            rf, _ = stat(g, f"ret_full{st}")
            rb, _ = stat(g, f"ret_base{st}")
            c, _ = stat(g, f"cost{st}")
            tp, _ = stat(g, f"topup{st}")
            cn, _ = stat(g, f"cnt{st}")
            ap, _ = stat(g, f"avgpx{st}")
            aps = "—" if np.isnan(ap) else f"{ap:.0f}"
            L.append(f"| {name} | {rf:.2f}% | {rb:.2f}% | {c:,.0f} | {tp:,.0f} | {cn:.0f} | {aps} |")
        L.append("")
        return None

    base_full = stat(res, "ret_full0")[0]
    base_cost = stat(res, "cost0")[0]
    L.append("## 2. 全样本\n")
    table(res, "全样本")
    L.append(f"基准 R0：全成本收益 {base_full:.2f}%，总花费 {base_cost:,.0f} 元（每期5000）。\n")

    L.append("## 3. 牛熊分组\n")
    table(res[res.exit_dd <= -20], "终点仍在熊市（离高点≤-20%）")
    table(res[res.exit_dd > -2], "终点创新高（离高点>-2%）")
    table(res[res.mdd <= -30], "窗口内深回撤（MDD≤-30%）")

    L.append("## 4. 结论\n")
    for st in range(1, len(NAMES)):
        rf, _ = stat(res, f"ret_full{st}")
        c, _ = stat(res, f"cost{st}")
        rb, _ = stat(res, f"ret_base{st}")
        L.append(f"- {NAMES[st]}：全成本收益 {rf:.2f}%（较基准 {rf-base_full:+.2f}pp），"
                 f"常规口径 {rb:.2f}%，总花费 {c:,.0f} 元（较基准 +{c-base_cost:,.0f}）")
    L.append("- 补仓越猛，总花费越高；全成本收益是否提升取决于补仓价是否真低于平均成本。")
    L.append("- 常规口径天然偏高（补仓钱不进分母），只用于对照「备用金」场景。\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("报告已写:", OUT)
    print("样本:", len(res))
    for st, name in enumerate(NAMES):
        rf, _ = stat(res, f"ret_full{st}")
        c, _ = stat(res, f"cost{st}")
        rb, _ = stat(res, f"ret_base{st}")
        print(f"{name:<12} 全成本 {rf:>6.2f}%  常规口径 {rb:>7.2f}%  总花费 {c:>10,.0f}")


if __name__ == "__main__":
    main()
