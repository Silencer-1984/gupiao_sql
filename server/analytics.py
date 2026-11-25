# -*- coding: utf-8 -*-
"""数据计算层：从 data/ashare.db 取数，产出网站需要的结构化结果。"""
import os
import json
import sqlite3
import datetime as dt
import time
import pandas as pd
import numpy as np

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ashare.db")

# 网站展示的重点标的
WATCH = [
    {"code": "000001", "name": "上证指数", "group": "大盘", "src": "csi"},
    {"code": "000922", "name": "中证红利", "group": "红利", "src": "csi"},
    {"code": "000300", "name": "沪深300", "group": "宽基", "src": "csi"},
    {"code": "000819", "name": "中证有色", "group": "周期", "src": "csi"},
    {"code": "000688", "name": "科创50", "group": "成长", "src": "csi"},
    {"code": ".NDX", "name": "纳斯达克100", "group": "海外", "src": "us"},
]
NAME_MAP = {"000300": "沪深300", "000985": "中证全指", "000922": "中证红利", "H30269": "红利低波",
            "930955": "红利低波100", "000819": "中证有色", "000688": "科创50", "399006": "创业板指",
            "931787": "港股创新药", "000001": "上证指数"}
FEAR_INDEXES = ["000300", "000985", "000922", "H30269", "930955", "000819", "000688", "399006", "931787"]


def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _ensure(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS web_daily_snapshot(
        trade_date TEXT PRIMARY KEY, temperature REAL, fear REAL,
        sh_pct REAL, sz_pct REAL, amount REAL, vol_ratio REAL, smallcap REAL,
        sentiment_score REAL, hot_mean_pct REAL, anomaly INTEGER,
        advice TEXT, summary TEXT, _saved_at TEXT);

    CREATE TABLE IF NOT EXISTS web_sentiment_meta(
        trade_date TEXT PRIMARY KEY, source_name TEXT, score REAL, mean_pct REAL,
        up_ratio REAL, fetched_at TEXT,
        score_text REAL, score_news REAL, score_price REAL,
        comment_n INTEGER, news_pos INTEGER, news_neg INTEGER, news_n INTEGER);

    CREATE TABLE IF NOT EXISTS web_daily_summary(
        trade_date TEXT, period TEXT, payload TEXT, generated_at TEXT,
        PRIMARY KEY(trade_date, period));

    CREATE TABLE IF NOT EXISTS web_sentiment(
        trade_date TEXT, source TEXT, rank INTEGER, code TEXT, name TEXT,
        pct REAL, heat REAL, _fetched_at TEXT,
        PRIMARY KEY(trade_date, source, rank));
    """)
    # 老库迁移：补上看法层字段（新库建表时已含，无需 ALTER）
    for _col, _typ in [("score_text", "REAL"), ("score_news", "REAL"), ("score_price", "REAL"),
                       ("comment_n", "INTEGER"), ("news_pos", "INTEGER"), ("news_neg", "INTEGER"),
                       ("news_n", "INTEGER")]:
        try:
            c.execute("ALTER TABLE web_sentiment_meta ADD COLUMN %s %s" % (_col, _typ))
        except Exception:
            pass
    c.commit()


# ---------------- 行情 ----------------
def _px(c, code, src):
    if src == "us":
        return pd.read_sql(
            "select trade_date, close, null as pct, volume as amount, null as pe_ttm "
            "from px_index_daily_us where index_code=? order by trade_date", c, params=(code,))
    if src == "cni":
        return pd.read_sql(
            "select trade_date, close, pct_chg_ratio*100 as pct, amount, null as pe_ttm "
            "from px_index_daily_cni where index_code=? order by trade_date", c, params=(code,))
    return pd.read_sql(
        "select trade_date, close, pct_chg as pct, amount, pe_ttm "
        "from px_index_daily_csi where index_code=? order by trade_date", c, params=(code,))


def get_series(code, freq="D", limit=260):
    c = conn()
    src = next((x["src"] for x in WATCH if x["code"] == code), "csi")
    d = _px(c, code, src)
    c.close()
    if not len(d):
        return {"code": code, "points": []}
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    d = d.set_index("trade_date")
    d["pct"] = d["pct"].fillna(d["close"] / d["close"].shift(1) * 100 - 100)
    rule = {"D": None, "W": "W-FRI", "M": "ME", "Y": "YE"}.get(freq)
    if rule:
        d = d.resample(rule).agg({"close": "last", "amount": "sum", "pe_ttm": "last"})
        d["pct"] = d["close"].pct_change() * 100
    d = d.dropna(subset=["close"]).tail(limit)
    pts = [{"date": i.strftime("%Y-%m-%d"),
            "close": None if pd.isna(r.close) else round(float(r.close), 2),
            "pct": None if pd.isna(r.pct) else round(float(r.pct), 2),
            "amount": None if pd.isna(r.amount) else round(float(r.amount), 1),
            "pe": None if pd.isna(r.pe_ttm) else round(float(r.pe_ttm), 2)}
           for i, r in d.iterrows()]
    return {"code": code, "freq": freq, "points": pts}


# ---------------- 温度 / 总览 ----------------
TEMP_BANDS = [
    (15, "寒冷刺骨", "#0f9d58"), (30, "寒冷", "#3ba55d"), (45, "偏冷", "#7bc47f"),
    (55, "中性", "#cfd8dc"), (70, "偏热", "#f2b134"), (85, "炎热", "#ef6c3a"), (101, "热浪滚滚", "#d63031"),
]


def _band(t):
    for th, label, color in TEMP_BANDS:
        if t < th:
            return label, color
    return "热浪滚滚", "#d63031"


def _latest_trade_date(c):
    return c.execute("select max(trade_date) from px_index_daily_csi where index_code='000300'").fetchone()[0]


def _last(c, sql, params=()):
    r = c.execute(sql, params).fetchone()
    return r[0] if r else None


def overview():
    c = conn()
    _ensure(c)
    date = _latest_trade_date(c)

    def px(code, table="px_index_daily_csi"):
        return pd.read_sql(
            f"select trade_date, close, {'pct_chg' if table.endswith('csi') else 'pct_chg_ratio*100 as pct_chg'}, "
            f"amount from {table} where index_code=? order by trade_date",
            c, params=(code,))

    sh = px("000001")
    sz = px("399001", "px_index_daily_cni")
    sz_all = px("399106", "px_index_daily_cni")
    hs300 = px("000300")
    allshare = px("000985")

    sh_pct = float(sh.pct_chg.iloc[-1])
    sz_pct = float(sz.pct_chg.iloc[-1])
    amount = float(sh.amount.iloc[-1] + sz_all.amount.iloc[-1])
    amt20 = float((sh.amount + sz_all.amount).tail(20).mean())
    vol_ratio = amount / amt20
    smallcap = float(allshare.pct_chg.iloc[-1] - hs300.pct_chg.iloc[-1])

    # 移动周线：沪深300 近 5 个交易日累计
    mrzq = (hs300.close.iloc[-1] / hs300.close.iloc[-6] - 1) * 100

    fear = pd.read_sql(
        "select index_code, fear_composite, fear_rv_pct, rv20 from mkt_fear_daily "
        "where trade_date=(select max(trade_date) from mkt_fear_daily)", c)
    fear_map = {r.index_code: r for r in fear.itertuples()}
    f_all = float(fear_map["000985"].fear_composite) if "000985" in fear_map else 50.0

    # 温度 = 100 - 全指恐慌度（恐慌越高越冷），再按当日大盘方向微调 ±3
    temp = max(0.0, min(100.0, 100 - f_all + np.clip(hs300.pct_chg.iloc[-1], -3, 3)))
    label, color = _band(temp)

    # 异常扫描：9 个指数里 恐慌>85 或 PE 分位>90/<10 的个数
    pe = pd.read_sql(
        "select index_code, pe_ttm from px_index_daily_csi where pe_ttm is not null "
        "and trade_date>=date((select max(trade_date) from px_index_daily_csi),'-5 years')", c)
    anomaly = 0
    detail = []
    for idx, g in pe.groupby("index_code"):
        if idx not in FEAR_INDEXES:
            continue
        s = g.pe_ttm.dropna()
        if len(s) < 250:
            continue
        pct = float((s < s.iloc[-1]).mean() * 100)
        fpct = float(fear_map[idx].fear_rv_pct) if idx in fear_map and pd.notna(fear_map[idx].fear_rv_pct) else np.nan
        flag = []
        if pct > 90 or pct < 10:
            flag.append("估值高位" if pct > 90 else "估值低位")
        if not np.isnan(fpct) and fpct > 85:
            flag.append("恐慌高位")
        if flag:
            anomaly += 1
            detail.append({"code": idx, "name": NAME_MAP.get(idx, idx),
                           "pe_pct": round(pct, 0),
                           "fear_pct": None if np.isnan(fpct) else round(fpct, 0), "flag": flag})

    # 策略建议（规则，透明可复核）
    g = fear_map.get("000688")
    v = fear_map.get("000922")
    cyc = fear_map.get("000819")
    advice, reason = _advice(pe, fear_map, hs300)
    sleeves = _sleeve_advice(c)

    snap = {
        "date": date,
        "temperature": round(temp, 1), "temp_label": label, "temp_color": color,
        "fear": round(f_all, 1),
        "sh": {"pct": round(sh_pct, 2), "close": round(float(sh.close.iloc[-1]), 2)},
        "sz": {"pct": round(sz_pct, 2), "close": round(float(sz.close.iloc[-1]), 2)},
        "amount": round(amount, 0), "vol_ratio": round(vol_ratio, 2),
        "smallcap": round(smallcap, 2),
        "mrzq": round(float(mrzq), 2),
        "anomaly": anomaly, "anomaly_detail": detail,
        "advice": advice, "advice_reason": reason, "sleeves": sleeves,
        "fear_board": [{"code": k, "fear": None if pd.isna(r.fear_composite) else round(float(r.fear_composite), 1),
                        "rv20": None if pd.isna(r.rv20) else round(float(r.rv20), 1)}
                       for k, r in fear_map.items()],
    }
    c.close()
    return snap


def _pct_rank(series, window=1250):
    """当前值在过去 window 个观测中的分位（0-100）。"""
    s = series.dropna()
    if len(s) < 60:
        return None
    w = s.tail(window)
    return float((w < s.iloc[-1]).mean() * 100)


def _sleeve_advice(c):
    """成长（科创50+有色）与价值（红利）各自的打分与操作建议。

    成长分 = 0.40×(100−PE分位) + 0.35×(100−恐慌分位) + 0.25×相对强弱分位
    价值分 = 0.40×股息率利差分位 + 0.30×(100−PE分位) + 0.30×(100−恐慌分位)
    """
    # --- 估值分位 ---
    pe = pd.read_sql(
        "select trade_date,index_code,pe_ttm from px_index_daily_csi where pe_ttm is not null", c)
    pe["trade_date"] = pd.to_datetime(pe["trade_date"])
    pe_map = {}
    for idx, g in pe.groupby("index_code"):
        pe_map[idx] = _pct_rank(g.set_index("trade_date").pe_ttm)

    # --- 恐慌分位 ---
    fear = pd.read_sql(
        "select index_code, fear_composite, fear_rv_pct from mkt_fear_daily "
        "where trade_date=(select max(trade_date) from mkt_fear_daily)", c)
    fear_map = {r.index_code: r for r in fear.itertuples()}

    # --- 股息率利差分位（红利）---
    dy = pd.read_sql(
        "select trade_date,index_code,div_yield from val_index_dividend_yield where index_code in ('000922','H30269')", c)
    by = pd.read_sql("select trade_date,cn_10y from macro_bond_yield where cn_10y is not null", c)
    spread_pct = {}
    if len(dy) and len(by):
        dy["trade_date"] = pd.to_datetime(dy["trade_date"])
        by["trade_date"] = pd.to_datetime(by["trade_date"])
        m = dy.merge(by, on="trade_date", how="left").sort_values(["index_code", "trade_date"])
        m["cn_10y"] = m.groupby("index_code").cn_10y.ffill()
        for idx, g in m.groupby("index_code"):
            g = g.set_index("trade_date")
            sp = (g.div_yield.rolling(20).mean() - g.cn_10y).dropna()
            spread_pct[idx] = (_pct_rank(sp), float(sp.iloc[-1]) if len(sp) else None)

    # --- 相对强弱：科创50 / 中证红利 ---
    px = pd.read_sql(
        "select trade_date,index_code,close from px_index_daily_csi where index_code in ('000688','000922')", c)
    px["trade_date"] = pd.to_datetime(px["trade_date"])
    rs_pct = None
    if len(px):
        w = px.pivot_table(index="trade_date", columns="index_code", values="close").ffill()
        if "000688" in w and "000922" in w:
            rs_pct = _pct_rank((w["000688"] / w["000922"]).dropna())

    def fv(idx, attr="fear_composite"):
        r = fear_map.get(idx)
        v = getattr(r, attr, None) if r is not None else None
        return None if v is None or pd.isna(v) else float(v)

    # ===== 成长：科创50 + 中证有色 =====
    g_pe = [pe_map.get("000688"), pe_map.get("000819")]
    g_fe = [fv("000688", "fear_rv_pct"), fv("000819", "fear_rv_pct")]
    g_pe_avg = np.nanmean([x for x in g_pe if x is not None]) if any(g_pe) else None
    g_fe_avg = np.nanmean([x for x in g_fe if x is not None]) if any(g_fe) else None
    g_score = None
    if g_pe_avg is not None and g_fe_avg is not None:
        rs = rs_pct if rs_pct is not None else 50.0
        g_score = 0.40 * (100 - g_pe_avg) + 0.35 * (100 - g_fe_avg) + 0.25 * rs

    # ===== 价值：中证红利 + 红利低波 =====
    v_sp = [spread_pct.get("000922", (None, None))[0], spread_pct.get("H30269", (None, None))[0]]
    v_pe = [pe_map.get("000922"), pe_map.get("H30269")]
    v_fe = [fv("000922", "fear_rv_pct"), fv("H30269", "fear_rv_pct")]
    v_sp_avg = np.nanmean([x for x in v_sp if x is not None]) if any(x is not None for x in v_sp) else None
    v_pe_avg = np.nanmean([x for x in v_pe if x is not None]) if any(v_pe) else None
    v_fe_avg = np.nanmean([x for x in v_fe if x is not None]) if any(v_fe) else None
    v_score = None
    if v_sp_avg is not None and v_pe_avg is not None:
        v_score = 0.40 * v_sp_avg + 0.30 * (100 - v_pe_avg) + 0.30 * (100 - v_fe_avg)

    def stance(sc):
        if sc is None:
            return "数据不足", "mid"
        if sc >= 65:
            return "加仓", "up"
        if sc >= 50:
            return "持有", "mid"
        if sc >= 35:
            return "减仓", "down"
        return "回避", "down"

    g_st, g_kind = stance(g_score)
    v_st, v_kind = stance(v_score)

    # 理由
    g_reasons = []
    if g_pe_avg is not None:
        g_reasons.append("估值分位 %.0f%%（%s）" % (
            g_pe_avg, "偏贵" if g_pe_avg > 70 else "不贵" if g_pe_avg < 40 else "中性"))
    if g_fe_avg is not None:
        g_reasons.append("恐慌分位 %.0f%%（%s）" % (
            g_fe_avg, "极高" if g_fe_avg > 85 else "偏高" if g_fe_avg > 75 else "正常"))
    if rs_pct is not None:
        g_reasons.append("相对强弱 %.0f%% 分位" % rs_pct)

    v_reasons = []
    if v_sp_avg is not None:
        v_reasons.append("利差分位 %.0f%%（%s）" % (v_sp_avg, "仍便宜" if v_sp_avg > 60 else "不便宜"))
    if v_pe_avg is not None:
        v_reasons.append("PE 分位 %.0f%%（%s）" % (v_pe_avg, "高位" if v_pe_avg > 85 else "中位"))
    if v_fe_avg is not None:
        v_reasons.append("恐慌分位 %.0f%%（%s）" % (v_fe_avg, "平稳" if v_fe_avg < 50 else "偏高"))

    tilt = "均衡"
    if g_score is not None and v_score is not None:
        if g_score - v_score > 8:
            tilt = "偏成长"
        elif v_score - g_score > 8:
            tilt = "偏价值"

    return {
        "tilt": tilt,
        "growth": {"name": "成长（科创50+有色）", "score": None if g_score is None else round(g_score, 1),
                   "stance": g_st, "kind": g_kind, "reasons": g_reasons},
        "value": {"name": "价值（红利）", "score": None if v_score is None else round(v_score, 1),
                  "stance": v_st, "kind": v_kind, "reasons": v_reasons},
    }


def _advice(pe, fear_map, hs300):
    """透明的规则建议：用估值分位 + 恐慌分位决定仓位偏向。"""
    pe_map = {}
    for idx, g in pe.groupby("index_code"):
        s = g.pe_ttm.dropna()
        if len(s) > 250:
            pe_map[idx] = float((s < s.iloc[-1]).mean() * 100)
    g_f = fear_map["000688"].fear_composite if "000688" in fear_map else 50
    v_pe = pe_map.get("000922", 50)
    v_f = fear_map["000922"].fear_composite if "000922" in fear_map else 50
    g_pe = pe_map.get("000688", 50)

    if g_f > 75 and v_pe > 90:
        return "减仓观望：两端都不便宜",             f"成长恐慌 {g_f:.0f}（高位）、红利 PE 分位 {v_pe:.0f}%（历史顶部），成长在杀跌、红利已买贵，降仓等信号"
    if g_f > 75 and v_f < 45:
        return "防守：红利为主，成长只留底仓", \
            f"成长恐慌度 {g_f:.0f}（极高）而红利仅 {v_f:.0f}，资金正在撤离成长；但红利 PE 分位 {v_pe:.0f}% 已不便宜，仓位控制在 5 成"
    if g_f < 30 and g_pe < 50:
        return "进攻：成长优先", f"成长恐慌回落至 {g_f:.0f}、PE 分位 {g_pe:.0f}%，赔率改善"
    return "均衡持有", f"成长恐慌 {g_f:.0f}、红利 PE 分位 {v_pe:.0f}%，无明显极端，维持均衡"


# ---------------- 舆情（缓存优先，不在请求链路里直连原始接口） ----------------
POS_WORDS = ("利好", "增持", "回购", "中标", "签约", "涨价", "提价", "超预期", "增长", "扭亏",
             "新高", "获批", "扩产", "分红", "加码", "突破", "合作", "订单", "补贴", "降准",
             "降息", "减税", "降费", "回暖", "复苏", "落地", "量产", "放量", "改善")
NEG_WORDS = ("利空", "减持", "亏损", "下滑", "下降", "处罚", "立案", "调查", "退市", "爆雷",
             "违约", "下调", "裁员", "停产", "召回", "诉讼", "质押", "减值", "跌停", "暴跌",
             "风险", "警示", "延期", "终止", "警示函", "问询", "解禁")


def _score_text(title):
    """单条文本多空打分：+1 偏多 / -1 偏空 / 0 中性。"""
    pos = sum(1 for w in POS_WORDS if w in title)
    neg = sum(1 for w in NEG_WORDS if w in title)
    if pos > neg:
        return 1
    if neg > pos:
        return -1
    return 0


def collect_opinion(hot_codes):
    """看法层：①千股千评综合得分（东财对个股的多空评分）②财联社快讯关键词多空。

    返回 dict，任何一路失败都不影响另一路。
    """
    import akshare as ak
    res = {"score_text": None, "comment_n": 0, "news_pos": 0, "news_neg": 0,
           "news_n": 0, "score_news": None, "news_samples": []}

    # ① 千股千评：热度股的综合得分（0-100，越高越看多）
    try:
        d = ak.stock_comment_em()
        d["代码"] = d["代码"].astype(str).str.zfill(6)
        sub = d[d["代码"].isin([str(x).zfill(6) for x in hot_codes])]
        if len(sub) >= 5:
            res["score_text"] = round(float(sub["综合得分"].mean()), 1)
            res["comment_n"] = int(len(sub))
            res["comment_market"] = round(float(d["综合得分"].mean()), 1)
    except Exception:
        pass

    # ② 财联社快讯：最近 20 条标题做关键词多空（样本小，只作方向参考）
    try:
        n = ak.stock_news_global_cls(symbol="全部")
        titles = [str(t) for t in n["标题"].tolist()][:20]
        pos = neg = 0
        samples = []
        for t in titles:
            sc = _score_text(t)
            if sc > 0:
                pos += 1
                if len(samples) < 3:
                    samples.append({"polarity": "正", "title": t[:40]})
            elif sc < 0:
                neg += 1
                if len(samples) < 3:
                    samples.append({"polarity": "负", "title": t[:40]})
        res.update({"news_pos": pos, "news_neg": neg, "news_n": len(titles),
                    "news_samples": samples})
        if pos + neg > 0:
            res["score_news"] = round(50 + 50 * (pos - neg) / max(len(titles), 1), 1)
        else:
            res["score_news"] = 50.0
    except Exception:
        pass
    return res


def _sem_meta(c, date):
    return c.execute(
        "select source_name, score, mean_pct, up_ratio, fetched_at, "
        "score_text, score_news, score_price, comment_n, news_pos, news_neg, news_n "
        "from web_sentiment_meta where trade_date=?", (date,)).fetchone()


def _sent_payload(c, date):
    rows = pd.read_sql("select * from web_sentiment where trade_date=? order by source, rank", c, params=(date,))
    return _pack_sentiment(rows, date, cached=True)


def _meta_payload(meta):
    keys = ["source_name", "score", "mean_pct", "up_ratio", "fetched_at",
            "score_text", "score_news", "score_price", "comment_n",
            "news_pos", "news_neg", "news_n"]
    d = {k: meta[i] for i, k in enumerate(keys)}
    return d


def get_sentiment_cached():
    """只读缓存：绝不触发外部抓取。缺失时回退最近一份并标 stale。"""
    c = conn()
    _ensure(c)
    today = dt.date.today().strftime("%Y-%m-%d")
    meta = _sem_meta(c, today)
    stale = False
    if not meta:
        prev = c.execute("select trade_date from web_sentiment_meta order by trade_date desc limit 1").fetchone()
        if prev:
            today, meta = prev[0], _sem_meta(c, prev[0])
            stale = True
    if not meta:
        c.close()
        return {"date": None, "pending": True, "stale": True, "score": None, "mean_pct": None,
                "up_ratio": None, "hot": [], "search": [], "source_name": None, "fetched_at": None}
    res = _sent_payload(c, today)
    c.close()
    res.update(_meta_payload(meta))
    res.update({"stale": stale, "pending": False})
    return res


def collect_sentiment(force=False, throttle_min=10):
    """抓原始接口并写缓存。10 分钟内不重复抓（force 例外）。"""
    import akshare as ak
    c = conn()
    _ensure(c)
    today = dt.date.today().strftime("%Y-%m-%d")
    meta = _sem_meta(c, today)
    if meta and not force:
        try:
            age = (dt.datetime.now() - dt.datetime.strptime(meta[4][:19], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
            if age < throttle_min:
                res = _sent_payload(c, today)
                c.close()
                res.update(_meta_payload(meta))
                res.update({"skipped": True})
                return res
        except Exception:
            pass

    out, now = [], dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hot, src_name = None, "东财人气榜"
    for _ in range(2):
        try:
            hot = ak.stock_hot_rank_em().head(20)
            break
        except Exception:
            time.sleep(1.2)
    if hot is None or not len(hot):
        try:
            xq = ak.stock_hot_tweet_xq(symbol="最热门").head(20)
            hot = pd.DataFrame({
                "当前排名": range(1, len(xq) + 1),
                "代码": xq["股票代码"], "股票名称": xq["股票简称"],
                "涨跌幅": np.nan, "关注": xq["关注"],
            })
            src_name = "雪球讨论榜"
        except Exception:
            hot = None
    if hot is not None and len(hot):
        for _, r in hot.iterrows():
            code = str(r["代码"]).replace("SH", "").replace("SZ", "").replace("BJ", "")
            pv, hv = r.get("涨跌幅"), r.get("关注")
            out.append((today, "热度榜", int(r["当前排名"]), code, r["股票名称"],
                        None if pv is None or pd.isna(pv) else float(pv),
                        None if hv is None or pd.isna(hv) else float(hv)))

    try:
        d = ak.stock_hot_search_baidu(symbol="A股", date=dt.date.today().strftime("%Y%m%d"), time="今日")
        for i, r in d.iterrows():
            nm = str(r["名称/代码"])
            pct = str(r["涨跌幅"]).replace("%", "").replace("+", "")
            out.append((today, "百度热搜", i + 1, "", nm,
                        float(pct) if pct not in ("", "nan") else None, float(r["综合热度"])))
    except Exception:
        pass

    if not out:
        c.close()
        return get_sentiment_cached()

    c.execute("DELETE FROM web_sentiment WHERE trade_date=?", (today,))
    c.executemany(
        "INSERT OR REPLACE INTO web_sentiment (trade_date,source,rank,code,name,pct,heat,_fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?)", [o + (now,) for o in out])
    c.commit()
    rows = pd.read_sql("select * from web_sentiment where trade_date=? order by source, rank", c, params=(today,))
    res = _pack_sentiment(rows, today, cached=False)
    # 看法层：热度股千股千评得分 + 快讯关键词多空
    hot_codes = [r["code"] for _, r in rows[rows.source == "热度榜"].iterrows() if r["code"]]
    op = collect_opinion(hot_codes)
    score_price = res["score"]
    parts = [(score_price, 0.25)]
    if op["score_text"] is not None:
        parts.append((op["score_text"], 0.40))
    if op["score_news"] is not None:
        parts.append((op["score_news"], 0.35))
    wsum = sum(w for _, w in parts)
    composite = round(sum(v * w for v, w in parts) / wsum, 1)
    res.update({"score": composite, "score_price": score_price,
                "score_text": op["score_text"], "score_news": op["score_news"],
                "comment_n": op["comment_n"], "comment_market": op.get("comment_market"),
                "news_pos": op["news_pos"], "news_neg": op["news_neg"], "news_n": op["news_n"],
                "news_samples": op["news_samples"]})
    c.execute("INSERT OR REPLACE INTO web_sentiment_meta (trade_date,source_name,score,mean_pct,up_ratio,fetched_at,"
              "score_text,score_news,score_price,comment_n,news_pos,news_neg,news_n) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (today, src_name, composite, res["mean_pct"], res["up_ratio"], now,
               op["score_text"], op["score_news"], score_price,
               op["comment_n"], op["news_pos"], op["news_neg"], op["news_n"]))
    c.commit()
    c.close()
    res.update({"source_name": src_name, "fetched_at": now, "stale": False, "pending": False})
    return res


def _pack_sentiment(rows, today, cached):
    if not len(rows):
        return {"date": today, "score": 50, "hot": [], "search": [], "mean_pct": 0, "up_ratio": 50,
                "cached": cached, "source_name": "热度榜"}
    hot = rows[rows.source == "热度榜"]
    sea = rows[rows.source == "百度热搜"]
    pcts = pd.concat([hot.pct, sea.pct]).dropna()
    mean_pct = float(pcts.mean()) if len(pcts) else 0.0
    up_ratio = float((pcts > 0).mean() * 100) if len(pcts) else 50.0
    score = float(np.clip(50 + (up_ratio - 50) * 1.5 + float(np.clip(mean_pct, -5, 5)) * 0.8, 0, 100))
    return {
        "date": today, "cached": cached, "source_name": "热度榜",
        "score": round(score, 1), "mean_pct": round(mean_pct, 2), "up_ratio": round(up_ratio, 0),
        "hot": [{"rank": int(r["rank"]), "code": r["code"], "name": r["name"],
                 "pct": None if pd.isna(r["pct"]) else round(float(r["pct"]), 2),
                 "heat": None if pd.isna(r["heat"]) else float(r["heat"])} for _, r in hot.iterrows()],
        "search": [{"rank": int(r["rank"]), "name": r["name"],
                    "pct": None if pd.isna(r["pct"]) else round(float(r["pct"]), 2),
                    "heat": None if pd.isna(r["heat"]) else int(r["heat"])} for _, r in sea.iterrows()],
    }


# ---------------- 总结（每天 20:00 生成一次，之后只读缓存） ----------------
RELEASE_HOUR = 20


def _build_summary(period="day"):
    c = conn()
    date = _latest_trade_date(c)
    ov = overview()
    days = {"day": 1, "week": 5, "month": 21}.get(period, 1)
    perf = []
    for w in WATCH:
        s = get_series(w["code"], "D", days + 1)["points"]
        if len(s) >= 2:
            ret = (s[-1]["close"] / s[0]["close"] - 1) * 100
            perf.append({"name": w["name"], "group": w["group"], "ret": round(ret, 2)})
    perf.sort(key=lambda x: -x["ret"])
    snaprows = pd.read_sql("select * from web_daily_snapshot order by trade_date desc limit ?", c, params=(days,))
    se = get_sentiment_cached()
    c.close()

    win = ("近%d个交易日" % days) if days > 1 else "今日"
    head = ("%s：上证 %+.2f%%、深证 %+.2f%%，两市成交 %.0f 亿（20日均值的 %.0f%%）"
            % (date, ov["sh"]["pct"], ov["sz"]["pct"], ov["amount"], ov["vol_ratio"] * 100))
    bullets = [
        "市场温度 %s（%s），全指恐慌度 %s" % (ov["temperature"], ov["temp_label"], ov["fear"]),
        "小盘相对大盘 %+.2fpp，%s" % (ov["smallcap"], "小盘占优" if ov["smallcap"] > 0 else "权重占优"),
        win + "表现：" + "、".join("%s %+.2f%%" % (p["name"], p["ret"]) for p in perf[:3])
        + "；最弱 " + "%s %+.2f%%" % (perf[-1]["name"], perf[-1]["ret"]),
        "极端信号 %d 个（估值高位/低位 或 恐慌高位）：%s" % (
            ov["anomaly"], "、".join("%s(%s)" % (d["name"], "/".join(d["flag"])) for d in ov["anomaly_detail"]) or "无"),
    ]
    if se and se.get("score") is not None:
        bullets.append("舆情情绪 %s（热门股平均 %+.2f%%，上涨占比 %.0f%%）"
                       % (se["score"], se["mean_pct"], se["up_ratio"]))
    trend = ""
    if len(snaprows) >= 2:
        d0, d1 = snaprows.iloc[0], snaprows.iloc[-1]
        trend = "温度由 %s 变为 %s（%+.1f）" % (d1.temperature, d0.temperature, d0.temperature - d1.temperature)
    return {"period": period, "date": date, "headline": head, "bullets": bullets,
            "conclusion": ov["advice"] + "。" + ov["advice_reason"], "trend": trend,
            "perf": perf, "temperature": ov["temperature"], "temp_label": ov["temp_label"]}


def collect_summary(period="day"):
    """生成并落库（幂等，一天一次即可）。"""
    payload = _build_summary(period)
    c = conn()
    _ensure(c)
    c.execute("INSERT OR REPLACE INTO web_daily_summary (trade_date, period, payload, generated_at) VALUES (?,?,?,?)",
              (payload["date"], period, json.dumps(payload, ensure_ascii=False),
               dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit()
    c.close()
    payload.update({"cached": False})
    return payload


def get_summary(period="day"):
    """只读缓存。未生成时：返回上一期并标 stale。"""
    c = conn()
    _ensure(c)
    key = _latest_trade_date(c)
    row = c.execute("select payload, generated_at from web_daily_summary where trade_date=? and period=?",
                    (key, period)).fetchone()
    if row:
        p = json.loads(row[0])
        p.update({"cached": True, "generated_at": row[1], "stale": False})
        c.close()
        return p
    prev = c.execute("select trade_date, payload, generated_at from web_daily_summary "
                     "where period=? and trade_date<? order by trade_date desc limit 1", (period, key)).fetchone()
    c.close()
    if prev:
        p = json.loads(prev[1])
        p.update({"cached": True, "generated_at": prev[2], "stale": True,
                  "note": "今日总结将于 %d:00 生成，当前为 %s 的版本" % (RELEASE_HOUR, prev[0])})
        return p
    return {"period": period, "date": key, "pending": True, "stale": True, "cached": True,
            "perf": [], "bullets": [], "headline": "",
            "note": "暂无历史总结。今日总结将于 %d:00 生成（或运行一次每日任务）" % RELEASE_HOUR,
            "conclusion": "", "temperature": None, "temp_label": ""}


# ---------------- 快照 / 每日任务 ----------------
def save_snapshot():
    c = conn()
    _ensure(c)
    ov = overview()
    se = get_sentiment_cached()
    sm = get_summary("day")
    txt = (sm.get("headline") or "") + "｜" + (sm.get("conclusion") or "")
    c.execute(
        "INSERT OR REPLACE INTO web_daily_snapshot (trade_date,temperature,fear,sh_pct,sz_pct,amount,"
        "vol_ratio,smallcap,sentiment_score,hot_mean_pct,anomaly,advice,summary,_saved_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ov["date"], ov["temperature"], ov["fear"], ov["sh"]["pct"], ov["sz"]["pct"], ov["amount"],
         ov["vol_ratio"], ov["smallcap"], se.get("score"), se.get("mean_pct"), ov["anomaly"],
         ov["advice"], txt, dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit()
    c.close()
    return {"ok": True, "date": ov["date"]}


def daily_job(force_sentiment=False):
    """每日任务：采集舆情 → 生成日/周/月总结 → 存快照。自动化命令直接调这个。"""
    steps = {}
    try:
        se = collect_sentiment(force=force_sentiment)
        steps["sentiment"] = {"score": se.get("score"), "skipped": se.get("skipped", False)}
    except Exception as e:
        steps["sentiment"] = {"error": "%s: %s" % (type(e).__name__, e)}
    for p in ("day", "week", "month"):
        try:
            s = collect_summary(p)
            steps["summary_" + p] = {"date": s["date"]}
        except Exception as e:
            steps["summary_" + p] = {"error": "%s: %s" % (type(e).__name__, e)}
    try:
        steps["snapshot"] = save_snapshot()
    except Exception as e:
        steps["snapshot"] = {"error": "%s: %s" % (type(e).__name__, e)}
    return {"ok": True, "ran_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "steps": steps}


def temp_history(freq="D"):
    c = conn()
    _ensure(c)
    d = pd.read_sql("select * from web_daily_snapshot order by trade_date", c)
    c.close()
    if not len(d):
        return {"points": []}
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    d = d.set_index("trade_date")
    if freq != "D":
        rule = {"W": "W-FRI", "M": "ME"}.get(freq)
        if rule:
            d = d.resample(rule).agg({"temperature": "mean", "amount": "mean", "sentiment_score": "mean"})
            d = d.dropna(subset=["temperature"])
    return {"points": [{"date": i.strftime("%Y-%m-%d"),
                        "temperature": round(float(r.temperature), 1) if pd.notna(r.temperature) else None,
                        "amount": round(float(r.amount), 0) if pd.notna(r.amount) else None,
                        "sentiment": round(float(r.sentiment_score), 1) if pd.notna(r.sentiment_score) else None}
                       for i, r in d.iterrows()]}


def watch_list():
    return {"items": WATCH}


# ---------------- 重点关注：多周期小卡片 ----------------
GRID = [
    {"code": "000001", "name": "上证指数", "src": "csi", "tag": "大盘"},
    {"code": "399001", "name": "深证成指", "src": "cni", "tag": "大盘"},
    {"code": "399006", "name": "创业板指", "src": "cni", "tag": "成长"},
    {"code": "000300", "name": "沪深300", "src": "csi", "tag": "宽基"},
    {"code": "000688", "name": "科创50", "src": "csi", "tag": "成长"},
    {"code": "000922", "name": "中证红利", "src": "csi", "tag": "价值"},
    {"code": "H30269", "name": "红利低波", "src": "csi", "tag": "价值"},
    {"code": "000819", "name": "中证有色", "src": "csi", "tag": "周期"},
    {"code": "931787", "name": "港股创新药", "src": "csi", "tag": "医药"},
    {"code": ".NDX", "name": "纳斯达克100", "src": "us", "tag": "海外", "premium": "159941"},
    {"code": "600941", "name": "中国移动", "src": "stock", "tag": "央企"},
    {"code": "601728", "name": "中国电信", "src": "stock", "tag": "央企"},
]


def _grid_series(c, code, src):
    if src == "cni":
        d = pd.read_sql("select trade_date, close from px_index_daily_cni where index_code=? order by trade_date",
                        c, params=(code,))
    elif src == "us":
        d = pd.read_sql("select trade_date, close from px_index_daily_us where index_code=? order by trade_date",
                        c, params=(code,))
    elif src == "stock":
        d = pd.read_sql("select trade_date, close from px_stock_daily where stock_code=? order by trade_date",
                        c, params=(code,))
    else:
        d = pd.read_sql("select trade_date, close from px_index_daily_csi where index_code=? order by trade_date",
                        c, params=(code,))
    if not len(d):
        return None
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.set_index("trade_date")["close"].dropna()


def grid_cards(freq="D"):
    """卡片数据：每个标的的最新点位 + 该周期涨跌幅；纳指附带 159941 溢价率。"""
    c = conn()
    rule = {"W": "W-FRI", "M": "ME", "Y": "YE"}.get(freq)
    out = []
    for it in GRID:
        s = _grid_series(c, it["code"], it["src"])
        if s is None or not len(s):
            out.append({**it, "close": None, "pct": None})
            continue
        last_close = float(s.iloc[-1])
        if rule:
            r = s.resample(rule).last().dropna()
            pct = float(r.iloc[-1] / r.iloc[-2] - 1) * 100 if len(r) >= 2 else None
        else:
            pct = float(s.iloc[-1] / s.iloc[-2] - 1) * 100 if len(s) >= 2 else None
        item = {**it, "date": s.index[-1].strftime("%Y-%m-%d"),
                "close": round(last_close, 2),
                "pct": None if pct is None else round(pct, 2)}
        if it.get("premium"):
            p = c.execute(
                "select trade_date, premium_lag from px_lof_daily where fund_code=? and premium_lag is not null "
                "order by trade_date desc limit 1", (it["premium"],)).fetchone()
            item["premium"] = None if p is None else round(float(p[1]), 2)
            item["premium_date"] = None if p is None else p[0]
        out.append(item)
    c.close()
    return {"freq": freq, "items": out}
