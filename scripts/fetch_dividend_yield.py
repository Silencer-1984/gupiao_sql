# -*- coding: utf-8 -*-
"""
补齐红利类指数成分股的分红明细与个股行情，并计算指数级股息率落入数据库。

新增/更新：
  1. px_index_daily_csi / px_index_cons_csi  追加 000015（上证红利）
  2. fin_dividend_detail_all                 成分股分红明细（新浪，含 600941/601728）
  3. px_stock_daily                          成分股不复权日行情（新浪）
  4. val_index_dividend_yield                指数股息率（权重加权 DPS_TTM/Price）
  5. val_stock_dividend_yield_focus          中国移动/中国电信 个股股息率
  6. px_lof_daily                            270042 场内价 + 单位净值 + 溢价率

设计说明：
- 指数股息率 DY(t) = Σ w_i·(DPS_TTM_i(t)/P_i(t)) / Σ w_i，权重来自当前成分股快照（存在存活偏差，已在文档标注）。
- DPS_TTM 用滚动 252 个交易日（≈1 年）已实施现金分红合计，按除权日归集。
- 价格用不复权收盘价，与 DPS 口径一致；停牌用 ffill，最多 20 个交易日。
- 幂等：主键覆盖写入，可反复运行；股票级抓取带断点续跑（data/.div_checkpoint.txt）。

用法：
  .venv/Scripts/python.exe scripts/fetch_dividend_yield.py            # 全量
  .venv/Scripts/python.exe scripts/fetch_dividend_yield.py --calc-only # 只重算股息率
"""
import os
import sys
import time
import json
import sqlite3
import datetime as dt
import traceback
import pandas as pd
import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
LOG = os.path.join(ROOT, "data", "fetch_dividends.log")
CKPT = os.path.join(ROOT, "data", ".div_checkpoint.txt")

DIV_INDEXES = ["000922", "H30269", "930955", "000015"]
FOCUS_STOCKS = {"600941": "中国移动", "601728": "中国电信"}
SLEEP = 0.45
START = "2015-01-01"

NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def conn():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def ensure_schema(c):
    c.executescript(
        """
    CREATE TABLE IF NOT EXISTS fin_dividend_detail_all(
        stock_code TEXT, announce_date TEXT, bonus_ratio REAL, transfer_ratio REAL,
        cash_div_per10 REAL, progress TEXT, ex_date TEXT, record_date TEXT,
        _source TEXT, _fetched_at TEXT,
        PRIMARY KEY(stock_code, ex_date, announce_date));

    CREATE TABLE IF NOT EXISTS px_stock_daily(
        stock_code TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
        volume REAL, amount REAL, float_shares REAL, turnover REAL,
        _source TEXT, _fetched_at TEXT,
        PRIMARY KEY(stock_code, trade_date));

    CREATE TABLE IF NOT EXISTS val_index_dividend_yield(
        trade_date TEXT, index_code TEXT, div_yield REAL, weight_coverage REAL,
        n_valid INTEGER, method TEXT, _built_at TEXT,
        PRIMARY KEY(trade_date, index_code));

    CREATE TABLE IF NOT EXISTS val_stock_dividend_yield_focus(
        trade_date TEXT, stock_code TEXT, stock_name TEXT, close REAL,
        dps_ttm REAL, div_yield REAL, _built_at TEXT,
        PRIMARY KEY(trade_date, stock_code));

    CREATE TABLE IF NOT EXISTS px_lof_daily(
        fund_code TEXT, trade_date TEXT, close REAL, nav REAL, premium REAL,
        _source TEXT, _fetched_at TEXT,
        PRIMARY KEY(fund_code, trade_date));
    """
    )
    c.commit()


def sname(code):
    """A股代码 -> 新浪 symbol"""
    code = str(code).zfill(6)
    if code[:2] in ("83", "87", "88", "43", "40", "42", "92"):
        return "bj" + code          # 北交所 / 新三板
    if code[0] in "65":
        return "sh" + code
    if code[0] in "013":
        return "sz" + code
    if code[0] == "9":
        return "sh" + code          # 900xxx B 股
    if code[0] == "2":
        return "sz" + code          # 200xxx B 股
    return "sh" + code


# ---------------- 1. 000015 行情与成分 ----------------
def add_index_000015(c):
    n = c.execute(
        "select count(*) from px_index_daily_csi where index_code='000015'"
    ).fetchone()[0]
    if n > 0:
        log(f"000015 行情已存在 {n} 行，跳过")
    else:
        df = ak.index_hist_csindex(symbol="000015", start_date="20150101", end_date="20261231")
        df = df.rename(
            columns={
                "日期": "trade_date", "指数代码": "index_code", "指数中文全称": "index_name_cn",
                "指数中文简称": "index_name_short", "开盘": "open", "最高": "high", "最低": "low",
                "收盘": "close", "涨跌": "change", "涨跌幅": "pct_chg", "成交量": "volume",
                "成交金额": "amount", "样本数量": "sample_size", "滚动市盈率": "pe_ttm",
            }
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
        df["_source"] = "ak.index_hist_csindex"
        df["_fetched_at"] = NOW
        # 只保留交易日
        cal = {
            r[0]
            for r in c.execute(
                "select trade_date from dim_trade_calendar where trade_date>='2015-01-01'"
            )
        }
        df = df[df["trade_date"].isin(cal)]
        cols = ["trade_date", "index_code", "index_name_cn", "index_name_short", "open", "high",
                "low", "close", "change", "pct_chg", "volume", "amount", "sample_size", "pe_ttm",
                "_source", "_fetched_at"]
        df = df[[x for x in cols if x in df.columns]]
        existing = [r[1] for r in c.execute("pragma table_info(px_index_daily_csi)")]
        for col in df.columns:
            if col not in existing:
                c.execute(f'ALTER TABLE px_index_daily_csi ADD COLUMN "{col}"')
        df.to_sql("_tmp_idx", c, if_exists="replace", index=False)
        names = ",".join(f'"{x}"' for x in df.columns)
        # 原表无主键，先删后插，避免重复
        c.execute("DELETE FROM px_index_daily_csi WHERE index_code='000015'")
        c.execute(f"INSERT INTO px_index_daily_csi ({names}) SELECT {names} FROM _tmp_idx")
        c.execute("DROP TABLE _tmp_idx")
        c.commit()
        log(f"000015 行情入库 {len(df)} 行")

    n = c.execute("select count(*) from px_index_cons_csi where index_code='000015'").fetchone()[0]
    if n > 0:
        log(f"000015 成分股已存在 {n} 行，跳过")
    else:
        df = ak.index_stock_cons_weight_csindex(symbol="000015")
        df = df.rename(
            columns={
                "日期": "as_of_date", "指数代码": "index_code", "指数名称": "index_name",
                "成分券代码": "stock_code", "成分券名称": "stock_name", "交易所": "exchange",
                "权重": "weight",
            }
        )
        df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.strftime("%Y-%m-%d")
        df["_source"] = "ak.index_stock_cons_weight_csindex"
        df["_fetched_at"] = NOW
        df = df[["as_of_date", "index_code", "index_name", "stock_code", "stock_name",
                 "exchange", "weight", "_source", "_fetched_at"]]
        df.to_sql("_tmp_cons", c, if_exists="replace", index=False)
        names = ",".join(f'"{x}"' for x in df.columns)
        c.execute("DELETE FROM px_index_cons_csi WHERE index_code='000015'")
        c.execute(f"INSERT INTO px_index_cons_csi ({names}) SELECT {names} FROM _tmp_cons")
        c.execute("DROP TABLE _tmp_cons")
        c.commit()
        log(f"000015 成分股入库 {len(df)} 行")


# ---------------- 2. 股票级抓取 ----------------
def iter_stocks(c):
    rows = c.execute(
        "select distinct stock_code from px_index_cons_csi where index_code in (%s)"
        % ",".join("?" * len(DIV_INDEXES)),
        DIV_INDEXES,
    ).fetchall()
    codes = {str(r[0]).zfill(6) for r in rows}
    codes |= set(FOCUS_STOCKS)
    return sorted(codes)


def load_ckpt():
    if os.path.exists(CKPT):
        return set(open(CKPT).read().split())
    return set()


def add_ckpt(code):
    with open(CKPT, "a") as f:
        f.write(code + "\n")


def retry(fn, *a, **kw):
    last = None
    for i in range(4):
        try:
            return fn(*a, **kw)
        except Exception as e:
            last = e
            time.sleep(2 + 2 * i)
    raise last


def fetch_one(c, code):
    ok_div = ok_px = False
    # 分红明细
    try:
        d = retry(ak.stock_history_dividend_detail, symbol=code, indicator="分红")
        if d is not None and len(d):
            d = d.rename(
                columns={
                    "公告日期": "announce_date", "送股": "bonus_ratio", "转增": "transfer_ratio",
                    "派息": "cash_div_per10", "进度": "progress", "除权除息日": "ex_date",
                    "股权登记日": "record_date",
                }
            )
            for col in ["announce_date", "ex_date", "record_date"]:
                d[col] = pd.to_datetime(d[col], errors="coerce").dt.strftime("%Y-%m-%d")
            d = d[["announce_date", "bonus_ratio", "transfer_ratio", "cash_div_per10",
                   "progress", "ex_date", "record_date"]]
            d.insert(0, "stock_code", code)
            d["_source"] = "ak.stock_history_dividend_detail"
            d["_fetched_at"] = NOW
            d.to_sql("_tmp_div", c, if_exists="replace", index=False)
            names = ",".join(f'"{x}"' for x in d.columns)
            c.execute(
                f"INSERT OR REPLACE INTO fin_dividend_detail_all ({names}) SELECT {names} FROM _tmp_div"
            )
            c.execute("DROP TABLE _tmp_div")
            ok_div = True
    except Exception as e:
        log(f"  ! 分红失败 {code}: {type(e).__name__} {str(e)[:80]}")
    time.sleep(SLEEP)

    # 日行情
    try:
        d = retry(ak.stock_zh_a_hist_sina, symbol=sname(code))
        if d is not None and len(d):
            d = d.rename(columns={"date": "trade_date"})
            d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
            d = d[d["trade_date"] >= "2014-12-01"]
            d["stock_code"] = code
            d["_source"] = "ak.stock_zh_a_hist_sina"
            d["_fetched_at"] = NOW
            d = d[["stock_code", "trade_date", "open", "high", "low", "close", "volume",
                   "amount", "outstanding_share", "turnover", "_source", "_fetched_at"]]
            d = d.rename(columns={"outstanding_share": "float_shares"})
            d.to_sql("_tmp_px", c, if_exists="replace", index=False)
            names = ",".join(f'"{x}"' for x in d.columns)
            c.execute(f"INSERT OR REPLACE INTO px_stock_daily ({names}) SELECT {names} FROM _tmp_px")
            c.execute("DROP TABLE _tmp_px")
            ok_px = True
    except Exception as e:
        log(f"  ! 行情失败 {code}: {type(e).__name__} {str(e)[:80]}")
    time.sleep(SLEEP)
    c.commit()
    return ok_div, ok_px


# ---------------- 3. 计算指数股息率 ----------------
def calc_index_dy(c):
    # 日历必须截断到「已有行情的最后一个交易日」，否则交易日历里的未来排定日期会造出假数据
    last_px = c.execute("select max(trade_date) from px_stock_daily").fetchone()[0]
    today = dt.date.today().strftime("%Y-%m-%d")
    end = min(last_px, today)
    cal = [r[0] for r in c.execute(
        "select trade_date from dim_trade_calendar where trade_date>=? and trade_date<=? order by 1",
        (START, end))]
    cal = pd.to_datetime(cal)
    log(f"  计算区间 {cal[0].date()} ~ {cal[-1].date()}（{len(cal)} 个交易日）")

    # DPS_TTM 需要回看 252 个交易日，日历向前多取一年，避免 2015 年股息率被系统性低估
    cal_ext = pd.to_datetime([r[0] for r in c.execute(
        "select trade_date from dim_trade_calendar where trade_date>=? and trade_date<=? order by 1",
        ("2014-01-01", end))])

    px = pd.read_sql(
        "select stock_code, trade_date, close from px_stock_daily", c,
        parse_dates=["trade_date"])
    div = pd.read_sql(
        "select stock_code, ex_date, cash_div_per10 from fin_dividend_detail_all where ex_date is not null",
        c, parse_dates=["ex_date"])

    px_wide = px.pivot_table(index="trade_date", columns="stock_code", values="close")
    px_wide = px_wide.reindex(cal).ffill(limit=20)

    # DPS_TTM：在扩展日历上做滚动 252 交易日求和，再切回正式区间
    dps_wide = pd.DataFrame(0.0, index=cal_ext, columns=px_wide.columns)
    div = div[div["cash_div_per10"].notna() & (div["cash_div_per10"] > 0)]
    for code, g in div.groupby("stock_code"):
        if code not in dps_wide.columns:
            continue
        s = g.groupby("ex_date")["cash_div_per10"].sum() / 10.0
        s = s.reindex(cal_ext, fill_value=0.0)
        dps_wide[code] = s
    dps_ttm = dps_wide.rolling(252, min_periods=240).sum().reindex(cal)

    dy_all = {}
    out = []
    for idx in DIV_INDEXES:
        cons = pd.read_sql(
            "select stock_code, weight from px_index_cons_csi where index_code=?", c, params=(idx,))
        cons["stock_code"] = cons["stock_code"].astype(str).str.zfill(6)
        cons = cons[cons["stock_code"].isin(px_wide.columns)]
        if not len(cons):
            log(f"  ! {idx} 无可用成分股")
            continue
        w = cons.set_index("stock_code")["weight"].astype(float)
        w = w / w.sum()
        P = px_wide[w.index]
        D = dps_ttm[w.index]
        yld = (D / P).mul(w, axis=1).sum(axis=1, min_count=1)
        cov = (D.notna() & P.notna()).mul(w, axis=1).sum(axis=1)
        nval = (D.notna() & P.notna()).sum(axis=1)
        valid = cov >= 0.5  # 权重覆盖过半才输出
        res = pd.DataFrame({
            "trade_date": cal.strftime("%Y-%m-%d"),
            "index_code": idx,
            "div_yield": yld * 100,
            "weight_coverage": cov * 100,
            "n_valid": nval.astype(int),
            "method": "wavg_dps_ttm_over_close",
            "_built_at": NOW,
        })[valid]
        out.append(res)
        dy_all[idx] = res
        log(f"  {idx}: 成分 {len(w)} 只, 输出 {len(res)} 天, 最新 {res['div_yield'].iloc[-1]:.2f}% "
            f"(权重覆盖 {res['weight_coverage'].iloc[-1]:.1f}%)" if len(res) else f"  {idx}: 无数据")

    if out:
        res = pd.concat(out)
        res.to_sql("_tmp_dy", c, if_exists="replace", index=False)
        cols = ",".join(f'"{x}"' for x in res.columns)
        # 清掉上一轮可能写入的、超出行情末日的假数据
        c.execute("DELETE FROM val_index_dividend_yield WHERE trade_date > ?", (end,))
        c.execute(f"INSERT OR REPLACE INTO val_index_dividend_yield ({cols}) SELECT {cols} FROM _tmp_dy")
        c.execute("DROP TABLE _tmp_dy")
        c.commit()
    return dy_all


def calc_focus_dy(c):
    px = pd.read_sql(
        "select stock_code, trade_date, close from px_stock_daily where stock_code in ('600941','601728')",
        c, parse_dates=["trade_date"])
    if not len(px):
        return
    div = pd.read_sql(
        "select stock_code, ex_date, cash_div_per10 from fin_dividend_detail_all "
        "where stock_code in ('600941','601728') and ex_date is not null", c, parse_dates=["ex_date"])
    rows = []
    for code, g in px.groupby("stock_code"):
        g = g.sort_values("trade_date").set_index("trade_date")
        cal = g.index
        d = div[div["stock_code"] == code]
        s = (d.groupby("ex_date")["cash_div_per10"].sum() / 10.0).reindex(cal, fill_value=0.0)
        dps = s.rolling(252, min_periods=1).sum()
        y = dps / g["close"] * 100
        tmp = pd.DataFrame({
            "trade_date": cal.strftime("%Y-%m-%d"),
            "stock_code": code,
            "stock_name": FOCUS_STOCKS[code],
            "close": g["close"].values,
            "dps_ttm": dps.values,
            "div_yield": y.values,
            "_built_at": NOW,
        })
        rows.append(tmp)
    if rows:
        res = pd.concat(rows)
        res.to_sql("_tmp_f", c, if_exists="replace", index=False)
        cols = ",".join(f'"{x}"' for x in res.columns)
        c.execute(f"INSERT OR REPLACE INTO val_stock_dividend_yield_focus ({cols}) SELECT {cols} FROM _tmp_f")
        c.execute("DROP TABLE _tmp_f")
        c.commit()
        for code, g in res.groupby("stock_code"):
            last = g.iloc[-1]
            log(f"  聚焦股 {code} {last['stock_name']}: 最新股息率 {last['div_yield']:.2f}% "
                f"(DPS_TTM {last['dps_ttm']:.3f}, close {last['close']:.2f})")


# ---------------- 4. 270042 LOF 溢价率 ----------------
def build_lof(c):
    code = "270042"
    try:
        nav = retry(ak.fund_open_fund_info_em, symbol=code, indicator="单位净值走势")
        nav = nav.rename(columns={"净值日期": "trade_date", "单位净值": "nav"})
        nav["trade_date"] = pd.to_datetime(nav["trade_date"]).dt.strftime("%Y-%m-%d")
        nav = nav[["trade_date", "nav"]].dropna()
        log(f"270042 净值 {len(nav)} 行，最新 {nav.iloc[-1]['trade_date']} = {nav.iloc[-1]['nav']}")
    except Exception as e:
        log(f"! 270042 净值失败: {type(e).__name__} {str(e)[:100]}")
        return

    px = None
    for attempt in range(3):
        try:
            px = ak.fund_lof_hist_em(symbol=code)
            break
        except Exception as e:
            log(f"! 270042 场内价第 {attempt+1} 次失败: {type(e).__name__}")
            time.sleep(60)
    if px is None or not len(px):
        log("! 270042 场内价不可得（东财 push2 限流），溢价率暂不计算")
        return
    px = px.rename(columns={"日期": "trade_date", "收盘": "close"})
    px["trade_date"] = pd.to_datetime(px["trade_date"]).dt.strftime("%Y-%m-%d")
    px = px[["trade_date", "close"]]
    m = px.merge(nav, on="trade_date", how="inner")
    m["premium"] = (m["close"] / m["nav"] - 1) * 100
    m["fund_code"] = code
    m["_source"] = "ak.fund_lof_hist_em+fund_open_fund_info_em"
    m["_fetched_at"] = NOW
    m = m[["fund_code", "trade_date", "close", "nav", "premium", "_source", "_fetched_at"]]
    m.to_sql("_tmp_lof", c, if_exists="replace", index=False)
    cols = ",".join(f'"{x}"' for x in m.columns)
    c.execute(f"INSERT OR REPLACE INTO px_lof_daily ({cols}) SELECT {cols} FROM _tmp_lof")
    c.execute("DROP TABLE _tmp_lof")
    c.commit()
    log(f"270042 溢价率入库 {len(m)} 行，区间 {m['trade_date'].min()}~{m['trade_date'].max()}")


def main():
    calc_only = "--calc-only" in sys.argv
    c = conn()
    ensure_schema(c)
    log("=" * 60)
    if not calc_only:
        add_index_000015(c)
        stocks = iter_stocks(c)
        done = load_ckpt()
        todo = [s for s in stocks if s not in done]
        log(f"待抓取股票 {len(stocks)} 只（已完成 {len(done)}，本次 {len(todo)}）")
        for i, code in enumerate(todo, 1):
            ok1, ok2 = fetch_one(c, code)
            add_ckpt(code)
            if i % 20 == 0 or i == len(todo):
                log(f"进度 {i}/{len(todo)}  最近 {code} 分红={ok1} 行情={ok2}")
    log("计算指数股息率…")
    calc_index_dy(c)
    calc_focus_dy(c)
    if "--no-lof" not in sys.argv:
        log("构建 270042 溢价率…")
        build_lof(c)
    log("完成")
    c.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        log("异常终止:\n" + traceback.format_exc()[:1000])
        sys.exit(1)
