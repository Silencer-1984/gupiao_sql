# -*- coding: utf-8 -*-
"""对 6 个上升波段的起点/终点打"买入推荐度"分（0-100），并给出决策标签。

评分卡只用前面已验证有效的因子：
  - ERP（全历史唯一稳定有效的估值闸门）
  - 5y PE 分位（高位保护，10年窗口污染小）
  - MA60 偏离 / 连跌 / 两融降（6波段验证的急跌时机增量）
  - 60 日回撤（位置确认）
剔除已证伪因子：恐慌度、股息率−国债、M1、拥挤度、隐含EPS增速。
权重为研究者设定，非统计估计——这是可解释打分卡，不是回归模型。
"""
import os
import json
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upswing_factor_data import build, nearest, SEGS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def band_score(v, bands):
    """bands: [(上界, 分数), ...] 从低到高；v 落在<=上界的第一档。"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 0.0
    for hi, sc in bands:
        if v <= hi:
            return float(sc)
    return 0.0


def score(r):
    """返回 (总分, 分项字典)。各维度均为'越高越该买'。"""
    # A 估值闸门 ERP（35）：来自全历史检验 6.5pp 稳定有效
    erp = r["erp"]
    a = (35 if erp >= 7.0 else 30 if erp >= 6.5 else
         18 if erp >= 6.0 else 10 if erp >= 5.5 else 0)

    # B 5y PE 分位（25）：高位保护；≤20 满，≥80 零
    pct = r["pe_pct5y"]
    b = (25 if pct <= 0.20 else 16 if pct <= 0.40 else
         9 if pct <= 0.60 else 3 if pct <= 0.80 else 0)

    # C 急跌时机 MA60 偏离（20）：6波段起点全在 -4.7~-10.9%
    d = r["ma60_dev"]
    c = (20 if d <= -0.08 else 15 if d <= -0.05 else
         10 if d <= -0.03 else 5 if d <= 0 else 0)

    # D 连跌 + 两融降（10）
    ds = r["down_streak"] if pd.notna(r["down_streak"]) else 0
    mg = r["margin_chg20"] if pd.notna(r["margin_chg20"]) else 0
    d1 = ds >= 2
    d2 = mg <= 0
    e = 10 if (d1 and d2) else 5 if (d1 or d2) else 0

    # E 位置确认 60日回撤（10）
    dd = r["dd60"]
    g = (10 if dd <= -0.12 else 7 if dd <= -0.08 else
         4 if dd <= -0.04 else 0)

    parts = {"ERP": a, "PE分位": b, "MA60偏离": c, "连跌两融": e, "回撤": g}
    return sum(parts.values()), parts


def decision(total):
    if total >= 75:
        return "强烈建议买入"
    if total >= 60:
        return "建议买入"
    if total >= 45:
        return "观望 / 小仓试探"
    if total >= 30:
        return "持有不加仓"
    return "不买 / 接近卖出区"


def hard_rule(r):
    """严格策略闸门：5y分位<=20% 且 ERP>=6.5（ERP绝对阈值）。"""
    return bool(r["pe_pct5y"] <= 0.20 and pd.notna(r["erp"]) and r["erp"] >= 6.5)


def sell_rule(r):
    """严格卖出闸门：5y分位>=80%（推荐85~90%视为更优）。"""
    return bool(r["pe_pct5y"] >= 0.80)


def main():
    f = build()
    rows = []
    for k, a, b in SEGS:
        for tag, dstr in (("IN", a), ("OUT", b)):
            d = nearest(f, dstr)
            r = f.loc[d]
            total, parts = score(r)
            rows.append({
                "seg": k, "tag": tag, "date": str(d.date()),
                "role": "起点" if tag == "IN" else "终点",
                "close": round(float(r["close"]), 1),
                "score": round(total, 1),
                "parts": parts,
                "decision": decision(total),
                "hard_buy": hard_rule(r),
                "hard_sell": sell_rule(r),
                "erp": round(float(r["erp"]), 2),
                "pe_pct5y": round(float(r["pe_pct5y"]) * 100, 1),
                "ma60_dev": round(float(r["ma60_dev"]) * 100, 1),
                "down_streak": int(r["down_streak"]) if pd.notna(r["down_streak"]) else 0,
                "margin_chg20": round(float(r["margin_chg20"]) * 100, 1)
                                if pd.notna(r["margin_chg20"]) else None,
                "dd60": round(float(r["dd60"]) * 100, 1),
                "fear": round(float(r["fear_fear_composite"]), 1),
                "dy_gap": round(float(r["dy_bond_gap"]), 2),
            })

    ins = [x for x in rows if x["tag"] == "IN"]
    outs = [x for x in rows if x["tag"] == "OUT"]
    res = {
        "meta": {
            "title": "6 个上升波段的买入推荐度打分",
            "scale": "0-100，越高越该买；权重为研究者设定，非统计估计",
            "factors_in": ["ERP", "5y PE分位", "MA60偏离", "连跌+两融降", "60日回撤"],
            "factors_out": ["恐慌度", "股息率−国债", "M1", "拥挤度", "隐含EPS增速"],
            "decision_bands": {"≥75": "强烈建议买入", "60-74": "建议买入",
                               "45-59": "观望/小仓试探", "30-44": "持有不加仓",
                               "<30": "不买/接近卖出区"},
            "hard_rule": "买入：5y PE分位≤20% 且 ERP≥6.5pp；卖出：5y PE分位≥80%（85~90%更优）",
            "caveat": "日频 pe_ttm 口径与月频加权 PE 不同，分位数值不可与月频报告直接比较",
        },
        "rows": rows,
        "summary": {
            "in_mean": round(float(np.mean([x["score"] for x in ins])), 1),
            "out_mean": round(float(np.mean([x["score"] for x in outs])), 1),
            "in_hard_buy": sum(1 for x in ins if x["hard_buy"]),
            "out_hard_sell": sum(1 for x in outs if x["hard_sell"]),
            "in_buy_rec": sum(1 for x in ins if x["score"] >= 60),
            "out_buy_rec": sum(1 for x in outs if x["score"] >= 60),
        },
    }
    path = os.path.join(ROOT, "data", "swing_scores.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=2)

    print("=== 打分结果 ===")
    for x in rows:
        print(f"{x['seg']} {x['role']} {x['date']}  分{x['score']:>5.1f}  "
              f"{x['decision']:<16s} 硬闸门买={x['hard_buy']} 卖={x['hard_sell']}  "
              f"分项{x['parts']}")
    print("\n=== 汇总 ===", res["summary"])


if __name__ == "__main__":
    main()
