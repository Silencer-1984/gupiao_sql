# -*- coding: utf-8 -*-
"""
纳指相关品种的净值 / 场内价 / 溢价率。

关于 270042 的结论（已核实）：
  270042 = 广发纳斯达克100指数(QDII)A，**场外份额，不在交易所上市**
  → 深交所/新浪/腾讯均无场内行情（sz270042 返回空）
  → 因此 270042 本身不存在「溢价率」，只有净值。

若要做「纳指溢价率」，需要用它在场内的同族份额或同标的 ETF：
  161130  纳指LOF（广发纳斯达克100，深交所上市，可算溢价率，样本 2017-07 起）
  159941  纳指ETF（广发，深交所上市，样本 2015-07 起）

本脚本三者都取：270042 只存净值（premium 留空），161130 / 159941 计算溢价率。
溢价率 = 场内收盘价 / 当日单位净值 - 1（QDII 净值按 T 日公布，未做 T-1 对齐）。
"""
import os, sys, time, sqlite3, datetime as dt, traceback
import pandas as pd
import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
LOG = os.path.join(ROOT, "data", "fetch_nasdaq.log")
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(m):
    line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")


def get_price(code):
    """场内价：新浪基金行情（ETF/LOF 均在 fund_etf_hist_sina 的覆盖范围内）"""
    s = ("sz" if code[0] in "013" else "sh") + code
    d = ak.fund_etf_hist_sina(symbol=s)
    if d is None or not len(d):
        return None
    d = d.rename(columns={"date": "trade_date"})
    d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
    return d[["trade_date", "close"]]


def get_nav(code):
    d = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    d = d.rename(columns={"净值日期": "trade_date", "单位净值": "nav"})
    d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
    return d[["trade_date", "nav"]].dropna()


def get_nav_exchange(code):
    d = ak.fund_exchange_nav_hist_em(fund=code, start_date="20150101", end_date="20261231")
    d = d.rename(columns={"净值日期": "trade_date", "单位净值": "nav"})
    d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
    return d[["trade_date", "nav"]].dropna()


def upsert(c, df):
    df = df.copy()
    df["_source"] = "sina_price + eastmoney_nav"
    df["_fetched_at"] = NOW
    df.to_sql("_tmp_lof", c, if_exists="replace", index=False)
    cols = ",".join(f'"{x}"' for x in df.columns)
    c.execute(f"INSERT OR REPLACE INTO px_lof_daily ({cols}) SELECT {cols} FROM _tmp_lof")
    c.execute("DROP TABLE _tmp_lof")
    c.commit()


def main():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS px_lof_daily(
        fund_code TEXT, trade_date TEXT, close REAL, nav REAL, premium REAL,
        _source TEXT, _fetched_at TEXT, PRIMARY KEY(fund_code, trade_date));
    CREATE TABLE IF NOT EXISTS meta_premium_stats(
        fund_code TEXT, fund_name TEXT, metric TEXT, value REAL, note TEXT,
        _built_at TEXT, PRIMARY KEY(fund_code, metric));
    """)

    specs = [
        ("270042", "广发纳斯达克100(QDII)A_场外", "nav_only"),
        ("161130", "纳指LOF(广发纳斯达克100,场内)", "both"),
        ("159941", "纳指ETF(广发纳斯达克100)", "both"),
    ]
    stats = []
    for code, name, mode in specs:
        log(f"--- {code} {name} ({mode}) ---")
        try:
            nav = get_nav_exchange(code) if code in ("161130", "159941") else get_nav(code)
            log(f"  净值 {len(nav)} 行 {nav.trade_date.min()}~{nav.trade_date.max()} 最新 {nav.nav.iloc[-1]}")
        except Exception as e:
            log(f"  ! 净值失败 {type(e).__name__} {str(e)[:100]}")
            continue

        if mode == "nav_only":
            df = nav.copy()
            df.insert(0, "fund_code", code)
            df["close"] = None
            df["premium"] = None
            upsert(c, df[["fund_code", "trade_date", "close", "nav", "premium"]])
            stats.append((code, name, "premium_available", 0, "场外份额，无场内价格"))
            continue

        try:
            px = get_price(code)
            log(f"  场内价 {len(px)} 行 {px.trade_date.min()}~{px.trade_date.max()}")
        except Exception as e:
            log(f"  ! 场内价失败 {type(e).__name__} {str(e)[:100]}")
            continue
        time.sleep(0.5)

        m = px.merge(nav, on="trade_date", how="inner").dropna()
        if not len(m):
            log("  ! 无重叠日期")
            continue
        m = m.sort_values("trade_date").reset_index(drop=True)
        m["premium"] = (m["close"] / m["nav"] - 1) * 100
        # 异常清洗：净值折分/数据错位会造成离谱溢价，用「价格涨跌 vs 净值涨跌」交叉校验
        p_ret = m["close"].pct_change()
        n_ret = m["nav"].pct_change()
        bad = (m["premium"].abs() > 60) | ((p_ret - n_ret).abs() > 0.25)
        if bad.sum():
            log(f"  剔除异常 {int(bad.sum())} 天: " + ", ".join(m.loc[bad, 'trade_date'].head(5)))
            m.loc[bad, "premium"] = None
        m.insert(0, "fund_code", code)
        upsert(c, m[["fund_code", "trade_date", "close", "nav", "premium"]])

        s = m["premium"].dropna()
        info = [
            ("premium_available", 1, ""),
            ("n_days", len(m), f"{m.trade_date.min()}~{m.trade_date.max()}"),
            ("premium_mean", s.mean(), "%"),
            ("premium_std", s.std(), "%"),
            ("premium_p05", s.quantile(0.05), "%"),
            ("premium_p50", s.quantile(0.50), "%"),
            ("premium_p95", s.quantile(0.95), "%"),
            ("premium_max", s.max(), f"@ {m.loc[s.idxmax(),'trade_date']}"),
            ("premium_min", s.min(), f"@ {m.loc[s.idxmin(),'trade_date']}"),
            ("premium_last", s.iloc[-1], f"@ {m.trade_date.iloc[-1]}"),
            ("days_over_3pct", (s > 3).mean() * 100, "溢价>3% 的交易日占比%"),
            ("days_over_10pct", (s > 10).mean() * 100, "溢价>10% 的交易日占比%"),
            ("std20_last", s.tail(20).std(), "最近20日波动(std%)"),
            ("premium_mean_1y", s.tail(250).mean(), "最近1年均值%"),
            ("premium_std_1y", s.tail(250).std(), "最近1年标准差%"),
        ]
        for metric, val, note in info:
            c.execute(
                "INSERT OR REPLACE INTO meta_premium_stats VALUES (?,?,?,?,?,?)",
                (code, name, metric, None if val is None else float(val), note, NOW),
            )
        c.commit()
        log(f"  溢价率: 均值{s.mean():.2f}% 标准差{s.std():.2f}% 最新{s.iloc[-1]:.2f}% "
            f"[{s.quantile(0.05):.2f}%, {s.quantile(0.95):.2f}%] 极值{s.max():.1f}%/{s.min():.1f}%")
    log("完成")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("异常:\n" + traceback.format_exc()[:800])
        sys.exit(1)
