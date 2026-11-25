# -*- coding: utf-8 -*-
"""6 个上升波段起点的因子归因：原始值 + 全样本分位 + 一致性评分。"""
import json
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from upswing_factor_data import build, SEGS, nearest

OUT = os.path.join(ROOT, "data", "upswing_analysis.json")

# 关注的因子及方向假设：+1 表示起点应该偏高，-1 表示偏低，0 表示无先验
FACTORS = {
    # 估值 / 性价比
    "pe_ttm": (-1, "PE 绝对值"), "pe_pct1y": (-1, "1年 PE 分位"),
    "pe_pct3y": (-1, "3年 PE 分位"), "pe_pct5y": (-1, "5年 PE 分位"),
    "erp": (+1, "ERP 股债性价比"), "dy_bond_gap": (+1, "股息率−国债"),
    "div_yield": (+1, "股息率"), "dy_pct1y": (+1, "股息率1年分位"),
    "bond_chg20": (-1, "国债20日变动(降息利好)"), "bond_chg60": (-1, "国债60日变动"),
    "yield_curve": (0, "期限利差"), "pe_chg20": (-1, "PE 20日变化"),
    # 价格位置 / 动量
    "dd60": (-1, "60日回撤"), "dd250": (-1, "250日回撤"),
    "mom20": (-1, "20日动量"), "mom60": (-1, "60日动量"),
    "mom120": (-1, "120日动量"), "mom250": (-1, "250日动量"),
    "ma20_dev": (-1, "20日均线偏离"), "ma60_dev": (-1, "60日均线偏离"),
    "ma20_60": (0, "20/60日均线比"), "down_streak": (+1, "连跌天数"),
    # 波动 / 恐慌
    "fear_fear_composite": (+1, "恐慌度综合"), "fear_fear_rv_pct": (+1, "恐慌RV分位"),
    "fear_fear_qvix_pct": (+1, "恐慌QVIX分位"), "fear_chg20": (+1, "恐慌度20日变化"),
    "rv20": (+1, "20日实现波动"), "rv60": (+1, "60日实现波动"),
    "rv_ratio": (0, "短长波动比"),
    # 量能
    "vol_ratio20": (0, "量比20日"), "amt_ratio20": (0, "额比20日"),
    "vol_chg20": (-1, "成交量20日变化"), "vol_ma20_120": (-1, "量能20/120比"),
    # 情绪 / 资金
    "congestion": (-1, "拥挤度"), "cong_pct1y": (-1, "拥挤度1年分位"),
    "margin_chg20": (-1, "两融20日变化"), "margin_chg60": (-1, "两融60日变化"),
    "north20": (+1, "北向20日净买"), "north60": (+1, "北向60日净买"),
    # 宏观
    "m1_yoy": (0, "M1同比"), "m2_yoy": (0, "M2同比"),
    "m1_m2_gap": (+1, "M1-M2剪刀差"), "pmi_manufacturing": (0, "PMI"),
    "sf_increment": (0, "社融增量"),
}


def main():
    f = build()
    starts = []
    for k, a, b in SEGS:
        da = nearest(f, a)
        db = nearest(f, b)
        sub = f.loc[da:db]
        starts.append({
            "id": k, "date": str(da.date()), "end": str(db.date()),
            "days": len(sub), "ret": round(float(sub.close.iloc[-1] / sub.close.iloc[0] - 1) * 100, 2),
            "row": f.loc[da],
        })

    # 全样本分位（2016 起，避开早期数据稀疏）
    base = f.loc["2016":]
    res = {"segments": [], "factors": {}}
    for s in starts:
        res["segments"].append({
            "id": s["id"], "date": s["date"], "end": s["end"],
            "days": s["days"], "ret": s["ret"],
        })

    for col, (direction, label) in FACTORS.items():
        if col not in f.columns:
            continue
        vals = [s["row"][col] for s in starts]
        valid = [v for v in vals if pd.notna(v)]
        if len(valid) < 3:
            continue
        series = base[col].dropna()
        if len(series) < 100:
            continue
        pcts = []
        for v in vals:
            if pd.isna(v):
                pcts.append(None)
            else:
                pcts.append(round(float((series <= v).mean()) * 100, 1))
        # 一致性：有方向假设的因子，6 个起点分位偏同一侧的程度
        score = None
        if direction != 0 and all(p is not None for p in pcts):
            if direction > 0:
                score = round(float(np.mean(pcts)), 1)  # 越高越一致
            else:
                score = round(100 - float(np.mean(pcts)), 1)
        res["factors"][col] = {
            "label": label, "direction": direction,
            "values": [round(float(v), 3) if pd.notna(v) else None for v in vals],
            "pcts": pcts, "consistency": score,
            "base_median": round(float(series.median()), 3),
            "base_p10": round(float(series.quantile(0.1)), 3),
            "base_p90": round(float(series.quantile(0.9)), 3),
        }

    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)

    print("=== 6 波段 ===")
    for s in res["segments"]:
        print(f"  {s['id']} {s['date']}→{s['end']} {s['days']:3d}日 {s['ret']:+.2f}%")
    print("\n=== 因子一致性排名（有方向假设）===")
    ranked = sorted([(v["consistency"], k, v) for k, v in res["factors"].items()
                     if v["consistency"] is not None], reverse=True)
    for score, k, v in ranked:
        print(f"  {v['label']:<22s} 一致度{score:5.1f}  分位{[f'{p:.0f}' if p is not None else '-' for p in v['pcts']]}")
    print("\n=== 中性因子（无先验）===")
    for k, v in res["factors"].items():
        if v["direction"] == 0:
            print(f"  {v['label']:<22s} 分位{[f'{p:.0f}' if p is not None else '-' for p in v['pcts']]}")


if __name__ == "__main__":
    main()
