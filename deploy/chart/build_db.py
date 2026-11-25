# -*- coding: utf-8 -*-
"""从主库抽取图表页所需数据，生成独立精简库（按标的过滤，最小化）。

只保留 9 个标的：沪深300 / 上证指数 / 红利低波 / 科创50 / 港股创新药 / 中证有色 /
纳斯达克100 / 中国电信 / 中国移动。

用法：uv run python deploy/chart/build_db.py
"""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "data", "ashare.db")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chart.db")

IDX = ("000300", "000001", "H30269", "000688", "931787", "000819")
US = (".NDX",)
STOCKS = ("601728", "600941")
FUND = "159941"

# (表名, where 子句, 参数)
SPECS = [
    ("px_index_daily_csi", "index_code in (%s)" % ",".join("?" * len(IDX)), IDX),
    ("px_index_daily_us", "index_code in (?)", US),
    ("val_index_dividend_yield", "index_code in (?)", ("H30269",)),
    ("mkt_fear_daily", "index_code in (%s)" % ",".join("?" * len(IDX)), IDX),
    ("macro_bond_yield", "1=1", ()),
    ("val_stock_dividend_yield_focus", "stock_code in (?,?)", STOCKS),
    ("val_stock_pe_daily", "stock_code in (?,?)", STOCKS),
    ("px_stock_daily", "stock_code in (?,?)", STOCKS),
    ("px_lof_daily", "fund_code=?", (FUND,)),
]


def main():
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    if os.path.exists(DST):
        os.remove(DST)
    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DST)
    for t, where, params in SPECS:
        cols = [r[1] for r in src.execute("pragma table_info(%s)" % t)]
        rows = src.execute("select * from %s where %s" % (t, where), params).fetchall()
        dst.execute("create table %s (%s)" % (t, ", ".join('"%s"' % c for c in cols)))
        dst.executemany("insert into %s values (%s)" % (t, ",".join("?" * len(cols))), rows)
        if "trade_date" in cols:
            dst.execute("create index ix_%s_date on %s(trade_date)" % (t, t))
        print("%-30s %7d rows" % (t, len(rows)))
    dst.commit()
    dst.execute("vacuum")
    dst.close()
    src.close()
    print("\n%s\n%.2f MB" % (DST, os.path.getsize(DST) / 1024 / 1024))


if __name__ == "__main__":
    main()
