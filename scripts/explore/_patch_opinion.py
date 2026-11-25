# -*- coding: utf-8 -*-
"""补丁：舆情情绪分拆成「看法层（千股千评+快讯多空）」与「表现层（涨跌）」。"""
import io
import os
import re

P = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "server", "analytics.py")
s = io.open(P, encoding="utf-8").read()

# 1) meta 表加列（幂等）
s = s.replace(
    '''    CREATE TABLE IF NOT EXISTS web_sentiment_meta(
        trade_date TEXT PRIMARY KEY, source_name TEXT, score REAL, mean_pct REAL,
        up_ratio REAL, fetched_at TEXT);''',
    '''    CREATE TABLE IF NOT EXISTS web_sentiment_meta(
        trade_date TEXT PRIMARY KEY, source_name TEXT, score REAL, mean_pct REAL,
        up_ratio REAL, fetched_at TEXT,
        score_text REAL, score_news REAL, score_price REAL,
        comment_n INTEGER, news_pos INTEGER, news_neg INTEGER, news_n INTEGER);''')

# 已有库的迁移
s = s.replace(
    '''    CREATE TABLE IF NOT EXISTS web_sentiment(''',
    '''    for _col, _typ in [("score_text", "REAL"), ("score_news", "REAL"), ("score_price", "REAL"),
                       ("comment_n", "INTEGER"), ("news_pos", "INTEGER"), ("news_neg", "INTEGER"),
                       ("news_n", "INTEGER")]:
        try:
            c.execute("ALTER TABLE web_sentiment_meta ADD COLUMN %s %s" % (_col, _typ))
        except Exception:
            pass

    CREATE TABLE IF NOT EXISTS web_sentiment(''')

# 2) 插入「看法层」采集函数（放在 _sem_meta 之前）
s = s.replace(
    '''def _sem_meta(c, date):''',
    '''POS_WORDS = ("利好", "增持", "回购", "中标", "签约", "涨价", "提价", "超预期", "增长", "扭亏",
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


def _sem_meta(c, date):''')

io.open(P, "w", encoding="utf-8").write(s)
print("part1 ok")
