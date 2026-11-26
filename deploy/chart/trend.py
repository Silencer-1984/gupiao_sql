# -*- coding: utf-8 -*-
"""指数走势模块：任意指数 × 任意区间/粒度的涨跌图表，附带最匹配该指数类型的指标副轴、
指标分位标准线、以及指数间对比曲线。

设计要点
- 指标白名单按指数类型（宽基/价值/成长/周期/海外）分配，只暴露对该类型真正有效的指标。
- 指标与其分位标准线共用一根副轴（PE 分位线画在 PE 轴上）。
- 对比指数走独立副轴，用「区间起点 = 100」的归一化序列，避免量级差异压扁主图。
"""
import os
import sqlite3
import numpy as np
import pandas as pd

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chart.db")

# ---------------- 指数池 ----------------
# cls: core 宽基/大盘 · value 价值 · growth 成长 · cycle 周期 · overseas 海外 · stock 个股
UNIVERSE = [
    {"code": "000300", "name": "沪深300", "src": "csi", "cls": "core", "tag": "大盘宽基"},
    {"code": "000001", "name": "上证指数", "src": "csi", "cls": "core", "tag": "大盘"},
    {"code": "H30269", "name": "红利低波", "src": "csi", "cls": "value", "tag": "价值"},
    {"code": "000688", "name": "科创50", "src": "csi", "cls": "growth", "tag": "成长"},
    {"code": "931787", "name": "港股创新药", "src": "csi", "cls": "growth", "tag": "医药成长"},
    {"code": "000819", "name": "中证有色", "src": "csi", "cls": "cycle", "tag": "周期"},
    {"code": ".NDX", "name": "纳斯达克100", "src": "us", "cls": "overseas", "tag": "海外"},
    {"code": "601728", "name": "中国电信", "src": "stock", "cls": "stock", "tag": "高股息央企"},
    {"code": "600941", "name": "中国移动", "src": "stock", "cls": "stock", "tag": "高股息央企"},
]
SRC = {u["code"]: u["src"] for u in UNIVERSE}
NAME = {u["code"]: u["name"] for u in UNIVERSE}

# ---------------- 指标字典 ----------------
IND = {
    "pe_ttm": {"label": "PE-TTM", "unit": "倍", "digits": 2, "kind": "line",
               "why": "宽基/成长定价的核心锚，看绝对估值水位"},
    "div": {"label": "股息率", "unit": "%", "digits": 2, "kind": "line",
            "why": "价值股的现金流回报，直接决定红利资产吸引力"},
    "spread": {"label": "股息率−10Y国债", "unit": "pp", "digits": 2, "kind": "line",
               "why": "红利的性价比本质是相对无风险利率的利差"},
    "erp": {"label": "股债性价比", "unit": "%", "digits": 2, "kind": "line",
            "why": "1/PE 减 10Y 国债，衡量股票相对债券的赔率"},
    "fear": {"label": "恐慌度", "unit": "", "digits": 1, "kind": "line",
             "why": "波动率+QVIX 合成分位，判断情绪是否到极端"},
    "vol": {"label": "20日年化波动", "unit": "%", "digits": 1, "kind": "line",
            "why": "波动是成长的定价来源，也是仓位管理依据"},
    "amount": {"label": "成交额", "unit": "亿", "digits": 0, "kind": "bar",
               "why": "量能决定趋势能否延续"},
    "rs": {"label": "相对沪深300（60日）", "unit": "pp", "digits": 2, "kind": "line",
           "why": "成长股的超额收益来自相对强弱，而非绝对点位"},
    "premium": {"label": "159941溢价", "unit": "%", "digits": 2, "kind": "line",
                "why": "A股收盘时可观测的QDII溢价；溢价越高，买入等于多付钱"},
}

# 每类指数只给「对它最有效」的指标，顺序即推荐优先级
CLASS_IND = {
    "core": ["pe_ttm", "erp", "amount", "fear", "vol"],
    "value": ["div", "spread", "pe_ttm", "vol"],
    "growth": ["pe_ttm", "fear", "vol"],
    "cycle": ["pe_ttm", "fear", "vol"],
    "overseas": ["premium", "vol"],
    "stock": ["div", "pe_ttm", "vol"],
}

# 计算分位标准线的指标（分位 → 指标数值的水平线）
PCT_IND = {"pe_ttm", "div", "spread", "erp", "premium"}
PCT_WINDOWS = {"1Y": 250, "3Y": 750, "5Y": 1250, "ALL": None}

RANGES = {
    "1M": {"label": "近1月", "days": 21, "gran": "D"},
    "3M": {"label": "近3月", "days": 63, "gran": "D"},
    "6M": {"label": "近半年", "days": 125, "gran": "W"},
    "1Y": {"label": "近1年", "days": 250, "gran": "W"},
    "3Y": {"label": "近3年", "days": 750, "gran": "W"},
    "5Y": {"label": "近5年", "days": 1250, "gran": "M"},
    "ALL": {"label": "全部数据", "days": None, "gran": "M"},
}
GRANS = {"D": {"label": "日", "rule": None},
         "W": {"label": "周", "rule": "W-FRI"},
         "M": {"label": "月", "rule": "ME"},
         "H": {"label": "半年", "rule": "6ME"},
         "Y": {"label": "年", "rule": "YE"}}

BENCH = "000300"


def conn():
    c = sqlite3.connect(DB, timeout=30)
    return c


# ---------------- 取数 ----------------
def _raw_price(c, code):
    src = SRC.get(code, "csi")
    if src == "cni":
        d = pd.read_sql("select trade_date, close, pct_chg_ratio*100 as pct, amount "
                        "from px_index_daily_cni where index_code=? order by trade_date", c, params=(code,))
    elif src == "us":
        d = pd.read_sql("select trade_date, close, null as pct, null as amount "
                        "from px_index_daily_us where index_code=? order by trade_date", c, params=(code,))
    elif src == "stock":
        # 个股成交额库内单位是元，除以 1e8 换成亿元，与指数口径一致；pct 由收盘价推算
        d = pd.read_sql("select trade_date, close, null as pct, amount/100000000.0 as amount "
                        "from px_stock_daily where stock_code=? order by trade_date", c, params=(code,))
    else:
        d = pd.read_sql("select trade_date, close, pct_chg as pct, amount "
                        "from px_index_daily_csi where index_code=? order by trade_date", c, params=(code,))
    if not len(d):
        return None
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    d = d.drop_duplicates("trade_date").set_index("trade_date").sort_index()
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    d["pct"] = pd.to_numeric(d["pct"], errors="coerce")
    d["amount"] = pd.to_numeric(d["amount"], errors="coerce")
    d = d.dropna(subset=["close"])
    d["pct"] = d["pct"].fillna(d["close"].pct_change() * 100).fillna(0.0)
    # 去掉指数发布前用发行基点填充的占位行（如科创50 的 2015-01-01 = 1000.00）
    i, first = 0, d["close"].iloc[0]
    while i < len(d) and abs(d["close"].iloc[i] - first) < 1e-9 and abs(d["pct"].iloc[i]) < 1e-9:
        i += 1
    d = d.iloc[max(i - 1, 0):]
    return d


def _pe(c, code):
    d = pd.read_sql("select trade_date, pe_ttm from px_index_daily_csi "
                    "where index_code=? and pe_ttm is not null order by trade_date", c, params=(code,))
    if not len(d):
        return None
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.drop_duplicates("trade_date").set_index("trade_date")["pe_ttm"].astype(float)


def _div(c, code):
    if SRC.get(code) == "stock":
        d = pd.read_sql("select trade_date, div_yield from val_stock_dividend_yield_focus "
                        "where stock_code=? and div_yield is not null order by trade_date", c, params=(code,))
    else:
        d = pd.read_sql("select trade_date, div_yield from val_index_dividend_yield "
                        "where index_code=? and div_yield is not null order by trade_date", c, params=(code,))
    if not len(d):
        return None
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.drop_duplicates("trade_date").set_index("trade_date")["div_yield"].astype(float)


def _stock_pe(c, code):
    d = pd.read_sql("select trade_date, pe_ttm from val_stock_pe_daily "
                    "where stock_code=? and pe_ttm is not null order by trade_date", c, params=(code,))
    if not len(d):
        return None
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.drop_duplicates("trade_date").set_index("trade_date")["pe_ttm"].astype(float)


def _premium(c, fund_code="159941"):
    """159941 溢价（premium_lag = A股收盘时可观测口径），字段本身是百分数。"""
    d = pd.read_sql("select trade_date, premium_lag from px_lof_daily "
                    "where fund_code=? and premium_lag is not null order by trade_date", c, params=(fund_code,))
    if not len(d):
        return None
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.drop_duplicates("trade_date").set_index("trade_date")["premium_lag"].astype(float)


def _fear(c, code):
    d = pd.read_sql("select trade_date, fear_composite from mkt_fear_daily "
                    "where index_code=? and fear_composite is not null order by trade_date", c, params=(code,))
    if not len(d):
        return None
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.drop_duplicates("trade_date").set_index("trade_date")["fear_composite"].astype(float)


def _bond(c):
    d = pd.read_sql("select trade_date, cn_10y from macro_bond_yield "
                    "where cn_10y is not null order by trade_date", c)
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    return d.drop_duplicates("trade_date").set_index("trade_date")["cn_10y"].astype(float)


# ---------------- 指标序列 ----------------
def _ind_series(c, code, key, price, bond):
    """返回与价格索引对齐的指标序列（日频，未重采样）。"""
    if key == "pe_ttm":
        return _stock_pe(c, code) if SRC.get(code) == "stock" else _pe(c, code)
    if key == "div":
        return _div(c, code)
    if key == "premium":
        return _premium(c)
    if key == "spread":
        dv = _div(c, code)
        if dv is None:
            return None
        b = bond.reindex(dv.index).ffill()
        return (dv - b).dropna()
    if key == "erp":
        pe = _pe(c, code)
        if pe is None:
            return None
        b = bond.reindex(pe.index).ffill()
        return (100.0 / pe - b).dropna()
    if key == "fear":
        return _fear(c, code)
    if key == "vol":
        return (price["pct"].rolling(20).std() * np.sqrt(252)).dropna()
    if key == "amount":
        return price["amount"].dropna()
    if key == "rs":
        b = _raw_price(c, BENCH)
        if b is None:
            return None
        w = pd.concat([price["close"], b["close"]], axis=1, keys=["a", "b"]).ffill().dropna()
        r = (w["a"] / w["a"].shift(60) - 1) * 100 - (w["b"] / w["b"].shift(60) - 1) * 100
        return r.dropna()
    return None


def _pct_value(series, q):
    s = series.dropna()
    if len(s) < 20:
        return None
    return float(np.percentile(s, q))


def _has_rows(c, sql, params=()):
    return c.execute(sql, params).fetchone()[0] > 60


def _available(c, code, cls):
    """轻量可用性判断，避免 meta 里跑重型分位计算。"""
    if SRC.get(code) == "stock":
        has_pe = _has_rows(c, "select count(*) from val_stock_pe_daily where stock_code=? and pe_ttm is not null",
                           (code,))
        has_div = _has_rows(c, "select count(*) from val_stock_dividend_yield_focus where stock_code=? and div_yield is not null",
                            (code,))
        has_fear, has_prem = False, False
    else:
        has_pe = _has_rows(c, "select count(*) from px_index_daily_csi where index_code=? and pe_ttm is not null",
                           (code,))
        has_div = _has_rows(c, "select count(*) from val_index_dividend_yield where index_code=? and div_yield is not null",
                            (code,))
        has_fear = _has_rows(c, "select count(*) from mkt_fear_daily where index_code=? and fear_composite is not null",
                             (code,))
        has_prem = _has_rows(c, "select count(*) from px_lof_daily where fund_code='159941' and premium_lag is not null")
    ok = {"pe_ttm": has_pe, "div": has_div, "spread": has_div,
          "erp": has_pe, "fear": has_fear, "premium": has_prem,
          "vol": True, "amount": True, "rs": True}
    return [k for k in CLASS_IND[cls] if ok.get(k)]


_META_CACHE = {"at": 0.0, "val": None}


def meta():
    """前端筛选框所需的元数据：可选指数、每类指数推荐指标、区间/粒度、分位窗口。"""
    import time
    if _META_CACHE["val"] is not None and time.time() - _META_CACHE["at"] < 600:
        return _META_CACHE["val"]
    c = conn()
    avail = {}
    for u in UNIVERSE:
        price = _raw_price(c, u["code"])
        if price is None or len(price) < 60:
            continue
        inds = []
        for k in _available(c, u["code"], u["cls"]):
            spec = dict(IND[k])
            spec.update({"key": k, "pct_line": k in PCT_IND})
            inds.append(spec)
        if not inds:
            continue
        avail[u["code"]] = {
            "code": u["code"], "name": u["name"], "cls": u["cls"], "tag": u["tag"],
            "start": price.index[0].strftime("%Y-%m-%d"),
            "end": price.index[-1].strftime("%Y-%m-%d"),
            "n": int(len(price)),
            "indicators": inds,
        }
    c.close()
    cls_label = {"core": "宽基/大盘", "value": "价值/红利", "growth": "成长",
                 "cycle": "周期", "overseas": "海外", "stock": "个股"}
    out = {
        "indexes": list(avail.values()),
        "by_code": avail,
        "classes": [{"key": k, "label": v} for k, v in cls_label.items()],
        "ranges": [{"key": k, "label": v["label"], "gran": v["gran"]} for k, v in RANGES.items()],
        "grans": [{"key": k, "label": v["label"]} for k, v in GRANS.items()],
        "pct_windows": [{"key": k, "label": {"1Y": "近1年", "3Y": "近3年", "5Y": "近5年", "ALL": "全部"}[k]}
                        for k in PCT_WINDOWS],
        "pct_levels": [20, 50, 80],
        "class_note": {
            "core": "宽基看估值水位与股债性价比，量能决定趋势延续性",
            "value": "红利资产的核心是股息率与相对国债的利差，PE 只是辅助",
            "growth": "成长股靠估值弹性与情绪，股息率几乎无参考价值",
            "cycle": "周期股看 PE 分位与恐慌度，盈利波动使绝对 PE 失真",
            "overseas": "海外指数无人民币估值数据，看波动与相对 A 股强弱",
            "stock": "个股无指数估值/恐慌度数据，看相对沪深300的强弱、量能与波动",
        },
        "default": {"code": "000300", "range": "1Y", "gran": "W", "mode": "point",
                    "ind": ["pe_ttm"], "pct_win": "3Y", "bench": ""},
    }
    _META_CACHE.update({"at": time.time(), "val": out})
    return out


def trend(code="000300", rng="1Y", gran=None, mode="pct", inds=None,
          pct_win="3Y", bench="", pct=None, pct_levels=(20, 50, 80)):
    """主入口：返回主序列、指标副轴序列、分位标准线、对比指数。

    inds 控制折线（最多 2 条）；pct 独立控制分位线，可不含在 inds 中。
    """
    inds = [k for k in (inds or []) if k][:2]
    # 分位线完全独立：只有显式传入的 pct 才画，绝不以指标曲线兜底
    pct_keys = [k for k in (pct or []) if k in PCT_IND]
    all_keys = list(dict.fromkeys(inds + pct_keys))
    c = conn()
    price = _raw_price(c, code)
    if price is None or not len(price):
        c.close()
        return {"code": code, "points": [], "indicators": [], "ref_lines": [], "bench": None}
    bond = _bond(c)

    # ---- 区间 ----
    spec = RANGES.get(rng, RANGES["1Y"])
    if spec["days"]:
        price = price.tail(spec["days"])
    g = gran or spec["gran"]
    rule = GRANS.get(g, GRANS["W"])["rule"]

    # ---- 主序列 ----
    daily = price.copy()
    daily["cum"] = (daily["close"] / daily["close"].iloc[0] - 1) * 100
    if rule:
        agg = daily.resample(rule).agg({"close": "last", "amount": "sum", "pct": "sum"})
        # 用桶内最后一个真实交易日做标签，避免出现「2026-12-31」这类未来日期
        agg["_lbl"] = daily.index.to_series().resample(rule).last().reindex(agg.index)
        agg["pct"] = agg["close"].pct_change() * 100
        agg = agg.dropna(subset=["close"])
        series = agg
    else:
        series = daily
        series["_lbl"] = series.index
    # 累积收益以「第一个展示点」为 0，保证曲线从 0 起
    series["cum"] = (series["close"] / series["close"].iloc[0] - 1) * 100
    if len(series) > 1:
        series.iloc[0, series.columns.get_loc("pct")] = np.nan

    points = []
    for i, r in series.iterrows():
        points.append({
            "date": pd.Timestamp(r["_lbl"]).strftime("%Y-%m-%d"),
            "close": round(float(r.close), 2),
            "pct": None if pd.isna(r.pct) else round(float(r.pct), 2),
            "cum": None if pd.isna(r.cum) else round(float(r.cum), 2),
            "amount": None if pd.isna(r.amount) else round(float(r.amount), 1),
        })

    # ---- 指标副轴 ----
    out_ind, ref_lines, stats_ind = [], [], {}
    nwin = PCT_WINDOWS.get(pct_win)
    for k in all_keys:
        s_daily = _ind_series(c, code, k, price, bond)
        if s_daily is None or not len(s_daily.dropna()):
            continue
        full = s_daily.dropna()

        # 折线：只有被选入 inds 的指标才输出曲线
        if k in inds:
            s = s_daily.reindex(price.index).ffill()
            if rule:
                s = s.resample(rule).last()
            s = s.reindex(series.index).ffill()
            pts = [{"date": pd.Timestamp(series["_lbl"].iloc[n]).strftime("%Y-%m-%d"),
                    "value": None if pd.isna(v) else round(float(v), IND[k]["digits"])}
                   for n, v in enumerate(s.tolist())]
            spec_k = dict(IND[k])
            spec_k.update({"key": k, "points": pts, "pct_line": k in PCT_IND})
            out_ind.append(spec_k)

        # 分位标准线：独立于折线，由 pct 参数单独控制
        if k in pct_keys and len(full) >= 60:
            base = full.tail(nwin) if nwin else full
            for q in pct_levels:
                v = _pct_value(base, q)
                if v is None:
                    continue
                ref_lines.append({
                    "ind": k, "q": q, "value": round(v, IND[k]["digits"]),
                    "label": "%s %d%% 分位" % (
                        {"1Y": "近1年", "3Y": "近3年", "5Y": "近5年", "ALL": "全部"}[pct_win]
                        if pct_win in PCT_WINDOWS else pct_win, q),
                })

        # 当前值分位：只对折线指标计算，用于统计卡展示
        if k in inds and len(full) >= 60:
            base = full.tail(nwin) if nwin else full
            stats_ind[k] = (round(float(full.iloc[-1]), IND[k]["digits"]),
                            round(float((base < full.iloc[-1]).mean() * 100), 0))

    # ---- 对比指数（独立副轴，用真实指数点位，不做归一化） ----
    bench_out = None
    if bench and bench != code:
        bp = _raw_price(c, bench)
        if bp is not None and len(bp):
            if spec["days"]:
                bp = bp.tail(spec["days"])
            bp = bp[bp.index >= series.index[0]]
            if len(bp) >= 2:
                nb = bp["close"]  # 点位，与主轴同口径，各自独立缩放
                if rule:
                    lbl = nb.index.to_series().resample(rule).last()
                    nb = nb.resample(rule).last().dropna()
                    lbl = lbl.reindex(nb.index)
                else:
                    lbl = nb.index.to_series()
                bench_out = {
                    "code": bench, "name": NAME.get(bench, bench),
                    "start": bp.index[0].strftime("%Y-%m-%d"),
                    "points": [{"date": pd.Timestamp(lbl.iloc[n]).strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                               for n, v in enumerate(nb.tolist())],
                    "ret": round(float(bp["close"].iloc[-1] / bp["close"].iloc[0] - 1) * 100, 2),
                    "last": round(float(bp["close"].iloc[-1]), 2),
                }

    # ---- 区间统计 ----
    peak = (series["close"] / series["close"].cummax() - 1) * 100
    bar_pct = series["pct"].dropna()  # 按展示粒度统计，与图上 K 线数量一致
    stats = {
        "ret": round(float(series["close"].iloc[-1] / series["close"].iloc[0] - 1) * 100, 2),
        "last": round(float(series["close"].iloc[-1]), 2),
        "last_pct": None if pd.isna(series["pct"].iloc[-1]) else round(float(series["pct"].iloc[-1]), 2),
        "mdd": round(float(peak.min()), 2),
        "vol": round(float(daily["pct"].std() * np.sqrt(252)), 2) if len(daily) > 5 else None,
        "up_days": int((bar_pct > 0).sum()),
        "down_days": int((bar_pct < 0).sum()),
        "start": pd.Timestamp(series["_lbl"].iloc[0]).strftime("%Y-%m-%d"),
        "end": pd.Timestamp(series["_lbl"].iloc[-1]).strftime("%Y-%m-%d"),
        "n": int(len(series)),
    }
    for o in out_ind:
        vals = [p["value"] for p in o["points"] if p["value"] is not None]
        if vals and o["key"] not in stats_ind:
            stats.setdefault("ind_last", {})[o["key"]] = vals[-1]
    for k, (v, q) in stats_ind.items():
        stats.setdefault("ind_last", {})[k] = v
        stats["ind_last"][k + "_pct"] = q

    c.close()
    u = next((x for x in UNIVERSE if x["code"] == code), {"name": code, "cls": "core", "tag": ""})
    return {
        "code": code, "name": u["name"], "cls": u["cls"], "tag": u["tag"],
        "range": rng, "gran": g, "mode": mode,
        "points": points, "indicators": out_ind, "ref_lines": ref_lines,
        "bench": bench_out, "stats": stats,
    }
