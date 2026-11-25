# -*- coding: utf-8 -*-
"""沪深300 择时因子月频面板：仅用当期及以前数据，无未来函数。

输出 DataFrame，index=月末 Period，列=各因子原值。供因子修正策略回测使用。
"""
import os
import sqlite3
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")


def _monthly_from_daily(sql, date_col="trade_date", value_cols=None):
    c = sqlite3.connect(DB)
    df = pd.read_sql(sql, c)
    c.close()
    if df.empty:
        return pd.DataFrame()
    df[date_col] = pd.to_datetime(df[date_col].astype(str), errors="coerce")
    df = df.dropna(subset=[date_col])
    df["ym"] = df[date_col].dt.to_period("M")
    if value_cols is None:
        value_cols = [x for x in df.columns if x not in (date_col, "ym")]
    return df.groupby("ym", as_index=False).last()[["ym"] + value_cols]


def load_factor_panel():
    c = sqlite3.connect(DB)
    pe = pd.read_sql(
        "select trade_date,index_close,pe_ttm from val_index_pe_lg "
        "where index_name='沪深300' order by trade_date", c)
    pe = pd.merge(
        pe,
        pd.read_sql("select trade_date,pb from val_index_pb_lg where index_name='沪深300'", c),
        on="trade_date", how="left")
    c.close()
    pe["trade_date"] = pd.to_datetime(pe.trade_date)
    pe["ym"] = pe.trade_date.dt.to_period("M")
    pe = pe.groupby("ym", as_index=False).last().sort_values("ym").reset_index(drop=True)
    base = pe[["ym", "index_close", "pe_ttm", "pb"]].copy()
    base = base.rename(columns={"pe_ttm": "pe", "pb": "pb"})

    # 隐含 EPS（指数点位/PE-TTM），衡量盈利趋势：股价跌但盈利涨 -> EPS 上行
    base["eps_implied"] = base.index_close / base.pe
    base["eps_growth12"] = base.eps_implied / base.eps_implied.shift(12) - 1
    base["pe_abs"] = base.pe
    base["pb_abs"] = base.pb

    # 股息率（全 A，日频 -> 月末）
    d = _monthly_from_daily("select trade_date,div_yield from val_a_dividend_yield")
    base = base.merge(d.rename(columns={"div_yield": "div_yield"}), on="ym", how="left")

    # 10 年国债收益率 -> 股权风险溢价 ERP = 盈利收益率 - 无风险
    b = _monthly_from_daily("select trade_date,cn_10y from macro_bond_yield")
    base = base.merge(b, on="ym", how="left")
    base["erp"] = 100.0 / base.pe - base.cn_10y

    # 恐慌度（0~100，越高越恐慌）
    f = _monthly_from_daily(
        "select trade_date,fear_composite from mkt_fear_daily where index_code='000300'")
    base = base.merge(f, on="ym", how="left")

    # 两融余额同比（杠杆情绪）
    mg = _monthly_from_daily("select trade_date,margin_balance from flow_margin_sse")
    mg["margin_balance"] = pd.to_numeric(mg.margin_balance, errors="coerce")
    mg["margin_yoy"] = mg.margin_balance / mg.margin_balance.shift(12) - 1
    base = base.merge(mg[["ym", "margin_yoy"]], on="ym", how="left")

    # 拥挤度
    cg = _monthly_from_daily("select trade_date,congestion from val_congestion_lg")
    base = base.merge(cg, on="ym", how="left")

    # M1 同比：stat_month 格式 "2026年10月份"，数据本身是月末发布，滞后 1 月使用
    c = sqlite3.connect(DB)
    m1 = pd.read_sql("select stat_month,m1_yoy from macro_money_supply", c)
    c.close()
    m1["ym"] = m1.stat_month.str.extract(r"(\d{4})年(\d{1,2})月份").apply(
        lambda r: pd.Period(f"{r[0]}-{int(r[1]):02d}", freq="M"), axis=1)
    m1["ym"] = m1.ym + 1  # 次月才可得
    base = base.merge(m1[["ym", "m1_yoy"]], on="ym", how="left")

    # 价格位置：36 月滚动峰值回撤 + 12 月均线偏离
    s = base.index_close
    base["dd36"] = s / s.rolling(36, min_periods=12).max() - 1
    base["ma12_dev"] = s / s.rolling(12, min_periods=12).mean() - 1
    return base.set_index("ym").sort_index()


def rolling_pct(series, win):
    v = series.values.astype(float)
    out = np.full(len(v), np.nan)
    for t in range(win - 1, len(v)):
        w = v[t - win + 1:t + 1]
        w = w[~np.isnan(w)]
        if len(w) >= win * 0.8:
            out[t] = float((w <= v[t]).mean())
    return out


if __name__ == "__main__":
    f = load_factor_panel()
    print(f.shape)
    print(f.loc["2026-11"].to_string())
    for p in ["2020-03", "2022-04", "2022-07", "2023-08", "2024-08", "2026-11"]:
        if pd.Period(p) in f.index:
            r = f.loc[pd.Period(p)]
            print(p, {k: (round(v, 3) if pd.notna(v) else None) for k, v in r.items()
                      if k in ["pe", "pb", "eps_growth12", "div_yield", "erp",
                               "fear_composite", "margin_yoy", "congestion", "m1_yoy", "dd36"]})
