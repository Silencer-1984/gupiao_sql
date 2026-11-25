# -*- coding: utf-8 -*-
"""
备用金加码定投（机会成本口径）：常规每月 5000 + 每年 20000 备用金池。

用户口径（真实场景）：
  - 常规每月 15 号投 5000 —— 这是**唯一的投资成本**
  - 备用金每年 20000（每月 1666.67）：本来是要花掉的钱（消费成商品），
    **不计入投资成本**；大跌时才从消费里省下来补进股市
  - 没触发大跌 → 钱花掉了，期末资产里没有这部分（不进分子）
  - 综合收益 = 期末股票市值 / (5000 × 月数) − 1   ← 分母只有常规投入

对照：
  A 纯常规无脑       只投 5000/月，无备用金（基准）
  B 备用金全程投     1666.67/月全额无脑买入（免费资金上限，不计成本）
  C1 回撤温和        回撤≤-10%补池1/4、-20%补1/2、-30%补全部
  C2 回撤激进        回撤≤-5%补1/4、-15%补1/2、-25%补全部
  C3 VXN共振         回撤≤-10%且VXN分位≥70补全部；仅回撤≤-10%补1/4
  C4 纯VXN分位       VXN分位≥90补全部、≥70补1/2、≤30补1/4

标的 .NDX；VXN 来自 mkt_vol_vxn（Cboe 官方）。
随机起点 + 5~9 年窗口，N=2000，seed=20261124。
输出：strategies/01_nasdaq_dca/backtest_reserve_fund.md（单份报告）
"""
import os
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "strategies", "01_nasdaq_dca", "backtest_reserve_fund.md")

BASE = 5000.0
RESERVE_YEAR = 20000.0
RESERVE_MONTH = RESERVE_YEAR / 12
N_SIM = 2000
HORIZONS = [60, 72, 84, 96, 108]
BUY_DAY = 15
SEED = 20261124

NAMES = ["A纯常规无脑", "B备用金全程投", "C1回撤温和", "C2回撤激进", "C3 VXN共振", "C4纯VXN分位"]


def load():
    c = sqlite3.connect(DB)
    ndx = pd.read_sql(
        "select trade_date, close from px_index_daily_us "
        "where index_code='.NDX' and close is not null order by trade_date",
        c, parse_dates=["trade_date"]).set_index("trade_date")["close"].astype(float)
    vxn = pd.read_sql(
        "select trade_date, close from mkt_vol_vxn order by trade_date",
        c, parse_dates=["trade_date"]).set_index("trade_date")["close"].astype(float)
    c.close()
    return ndx, vxn


def prep(ndx, vxn):
    df = pd.DataFrame({"px": ndx})
    df["peak250"] = df.px.rolling(250, min_periods=250).max()
    df["dd"] = (df.px / df.peak250 - 1) * 100
    df["vxn"] = vxn.reindex(df.index)
    v = df.vxn.values
    pct = np.full(len(v), np.nan)
    W = 1250
    for i in range(len(v)):
        if np.isnan(v[i]):
            continue
        w = v[max(0, i - W + 1):i + 1]
        w = w[~np.isnan(w)]
        if len(w):
            pct[i] = (w <= v[i]).mean() * 100
    df["vp"] = pct
    return df


def buy_dates(idx, start_month, months):
    out = []
    for k in range(months):
        m = (start_month + pd.offsets.MonthBegin(k)).replace(day=1)
        target = m.replace(day=BUY_DAY)
        cand = idx[idx >= target]
        cand = cand[cand < m + pd.offsets.MonthBegin(1)]
        if not len(cand):
            cand = idx[idx >= target][:1]
        if not len(cand):
            return None
        out.append(cand[0])
    return pd.DatetimeIndex(out)


def reserve_fraction(st, dd, vp):
    """本月补入池子的比例（0~1）。"""
    if st <= 1:
        return 0.0
    if np.isnan(dd) and st in (2, 3):
        return 0.0
    if st == 2:    # 回撤温和
        if dd <= -30: return 1.0
        if dd <= -20: return 0.5
        if dd <= -10: return 0.25
        return 0.0
    if st == 3:    # 回撤激进
        if dd <= -25: return 1.0
        if dd <= -15: return 0.5
        if dd <= -5:  return 0.25
        return 0.0
    if st == 4:    # VXN 共振
        if np.isnan(dd) or np.isnan(vp): return 0.0
        if dd <= -10 and vp >= 70: return 1.0
        if dd <= -10: return 0.25
        return 0.0
    if st == 5:    # 纯 VXN 分位
        if np.isnan(vp): return 0.0
        if vp >= 90: return 1.0
        if vp >= 70: return 0.5
        if vp <= 30: return 0.25
        return 0.0
    return 0.0


def simulate(prices, dds, vps, n):
    """返回 (期末股票市值, 路径, 备用金已用, 备用金额度, 补入月数)。
    未动用备用金视作已消费，不计入期末资产。"""
    out = []
    for st in range(len(NAMES)):
        sh = 0.0
        reserve = 0.0          # 未动用池子（期末清零，视作消费）
        used = 0.0
        total = 0.0
        add_months = 0
        path = []
        for k in range(n):
            sh += BASE / prices[k]
            if st == 0:
                pass
            elif st == 1:
                sh += RESERVE_MONTH / prices[k]
                total += RESERVE_MONTH
                used += RESERVE_MONTH
            else:
                reserve += RESERVE_MONTH
                total += RESERVE_MONTH
                frac = reserve_fraction(st, dds[k], vps[k])
                if frac > 0 and reserve > 0:
                    amt = reserve * frac
                    sh += amt / prices[k]
                    reserve -= amt
                    used += amt
                    add_months += 1
            path.append(sh * prices[k])   # 未用备用金已消费，不进资产
        out.append((path[-1], np.array(path), used, total, add_months))
    return out


def main():
    ndx, vxn = load()
    df = prep(ndx, vxn)
    idx = ndx.index
    months = pd.date_range(idx.min().normalize(), idx.max().normalize(), freq="MS")
    rng = np.random.default_rng(SEED)

    rows = []
    for _ in range(N_SIM):
        L = int(rng.choice(HORIZONS))
        if len(months) - L - 1 < 2:
            continue
        si = int(rng.integers(0, len(months) - L))
        ds = buy_dates(idx, months[si], L)
        if ds is None or len(ds) != L:
            continue
        d = df.loc[ds]
        res = simulate(d.px.values, d.dd.values, d.vp.values, L)
        seg = df.loc[(df.index >= ds[0]) & (df.index <= ds[-1]), "px"]
        peak = seg.cummax()
        rec = {
            "start": ds[0].strftime("%Y-%m-%d"), "end": ds[-1].strftime("%Y-%m-%d"),
            "months": L, "mkt_ret": (d.px.values[-1] / d.px.values[0] - 1) * 100,
            "mdd": (seg / peak - 1).min() * 100,
            "exit_dd": (d.px.values[-1] / seg.max() - 1) * 100,
            "entry_vp": d.vp.values[0],
        }
        cost = BASE * L          # 唯一投资成本：常规定投
        for st, (v, path, used, total, addm) in enumerate(res):
            rec[f"v{st}"] = v
            rec[f"ret{st}"] = (v / cost - 1) * 100       # 综合收益（分母只算常规）
            rec[f"used{st}"] = used / total if total else 0.0
            rec[f"add{st}"] = addm / L * 100
            pk = np.maximum.accumulate(path)
            rec[f"pmdd{st}"] = (path / pk - 1).min() * 100
        rows.append(rec)

    res = pd.DataFrame(rows).dropna(subset=["v0"])

    def stat(g, col):
        x = g[col].replace([np.inf, -np.inf], np.nan).dropna()
        return x.mean(), x.median(), x.quantile(0.05), x.quantile(0.95)

    def win(g, st, base):
        return (g[f"v{st}"] > g[f"v{base}"]).mean() * 100

    L = []
    L.append("# 备用金加码定投（机会成本口径）：大跌时从消费里省钱补仓\n")
    L.append(f"> 脚本 `scripts/backtest_reserve_fund.py`　seed={SEED}　N={len(res)} 组\n")
    L.append("## 1. 口径（关键）\n")
    L.append("- **常规每月 15 号投 5000 —— 这是唯一的投资成本**")
    L.append("- 备用金每年 20000（每月 1666.67）：本来要花掉的钱（消费成商品），**不计入投资成本**；")
    L.append("  大跌时才省下来补进股市；没触发就花掉了，期末资产里没有这部分")
    L.append("- **综合收益 = 期末股票市值 / (5000 × 月数) − 1**（分母只有常规投入）")
    L.append("- 对照 B 轨＝备用金全程无脑投（免费资金全部到位，理论上限）；C 轨＝只在跌时补")
    L.append("- 标的 `.NDX`；VXN 来自 Cboe 官方 CSV（与 .NDX 100% 对齐）；随机起点 + 5~9 年窗口\n")

    L.append("## 2. 策略定义\n")
    L.append("| 策略 | 备用金规则 |\n|---|---|")
    L.append("| A 纯常规无脑 | 无备用金，只投 5000/月 |")
    L.append("| B 备用金全程投 | 1666.67/月全额无脑买入（不计成本，免费资金上限）|")
    L.append("| C1 回撤温和 | ≤-10%补池1/4、≤-20%补1/2、≤-30%补全部 |")
    L.append("| C2 回撤激进 | ≤-5%补1/4、≤-15%补1/2、≤-25%补全部 |")
    L.append("| C3 VXN共振 | 回撤≤-10%且VXN分位≥70补全部；仅回撤≤-10%补1/4 |")
    L.append("| C4 纯VXN分位 | ≥90补全部、≥70补1/2、≤30补1/4 |\n")

    def table(g, title):
        L.append(f"### {title}（n={len(g)}）\n")
        L.append("| 策略 | 综合收益均值 | 中位 | 较A提升 | 胜A | 胜B | 备用金动用率 | 补入月占比 | 组合MDD |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        a = stat(g, "ret0")[0]
        for st, name in enumerate(NAMES):
            rm, rmd, _, _ = stat(g, f"ret{st}")
            um, _, _, _ = stat(g, f"used{st}")
            am, _, _, _ = stat(g, f"add{st}")
            mm, _, _, _ = stat(g, f"pmdd{st}")
            wa = "—" if st == 0 else f"{win(g, st, 0):.1f}%"
            wb = "—" if st <= 1 else f"{win(g, st, 1):.1f}%"
            L.append(f"| {name} | {rm:.2f}% | {rmd:.2f}% | " +
                     ("—" if st == 0 else f"+{rm-a:.2f}pp") +
                     f" | {wa} | {wb} | {um*100:.1f}% | {am:.1f}% | {mm:.2f}% |")
        L.append("")

    L.append("## 3. 全样本\n")
    table(res, "全样本")

    L.append("## 4. 牛熊分组\n")
    table(res[res.exit_dd <= -20], "终点仍在熊市（离高点≤-20%）")
    table(res[res.exit_dd > -2], "终点创新高（离高点>-2%）")
    table(res[res.mdd <= -30], "窗口内深回撤（MDD≤-30%）")
    table(res[res.entry_vp >= 70], "VXN高位入场（起点分位≥70）")
    table(res[res.entry_vp <= 30], "VXN低位入场（起点分位≤30）")

    L.append("## 5. 结论\n")
    means = [stat(res, f"ret{k}")[0] for k in range(len(NAMES))]
    L.append("- 全样本综合收益均值：" + " / ".join(f"{n} {m:.2f}%" for n, m in zip(NAMES, means)))
    L.append("- C 轨综合收益必然高于 A：因为备用金是白来的钱（不进分母），只要补仓就提升期末市值。")
    L.append("  真正的问题是「择时补 vs 全程投」——对照 B 轨。")
    for st in range(2, len(NAMES)):
        L.append(f"- {NAMES[st]}：较 A +{means[st]-means[0]:.2f}pp，胜 B {win(res, st, 1):.1f}%，"
                 f"备用金动用率 {stat(res, f'used{st}')[0]*100:.1f}%")
    L.append("- 没触发的备用金视作消费掉、不计入资产；因此动用率越低，白来的钱浪费越多，综合收益越接近 A。\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("报告已写:", OUT)
    print("样本:", len(res))
    for st, name in enumerate(NAMES):
        m, _, _, _ = stat(res, f"ret{st}")
        u, _, _, _ = stat(res, f"used{st}")
        print(f"{name:<14} 综合收益 {m:>6.2f}%  动用率 {u*100:>5.1f}%  胜B "
              f"{'—' if st<=1 else f'{win(res,st,1):.1f}%'}")


if __name__ == "__main__":
    main()
