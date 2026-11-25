# -*- coding: utf-8 -*-
"""
抓取 Cboe 官方 VXN（纳斯达克100波动率指数）历史日线，入库 mkt_vol_vxn。

数据源：Cboe 官方 CSV（一手来源）
  https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv
  字段 DATE,OPEN,HIGH,LOW,CLOSE；实测区间 2009-09-14 ~ 今日
  说明：VXN 实际可用历史从 2009 年起（非网上常说的 2001）

用法：uv run python scripts/fetch_vxn.py
"""
import os
import sqlite3
import datetime as dt
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv"
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    from io import BytesIO
    df = pd.read_csv(BytesIO(raw))
    df.columns = [c.strip() for c in df.columns]
    need = {"DATE", "OPEN", "HIGH", "LOW", "CLOSE"}
    if not need.issubset(df.columns):
        raise ValueError(f"CSV 字段异常: {list(df.columns)}")
    df["trade_date"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"OPEN": "open", "HIGH": "high", "LOW": "low", "CLOSE": "close"})
    df = df[["trade_date", "open", "high", "low", "close"]].dropna(subset=["close"])
    df = df[df["close"] > 0].sort_values("trade_date").reset_index(drop=True)
    df["_source"] = "cboe_vxn_csv"
    df["_fetched_at"] = NOW
    return df


def main():
    df = fetch()
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS mkt_vol_vxn(
        trade_date TEXT PRIMARY KEY,
        open REAL, high REAL, low REAL, close REAL,
        _source TEXT, _fetched_at TEXT);
    """)
    df.to_sql("_tmp_vxn", c, if_exists="replace", index=False)
    c.execute("""
        INSERT OR REPLACE INTO mkt_vol_vxn
        (trade_date,open,high,low,close,_source,_fetched_at)
        SELECT trade_date,open,high,low,close,_source,_fetched_at FROM _tmp_vxn
    """)
    c.execute("DROP TABLE _tmp_vxn")
    c.commit()
    n = c.execute("select count(*) from mkt_vol_vxn").fetchone()[0]
    rng = c.execute("select min(trade_date),max(trade_date) from mkt_vol_vxn").fetchone()
    c.close()
    print(f"VXN 入库完成：{n} 行，{rng[0]} ~ {rng[1]}，来源 {URL}")


if __name__ == "__main__":
    main()
