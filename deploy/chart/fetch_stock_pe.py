# -*- coding: utf-8 -*-
"""拉取个股 PE-TTM 历史（百度股市通），写入主库 val_stock_pe_daily。
用法：uv run python deploy/chart/fetch_stock_pe.py
"""
import os
import sqlite3
import datetime as dt

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "data", "ashare.db")
STOCKS = {"601728": "中国电信", "600941": "中国移动"}

DDL = """
create table if not exists val_stock_pe_daily (
    stock_code text not null,
    trade_date text not null,
    pe_ttm real,
    _source text,
    _fetched_at text,
    primary key (stock_code, trade_date)
)
"""


def main():
    c = sqlite3.connect(DB)
    c.execute(DDL)
    now = dt.datetime.now().isoformat(timespec="seconds")
    for code in STOCKS:
        try:
            df = ak.stock_zh_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="全部")
            rows = [(code, str(r["date"]), float(r["value"]), "baidu", now)
                    for _, r in df.iterrows() if r["value"] is not None]
            c.executemany("insert or replace into val_stock_pe_daily values (?,?,?,?,?)", rows)
            print(f"{code} {STOCKS[code]} {len(rows)} rows, latest {rows[-1][1] if rows else '-'}")
        except Exception as e:
            print(f"{code} ERR {type(e).__name__}: {e}")
    c.commit()
    c.close()


if __name__ == "__main__":
    main()
