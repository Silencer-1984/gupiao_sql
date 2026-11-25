# -*- coding: utf-8 -*-
"""
策略一（回撤阶梯加码）与策略二（均线偏离 + VXN 共振）随机窗口回测。

标的 .NDX；每月固定日投 5000，钱先进现金池，按信号决定本月买多少；
池子超过 3 期（15000）强制投出，避免资金长期停摆。

策略一 回撤阶梯加码：按标的距 250 日峰值的回撤 d 分档
  D1 温和  0/1/2/3/4 倍：d>-5% 投0、[-10,-5) 投1、[-20,-10) 投2、[-30,-20) 投3、<=-30 投4
  D2 激进  0/1/2/4/6 倍
  D3 只加不减（任何回撤至少投 1 倍，深回撤加码）：1/1.5/2/3/4

策略二 均线偏离 + VXN 共振（两个条件同时满足才加码）：
  偏离 = 收盘/MA200 - 1；恐慌 = VXN 绝对阈值 或 滚动5年分位
  S1 共振严格：偏离<=-10% 且 VXN分位>=70 → 3倍；否则偏离档位单独生效(最高2倍)
  S2 共振宽松：偏离<=-10% 或 (VXN分位>=80 且 偏离<0) → 2倍
  S3 纯VXN分位（对照）：>=90→3倍, >=70→2倍, <=20→0.5倍

分组：全样本 / 起点高位 / 起点低位 / 终点熊市 / 终点创新高 / 深回撤。
输出：strategies/01_nasdaq_dca/backtest_drawdown_vxn.md（单份报告）
"""
import os
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "strategies", "01_nasdaq_dca", "backtest_drawdown_vxn.md")

BASE = 5000.0
CASH_CAP = 3 * BASE
N_SIM = 2000
HORIZONS = [60, 72, 84, 96, 108]
BUY_DAY = 15
SEED = 20261124

STRATS = ["无脑定投", "D1温和阶梯", "D2激进阶梯", "D3只加不减",
          "S1严格共振", "S2宽松共振", "S3纯VXN分位"]


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
    df["ma200"] = df.px.rolling(200, min_periods=200).mean()
    df["peak250"] = df.px.rolling(250, min_periods=250).max()
    df["dd"] = (df.px / df.peak250 - 1) * 100          # 负值=回撤
    df["dev"] = (df.px / df.ma200 - 1) * 100            # 均线偏离
    # 先把 VXN 对齐到 .NDX 交易日，再算分位（长度必须一致）
    df["vxn"] = vxn.reindex(df.index)
    v = df.vxn.values
    pct = np.full(len(v), np.nan)
    W = 1250
    for i in range(len(v)):
        if np.isnan(v[i]):
            continue
        valid = v[max(0, i - W + 1):i + 1]
        valid = valid[~np.isnan(valid)]
        if len(valid):
            pct[i] = (valid <= v[i]).mean() * 100
    df["vxn_pct"] = pct
    return df


def buy_dates(idx, start_month, months):
    out = []
    for k in range(months):
        m = (start_month + pd.offsets.MonthBegin(k)).replace(day=1)
        target = m.replace(day=BUY_DAY)
        cand = idx[idx >= target]
        nxt = m + pd.offsets.MonthBegin(1)
        cand = cand[cand < nxt]
        if not len(cand):
            cand = idx[idx >= target][:1]
        if not len(cand):
            return None
        out.append(cand[0])
    return pd.DatetimeIndex(out)


def tier_mult(st, dd, dev, vp):
    """返回本月买入倍数。dd/dev/vp 可能为 nan。"""
    if st == 0:
        return 1.0
    if st == 1:   # D1 温和阶梯（按回撤）
        if np.isnan(dd): return 1.0
        if dd > -5:   return 0.0
        if dd > -10:  return 1.0
        if dd > -20:  return 2.0
        if dd > -30:  return 3.0
        return 4.0
    if st == 2:   # D2 激进阶梯
        if np.isnan(dd): return 1.0
        if dd > -5:   return 0.0
        if dd > -10:  return 1.0
        if dd > -20:  return 2.0
        if dd > -30:  return 4.0
        return 6.0
    if st == 3:   # D3 只加不减
        if np.isnan(dd): return 1.0
        if dd > -10:  return 1.0
        if dd > -20:  return 1.5
        if dd > -30:  return 2.0
        if dd > -40:  return 3.0
        return 4.0
    if st == 4:   # S1 严格共振
        if np.isnan(dev) or np.isnan(vp): return 1.0
        if dev <= -10 and vp >= 70: return 3.0
        if dev <= -20:  return 2.0
        if dev <= -10:  return 1.5
        if dev > 10:    return 0.5
        return 1.0
    if st == 5:   # S2 宽松共振
        if np.isnan(dev) or np.isnan(vp): return 1.0
        if dev <= -10 or (vp >= 80 and dev < 0): return 2.0
        if dev > 10: return 0.5
        return 1.0
    if st == 6:   # S3 纯 VXN 分位（对照）
        if np.isnan(vp): return 1.0
        if vp >= 90: return 3.0
        if vp >= 70: return 2.0
        if vp <= 20: return 0.5
        return 1.0
    return 1.0


def simulate(prices, dds, devs, vps, n):
    """每条轨返回 (期末总价值, 逐月组合价值, 实际买入额, 暂停次数, 强制次数)。"""
    out = []
    for st in range(len(STRATS)):
        cash = sh = 0.0
        invested = paused = forced = boosted = 0
        path = []
        for k in range(n):
            cash += BASE
            want = BASE * tier_mult(st, dds[k], devs[k], vps[k])
            if cash > CASH_CAP:
                want = max(want, cash - CASH_CAP)
                forced += 1
            buy = min(cash, max(want, 0.0))
            if buy > 0:
                sh += buy / prices[k]
                cash -= buy
                invested += buy
                if buy > BASE * 1.01:
                    boosted += 1
            else:
                paused += 1
            path.append(sh * prices[k] + cash)
        out.append((path[-1], np.array(path), invested, paused, forced, boosted))
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
        px = d.px.values
        res = simulate(px, d.dd.values, d.dev.values, d.vxn_pct.values, L)
        seg = df.loc[(df.index >= ds[0]) & (df.index <= ds[-1]), "px"]
        peak = seg.cummax()
        rec = {
            "start": ds[0].strftime("%Y-%m-%d"), "end": ds[-1].strftime("%Y-%m-%d"),
            "months": L, "mkt_ret": (px[-1] / px[0] - 1) * 100,
            "mdd": (seg / peak - 1).min() * 100,
            "exit_dd": (px[-1] / seg.max() - 1) * 100,
            "entry_pct": d.vxn_pct.values[0],
        }
        for st, (v, path, inv, paused, forced, boosted) in enumerate(res):
            rec[f"v{st}"] = v
            rec[f"ret{st}"] = (v / (BASE * L) - 1) * 100
            rec[f"deploy{st}"] = inv / (BASE * L)
            rec[f"paused{st}"] = paused / L * 100
            rec[f"forced{st}"] = forced / L * 100
            rec[f"boosted{st}"] = boosted / L * 100
            pk = np.maximum.accumulate(path)
            rec[f"pmdd{st}"] = (path / pk - 1).min() * 100
        rows.append(rec)

    res = pd.DataFrame(rows).dropna(subset=["v0"])

    def stat(g, col):
        x = g[col].replace([np.inf, -np.inf], np.nan).dropna()
        return x.mean(), x.median(), x.quantile(0.05), x.quantile(0.95)

    def win(g, st):
        return (g[f"v{st}"] > g["v0"]).mean() * 100

    L = []
    L.append("# 回撤阶梯加码 & 均线偏离+VXN 共振：随机窗口回测\n")
    L.append(f"> 脚本 `scripts/backtest_drawdown_vxn.py`　seed={SEED}　N={len(res)} 组\n")
    L.append("## 1. 数据与口径\n")
    L.append("- 标的 `.NDX` 2014-02~2026-11；VXN 来自 Cboe 官方 CSV（`mkt_vol_vxn`，2009-09 起，与 .NDX 100% 对齐）")
    L.append("- 每月 15 号（顺延）投 5000，钱先入现金池；池子 >15000 强制投出；未投的钱不计时（保守口径）")
    L.append("- 随机起点 + 5~9 年窗口（60/72/84/96/108 月）")
    L.append("- 回撤 = 收盘 / 250日峰值 − 1；均线偏离 = 收盘 / MA200 − 1；VXN 分位 = 滚动 5 年\n")

    L.append("## 2. 策略定义\n")
    L.append("| 策略 | 规则 |\n|---|---|")
    L.append("| D1 温和阶梯 | 回撤 >-5%投0；-5~-10%投1倍；-10~-20%投2倍；-20~-30%投3倍；<-30%投4倍 |")
    L.append("| D2 激进阶梯 | 同 D1，深档提到 4/6 倍 |")
    L.append("| D3 只加不减 | 浅回撤也投1倍；-10~-20%投1.5；-20~-30%投2；更深 3/4 倍 |")
    L.append("| S1 严格共振 | 偏离≤-10% 且 VXN分位≥70 → 3倍；否则偏离≤-20%投2、≤-10%投1.5、>10%投0.5 |")
    L.append("| S2 宽松共振 | 偏离≤-10% 或 (VXN分位≥80 且偏离<0) → 2倍；偏离>10% 投0.5 |")
    L.append("| S3 纯VXN分位 | ≥90投3、≥70投2、≤20投0.5（对照，不看均线）|\n")

    def table(g, title):
        L.append(f"### {title}（n={len(g)}）\n")
        L.append("| 策略 | 总收益均值 | 胜基准 | 部署率 | 真实加码月 | 暂停月 | 组合MDD |")
        L.append("|---|---:|---:|---:|---:|---:|---:|")
        for st, name in enumerate(STRATS):
            rm, rmd, _, _ = stat(g, f"ret{st}")
            dm, _, _, _ = stat(g, f"deploy{st}")
            pm, _, _, _ = stat(g, f"paused{st}")
            bm, _, _, _ = stat(g, f"boosted{st}")
            mm, _, _, _ = stat(g, f"pmdd{st}")
            L.append(f"| {name} | {rm:.2f}% | {'—' if st==0 else f'{win(g,st):.1f}%'} | "
                     f"{dm*100:.1f}% | {bm:.1f}% | {pm:.1f}% | {mm:.2f}% |")
        L.append("")

    L.append("## 3. 全样本\n")
    table(res, "全样本")

    L.append("## 4. 牛熊分组\n")
    table(res[res.exit_dd <= -20], "终点仍在熊市（离高点≤-20%）")
    table(res[res.exit_dd > -2], "终点创新高（离高点>-2%）")
    table(res[res.entry_pct >= 70], "VXN高位入场（起点分位≥70）")
    table(res[res.entry_pct <= 30], "VXN低位入场（起点分位≤30）")
    table(res[res.mdd <= -30], "窗口内深回撤（MDD≤-30%）")

    L.append("## 5. 结论\n")
    means = [stat(res, f"ret{k}")[0] for k in range(len(STRATS))]
    wins = [win(res, k) for k in range(1, len(STRATS))]
    L.append(f"- 全样本总收益均值：{' / '.join(f'{n} {m:.2f}%' for n, m in zip(STRATS, means))}")
    L.append(f"- 相对无脑的胜率：{' / '.join(f'{n} {w:.1f}%' for n, w in zip(STRATS[1:], wins))}")
    L.append("- 阶梯加码的资金来自「原本要投的钱」后移，不是外部增量；深跌时加码的收益来自低位多买，")
    L.append("  代价是上涨时空仓（暂停月）。看结果时务必同时看部署率、真实加码月与暂停月占比。")
    bd = [stat(res, f"boosted{k}")[0] for k in range(len(STRATS))]
    L.append(f"- 真实加码月占比：{' / '.join(f'{n} {b:.1f}%' for n, b in zip(STRATS, bd))}")
    L.append("  D3「只加不减」没有暂停月、也几乎没有真实加码月 → 等于无脑定投，这个结果符合预期：")
    L.append("  没有暂停就没有多余弹药，加码幅度被现金池上限（3 期）锁死。")
    L.append("- VXN 共振类策略在恐慌高位加码，若 VXN 高位常对应长期底部则有效；否则只增加空仓时间。\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("报告已写:", OUT)
    print("样本:", len(res))
    for st, name in enumerate(STRATS):
        m, _, _, _ = stat(res, f"ret{st}")
        d, _, _, _ = stat(res, f"deploy{st}")
        print(f"{name:<12} 收益 {m:>6.2f}%  部署 {d*100:>5.1f}%  胜基准 "
              f"{'—' if st==0 else f'{win(res,st):.1f}%'}")


if __name__ == "__main__":
    main()
