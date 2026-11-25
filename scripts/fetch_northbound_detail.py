# -*- coding: utf-8 -*-
"""
北向/南向资金分项历史（沪股通 / 深股通 / 港股通沪 / 港股通深）。

关键事实：
  北向「每日净买入」自 2024-08-19 起**停止披露**（交易所改革，只保留成交总额且不再给方向），
  接口仍返回日期行，但 净买额/买入/卖出 全为空或 0。南向（港股通）仍每日披露。

用法：
  .venv/Scripts/python.exe scripts/fetch_northbound_detail.py
"""
import os, sys, sqlite3, datetime as dt, traceback
import pandas as pd
import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
LOG = os.path.join(ROOT, "data", "fetch_northbound.log")
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

BRANCHES = [
    ("沪股通", "北向", "sh"),
    ("深股通", "北向", "sz"),
    ("港股通沪", "南向", "hk_sh"),
    ("港股通深", "南向", "hk_sz"),
]


def log(m):
    line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")


def main():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS flow_hsgt_branch(
        trade_date TEXT, branch TEXT, direction TEXT, branch_code TEXT,
        net_buy REAL, buy_amount REAL, sell_amount REAL, net_inflow REAL,
        hold_mv REAL, index_close REAL, index_pct REAL,
        _source TEXT, _fetched_at TEXT, PRIMARY KEY(trade_date, branch));
    """)

    for br, direction, code in BRANCHES:
        try:
            d = ak.stock_hsgt_hist_em(symbol=br)
        except Exception as e:
            log(f"! {br} 失败 {type(e).__name__} {str(e)[:100]}")
            continue
        d = d.rename(columns={
            "日期": "trade_date", "当日成交净买额": "net_buy", "买入成交额": "buy_amount",
            "卖出成交额": "sell_amount", "当日资金流入": "net_inflow", "持股市值": "hold_mv",
        })
        idx_col = next((x for x in d.columns if x.endswith("-涨跌幅")), None)
        close_col = next((x for x in d.columns if x.endswith("指数")), None)
        out = pd.DataFrame({
            "trade_date": pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d"),
            "branch": br,
            "direction": direction,
            "branch_code": code,
            "net_buy": pd.to_numeric(d.get("net_buy"), errors="coerce"),
            "buy_amount": pd.to_numeric(d.get("buy_amount"), errors="coerce"),
            "sell_amount": pd.to_numeric(d.get("sell_amount"), errors="coerce"),
            "net_inflow": pd.to_numeric(d.get("net_inflow"), errors="coerce"),
            "hold_mv": pd.to_numeric(d.get("hold_mv"), errors="coerce"),
            "index_close": pd.to_numeric(d.get(close_col), errors="coerce") if close_col else None,
            "index_pct": pd.to_numeric(d.get(idx_col), errors="coerce") if idx_col else None,
        })
        # 净买额为 0 且买卖皆空的行 = 停披露，剔除方向字段
        out["_source"] = "ak.stock_hsgt_hist_em"
        out["_fetched_at"] = NOW
        out.loc[out["buy_amount"].isna(), ["net_buy", "net_inflow"]] = None

        out.to_sql("_tmp_nb", c, if_exists="replace", index=False)
        cols = ",".join(f'"{x}"' for x in out.columns)
        c.execute("DELETE FROM flow_hsgt_branch WHERE branch=?", (br,))
        c.execute(f"INSERT OR REPLACE INTO flow_hsgt_branch ({cols}) SELECT {cols} FROM _tmp_nb")
        c.execute("DROP TABLE _tmp_nb")
        c.commit()
        valid = out["net_buy"].notna()
        log(f"{br}({direction}) 入库 {len(out)} 行，有方向 {int(valid.sum())} 行，"
            f"{out.loc[valid,'trade_date'].min() if valid.any() else '-'} ~ "
            f"{out.loc[valid,'trade_date'].max() if valid.any() else '-'}")
    log("完成")
    c.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("异常:\n" + traceback.format_exc()[:1000])
        sys.exit(1)
