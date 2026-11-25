# -*- coding: utf-8 -*-
"""
纳指100（.NDX）四类进阶定投策略 vs 无脑定投：随机起点蒙特卡洛。

四类策略 + 基准：
  0 无脑定投      每月固定 5000 元买入（固定日期）
  1 价值平均      目标市值每月 +5000，低于目标补买、高于目标卖出（资金从现金池进出）
  2 估值分位      用价格历史分位代替 PE：<30% 投 2 倍 / 30~70% 投 1 倍 / >70% 暂停
  3 均线偏离      200 日均线偏离度分 5 档：-20%以下 3 倍 / -20~-10% 2 倍 / ±10% 1 倍
                  / +10~20% 0.5 倍 / +20% 以上暂停
  4 纪律化止盈    每月 5000 买入，浮盈达 +30% 卖出一半并重置成本
  5 组合再平衡    股债 50/50，每月 5000 入现金池，每年再平衡一次

统一口径（保证可比）：
  - 每条轨每月外部现金流都是 5000 元，未投入的钱躺在现金池，年化 3%（月复利）
  - 最终价值 = 股票市值 + 现金池；因此可直接比最终价值 / 总收益率 / IRR
  - 买入日为每月固定日（15 号或顺延到下一交易日），六条轨完全相同
  - 随机起点 + 随机 5~9 年窗口，N_SIM 组；按牛/熊与最大回撤分组统计

输出：只打印到 stdout，由调用方写入 strategies/01_nasdaq_dca/backtest_4strategies_ndx.md
"""
import os
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")

BUDGET = 5000.0
CASH_ANNUAL = 0.03
RM = (1 + CASH_ANNUAL) ** (1 / 12) - 1
N_SIM = 2000
HORIZONS = [60, 72, 84, 96, 108]   # 5~9 年
BUY_DAY = 15
SEED = 20261123

NAMES = ["无脑定投", "价值平均", "估值分位", "均线偏离", "纪律止盈", "组合再平衡"]


def load():
    c = sqlite3.connect(DB)
    df = pd.read_sql(
        "select trade_date, close from px_index_daily_us "
        "where index_code='.NDX' and close is not null order by trade_date",
        c, parse_dates=["trade_date"])
    c.close()
    s = df.set_index("trade_date")["close"].astype(float)
    return s


def prep(s):
    """MA200 + 价格分位。
    pct  : expanding 全历史分位（诊断用，长期牛市会永远高位）
    pct5 : 滚动 5 年（1250 交易日）分位——策略实际使用，避免单边牛市下永远不买
    """
    ma200 = s.rolling(200, min_periods=200).mean()
    arr = s.values
    pct = np.empty(len(arr))
    pct5 = np.empty(len(arr))
    W = 1250
    for i in range(len(arr)):
        w_all = arr[:i + 1]
        pct[i] = (w_all <= arr[i]).mean() * 100
        w5 = arr[max(0, i - W + 1):i + 1]
        pct5[i] = (w5 <= arr[i]).mean() * 100
    return pd.DataFrame({"close": s, "ma200": ma200, "pct": pct, "pct5": pct5})


def buy_dates(idx, start_month, months):
    """每月固定 BUY_DAY（遇非交易日顺延），返回 DatetimeIndex。"""
    out = []
    for k in range(months):
        m = (start_month + pd.offsets.MonthBegin(k)).replace(day=1)
        target = m.replace(day=BUY_DAY)
        cand = idx[idx >= target]
        if not len(cand):
            return None
        # 限定在当月内，避免跨月取到下个月
        nxt = m + pd.offsets.MonthBegin(1)
        cand = cand[cand < nxt]
        if not len(cand):
            cand = idx[idx >= target][:1]
        if not len(cand):
            return None
        out.append(cand[0])
    return pd.DatetimeIndex(out)


def irr_monthly(flows):
    """二分法求月度 IRR；flows[-1] 为期末价值（正）。返回年化 %。"""
    lo, hi = -0.90, 2.0
    def npv(r):
        v = 0.0
        for k in range(len(flows) - 1, -1, -1):   # 从后往前，数值更稳
            v = v / (1 + r) + flows[k]
        return v
    f_lo, f_hi = npv(lo), npv(hi)
    if not np.isfinite(f_lo) or not np.isfinite(f_hi) or f_lo * f_hi > 0:
        return np.nan
    for _ in range(100):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo = mid
            f_lo = f_mid
    r = (lo + hi) / 2
    return ((1 + r) ** 12 - 1) * 100


def simulate(strategy, prices, pcts, mas, n):
    """返回 (期末总价值, 逐月组合价值序列, 累计实际买入额)。"""
    cash = 0.0
    shares = 0.0
    cost = 0.0            # 纪律止盈用的股票成本
    invested = 0.0        # 累计实际买入金额（含再投入）
    path = []
    for k in range(n):
        cash += BUDGET
        p = prices[k]
        eq = shares * p

        if strategy == 0:                      # 无脑
            want = BUDGET
        elif strategy == 1:                    # 价值平均
            want = BUDGET * (k + 1) - eq
        elif strategy == 2:                    # 估值分位
            q = pcts[k]
            mult = 2.0 if q < 30 else (0.0 if q > 70 else 1.0)
            want = BUDGET * mult
        elif strategy == 3:                    # 均线偏离
            ma = mas[k]
            if np.isnan(ma):
                d = 0.0
            else:
                d = p / ma - 1
            if d <= -0.20: mult = 3.0
            elif d <= -0.10: mult = 2.0
            elif d < 0.10: mult = 1.0
            elif d < 0.20: mult = 0.5
            else: mult = 0.0
            want = BUDGET * mult
        elif strategy == 4:                    # 纪律止盈
            want = BUDGET
        else:                                  # 组合再平衡：平时只入现金，年度再平衡
            want = 0.0

        if want >= 0:
            invest = min(want, cash)
            shares += invest / p
            cash -= invest
            cost += invest
            invested += invest
        else:
            sell = min(-want, eq)
            shares -= sell / p
            cash += sell
            cost = max(cost - sell, 0.0)

        if strategy == 4 and cost > 0 and eq > 0:
            # 用买入后的市值判断浮盈；达 +30% 卖出一半，成本减半
            eq2 = shares * p
            if eq2 / cost - 1 >= 0.30:
                sell = eq2 * 0.5
                shares -= sell / p
                cash += sell
                cost *= 0.5

        if strategy == 5 and (k + 1) % 12 == 0:
            eq2 = shares * p
            target_eq = (eq2 + cash) * 0.5
            if target_eq > eq2:
                invest = min(target_eq - eq2, cash)
                shares += invest / p
                cash -= invest
                invested += invest
            else:
                sell = min(eq2 - target_eq, eq2)
                shares -= sell / p
                cash += sell

        # 月末现金计息（最后一次也计，统一）
        cash *= (1 + RM)
        path.append(shares * p + cash)

    return path[-1], np.array(path), invested


def main():
    s = load()
    ind = prep(s)
    idx = s.index
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
        px = ind.loc[ds, "close"].values
        pct = ind.loc[ds, "pct5"].values   # 策略用滚动5年分位
        pct_all = ind.loc[ds, "pct"].values
        ma = ind.loc[ds, "ma200"].values

        final, paths, deployed = [], [], []
        for st in range(6):
            v, path, inv_amt = simulate(st, px, pct, ma, L)
            final.append(v)
            paths.append(path)
            deployed.append(inv_amt / (BUDGET * L))
        base = paths[0]
        # 窗口内纳指涨跌与最大回撤（用买入日价格序列近似）
        ret_mkt = (px[-1] / px[0] - 1) * 100
        peak = np.maximum.accumulate(px)
        mdd = (px / peak - 1).min() * 100
        exit_dd = (px[-1] / px.max() - 1) * 100
        rec = {
            "start": ds[0].strftime("%Y-%m-%d"),
            "end": ds[-1].strftime("%Y-%m-%d"),
            "months": L,
            "mkt_ret": ret_mkt,
            "mdd": mdd,
            "exit_dd": exit_dd,
            "entry_pct": pct[0],
            "exit_pct": pct[-1],
            "entry_pct_all": pct_all[0],
        }
        for st in range(6):
            v = final[st]
            rec[f"deploy{st}"] = deployed[st]
            rec[f"v{st}"] = v
            rec[f"ret{st}"] = (v / (BUDGET * L) - 1) * 100
            rec[f"irr{st}"] = irr_monthly([-BUDGET] * L + [v])
            # 组合净值最大回撤（逐月）
            pk = np.maximum.accumulate(paths[st])
            rec[f"pmdd{st}"] = (paths[st] / pk - 1).min() * 100
        rows.append(rec)

    df = pd.DataFrame(rows)
    out = os.path.join(ROOT, "data", "4strategies_samples.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")

    def stat(col, g=df):
        x = g[col].dropna()
        return x.mean(), x.median(), x.quantile(0.05), x.quantile(0.95)

    def win(st, g=df):
        return (g[f"v{st}"] > g["v0"]).mean() * 100

    print(f"样本数 {len(df)}，区间 {df.start.min()} ~ {df.end.max()}，月数分布：")
    print(df.months.value_counts().sort_index().to_string())
    print("\n=== 全样本 ===")
    print(f"{'策略':<10}{'期末均值':>10}{'期末中位':>10}{'总收益均值':>11}{'IRR均值':>9}{'IRR中位':>9}{'胜基准':>8}{'组合MDD':>9}")
    for st in range(6):
        vm, vmd, _, _ = stat(f"v{st}")
        rm_, rmd, _, _ = stat(f"ret{st}")
        im, imd, _, _ = stat(f"irr{st}")
        mm, _, _, _ = stat(f"pmdd{st}")
        print(f"{NAMES[st]:<10}{vm:>10.0f}{vmd:>10.0f}{rm_:>10.2f}%{im:>8.2f}%{imd:>8.2f}%{win(st):>7.1f}%{mm:>8.2f}%")

    groups = {
        "牛市顶部入场(起点分位>70%)": df[df.entry_pct > 70],
        "熊市底部入场(起点分位<30%)": df[df.entry_pct < 30],
        "中段入场(30~70%)": df[(df.entry_pct >= 30) & (df.entry_pct <= 70)],
        "含大回撤(MDD≤-20%)": df[df.mdd <= -20],
        "深熊(MDD≤-30%)": df[df.mdd <= -30],
        "温和(MDD>-15%)": df[df.mdd > -15],
        "终点仍在熊市(离高点≤-20%)": df[df.exit_dd <= -20],
        "终点创新高(离高点>-2%)": df[df.exit_dd > -2],
    }
    for name, g in groups.items():
        if len(g) < 10:
            print(f"\n=== {name} === 样本不足({len(g)})，跳过")
            continue
        print(f"\n=== {name} === n={len(g)}  纳指均涨 {g.mkt_ret.mean():.1f}%  均MDD {g.mdd.mean():.1f}%")
        print(f"{'策略':<10}{'总收益均值':>11}{'IRR均值':>9}{'IRR中位':>9}{'胜基准':>8}{'组合MDD':>9}")
        for st in range(6):
            rm_, rmd, _, _ = stat(f"ret{st}", g)
            im, imd, _, _ = stat(f"irr{st}", g)
            mm, _, _, _ = stat(f"pmdd{st}", g)
            print(f"{NAMES[st]:<10}{rm_:>10.2f}%{im:>8.2f}%{imd:>8.2f}%{win(st,g):>7.1f}%{mm:>8.2f}%")

    print("\n=== 期末价值分位（全样本）===")
    for st in range(6):
        _, _, p05, p95 = stat(f"v{st}")
        print(f"{NAMES[st]:<10} 5% {p05:>9.0f}  95% {p95:>9.0f}  元(每期5000)")

    print("\n=== 资金部署率（累计买入额 / 理论投入，全样本）===")
    for st in range(6):
        m, md, _, _ = stat(f"deploy{st}")
        print(f"{NAMES[st]:<10} 均值 {m*100:>6.1f}%  中位 {md*100:>6.1f}%")

    print("\n=== 起点分位分布 ===")
    print(f"滚动5年分位：起点均值 {df.entry_pct.mean():.1f}%  中位 {df.entry_pct.median():.1f}%  "
          f">70% 占比 {(df.entry_pct>70).mean()*100:.1f}%  <30% 占比 {(df.entry_pct<30).mean()*100:.1f}%")
    print(f"全历史分位：起点均值 {df.entry_pct_all.mean():.1f}%  >70% 占比 {(df.entry_pct_all>70).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
