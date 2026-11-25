# -*- coding: utf-8 -*-
"""6 波段验证 + 组合信号前瞻检验，输出报告数据。"""
import json
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from upswing_factor_data import build, nearest, SEGS
from analyze_upswing import FACTORS

OUT = os.path.join(ROOT, "data", "upswing_signals.json")


def main():
    f = build()
    c = f.close
    fwd = {n: c.shift(-n) / c - 1 for n in (20, 60, 120)}
    base = f.loc["2016":]

    # 单因子检验
    singles = {}
    tests = [
        ("ma60_dev", -0.05, "le", "MA60偏离≤-5%"), ("ma20_dev", -0.03, "le", "MA20偏离≤-3%"),
        ("down_streak", 2, "ge", "连跌≥2日"), ("down_streak", 3, "ge", "连跌≥3日"),
        ("erp", 6.0, "ge", "ERP≥6.0"), ("erp", 6.5, "ge", "ERP≥6.5"),
        ("dy_bond_gap", 0.5, "ge", "股息差≥0.5"), ("dy_bond_gap", 1.0, "ge", "股息差≥1.0"),
        ("margin_chg20", 0, "le", "两融20日下降"),
        ("fear_fear_qvix_pct", 60, "ge", "QVIX恐慌分位≥60"),
        ("fear_fear_composite", 55, "ge", "恐慌度≥55"),
        ("pe_pct5y", 0.2, "le", "5年PE分位≤20%"), ("dd60", -0.10, "le", "60日回撤≤-10%"),
        ("rv_ratio", 1.1, "ge", "短长波动比≥1.1"),
    ]
    for col, th, mode, label in tests:
        s = base[col]
        m = (s <= th) if mode == "le" else (s >= th)
        # 事件簇去重
        grp = (m != m.shift()).cumsum()
        first = m & (grp != grp.shift())
        idx = base.index[first]
        out = {"n_days": int(m.sum()), "n_clusters": int(first.sum()), "label": label}
        for n in (20, 60, 120):
            x = fwd[n][idx].dropna()
            out[f"fwd{n}"] = round(float(x.mean()) * 100, 2) if len(x) else None
            out[f"win{n}"] = round(float((x > 0).mean()) * 100, 1) if len(x) else None
        singles[label] = out
    bench = {"n": len(base)}
    for n in (20, 60, 120):
        x = fwd[n][base.index].dropna()
        bench[f"fwd{n}"] = round(float(x.mean()) * 100, 2)
        bench[f"win{n}"] = round(float((x > 0).mean()) * 100, 1)

    # 组合信号
    combos = {
        "ERP≥6.0": lambda r: r.erp >= 6.0,
        "ERP≥6.0 + 破MA60深": lambda r: r.erp >= 6.0 and r.ma60_dev <= -0.05,
        "ERP≥6.0 + 连跌≥2": lambda r: r.erp >= 6.0 and r.down_streak >= 2,
        "ERP≥6.0 + 两融降": lambda r: r.erp >= 6.0 and r.margin_chg20 <= 0,
        "ERP≥6.0 + 股息差≥1": lambda r: r.erp >= 6.0 and r.dy_bond_gap >= 1.0,
        "ERP≥6.0 + 破MA60 + 连跌": lambda r: r.erp >= 6.0 and r.ma60_dev <= -0.05 and r.down_streak >= 2,
        "四条件全满足": lambda r: r.erp >= 6.0 and r.ma60_dev <= -0.05 and r.down_streak >= 2 and r.margin_chg20 <= 0,
        "仅破MA60深": lambda r: r.ma60_dev <= -0.05,
    }
    combo_res = {}
    events = {}
    for name, fn in combos.items():
        mask = base.apply(fn, axis=1)
        grp = (mask != mask.shift()).cumsum()
        first = mask & (grp != grp.shift())
        idx = [pd.Timestamp(d) for d in base.index[first]]
        # 30日窗口去重
        uniq = []
        for d in idx:
            if not uniq or (d - uniq[-1]).days > 30:
                uniq.append(d)
        row = {"n_cluster": len(idx), "n_unique": len(uniq)}
        for label, dates in [("cluster", idx), ("unique", uniq)]:
            vals = [(str(d.date()), fwd[60].get(d, np.nan)) for d in dates]
            valid = [(d, v) for d, v in vals if pd.notna(v)]
            row[f"{label}_fwd60"] = round(float(np.mean([v for _, v in valid])) * 100, 2) if valid else None
            row[f"{label}_win60"] = round(float(np.mean([v > 0 for _, v in valid])) * 100, 1) if valid else None
            row[f"{label}_fwd120"] = round(float(np.mean([fwd[120].get(pd.Timestamp(d), np.nan)
                                                          for d, _ in valid if pd.notna(fwd[120].get(pd.Timestamp(d), np.nan))])) * 100, 2) if valid else None
            if label == "unique":
                row["unique_list"] = [(d, round(float(v) * 100, 2)) for d, v in valid]
        combo_res[name] = row
        if name == "四条件全满足":
            events = row["unique_list"]

    # 随机对照
    vals = [v for _, v in events if pd.notna(v)]
    obs = float(np.mean(vals))  # events 里的 v 已是百分数
    rng = np.random.default_rng(42)
    allidx = [pd.Timestamp(d) for d in base.index]
    sims = []
    for _ in range(2000):
        picks = []
        for _t in range(400):
            d = pd.Timestamp(rng.choice(allidx))
            if all(abs((d - p).days) >= 30 for p in picks):
                picks.append(d)
                if len(picks) >= len(vals):
                    break
        vv = [fwd[60].get(p, np.nan) for p in picks]
        vv = [v for v in vv if pd.notna(v)]
        if len(vv) >= len(vals) - 2:
            sims.append(float(np.mean(vv)) * 100)
    sims = np.array(sims)
    mc = {
        "observed": round(obs, 2), "n": len(vals), "sims": len(sims),
        "median": round(float(np.median(sims)), 2),
        "p95": round(float(np.quantile(sims, 0.95)), 2),
        "p99": round(float(np.quantile(sims, 0.99)), 2),
        "p_value": round(float((sims >= obs).mean()) * 100, 3),
    }

    # 6 波段起点命中
    seg_hit = []
    for k, a, b in SEGS:
        d = nearest(f, a)
        r = f.loc[d]
        hits = [name for name, fn in combos.items() if fn(r)]
        sub = f.loc[d:nearest(f, b)]
        seg_hit.append({
            "id": k, "date": str(d.date()), "end": str(nearest(f, b).date()),
            "ret": round(float(sub.close.iloc[-1] / sub.close.iloc[0] - 1) * 100, 2),
            "days": len(sub), "erp": round(float(r.erp), 2),
            "ma60_dev": round(float(r.ma60_dev) * 100, 1),
            "down_streak": int(r.down_streak),
            "margin_chg20": round(float(r.margin_chg20) * 100, 1),
            "pe_pct5y": round(float(r.pe_pct5y) * 100, 1),
            "hits": hits,
        })

    res = {"singles": singles, "bench": bench, "combos": combo_res,
           "mc": mc, "segments": seg_hit}
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)

    print("=== 单因子（簇首）===")
    for k, v in singles.items():
        print(f"  {v['label']:<18s} 簇{v['n_clusters']:3d}  60日{v['fwd60']:+6.2f}% 胜率{v['win60']:5.1f}%")
    print(f"  基准 60日{bench['fwd60']:+.2f}%")
    print("\n=== 组合（30日去重）===")
    for k, v in combo_res.items():
        print(f"  {k:<24s} {v['n_unique']:2d}簇 60日{v['unique_fwd60']:+6.2f}% 胜率{v['unique_win60']:5.1f}%")
    print("\n=== 随机对照 ===", mc)
    print("\n=== 6波段命中 ===")
    for s in seg_hit:
        print(f"  {s['id']} {s['date']} ERP{s['erp']:5.2f} MA60{s['ma60_dev']:6.1f}% 命中{len(s['hits'])}项")


if __name__ == "__main__":
    main()
