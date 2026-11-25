# -*- coding: utf-8 -*-
"""
159941（纳指ETF）历史溢价率 + 纳斯达克100 对比。

溢价率两种口径（必须分开看，否则会把「时差错觉」当成真溢价）：
  premium_same = 收盘价(T) / 单位净值(T)   - 1   ← 行情软件常用口径，但含 T 日美股涨跌（当时还没发生）
  premium_lag  = 收盘价(T) / 单位净值(T-1) - 1   ← 时点匹配口径：A股 T 日 15:00 收盘时真正可观测的溢价

原因：QDII 的 T 日净值反映的是美股 T 日收盘（北京时间 T+1 凌晨），
而 A 股 T 日 15:00 收盘时，最新可知的是美股 T-1 日收盘 → 用 nav(T-1) 才不含未来信息。

入库：
  px_index_daily_us        纳斯达克100（.NDX）与纳斯达克综合（.IXIC）日线
  px_lof_daily             新增列 premium_lag，回填 159941 两种口径
  val_qdii_ndx_compare     159941 溢价率 + 纳指收益/回撤 对齐表
  meta_premium_stats       补充统计指标
"""
import os, sys, sqlite3, datetime as dt, traceback
import pandas as pd
import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
LOG = os.path.join(ROOT, "data", "fetch_ndx.log")
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
FUND = "159941"


def log(m):
    line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")


def main():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS px_index_daily_us(
        index_code TEXT, index_name TEXT, trade_date TEXT,
        open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL,
        _source TEXT, _fetched_at TEXT, PRIMARY KEY(index_code, trade_date));

    CREATE TABLE IF NOT EXISTS val_qdii_ndx_compare(
        fund_code TEXT, trade_date TEXT, close REAL, nav REAL,
        premium_same REAL, premium_lag REAL,
        ndx_close REAL, ndx_ret_1d REAL, ndx_ret_5d REAL, ndx_ret_20d REAL, ndx_dd60 REAL,
        _built_at TEXT, PRIMARY KEY(fund_code, trade_date));
    """)

    # ---------- 1. 纳指 ----------
    for sym, name in [(".NDX", "纳斯达克100"), (".IXIC", "纳斯达克综合")]:
        try:
            d = ak.index_us_daily_sina(symbol=sym)
        except Exception as e:
            log(f"! {sym} 失败 {type(e).__name__} {str(e)[:100]}")
            continue
        d = d.rename(columns={"date": "trade_date"})
        d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
        d["index_code"] = sym
        d["index_name"] = name
        d["_source"] = "ak.index_us_daily_sina"
        d["_fetched_at"] = NOW
        d = d[["index_code", "index_name", "trade_date", "open", "high", "low", "close",
               "volume", "amount", "_source", "_fetched_at"]]
        d.to_sql("_tmp_us", c, if_exists="replace", index=False)
        cols = ",".join(f'"{x}"' for x in d.columns)
        c.execute(f"INSERT OR REPLACE INTO px_index_daily_us ({cols}) SELECT {cols} FROM _tmp_us")
        c.execute("DROP TABLE _tmp_us")
        c.commit()
        log(f"{sym} {name} 入库 {len(d)} 行 {d.trade_date.min()}~{d.trade_date.max()} 最新 {d.close.iloc[-1]:.2f}")

    # ---------- 2. 溢价率（两种口径） ----------
    cols = [r[1] for r in c.execute("pragma table_info(px_lof_daily)")]
    if "premium_lag" not in cols:
        c.execute("ALTER TABLE px_lof_daily ADD COLUMN premium_lag REAL")
        c.commit()
        log("px_lof_daily 新增列 premium_lag")

    px = pd.read_sql(
        f"select trade_date, close, nav from px_lof_daily where fund_code='{FUND}' order by trade_date",
        c)
    if not len(px):
        raise RuntimeError("px_lof_daily 中没有 159941")
    px["trade_date"] = pd.to_datetime(px["trade_date"])
    px = px.sort_values("trade_date").reset_index(drop=True)
    px["premium_same"] = (px["close"] / px["nav"] - 1) * 100
    px["premium_lag"] = (px["close"] / px["nav"].shift(1) - 1) * 100

    # 清洗：净值折分/错位造成的离谱值
    p_ret = px["close"].pct_change()
    n_ret = px["nav"].pct_change()
    bad = (px["premium_same"].abs() > 60) | ((p_ret - n_ret).abs() > 0.25)
    bad |= (px["premium_lag"].abs() > 60)
    log(f"清洗异常 {int(bad.sum())} 天（净值折分/数据错位）")
    for col in ["premium_same", "premium_lag"]:
        px.loc[bad, col] = None

    for _, r in px.iterrows():
        c.execute(
            "UPDATE px_lof_daily SET premium=?, premium_lag=? WHERE fund_code=? AND trade_date=?",
            (None if pd.isna(r.premium_same) else float(r.premium_same),
             None if pd.isna(r.premium_lag) else float(r.premium_lag),
             FUND, r.trade_date.strftime("%Y-%m-%d")),
        )
    c.commit()
    log(f"回填 159941 溢价率 {len(px)} 行")

    # ---------- 3. 与纳指对齐 ----------
    ndx = pd.read_sql("select trade_date, close from px_index_daily_us where index_code='.NDX'", c)
    ndx["trade_date"] = pd.to_datetime(ndx["trade_date"])
    ndx = ndx.sort_values("trade_date").set_index("trade_date")
    ndx["ret_1d"] = ndx["close"].pct_change() * 100
    ndx["ret_5d"] = ndx["close"].pct_change(5) * 100
    ndx["ret_20d"] = ndx["close"].pct_change(20) * 100
    ndx["dd60"] = (ndx["close"] / ndx["close"].rolling(60).max() - 1) * 100

    m = px.set_index("trade_date").join(ndx.add_prefix("ndx_"), how="left")

    out = pd.DataFrame({
        "fund_code": FUND,
        "trade_date": m.index.strftime("%Y-%m-%d"),
        "close": m["close"].values,
        "nav": m["nav"].values,
        "premium_same": m["premium_same"].values,
        "premium_lag": m["premium_lag"].values,
        "ndx_close": m["ndx_close"].values,
        "ndx_ret_1d": m["ndx_ret_1d"].values,
        "ndx_ret_5d": m["ndx_ret_5d"].values,
        "ndx_ret_20d": m["ndx_ret_20d"].values,
        "ndx_dd60": m["ndx_dd60"].values,
        "_built_at": NOW,
    })
    out.to_sql("_tmp_cmp", c, if_exists="replace", index=False)
    cl = ",".join(f'"{x}"' for x in out.columns)
    c.execute(f"INSERT OR REPLACE INTO val_qdii_ndx_compare ({cl}) SELECT {cl} FROM _tmp_cmp")
    c.execute("DROP TABLE _tmp_cmp")
    c.commit()
    log(f"对齐表入库 {len(out)} 行，NDX 覆盖 {out.ndx_close.notna().sum()} 行")

    # ---------- 4. 统计 ----------
    sub = out[out.trade_date >= "2021-06-01"].copy()   # 近 5 年
    stats = []

    def add(metric, val, note=""):
        c.execute("INSERT OR REPLACE INTO meta_premium_stats VALUES (?,?,?,?,?,?)",
                  (FUND, "纳指ETF(广发纳指100)", metric, None if val is None else float(val), note, NOW))
        stats.append((metric, val, note))

    for tag, col in [("near5y_same", "premium_same"), ("near5y_lag", "premium_lag")]:
        s = sub[col].dropna()
        add(f"{tag}_n", len(s), "近5年样本天数")
        add(f"{tag}_mean", s.mean())
        add(f"{tag}_std", s.std())
        add(f"{tag}_p50", s.median())
        add(f"{tag}_p95", s.quantile(0.95))
        add(f"{tag}_max", s.max(), f"@ {sub.loc[s.idxmax(),'trade_date']}")
        add(f"{tag}_last", s.iloc[-1], f"@ {sub.loc[s.index[-1],'trade_date']}")
        add(f"{tag}_over10_pct", (s > 10).mean() * 100, "溢价>10% 占比%")

    lag = sub.dropna(subset=["premium_lag", "ndx_ret_5d"])
    add("corr_lag_ndx5d", lag["premium_lag"].corr(lag["ndx_ret_5d"]), "溢价(lag) vs 纳指近5日收益")
    add("corr_chg_lag_ndx1d", sub["premium_lag"].diff().corr(sub["ndx_ret_1d"]), "溢价(lag)日变动 vs 纳指1日")
    c.commit()
    for k, v, n in stats:
        log(f"  {k:22s} {v if v is None else round(float(v), 3)} {n}")
    log("完成")
    c.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("异常:\n" + traceback.format_exc()[:1200])
        sys.exit(1)
