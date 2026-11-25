# -*- coding: utf-8 -*-
"""6 个上升波段起点/终点的日频因子面板。

波段由用户从 K 线识别，本脚本只做验证与因子归因，不做择时回测。
所有因子只用起点当日及以前数据，无未来函数。
"""
import os
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")

SEGS = [
    ("A", "2022-05-06", "2022-07-01"),
    ("B", "2022-10-28", "2023-01-20"),
    ("C", "2024-02-02", "2024-05-07"),
    ("D", "2024-09-13", "2024-11-08"),
    ("E", "2025-01-10", "2026-01-09"),
    ("F", "2026-04-03", "2026-06-18"),
]


def load_daily(sql, date_col="trade_date"):
    c = sqlite3.connect(DB)
    d = pd.read_sql(sql, c)
    c.close()
    d[date_col] = pd.to_datetime(d[date_col].astype(str))
    return d


def pct_rank(series, win, minp=0.7):
    """当前值在过去 win 期的分位（0~1），只用历史。"""
    v = series.values.astype(float)
    out = np.full(len(v), np.nan)
    need = int(win * minp)
    for t in range(len(v)):
        w = v[max(0, t - win + 1): t + 1]
        w = w[~np.isnan(w)]
        if len(w) >= need and not np.isnan(v[t]):
            out[t] = float((w <= v[t]).mean())
    return out


def build():
    c = sqlite3.connect(DB)
    # 基准：沪深300 日频（含日频 PE-TTM）
    px = pd.read_sql(
        "select trade_date,close,volume,amount,pct_chg,pe_ttm from px_index_daily_csi "
        "where index_code='000300' order by trade_date", c)
    c.close()
    px["trade_date"] = pd.to_datetime(px.trade_date)
    px = px.drop_duplicates("trade_date").set_index("trade_date").sort_index()
    f = px.copy()

    # --- 价格动量 / 位置 ---
    close = f.close
    for n in (5, 20, 60, 120, 250):
        f[f"mom{n}"] = close / close.shift(n) - 1
    f["dd60"] = close / close.rolling(60, min_periods=40).max() - 1
    f["dd250"] = close / close.rolling(250, min_periods=180).max() - 1
    f["ma20_dev"] = close / close.rolling(20, min_periods=15).mean() - 1
    f["ma60_dev"] = close / close.rolling(60, min_periods=40).mean() - 1
    f["ma20_60"] = close.rolling(20).mean() / close.rolling(60).mean() - 1
    # 连跌天数
    neg = (f.pct_chg < 0).astype(int)
    grp = (neg != neg.shift()).cumsum()
    f["down_streak"] = neg.groupby(grp).cumsum()
    # 20日/60日实现波动
    r = close.pct_change()
    f["rv20"] = r.rolling(20).std() * np.sqrt(250)
    f["rv60"] = r.rolling(60).std() * np.sqrt(250)
    f["rv_ratio"] = f.rv20 / f.rv60

    # --- 量能 ---
    f["vol_ratio20"] = f.volume / f.volume.rolling(20).mean()
    f["amt_ratio20"] = f.amount / f.amount.rolling(20).mean()
    f["vol_chg20"] = f.volume / f.volume.shift(20) - 1
    f["vol_ma20_120"] = f.volume.rolling(20).mean() / f.volume.rolling(120).mean() - 1

    # --- 日频 PE 与分位（关键：比月频更早） ---
    f["pe_ttm"] = f.pe_ttm.replace(0, np.nan)
    f["ey"] = 100.0 / f.pe_ttm
    for w, lab in ((250, "pe_pct1y"), (750, "pe_pct3y"), (1250, "pe_pct5y")):
        f[lab] = pct_rank(f.pe_ttm, w)
    f["pe_chg20"] = f.pe_ttm / f.pe_ttm.shift(20) - 1
    f["pe_chg60"] = f.pe_ttm / f.pe_ttm.shift(60) - 1

    # --- 利率与股债性价比 ---
    b = load_daily("select trade_date,cn_2y,cn_5y,cn_10y,cn_30y,cn_10y_2y_spread from macro_bond_yield")
    b = b.drop_duplicates("trade_date").set_index("trade_date")
    f = f.join(b, how="left")
    f["cn_10y"] = f.cn_10y.ffill()
    f["cn_2y"] = f.cn_2y.ffill()
    f["erp"] = f.ey - f.cn_10y
    f["dy_gap"] = f.ey - f.cn_10y  # 等价于 ERP（全A股息率另算）
    f["bond_chg20"] = f.cn_10y - f.cn_10y.shift(20)
    f["bond_chg60"] = f.cn_10y - f.cn_10y.shift(60)
    f["yield_curve"] = f.cn_10y - f.cn_2y

    # 全 A 股息率（日频）
    d = load_daily("select trade_date,div_yield from val_a_dividend_yield")
    d = d.drop_duplicates("trade_date").set_index("trade_date").div_yield
    f["div_yield"] = d.reindex(f.index).ffill()
    f["dy_bond_gap"] = f.div_yield - f.cn_10y
    f["dy_pct1y"] = pct_rank(f.div_yield, 250)

    # --- 恐慌度 ---
    z = load_daily(
        "select trade_date,fear_composite,fear_rv_pct,fear_qvix_pct,rv20 as f_rv20,dd60 as f_dd60 "
        "from mkt_fear_daily where index_code='000300'")
    z = z.drop_duplicates("trade_date").set_index("trade_date")
    f = f.join(z.add_prefix("fear_"), how="left")
    for col in ["fear_fear_composite", "fear_fear_rv_pct", "fear_fear_qvix_pct"]:
        f[col] = f[col].ffill()
    f["fear_chg20"] = f.fear_fear_composite - f.fear_fear_composite.shift(20)

    # --- 拥挤度（日频） ---
    g = load_daily("select trade_date,congestion from val_congestion_lg")
    g = g.drop_duplicates("trade_date").set_index("trade_date").congestion
    f["congestion"] = g.reindex(f.index).ffill()
    f["cong_pct1y"] = pct_rank(f.congestion, 250)

    # --- 两融（日频） ---
    m = load_daily("select trade_date,margin_balance from flow_margin_sse")
    m = m.drop_duplicates("trade_date").set_index("trade_date").margin_balance
    f["margin"] = m.reindex(f.index).ffill()
    f["margin_chg20"] = f.margin / f.margin.shift(20) - 1
    f["margin_chg60"] = f.margin / f.margin.shift(60) - 1

    # --- 北向（日频，2024-08 后停止披露） ---
    n = load_daily("select trade_date,net_buy from flow_northbound")
    n = n.drop_duplicates("trade_date").set_index("trade_date").net_buy
    f["north20"] = n.reindex(f.index).rolling(20, min_periods=10).sum()
    f["north60"] = n.reindex(f.index).rolling(60, min_periods=30).sum()

    # --- 宏观月频（用可得日对齐到月末后 ffill）：M1/PPMI/社融 ---
    c = sqlite3.connect(DB)
    m1 = pd.read_sql("select stat_month,m1_yoy,m2_yoy from macro_money_supply", c)
    pm = pd.read_sql("select stat_month,pmi_manufacturing from macro_pmi", c)
    sf = pd.read_sql("select stat_month,sf_increment from macro_social_financing", c)
    c.close()
    def month_to_next_start(s):
        # 支持 "2026年10月份" 与 "202604" 两种格式；滞后 1 月（次月首个交易日才可得）
        g = s.astype(str).str.extract(r"(\d{4})[年]?0?(\d{1,2})")
        ym = pd.PeriodIndex([f"{a}-{int(b):02d}" for a, b in zip(g[0], g[1])], freq="M")
        return (ym + 1).to_timestamp()

    for src, cols in ((m1, ["m1_yoy", "m2_yoy"]), (pm, ["pmi_manufacturing"]), (sf, ["sf_increment"])):
        src["dt"] = month_to_next_start(src.stat_month)
        for col in cols:
            f[col] = src.set_index("dt")[col].reindex(f.index, method="ffill")
    f["m1_m2_gap"] = f.m1_yoy - f.m2_yoy

    return f


def nearest(f, date):
    d = pd.Timestamp(date)
    if d in f.index:
        return d
    prev = f.index[f.index <= d]
    return prev[-1] if len(prev) else None


if __name__ == "__main__":
    f = build()
    print("panel", f.shape, str(f.index[0].date()), str(f.index[-1].date()))
    for k, a, b in SEGS:
        da, db = nearest(f, a), nearest(f, b)
        sub = f.loc[da:db]
        print(k, da.date(), "→", db.date(), "涨%.2f%%" % ((sub.close.iloc[-1] / sub.close.iloc[0] - 1) * 100))
