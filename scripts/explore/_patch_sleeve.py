# -*- coding: utf-8 -*-
"""补丁：风格策略卡增加「成长（科创+有色）」与「价值（红利）」两套分项建议。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.path.join(ROOT, "server", "analytics.py")
s = io.open(P, encoding="utf-8").read()

# 1) 新函数：分风格打分（放在 _advice 之前）
FUNC = '''def _pct_rank(series, window=1250):
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
        g_reasons.append("估值分位 %.0f%%（%s）" % (g_pe_avg, "偏贵" if g_pe_avg > 70 else "不贵" if g_pe_avg < 40 else "中性"))
    if g_fe_avg is not None:
        g_reasons.append("恐慌分位 %.0f%%（%s）" % (g_fe_avg, "极高，短期反抽概率大但60日跑输" if g_fe_avg > 85 else "正常"))
    if rs_pct is not None:
        g_reasons.append("科创/红利相对强弱 %.0f%% 分位" % rs_pct)

    v_reasons = []
    if v_sp_avg is not None:
        v_reasons.append("股息率利差分位 %.0f%%（%s）" % (v_sp_avg, "仍便宜" if v_sp_avg > 60 else "已不便宜"))
    if v_pe_avg is not None:
        v_reasons.append("PE 分位 %.0f%%（%s）" % (v_pe_avg, "历史高位" if v_pe_avg > 85 else "中位"))
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
        "growth": {"name": "成长 · 科创50 + 中证有色", "score": None if g_score is None else round(g_score, 1),
                   "stance": g_st, "kind": g_kind, "reasons": g_reasons},
        "value": {"name": "价值 · 中证红利 + 红利低波", "score": None if v_score is None else round(v_score, 1),
                  "stance": v_st, "kind": v_kind, "reasons": v_reasons},
    }


'''
s = s.replace("def _advice(pe, fear_map, hs300):", FUNC + "def _advice(pe, fear_map, hs300):")

# 2) overview 里挂上
s = s.replace('''    advice, reason = _advice(pe, fear_map, hs300)''',
              '''    advice, reason = _advice(pe, fear_map, hs300)
    sleeves = _sleeve_advice(c)''')
s = s.replace('''        "advice": advice, "advice_reason": reason,''',
              '''        "advice": advice, "advice_reason": reason, "sleeves": sleeves,''')

io.open(P, "w", encoding="utf-8").write(s)
print("patched")
