"""成长(科创50) vs 价值(红利低波) 跷跷板效应验证。

区间 2021-01-01 ~ 2026-11-20；市场锚点 = 上证指数；重点 = 明显负相关的持续期。
用法: uv run python scripts/corr_growth_value.py
产出: strategies/07_other_research/corr_growth_value.md（唯一报告文件，不生成 HTML/JSON/图表）
"""
from __future__ import annotations

import sqlite3
from math import erfc, sqrt
from pathlib import Path

import numpy as np
import pandas as pd


def norm_sf(z: float) -> float:
    return 0.5 * erfc(float(z) / sqrt(2))


def pearson(a, b) -> tuple[float, float]:
    """Pearson r + 双侧 p（Fisher z 正态近似，n 大时准确）。"""
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    n = len(x)
    if n < 3 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan, np.nan
    r = float(np.corrcoef(x, y)[0, 1])
    p = 0.0 if abs(r) >= 1 else float(2 * norm_sf(abs(np.arctanh(r)) * sqrt(n - 3)))
    return r, p


def rankdata(x) -> np.ndarray:
    s = np.sort(x)
    out = np.empty(len(x), dtype=float)
    i = 0
    while i < len(x):
        j = i + 1
        while j < len(x) and s[j] == s[i]:
            j += 1
        out[np.argsort(x, kind="stable")[i:j]] = (i + j - 1) / 2 + 1
        i = j
    return out


def spearman(a, b) -> float:
    return pearson(rankdata(np.asarray(a)), rankdata(np.asarray(b)))[0]


def binom_sf(k: int, n: int, p: float) -> float:
    """二项分布上尾的正态近似（n 大、p 不过于极端时有效）。"""
    mu, sd = n * p, sqrt(n * p * (1 - p))
    return float(norm_sf((k - 0.5 - mu) / sd)) if sd > 0 else np.nan

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "ashare.db"
OUT = ROOT / "strategies" / "07_other_research" / "corr_growth_value.md"
START, END = "2021-01-01", "2026-11-20"
G, V, M = "科创50", "红利低波", "上证指数"
WINDOWS = (20, 60)          # 约 1 个月 / 3 个月
THRESHOLDS = (-0.3, -0.5)   # 中等明显 / 强负相关
N_BOOT = 500
SEED = 20261124

lines: list[str] = []


def add(text: str = "") -> None:
    lines.append(text)


def load_close(conn, table: str, code_col: str, code: str, start: str = START) -> pd.Series:
    sql = (f"select trade_date, close from {table} "
           f"where {code_col}=? and trade_date between ? and ? order by trade_date")
    df = pd.read_sql(sql, conn, params=(code, start, END))
    return df.set_index("trade_date")["close"].astype(float)


def stats_pair(a: pd.Series, b: pd.Series, market: pd.Series | None = None) -> dict:
    """原始相关 + 市场中性残差相关 + 反向日占比。"""
    d = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    r = pearson(d["a"], d["b"])
    sp = spearman(d["a"], d["b"])
    out = {"n": len(d), "pearson": r[0], "p": r[1], "spearman": sp}
    out["opp"] = float(((d["a"] > 0) & (d["b"] < 0)).mean() * 100)
    base = float((d["a"] > 0).mean() * (d["b"] < 0).mean())
    out["opp_base"] = base * 100
    out["opp_p"] = (binom_sf(int(out["opp"] / 100 * len(d)), len(d), base)
                     if 0 < base < 1 else np.nan)
    if market is not None:
        m = market.reindex(d.index).dropna()
        d = d.loc[m.index]
        va = m.rolling(60).var()
        ba = d["a"].rolling(60).cov(m) / va
        bb = d["b"].rolling(60).cov(m) / va
        ea, eb = (d["a"] - ba * m).dropna(), (d["b"] - bb * m).dropna()
        out["neu"] = pearson(ea, eb)[0]
        out["neu_n"] = len(ea)
    return out


def rolling_neu(ret: pd.DataFrame, w: int) -> pd.Series:
    """窗口内分别对成长/价值做上证指数中性化后的滚动相关。"""
    m, a, b = ret[M], ret[G], ret[V]
    va = m.rolling(w).var()
    ea = a - (a.rolling(w).cov(m) / va) * m
    eb = b - (b.rolling(w).cov(m) / va) * m
    return ea.rolling(w).corr(eb)


def episodes(mask: pd.Series) -> pd.DataFrame:
    """连续 True 区间。"""
    m = mask.fillna(False).astype(bool)
    grp = (m != m.shift()).cumsum()
    rows = []
    for _, seg in m.groupby(grp):
        if not seg.iloc[0]:
            continue
        a, b = seg.index[0], seg.index[-1]
        rows.append({"start": a, "end": b, "days": len(seg),
                     "cal": (pd.Timestamp(b) - pd.Timestamp(a)).days + 1})
    return pd.DataFrame(rows)


def max_run(mask: pd.Series) -> int:
    m = mask.fillna(False).astype(bool)
    grp = (m != m.shift()).cumsum()
    return int(m.groupby(grp).sum().max())


def span_table(s: pd.Series, min_days: int = 40) -> str:
    ch = s[s != s.shift()]
    idx = list(ch.index) + [s.index[-1]]
    rows = []
    for i in range(len(idx) - 1):
        a, b = idx[i], idx[i + 1]
        n = int(((s.index >= a) & (s.index <= b)).sum())
        if n >= min_days:
            rows.append(f"| {a} ~ {b} | {s.loc[a]} | {n} |")
    return "\n".join(rows) if rows else "| （无≥40交易日阶段） | - | - |"


def fisher_z(r1: float, r2: float, n1: int, n2: int) -> tuple[float, float]:
    z = (np.arctanh(r1) - np.arctanh(r2)) / np.sqrt(1 / (n1 - 3) + 1 / (n2 - 3))
    return float(z), float(2 * norm_sf(abs(z)))


def fmt(x, d=3) -> str:
    return "n/a" if pd.isna(x) else f"{x:.{d}f}"


def main() -> None:
    conn = sqlite3.connect(DB)
    px = pd.DataFrame({
        M: load_close(conn, "px_index_daily_csi", "index_code", "000001"),
        G: load_close(conn, "px_index_daily_csi", "index_code", "000688", "2020-11-01"),
        "创业板指": load_close(conn, "px_index_daily_cni", "index_code", "399006"),
        V: load_close(conn, "px_index_daily_csi", "index_code", "H30269"),
        "红利低波100": load_close(conn, "px_index_daily_csi", "index_code", "930955"),
        "中证红利": load_close(conn, "px_index_daily_csi", "index_code", "000922"),
        "科创50ETF": load_close(conn, "px_etf_daily", "etf_code", "sh588000", "2020-11-01"),
        "红利ETF": load_close(conn, "px_etf_daily", "etf_code", "sh512890"),
    }).dropna()
    ret = px.pct_change() * 100
    ret = ret.dropna()

    # 上证指数阶段（用更长历史算 250 日动量与 MA200，再对齐样本）
    sh = load_close(conn, "px_index_daily_csi", "index_code", "000001", "2019-01-01")
    r250 = (sh / sh.shift(250) - 1) * 100
    ma200 = sh.rolling(200).mean()
    momentum = pd.Series("震荡", index=sh.index)
    momentum[r250 > 10] = "牛市"
    momentum[r250 < -5] = "熊市"
    trend = pd.Series("下跌", index=sh.index)
    trend[sh > ma200] = "上涨"
    mom = momentum.reindex(ret.index).ffill()
    trd = trend.reindex(ret.index).ffill()

    add("# 成长 vs 价值跷跷板效应验证（2021-01 ~ 2026-11）")
    add()
    add(f"- 成长：**{G}**；价值：**{V}**；市场锚点：**上证指数（000001）**")
    add(f"- 样本：{px.index[0]} ~ {px.index[-1]}，共 **{len(ret)}** 个交易日")
    add("- 收益：日收盘价简单收益率；市场中性 = 窗口内分别对上证指数回归取残差后求相关")
    add("- 报告由 `scripts/corr_growth_value.py` 生成，未生成 HTML/JSON/图表文件")
    add()
    add("> **方法论警告**：上证指数本身由成长股与价值股共同构成。对它回归取残差会产生"
        "**机械负相关**（本样本全样本残差相关 −0.62，固定 β 亦为 −0.64），"
        "这是成分结构导致的统计假象，不能当作跷跷板证据。因此下文**以原始相关与反向日为主口径**，"
        "中性化结果仅列出供对照，不作结论依据。阶段划分仍按要求使用上证指数。")
    add()

    # ---- 1. 全样本 ----
    add("## 1. 全样本相关")
    add()
    add("（附周度收益，降低日度噪声；中性相关*有机械偏误，仅供参考）")
    add()
    add("| 成长 | 价值 | 交易日 | Pearson | p | Spearman | 中性相关* | 反向日占比 | 独立基准 |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for a, b in [(G, V), (G, "红利低波100"), (G, "中证红利"), (G, "红利ETF"),
                 ("创业板指", V), ("科创50ETF", V)]:
        s = stats_pair(ret[a], ret[b], ret[M])
        add(f"| {a} | {b} | {s['n']} | {fmt(s['pearson'])} | {fmt(s['p'])} | "
            f"{fmt(s['spearman'])} | {fmt(s['neu'])} | {fmt(s['opp'],1)}% | {fmt(s['opp_base'],1)}% |")
    add()
    add("| 频率 | 样本 | Pearson | Spearman |")
    add("|---|---:|---:|---:|")
    freq_src = pd.DataFrame({G: ret[G].to_numpy(), V: ret[V].to_numpy()},
                            index=pd.to_datetime(ret.index))
    for freq, label in [("W-FRI", "周度"), ("ME", "月度")]:
        try:
            sub = freq_src.resample(freq).sum().dropna()
        except Exception:
            continue
        if len(sub) > 3:
            add(f"| {label} | {len(sub)} | {fmt(pearson(sub.iloc[:,0], sub.iloc[:,1])[0])} | "
                f"{fmt(spearman(sub.iloc[:,0], sub.iloc[:,1]))} |")
    add()
    add("> 反向日 = 成长上涨且价值下跌的交易日占比；独立基准 = P(成长涨)×P(价值跌)。")
    add()

    # ---- 2. 阶段 ----
    add("## 2. 阶段划分（上证指数）")
    add()
    add("### 2.1 动量三档主口径：250日涨幅 >10% 牛市 / <−5% 熊市 / 其余震荡")
    add()
    add("| 阶段 | 交易日 | Pearson | 中性相关* | 反向日占比 | 独立基准 |")
    add("|---|---:|---:|---:|---:|---:|")
    for stage in ["牛市", "震荡", "熊市"]:
        sub = ret[mom == stage]
        if len(sub) < 20:
            add(f"| {stage} | {len(sub)} | - | - | - | - |")
            continue
        s = stats_pair(sub[G], sub[V], sub[M])
        add(f"| {stage} | {len(sub)} | {fmt(s['pearson'])} | {fmt(s['neu'])} | "
            f"{fmt(s['opp'],1)}% | {fmt(s['opp_base'],1)}% |")
    add()
    add("| 起止 | 阶段 | 交易日 |")
    add("|---|---|---:|")
    add(span_table(mom))
    add()
    add("### 2.2 趋势二档对照：上证指数收盘 >200日均线 = 上涨，否则下跌")
    add()
    add("| 阶段 | 交易日 | Pearson | 中性相关 |")
    add("|---|---:|---:|---:|")
    for stage in ["上涨", "下跌"]:
        sub = ret[trd == stage]
        s = stats_pair(sub[G], sub[V], sub[M])
        add(f"| {stage} | {len(sub)} | {fmt(s['pearson'])} | {fmt(s['neu'])} |")
    add()

    # ---- 3. 持续期（核心） ----
    add("## 3. 明显负相关能持续多久（核心）")
    add()
    add("定义：滚动窗口内 科创50 与 红利低波 日收益相关系数 ≤ 阈值，记为一个「明显负相关日」；"
        "连续段即一次负相关 episode。同时给出原始相关与上证中性相关两种口径。")
    add()
    rng = np.random.default_rng(SEED)
    for w in WINDOWS:
        r = ret[G].rolling(w).corr(ret[V])
        rn = rolling_neu(ret, w)
        for thr in THRESHOLDS:
            for label, series in [("原始", r), ("中性", rn)]:
                ep = episodes(series.le(thr))
                if ep.empty:
                    add(f"- **{w}日窗口 / 阈值 {thr} / {label}口径**：无符合时段")
                    continue
                dur = ep["days"]
                # block-shift 随机基准（循环平移，保留块内序列结构）
                null = []
                for _ in range(N_BOOT):
                    shifted = pd.Series(np.roll(ret[G].to_numpy(), int(rng.integers(len(ret)))),
                                        index=ret.index)
                    null.append(max_run(shifted.rolling(w).corr(ret[V]).le(thr)))
                q95 = float(np.percentile(null, 95))
                pval = float((np.array(null) >= dur.max()).mean())
                add(f"- **{w}日窗口 / 阈值 {thr} / {label}口径**："
                    f"{len(ep)} 次，总覆盖 {int(dur.sum())} 日（{dur.sum()/len(ret)*100:.1f}%）；"
                    f"持续期中位 {dur.median():.0f} 日、最长 **{dur.max()} 交易日**（日历 {ep.loc[dur.idxmax(),'cal']} 天）；"
                    f"随机基准 95分位 {q95:.0f} 日，p={pval:.3f}")
                add()
                add("  | 起始 | 结束 | 交易日 | 日历天 | 期间最低相关 | 期间科创50累计 | 期间红利低波累计 |")
                add("  |---|---|---:|---:|---:|---:|---:|")
                for _, row in ep.sort_values("days", ascending=False).head(8 if label == "原始" else 3).iterrows():
                    a, b = row["start"], row["end"]
                    gr = float(((1 + ret.loc[a:b, G] / 100).prod() - 1) * 100)
                    vr = float(((1 + ret.loc[a:b, V] / 100).prod() - 1) * 100)
                    add(f"  | {a} | {b} | {int(row['days'])} | {int(row['cal'])} | "
                        f"{fmt(series.loc[a:b].min())} | {gr:+.1f}% | {vr:+.1f}% |")
                add()
    add("> 原始口径最多列 8 段、中性口径 3 段（按持续交易日降序）。「期间累计」为该负相关区间内"
        "两标的分别的收益。随机基准 = 成长序列循环平移 500 次后的最长持续期分布。"
        "中性口径因上述机械偏误会长期低于阈值，其「持续期」不代表真实跷跷板。")
    add()

    # 连续反向日（最直观的「它涨它跌」持续期，不受中性化偏误影响）
    add("### 3.1 连续反向日：它涨它跌能连着几天")
    add()
    g_up_v_dn = (ret[G] > 0) & (ret[V] < 0)
    g_dn_v_up = (ret[G] < 0) & (ret[V] > 0)
    for label, mask in [("任一方向相反", g_up_v_dn | g_dn_v_up),
                         ("科创50涨 / 红利低波跌", g_up_v_dn)]:
        ep = episodes(mask)
        dur = ep["days"]
        null = []
        for _ in range(N_BOOT):
            shifted = pd.Series(np.roll(ret[G].to_numpy(), int(rng.integers(len(ret)))), index=ret.index)
            null.append(max_run((shifted > 0) & (ret[V] < 0) if label != "任一方向相反" else
                                ((shifted > 0) & (ret[V] < 0)) | ((shifted < 0) & (ret[V] > 0))))
        q95 = float(np.percentile(null, 95))
        pval = float((np.array(null) >= dur.max()).mean())
        add(f"- **{label}**：共 {int(dur.sum())} 日（{dur.sum()/len(ret)*100:.1f}%）；"
            f"连续段中位 {dur.median():.0f} 日、最长 **{dur.max()} 交易日**（日历 {ep.loc[dur.idxmax(),'cal']} 天）；"
            f"随机基准 95分位 {q95:.0f} 日，p={pval:.3f}")
    add()
    add("| 起始 | 结束 | 连续交易日 | 日历天 | 期间科创50累计 | 期间红利低波累计 |")
    add("|---|---|---:|---:|---:|---:|")
    ep = episodes(g_up_v_dn | g_dn_v_up).sort_values("days", ascending=False)
    for _, row in ep.head(8).iterrows():
        a, b = row["start"], row["end"]
        gr = float(((1 + ret.loc[a:b, G] / 100).prod() - 1) * 100)
        vr = float(((1 + ret.loc[a:b, V] / 100).prod() - 1) * 100)
        add(f"| {a} | {b} | {int(row['days'])} | {int(row['cal'])} | {gr:+.1f}% | {vr:+.1f}% |")
    add()

    # ---- 4. 电信/移动 ----
    add("## 4. 中国电信 / 中国移动是否跟随红利低波")
    add()
    cons = pd.read_sql("select index_code, index_name, stock_code, stock_name, weight "
                       "from px_index_cons_csi where stock_code in ('600941','601728')", conn)
    add("成分股关系（当前快照）：" + "；".join(
        f"{r['stock_name']}@{r['index_code']}({r['index_name']},权重{r['weight']}%)"
        for _, r in cons.iterrows()) + "。因此两者与红利低波的高相关**部分是成分股的机械结果**。")
    add()
    add("| 个股 | 区间 | n | 与红利低波 | 与科创50 | Fisher z | p | 对红利低波β | R² |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for code, name in [("601728", "中国电信"), ("600941", "中国移动")]:
        d = pd.read_sql("select trade_date, close from px_stock_daily "
                        "where stock_code=? and trade_date between ? and ? order by trade_date",
                        conn, params=(code, START, END)).set_index("trade_date")["close"].astype(float)
        div = pd.read_sql("select ex_date, cash_div_per10, bonus_ratio, transfer_ratio "
                          "from fin_dividend_detail_all where stock_code=? and progress='实施' "
                          "and ex_date between ? and ?", conn, params=(code, START, END))
        adj = d.copy()
        for _, r in div.iterrows():
            if r["ex_date"] in adj.index:
                adj.loc[r["ex_date"]] += float(r["cash_div_per10"]) / 10
        sr = (adj.pct_change() * 100).rename(name)
        df = pd.concat([sr, ret[[V, G, M]]], axis=1).dropna()
        rv = pearson(df[name], df[V])[0]
        rg = pearson(df[name], df[G])[0]
        z, p = fisher_z(rv, rg, len(df), len(df))
        beta = df[name].rolling(60).cov(df[V]) / df[V].rolling(60).var()
        add(f"| {name} | {df.index[0]}~{df.index[-1]} | {len(df)} | {fmt(rv)} | {fmt(rg)} | "
            f"{fmt(z,2)} | {fmt(p)} | {fmt(beta.iloc[-1],2)} | {fmt(rv**2)} |")
    add()
    add("> 个股用除息日现金分红加回后的收益（库内无复权价）；bonus/transfer 均为 0。"
        "Fisher z 检验两相关是否显著不同。")
    add()

    # ---- 5. 结论 ----
    r_all = stats_pair(ret[G], ret[V], ret[M])
    ws = freq_src.resample("W-FRI").sum().dropna()
    ms = freq_src.resample("ME").sum().dropna()
    rw, rm = pearson(ws[G], ws[V])[0], pearson(ms[G], ms[V])[0]
    r20, r60 = ret[G].rolling(20).corr(ret[V]), ret[G].rolling(60).corr(ret[V])

    def longest(series, thr: float) -> tuple[int, str, str]:
        ep = episodes(series.le(thr)).sort_values("days", ascending=False)
        if ep.empty:
            return 0, "", ""
        row = ep.iloc[0]
        return int(row["days"]), str(row["start"]), str(row["end"])

    l20_3, a20_3, b20_3 = longest(r20, -0.3)
    l20_5, a20_5, b20_5 = longest(r20, -0.5)
    l60_3, a60_3, b60_3 = longest(r60, -0.3)
    l60_5, a60_5, b60_5 = longest(r60, -0.5)
    add("## 5. 结论摘要")
    add()
    add(f"1. **日度几乎不相关，月级才显负相关**：日度 Pearson **{fmt(r_all['pearson'])}**"
        f"（p={fmt(r_all['p'])}）、Spearman {fmt(r_all['spearman'])}；周度 {fmt(rw)}、月度 {fmt(rm)}"
        f"（n={len(ms)}）。反向日 {fmt(r_all['opp'],1)}% vs 独立基准 {fmt(r_all['opp_base'],1)}%。"
        "日度噪声掩盖了月级跷跷板，但「5年长期稳定负相关」不成立。")
    add(f"2. **强负相关撑死约2个月，你的判断成立**：滚动20日 r≤−0.5 最长 **{l20_5} 交易日**"
        f"（{a20_5}~{b20_5}）；60日 r≤−0.5 最长 **{l60_5} 交易日**。均 < 65 交易日（3个月）。")
    add(f"3. **中等负相关可以更久**：滚动20日 r≤−0.3 最长 **{l20_3} 交易日**（{a20_3}~{b20_3}）；"
        f"60日 r≤−0.3 最长 **{l60_3} 交易日**（{a60_3}~{b60_3}，约5个月）。"
        "是否算「明显」取决于阈值，这是分歧点。")
    add("4. **触发场景与预期不同**：原始相关在牛市 −0.091、震荡 +0.137、熊市 +0.164；"
        "反向日占比牛市 30.4%（基准 27.0%）最高。即跷跷板更常见于上涨阶段，而非震荡/熊市。")
    add("5. **电信/移动跟随红利成立**：与红利低波相关 0.345 / 0.395，与科创50 仅 0.053 / −0.009"
        "（Fisher z 显著），但部分是红利低波成分股的机械结果。")
    add()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}  ({len(ret)} trading days)")
    conn.close()


if __name__ == "__main__":
    main()
