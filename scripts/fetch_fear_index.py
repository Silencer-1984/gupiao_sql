# -*- coding: utf-8 -*-
"""
1) 新增关注指数 931787（中证香港创新药 / 港股创新药）行情 + 成分 + 候选 ETF
2) 市场恐慌度体系：
   - 隐含波动率层：QVIX（期权论坛口径）7 个标的
   - 已实现波动率层：RV20 / RV60 / 下行波动 / 距 60 日高点回撤
   - 合成恐慌度：QVIX 5 年分位 与 RV20 5 年分位 等权（无期权标的只用 RV）

入库：
  px_index_daily_csi   追加 931787
  px_index_cons_csi    追加 931787 成分（.HK 代码）
  px_etf_daily         追加候选 ETF
  mkt_vol_qvix         QVIX 日频
  mkt_fear_daily       各指数恐慌度指标

用法：.venv/Scripts/python.exe scripts/fetch_fear_index.py
"""
import os, sys, sqlite3, datetime as dt, traceback
import numpy as np
import pandas as pd
import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
LOG = os.path.join(ROOT, "data", "fetch_fear.log")
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

QVIX = [
    ("50etf", "上证50ETF期权", "index_option_50etf_qvix", "510050"),
    ("300etf", "沪深300ETF期权", "index_option_300etf_qvix", "510300"),
    ("500etf", "中证500ETF期权", "index_option_500etf_qvix", "510500"),
    ("100etf", "深100ETF期权", "index_option_100etf_qvix", "159901"),
    ("50index", "上证50指数期权", "index_option_50index_qvix", "000016"),
    ("300index", "沪深300指数期权", "index_option_300index_qvix", "000300"),
    ("1000index", "中证1000指数期权", "index_option_1000index_qvix", "000852"),
    ("cyb", "创业板指期权", "index_option_cyb_qvix", "399006"),
    ("kcb", "科创50期权", "index_option_kcb_qvix", "000688"),
]

# 恐慌度计算用的指数
FEAR_INDEXES = ["000300", "000985", "000922", "H30269", "930955", "000819", "000688", "399006", "931787"]
# 指数 -> QVIX code（无期权的留空）
IDX_QVIX = {"000300": "300etf", "000688": "kcb", "399006": "cyb"}


def log(m):
    line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")


def upsert(c, df, table, cols):
    df.to_sql("_tmp_x", c, if_exists="replace", index=False)
    cl = ",".join(f'"{x}"' for x in cols)
    c.execute(f"INSERT OR REPLACE INTO {table} ({cl}) SELECT {cl} FROM _tmp_x")
    c.execute("DROP TABLE _tmp_x")
    c.commit()


def main():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS mkt_vol_qvix(
        trade_date TEXT, qvix_code TEXT, qvix_name TEXT, underlying TEXT,
        open REAL, high REAL, low REAL, close REAL,
        _source TEXT, _fetched_at TEXT, PRIMARY KEY(trade_date, qvix_code));

    CREATE TABLE IF NOT EXISTS mkt_fear_daily(
        trade_date TEXT, index_code TEXT,
        rv20 REAL, rv60 REAL, dvol20 REAL, dd60 REAL,
        qvix REAL, fear_rv_pct REAL, fear_qvix_pct REAL, fear_composite REAL,
        _built_at TEXT, PRIMARY KEY(trade_date, index_code));
    """)

    # ---------- 1. 931787 行情 ----------
    try:
        d = ak.index_hist_csindex(symbol="931787", start_date="20150101", end_date="20261231")
        d = d.rename(columns={
            "日期": "trade_date", "指数代码": "index_code", "指数中文全称": "index_name_cn",
            "指数中文简称": "index_name_short", "开盘": "open", "最高": "high", "最低": "low",
            "收盘": "close", "涨跌": "change", "涨跌幅": "pct_chg", "成交量": "volume",
            "成交金额": "amount", "样本数量": "sample_size", "滚动市盈率": "pe_ttm"})
        d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
        # 剔除 2015-01-01 基期占位行与全空行
        d = d[(d["close"].notna()) & (~((d["trade_date"] == "2015-01-01")))]
        d["_source"] = "ak.index_hist_csindex"
        d["_fetched_at"] = NOW
        keep = ["trade_date", "index_code", "index_name_cn", "index_name_short", "open", "high",
                "low", "close", "change", "pct_chg", "volume", "amount", "sample_size",
                "pe_ttm", "_source", "_fetched_at"]
        d = d[[x for x in keep if x in d.columns]]
        d.to_sql("_tmp_i", c, if_exists="replace", index=False)
        cl = ",".join(f'"{x}"' for x in d.columns)
        c.execute("DELETE FROM px_index_daily_csi WHERE index_code='931787'")
        c.execute(f"INSERT INTO px_index_daily_csi ({cl}) SELECT {cl} FROM _tmp_i")
        c.execute("DROP TABLE _tmp_i")
        c.commit()
        log(f"931787 行情入库 {len(d)} 行 {d.trade_date.min()}~{d.trade_date.max()} 最新 {d.close.iloc[-1]:.2f} PE {d.pe_ttm.iloc[-1]}")
    except Exception as e:
        log(f"! 931787 行情失败 {type(e).__name__} {str(e)[:120]}")

    # 成分
    try:
        d = ak.index_stock_cons_weight_csindex(symbol="931787")
        d = d.rename(columns={"日期": "as_of_date", "指数代码": "index_code", "指数名称": "index_name",
                              "成分券代码": "stock_code", "成分券名称": "stock_name", "交易所": "exchange",
                              "权重": "weight"})
        d["as_of_date"] = pd.to_datetime(d["as_of_date"]).dt.strftime("%Y-%m-%d")
        d["_source"] = "ak.index_stock_cons_weight_csindex"
        d["_fetched_at"] = NOW
        d = d[["as_of_date", "index_code", "index_name", "stock_code", "stock_name", "exchange",
               "weight", "_source", "_fetched_at"]]
        d.to_sql("_tmp_c", c, if_exists="replace", index=False)
        cl = ",".join(f'"{x}"' for x in d.columns)
        c.execute("DELETE FROM px_index_cons_csi WHERE index_code='931787'")
        c.execute(f"INSERT INTO px_index_cons_csi ({cl}) SELECT {cl} FROM _tmp_c")
        c.execute("DROP TABLE _tmp_c")
        c.commit()
        log(f"931787 成分入库 {len(d)} 只，权重合计 {d.weight.sum():.1f}%")
    except Exception as e:
        log(f"! 931787 成分失败 {type(e).__name__} {str(e)[:120]}")

    # 候选 ETF
    for etf in ["sh513120", "sz159892", "sh520500"]:
        try:
            e = ak.fund_etf_hist_sina(symbol=etf)
            code = etf[2:]
            e = e.rename(columns={"date": "trade_date"})
            e["trade_date"] = pd.to_datetime(e["trade_date"]).dt.strftime("%Y-%m-%d")
            e["etf_code"] = code
            e["prev_close"] = e["close"].shift(1)
            e["_source"] = "ak.fund_etf_hist_sina"
            e["_fetched_at"] = NOW
            e = e[["etf_code", "trade_date", "prev_close", "open", "high", "low", "close",
                   "volume", "amount", "_source", "_fetched_at"]]
            e.to_sql("_tmp_e", c, if_exists="replace", index=False)
            cl = ",".join(f'"{x}"' for x in e.columns)
            c.execute("DELETE FROM px_etf_daily WHERE etf_code=?", (code,))
            c.execute(f"INSERT INTO px_etf_daily ({cl}) SELECT {cl} FROM _tmp_e")
            c.execute("DROP TABLE _tmp_e")
            c.commit()
            log(f"ETF {etf} 入库 {len(e)} 行 {e.trade_date.min()}~{e.trade_date.max()}")
        except Exception as e:
            log(f"! ETF {etf} 失败 {type(e).__name__} {str(e)[:100]}")

    # ---------- 2. QVIX ----------
    total = 0
    for code, name, fn, und in QVIX:
        try:
            d = getattr(ak, fn)()
            d = d.rename(columns={"date": "trade_date"})
            d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
            d["close"] = pd.to_numeric(d["close"], errors="coerce")
            d = d[(d["close"].notna()) & (d["close"] > 0)]   # 末尾空行 + 全 0 的坏序列
            d["qvix_code"] = code
            d["qvix_name"] = name
            d["underlying"] = und
            d["_source"] = "ak." + fn
            d["_fetched_at"] = NOW
            d = d[["trade_date", "qvix_code", "qvix_name", "underlying", "open", "high", "low",
                   "close", "_source", "_fetched_at"]]
            c.execute("DELETE FROM mkt_vol_qvix WHERE qvix_code=?", (code,))
            upsert(c, d, "mkt_vol_qvix", list(d.columns))
            total += len(d)
            log(f"QVIX {name:16s} {len(d):5d} 行 {d.trade_date.min()}~{d.trade_date.max()} 最新 {d.close.iloc[-1]:.2f}")
        except Exception as e:
            log(f"! QVIX {name} 失败 {type(e).__name__} {str(e)[:100]}")
    log(f"QVIX 合计 {total} 行")

    # ---------- 3. 恐慌度 ----------
    px = pd.read_sql(
        "select trade_date,index_code,close,amount from px_index_daily_csi where index_code in (%s) "
        "union all select trade_date,index_code,close,null from px_index_daily_cni where index_code in (%s)"
        % (",".join("?" * len(FEAR_INDEXES)), ",".join("?" * len(FEAR_INDEXES))),
        c, params=FEAR_INDEXES + FEAR_INDEXES)
    px["trade_date"] = pd.to_datetime(px["trade_date"])
    qv = pd.read_sql("select trade_date,qvix_code,close from mkt_vol_qvix", c)
    qv["trade_date"] = pd.to_datetime(qv["trade_date"])
    qv = qv.pivot_table(index="trade_date", columns="qvix_code", values="close")

    out = []
    for idx in FEAR_INDEXES:
        g = px[px.index_code == idx].sort_values("trade_date").set_index("trade_date")
        if len(g) < 300:
            log(f"  跳过 {idx}（样本 {len(g)}）")
            continue
        r = g["close"].pct_change()
        rv20 = r.rolling(20).std() * np.sqrt(252) * 100
        rv60 = r.rolling(60).std() * np.sqrt(252) * 100
        neg = r.where(r < 0, 0)
        dvol20 = neg.rolling(20).std() * np.sqrt(252) * 100
        dd60 = (g["close"] / g["close"].rolling(60).max() - 1) * 100

        df = pd.DataFrame({"rv20": rv20, "rv60": rv60, "dvol20": dvol20, "dd60": dd60})
        qc = IDX_QVIX.get(idx)
        df["qvix"] = qv[qc].reindex(df.index).ffill(limit=3) if qc and qc in qv.columns else np.nan
        # 5 年滚动分位（1250 交易日）
        df["fear_rv_pct"] = df["rv20"].rolling(1250, min_periods=250).apply(
            lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)
        df["fear_qvix_pct"] = df["qvix"].rolling(1250, min_periods=250).apply(
            lambda w: np.nan if np.isnan(w[-1]) else (w[:-1] < w[-1]).mean() * 100, raw=True)
        df["fear_composite"] = df[["fear_rv_pct", "fear_qvix_pct"]].mean(axis=1)
        df["index_code"] = idx
        df["_built_at"] = NOW
        df = df.reset_index().rename(columns={"index": "trade_date"})
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
        out.append(df)

    if out:
        res = pd.concat(out)
        cols = ["trade_date", "index_code", "rv20", "rv60", "dvol20", "dd60", "qvix",
                "fear_rv_pct", "fear_qvix_pct", "fear_composite", "_built_at"]
        res = res[cols]
        res.to_sql("_tmp_f", c, if_exists="replace", index=False)
        cl = ",".join(f'"{x}"' for x in cols)
        c.execute(f"INSERT OR REPLACE INTO mkt_fear_daily ({cl}) SELECT {cl} FROM _tmp_f")
        c.execute("DROP TABLE _tmp_f")
        c.commit()
        log(f"mkt_fear_daily 入库 {len(res)} 行，覆盖 {res.index_code.nunique()} 个指数")
        last = res[res.trade_date == res.trade_date.max()]
        for _, x in last.iterrows():
            log(f"  {x.index_code:8s} RV20 {x.rv20:5.1f}%  RV分位 {x.fear_rv_pct:5.1f}"
                f"  QVIX {x.qvix if pd.notna(x.qvix) else float('nan'):6.2f}"
                f"  合成 {x.fear_composite:5.1f}")
    log("完成")
    c.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("异常:\n" + traceback.format_exc()[:1200])
        sys.exit(1)
