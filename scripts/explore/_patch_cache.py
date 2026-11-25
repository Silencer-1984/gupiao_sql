# -*- coding: utf-8 -*-
"""一次性补丁脚本：把 analytics.py 的舆情/总结改为缓存优先，并新增每日任务。"""
import io
import os

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server", "analytics.py")
src = io.open(P, encoding="utf-8").read()

NEW = r'''# ---------------- 舆情（缓存优先，不在请求链路里直连原始接口） ----------------
def _sem_meta(c, date):
    return c.execute(
        "select source_name, score, mean_pct, up_ratio, fetched_at "
        "from web_sentiment_meta where trade_date=?", (date,)).fetchone()


def _sent_payload(c, date):
    rows = pd.read_sql("select * from web_sentiment where trade_date=? order by source, rank", c, params=(date,))
    return _pack_sentiment(rows, date, cached=True)


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
    res.update({"score": meta[1], "mean_pct": meta[2], "up_ratio": meta[3],
                "source_name": meta[0], "fetched_at": meta[4], "stale": stale, "pending": False})
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
                res.update({"score": meta[1], "mean_pct": meta[2], "up_ratio": meta[3],
                            "source_name": meta[0], "fetched_at": meta[4], "skipped": True})
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
    c.execute("INSERT OR REPLACE INTO web_sentiment_meta (trade_date,source_name,score,mean_pct,up_ratio,fetched_at) "
              "VALUES (?,?,?,?,?,?)",
              (today, src_name, res["score"], res["mean_pct"], res["up_ratio"], now))
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


'''

i = src.index("# ---------------- 舆情 ----------------")
j = src.index("def temp_history(")
out = src[:i] + NEW + src[j:]

# 扩展 _ensure 建表
out = out.replace(
    '''    CREATE TABLE IF NOT EXISTS web_sentiment(''',
    '''    CREATE TABLE IF NOT EXISTS web_sentiment_meta(
        trade_date TEXT PRIMARY KEY, source_name TEXT, score REAL, mean_pct REAL,
        up_ratio REAL, fetched_at TEXT);

    CREATE TABLE IF NOT EXISTS web_daily_summary(
        trade_date TEXT, period TEXT, payload TEXT, generated_at TEXT,
        PRIMARY KEY(trade_date, period));

    CREATE TABLE IF NOT EXISTS web_sentiment(''')

io.open(P, "w", encoding="utf-8").write(out)
print("patched:", len(out), "chars")
