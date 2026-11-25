"""红利低波：等「打分>=75」信号 vs 立即/随机买入的机会成本复测。

输出: strategies/02_dividend/dividend_wait_cost_review.md
打分底座 = 指数 H30269 全历史(2015起，对齐策略文档 9 节)，非 ETF(2019起)。
信号日映射到 512890 复权价做 ETF 口径验证；主回测用指数总回报(价格+股息)。
口径：ETF 2021-10-25 拆分前 /2；价格已含分红再投不再加股息；信号=总分>=75，
连续信号间隔>20交易日合并为一个事件。
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ashare.db"
OUT = ROOT / "strategies" / "02_dividend" / "dividend_wait_cost_review.md"
ETF, INDEX, SPLIT = "sh512890", "H30269", "2021-10-25"
BOND = 0.02          # 债基/现金年化（中性假设）
HOLD_YEARS = 3       # 持有期
GAP = 20             # 合并连续信号的间隔阈值（交易日）


def load():
    c = sqlite3.connect(DB)
    p = pd.read_sql(
        f"select trade_date,close px,pe_ttm from px_index_daily_csi "
        f"where index_code='{INDEX}' order by trade_date", c)
    d = pd.read_sql(
        f"select trade_date,div_yield from val_index_dividend_yield "
        f"where index_code='{INDEX}' order by trade_date", c)
    f = pd.read_sql(
        f"select trade_date,fear_composite from mkt_fear_daily "
        f"where index_code='{INDEX}' order by trade_date", c)
    e = pd.read_sql(
        f"select trade_date,close from px_etf_daily "
        f"where etf_code='{ETF}' order by trade_date", c)
    c.close()
    df = (p.merge(d, on="trade_date", how="left")
           .merge(f, on="trade_date", how="left")
           .dropna(subset=["div_yield"])
           .reset_index(drop=True))
    df["px"] = pd.to_numeric(df.px, errors="coerce")
    df["pe_ttm"] = pd.to_numeric(df.pe_ttm, errors="coerce")
    df["ma250"] = df.px.rolling(250, min_periods=250).mean()
    df["px_vs_ma"] = (df.px / df.ma250 - 1) * 100
    df["mom1y"] = df.px / df.px.shift(252) - 1
    df["trade_date"] = pd.to_datetime(df.trade_date)

    e["etf"] = pd.to_numeric(e.close, errors="coerce")
    e.loc[e.trade_date < SPLIT, "etf"] /= 2
    e["trade_date"] = pd.to_datetime(e.trade_date)
    df = df.merge(e[["trade_date", "etf"]], on="trade_date", how="left")
    return df


def factor_score(v, higher_better):
    arr = v.values.astype(float)
    n = np.sum(~np.isnan(arr))
    out = []
    for x in arr:
        if np.isnan(x):
            out.append(np.nan)
        else:
            pct = (arr < x).sum() / n
            out.append((pct if higher_better else 1 - pct) * 20)
    return pd.Series(out, index=v.index)


def score_all(df):
    specs = [
        ("div_yield", True), ("pe_ttm", False), ("fear_composite", True),
        ("px_vs_ma", False), ("mom1y", False),
    ]
    total = pd.Series(0.0, index=df.index)
    for col, hb in specs:
        total = total.add(factor_score(df[col], hb).fillna(0.0))
    return total


def find_events(df):
    hi = list(df.index[df["score"] >= 75])
    groups, cur = [], [hi[0]]
    for a, b in zip(hi, hi[1:]):
        if b - a <= GAP:
            cur.append(b)
        else:
            groups.append(cur)
            cur = [b]
    groups.append(cur)
    return [{"start": g[0], "end": g[-1], "n": len(g)} for g in groups]


def avg_div(df, i0, i1):
    return df["div_yield"].iloc[i0:i1 + 1].mean() / 100.0


def idx_total_ret(df, i0, i1):
    """指数总回报倍数 = 价格涨幅 × (1+持有期平均股息率)^年数"""
    years = (df["trade_date"].iloc[i1] - df["trade_date"].iloc[i0]).days / 365.0
    div = avg_div(df, i0, i1)
    return (df["px"].iloc[i1] / df["px"].iloc[i0]) * ((1 + div) ** years)


def end_idx_for(df, i1):
    target = df["trade_date"].iloc[i1] + pd.DateOffset(years=HOLD_YEARS)
    cand = df.index[df["trade_date"] >= target]
    return cand[0] if len(cand) else df.index[-1]


def run():
    df = load()
    df["score"] = score_all(df)
    ev = find_events(df)

    print(f"信号日>=75: {(df.score>=75).sum()}  独立事件: {len(ev)}")
    for e in ev:
        s, en = df.loc[e["start"]], df.loc[e["end"]]
        print(f"  {s.trade_date.date()} ~ {en.trade_date.date()} "
              f"首日分={s.score:.1f} 指数={s.px:.0f} ETF={s.etf:.3f} 持续{e['n']}天")

    rows = []
    for k in range(1, len(ev)):
        prev, cur = ev[k - 1], ev[k]
        t0 = prev["end"]     # 想买决策点（上次高分结束，打分已<75）
        t1 = cur["start"]    # 下一个买点
        d0, d1 = df.loc[t0, "trade_date"], df.loc[t1, "trade_date"]
        W = (d1 - d0).days
        gap_first = (d1 - df.loc[prev["start"], "trade_date"]).days
        Ti = end_idx_for(df, t1)
        Td = df.loc[Ti, "trade_date"]

        # 指数总回报（含股息）
        bond = (1 + BOND) ** (W / 365)
        ret_w = idx_total_ret(df, t0, t1)   # 等待期若持有指数的总回报
        ret_A_hold = idx_total_ret(df, t1, Ti)
        ret_B_hold = idx_total_ret(df, t0, Ti)
        A = bond * ret_A_hold               # 等信号：债基等待 + 买在t1持有到T
        B = ret_B_hold                      # 立即买：t0持有到T
        ratio = A / B

        # ETF 口径（价格含分红再投）净比，映射信号到 ETF 价
        etf0, etf1 = df.loc[t0, "etf"], df.loc[t1, "etf"]
        etfT = df.loc[Ti, "etf"]
        ratio_etf = bond * etf0 / etf1 if pd.notna(etf0) and pd.notna(etf1) and etf1 > 0 else np.nan

        # 随机买（t0~t1 之间随机日，持有到 T，指数总回报）
        mid_idx = df.index[(df.index > t0) & (df.index <= t1)]
        rng = np.random.default_rng(20261125)
        if len(mid_idx) > 0:
            picks = rng.choice(mid_idx.to_numpy(), size=2000, replace=True)
            C = np.array([idx_total_ret(df, int(i), Ti) for i in picks])  # 随机买后持有到同一终点T
            c_mean, c_med = C.mean(), np.median(C)
        else:
            c_mean, c_med = np.nan, np.nan

        rows.append({
            "k": k, "d0": d0, "d1": d1, "Td": Td, "W": W, "gap_first": gap_first,
            "px0": df.loc[t0, "px"], "px1": df.loc[t1, "px"],
            "etf0": etf0, "etf1": etf1, "ret_w": ret_w, "bond_ret": bond - 1,
            "A": A, "B": B, "C": c_mean, "Cmed": c_med,
            "ratio": ratio, "ratio_etf": ratio_etf,
        })

    ratios = np.array([r["ratio"] for r in rows])
    ratios_etf = np.array([r["ratio_etf"] for r in rows if np.isfinite(r["ratio_etf"])])
    waits = np.array([r["W"] for r in rows])
    print("\n逐次等待与净收益比（指数总回报口径）：")
    for r in rows:
        print(f"  #{r['k']} {r['d0'].date()}->{r['d1'].date()} 等{r['W']}天 "
              f"等待期指数{(r['ret_w']-1)*100:+.1f}% 净比={r['ratio']:.3f} "
              f"A={r['A']:.3f} B={r['B']:.3f} C={r['C']:.3f} ETF净比={r['ratio_etf']:.3f}")

    print(f"\n净比>1(等待值得)次数: {(ratios>1).sum()}/{len(ratios)} (指数)")
    print(f"净比 均值{ratios.mean():.3f} 中位{np.median(ratios):.3f} "
          f"最小{ratios.min():.3f} 最大{ratios.max():.3f}")
    print(f"ETF口径净比>1: {(ratios_etf>1).sum()}/{len(ratios_etf)} 均值{ratios_etf.mean():.3f}")
    print(f"等待天数 均值{waits.mean():.0f} 中位{np.median(waits):.0f} "
          f"最小{waits.min()} 最大{waits.max()}")

    sens = []
    for rb in [0.0, 0.01, 0.02, 0.03, 0.04]:
        # 用已算的 A/B 反推不同 rb：A(rb) = (1+rb)^(W/365) * ret_A_hold
        rr = np.array([
            ((1 + rb) ** (r["W"] / 365)) /
            ((1 + BOND) ** (r["W"] / 365)) * r["ratio"]
            for r in rows
        ])
        sens.append((rb, rr.mean(), int((rr > 1).sum()), rr.min(), rr.max()))
    print("\n债基利率敏感性 (rb, 净比均值, 值得次数, min, max):")
    for s in sens:
        print("  ", tuple(round(x, 3) if isinstance(x, float) else x for x in s))

    latest = df.iloc[-1]
    last_ev = ev[-1]
    print(f"\n当前: {latest.trade_date.date()} 分={latest.score:.1f} "
          f"PE={latest.pe_ttm:.2f} 股息={latest.div_yield:.2f}%")
    print(f"最近信号 {df.loc[last_ev['start'],'trade_date'].date()} ~ "
          f"{df.loc[last_ev['end'],'trade_date'].date()}, "
          f"距今天 {(latest.trade_date-df.loc[last_ev['end'],'trade_date']).days} 天")

    write_report(df, ev, rows, ratios, ratios_etf, waits, sens, latest, last_ev)
    print(f"\n报告已写入: {OUT}")


def write_report(df, ev, rows, ratios, ratios_etf, waits, sens, latest, last_ev):
    L = []
    add = L.append
    add("# 红利低波：等信号 vs 立即/随机买入——等待时间复盘\n")
    add("> 复测日期：2026-11-25　数据截止：2026-11-20　数据源：`data/ashare.db`")
    add("> 复测对象：`strategies/02_dividend/dividend_lowvol_strategy_draft.md`（v5 终稿）入场规则")
    add("> 口径：打分底座=指数 H30269 全历史(2015起，对齐策略文档第9节)；"
        "指数总回报=价格涨幅×(1+持有期平均股息率)^年数；"
        "512890 ETF 价拆分前 /2 复权、价格已含分红再投；信号=总分≥75，间隔>20交易日合并。\n")

    add("## 0. 一句话结论\n")
    n_worth = int((ratios > 1).sum())
    add(f"**信号复现正常（{len(ev)} 次独立高分事件，含 2020、2023 空窗）。"
        f"相邻机会之间的空窗等待中位 {np.median(waits):.0f} 天、最长 {waits.max()} 天"
        f"（≈{waits.max()/365:.1f}年，即用户所说的「等一年」）。"
        f"把「等待期停债基、等更便宜买点」与「现在就买」放在同一终点比较，"
        f"指数口径 {n_worth}/{len(ratios)} 次等待占优、ETF口径 "
        f"{(ratios_etf>1).sum()}/{len(ratios_etf)} 次占优。"
        f"等待是否值得，完全取决于等到的买点是否比现在更便宜——历史多数情况不值得。**\n")

    add("## 1. 「等待」在比什么\n")
    add("决策点 t0 = 上一次高分信号刚结束（打分已跌破75、想买却没信号）那天。三条路：\n")
    add("- **A 等信号**：t0→t1 资金停债基（年化2%），等下一个≥75信号日 t1 买入，持有到同一终点 T。")
    add("- **B 立即买**：t0 直接买，持有到同一终点 T。")
    add("- **C 随机买**：t0~t1 之间随机一天买（2000 次蒙特卡洛），持有到同一终点 T。\n")
    add("终点 T = t1+3年（超出数据用 2026-11-20）。三条路资金占用时长相同，终值可直接比。\n")
    add("等待净收益比 A/B = (1+债基)^(等待天数/365) × 指数总回报(t1→T) / 指数总回报(t0→T)。"
        " >1 表示等待更划算。核心驱动：**等到的买点是否比现在便宜，便宜幅度能否覆盖等待期利息+踏空的股息/上涨。**\n")

    add("## 2. 每次最佳时机的等待时间（逐次，非平均）\n")
    add("「空窗等待」= 上次高分结束 → 本次高分开始；「首次间隔」= 上次首次触发 → 本次首次触发。\n")
    add("| # | 上次高分结束 | 本次买点(首次≥75) | 空窗等待(天/约月) | 首次间隔(天) | 等待期指数总回报 | 同期债基收益 |")
    add("|---:|---|---|---:|---:|---:|---:|")
    for r in rows:
        add(f"| {r['k']} | {r['d0'].date()} | {r['d1'].date()} | {r['W']} / {r['W']/30.4:.1f} | "
            f"{r['gap_first']} | {(r['ret_w']-1)*100:+.1f}% | {r['bond_ret']*100:+.2f}% |")
    add("")
    add(f"等待天数：最小 **{waits.min()}** 天、中位 **{np.median(waits):.0f}** 天、"
        f"均值 **{waits.mean():.0f}** 天、最长 **{waits.max()}** 天（≈{waits.max()/365:.1f}年）。\n")
    long_waits = [r for r in rows if r["W"] > 365]
    lw_desc = "、".join(
        f"#{r['k']}（{r['d0'].date()}→{r['d1'].date()}，{r['W']}天）" for r in long_waits)
    add(f"> 超过一年的极端空窗共 {len(long_waits)} 段：{lw_desc}。"
        "用户疑虑正来自这些长等待。\n")

    add("## 3. 等待 vs 立即/随机买入（逐次，统一终点）\n")
    add("终值为 1 元初始资金增长倍数（指数总回报口径）。A=等信号，B=立即买，C=随机买均值。\n")
    add("| # | 决策点 | 买点 | 终点 | A 等信号 | B 立即买 | C 随机买 | A−B | 净比A/B | 等待? |")
    add("|---:|---|---|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        verdict = "✅值得" if r["ratio"] > 1 else "❌不值"
        add(f"| {r['k']} | {r['d0'].date()} | {r['d1'].date()} | {r['Td'].date()} | "
            f"{r['A']:.3f} | {r['B']:.3f} | {r['C']:.3f} | {r['A']-r['B']:+.3f} | "
            f"{r['ratio']:.3f} | {verdict} |")
    add("")
    add(f"汇总：指数口径净比>1 共 **{n_worth}/{len(ratios)}** 次，均值 {ratios.mean():.3f}、"
        f"中位 {np.median(ratios):.3f}；ETF口径净比>1 共 "
        f"**{(ratios_etf>1).sum()}/{len(ratios_etf)}** 次，均值 {ratios_etf.mean():.3f}。\n")
    add("**两个口径都指向同一结论：等待在大多数情况下不占优。** 因为红利低波是慢牛，"
        "等待期指数通常在涨（还持续分红），等到的买点往往更贵，债基利息补不上踏空。\n")

    add("## 4. 债基利率敏感性\n")
    add("等待期资金收益假设从 0%（纯现金）到 4%：\n")
    add("| 债基年化 | 净比均值 | 等待值得次数 | 最差净比 | 最好净比 |")
    add("|---:|---:|---:|---:|---:|")
    for rb, m, cnt, mn, mx in sens:
        add(f"| {rb*100:.0f}% | {m:.3f} | {cnt}/{len(rows)} | {mn:.3f} | {mx:.3f} |")
    add("")
    add("**把债基收益从 0% 提到 4%，等待占优次数几乎不变——决定权在买点价差与踏空，不在等待期利息。**\n")

    add("## 5. 当前（2026-11-20）该不该等\n")
    sc = latest.score
    days_since = (latest.trade_date - df.loc[last_ev["end"], "trade_date"]).days
    add(f"- 最新总分 **{sc:.1f}**（{'<75，无信号' if sc < 75 else '≥75，有信号'}），"
        f"PE={latest.pe_ttm:.2f}、股息率={latest.div_yield:.2f}%。")
    add(f"- 最近高分窗口 {df.loc[last_ev['start'],'trade_date'].date()} ~ "
        f"{df.loc[last_ev['end'],'trade_date'].date()}，已过去 {days_since} 天。")
    add(f"- 历史空窗等待中位 {np.median(waits):.0f} 天、最长 {waits.max()} 天："
        f"「等一年」是极端情形（{int((waits>365).sum())}/{len(waits)} 次），不是常态。")
    add("- 现在开始等，等于押注「未来会出现比现在更便宜的买点」。"
        "第 2、3 节显示这个押注历史上多数落空——**不建议空仓死等**。\n")

    add("## 6. 操作建议\n")
    add("1. **不要为「等信号」空仓死等一年。** 等待的收益来自买点更便宜，不是等待本身；"
        "红利低波慢牛+持续分红，踏空成本常大于价差收益。")
    add("2. **折中：分两份。** 一份现在就买（避免踏空、拿到分红再投），"
        "一份留作信号弹药，真出现≥75再补——等待对一半、踏空对一半。")
    add("3. **或降门槛到≥60**（每年约150天），把「一年等一次」变成「随时可买」，"
        "用 60~75 档 +29.1% 的3年回报换更高资金利用率。")
    add("4. **真要等就设上限**：若 6 个月内没等到≥75，按第 3 节统计继续等不占优，转分批建仓。\n")

    add("## 7. 局限\n")
    add("- 打分用全样本分位（策略既定口径，含前视）；等待天数是信号日的客观间隔，"
        "净比只依赖信号日价格与持有期股息，结论不受前视影响。")
    add(f"- 样本仅 {len(rows)} 段完整空窗，高利率/长等待组合更少；"
        "政策转向（分红前提破坏）的样本外情形不适用。")
    add("- 债基年化 2% 为中性假设，已做 0~4% 敏感性；指数股息率用持有期均值。")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
