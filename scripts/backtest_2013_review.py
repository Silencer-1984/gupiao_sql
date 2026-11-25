# -*- coding: utf-8 -*-
"""2013-01 ~ 2026-11 策略逐笔复盘（不计算年化，只看持有月数与累计收益）+ 五维评分。

主策略 S：5 年 PE 分位<=20% 且 ERP>=6.5pp 买入；分位>=80% 卖出。
对照：5y 基线（无 ERP）、3y+ERP、买入持有。
评分：收益 30 / 回撤 25 / 熊市规避 20 / 执行效率 15 / 资金利用率 10，满分 100。
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from factor_timing_data import load_factor_panel, rolling_pct as rp
from backtest_pe_pct_2019 import apply_pos

START, END = "2013-01", "2026-11"
OUT = os.path.join(ROOT, "data", "review_2013.json")
OUT_CSV = os.path.join(ROOT, "data", "review_2013_trades.csv")


def build():
    f = load_factor_panel()
    f["pe_pct3"] = rp(f.pe, 36)
    f["pe_pct5"] = rp(f.pe, 60)
    return f


def run_strategy(f, y, erp_th=None, start=START):
    ym = f.index.values.astype(str)
    lo = int(np.searchsorted(ym, start))
    hi = int(np.searchsorted(ym, END)) + 1
    hi = min(hi, len(f))
    p = f[f"pe_pct{y}"].values.astype(float)
    pos = np.zeros(len(f))
    s = 0.0
    for i in range(lo, hi):
        r = f.iloc[i]
        if s == 0.0:
            ok = p[i] <= 0.20
            if erp_th is not None:
                ok = ok and pd.notna(r.erp) and r.erp >= erp_th
            if ok:
                s = 1.0
        elif p[i] >= 0.80:
            s = 0.0
        pos[i] = s
    close = f.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])
    r = apply_pos(pos[lo:hi], ret[lo:hi])
    eq = np.cumprod(1 + r)
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())

    # 逐笔：买入信号月 i（pos 从 i 起为1，收益从 i 月末到 i+1 月），卖出信号月 j+1
    segs = []
    i = lo
    while i < hi:
        if pos[i] == 1 and (i == lo or pos[i - 1] == 0):
            j = i
            while j + 1 < hi and pos[j + 1] == 1:
                j += 1
            seg_rets = ret[i:j + 1]
            seg = float(np.prod(1 + np.nan_to_num(seg_rets)) - 1) * 100
            segs.append({
                "in_signal": str(f.index[i]), "out_signal": str(f.index[min(j + 1, hi - 1)]),
                "months": j - i + 1,
                "ret": round(seg, 2),
                "pe_pct_in": round(float(p[i]) * 100, 1),
                "erp_in": round(float(f.erp.iloc[i]), 2) if pd.notna(f.erp.iloc[i]) else None,
                "pb_in": round(float(f.pb.iloc[i]), 2) if pd.notna(f.pb.iloc[i]) else None,
                "equity_after": round(float(eq[j - lo]), 4),
            })
            i = j + 1
        else:
            i += 1

    # 熊市：距 36 月滚动峰值回撤<=-20%（事前可得）
    sclose = pd.Series(close)
    dd = (sclose / sclose.rolling(36, min_periods=12).max() - 1).values
    bear = np.zeros(len(f), bool)
    bear[36:] = dd[36:] <= -0.20
    mask = np.zeros(len(f), bool); mask[lo:hi] = True
    bear &= mask

    bh = np.prod(1 + np.nan_to_num(ret[lo:hi]))
    return {
        "period": f"{ym[lo]}~{str(f.index[hi-1])}", "months": hi - lo,
        "final_equity": round(float(eq[-1]), 4),
        "total_ret": round(float(eq[-1] - 1) * 100, 2),
        "max_dd": round(mdd * 100, 1),
        "tim": round(float(pos[lo:hi].mean()) * 100, 1),
        "ntr": len(segs), "trades": segs,
        "bh_total_ret": round((bh - 1) * 100, 2),
        "excess_pp": round((eq[-1] - bh) * 100, 2),
        "bear_tim": round(float(pos[bear].mean()) * 100, 1) if bear.any() else 0,
        "bear_months": int(bear.sum()),
        "bull_tim": round(float(pos[mask & ~bear].mean()) * 100, 1),
        "eq_curve": [round(float(x), 4) for x in eq],
        "bh_curve": [round(float(x), 4) for x in np.cumprod(1 + np.nan_to_num(ret[lo:hi]))],
        "ym": [str(x) for x in f.index[lo:hi]],
    }


def score(r, bh):
    parts = {}
    e = r["excess_pp"]
    parts["收益"] = (30 if e >= 50 else 24 if e >= 30 else 18 if e >= 10
                    else 12 if e >= 0 else 0)
    dd = r["max_dd"]
    parts["回撤"] = (25 if dd >= -20 else 18 if dd >= -30 else 10 if dd >= -40 else 0)
    bt = r["bear_tim"]
    parts["熊市规避"] = (20 if bt <= 15 else 16 if bt <= 30 else 11 if bt <= 45
                      else 6 if bt <= 60 else 0)
    n = r["ntr"]
    parts["执行效率"] = (15 if 2 <= n <= 5 else 10 if n <= 8 else 5 if n <= 12 else 0)
    tm = r["tim"]
    parts["资金利用"] = (10 if 40 <= tm <= 65 else 7 if 30 <= tm < 40 or 65 < tm <= 75
                      else 4 if 20 <= tm < 30 or 75 < tm <= 85 else 1)
    return {"parts": parts, "total": sum(parts.values()),
            "rules": {
                "收益(30)": "超额≥50pp=30, ≥30=24, ≥10=18, ≥0=12, <0=0",
                "回撤(25)": "优于-20%=25, -20~-30=18, -30~-40=10, 劣于-40=0",
                "熊市规避(20)": "熊市持仓≤15%=20, ≤30=16, ≤45=11, ≤60=6, >60=0",
                "执行效率(15)": "2~5笔=15, 6~8=10, 9~12=5, 其他=0",
                "资金利用(10)": "持仓40~65%=10, 30~40或65~75=7, 20~30或75~85=4, 其他=1",
            }}


def main():
    f = build()
    res = {"meta": {"period": f"{START}~{END}", "note": "不看年化，只看持有月数与累计收益；月末信号次月生效，单边5bp",
                    "main": "5y PE分位<=20% 且 ERP>=6.5pp 买入；分位>=80% 卖出"},
           "strategies": {}, "scores": {}}
    variants = {
        "S_5y_ERP": (5, 6.5),
        "C_5y_base": (5, None),
        "C_3y_ERP": (3, 6.5),
    }
    for name, (y, th) in variants.items():
        res["strategies"][name] = run_strategy(f, y, th)
        res["scores"][name] = score(res["strategies"][name], None)
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)
    rows = []
    for name, v in res["strategies"].items():
        for t in v["trades"]:
            rows.append({"strategy": name, **t})
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    for name, v in res["strategies"].items():
        sc = res["scores"][name]
        print(f"===== {name}  {v['period']} =====")
        print(f"  累计 {v['total_ret']:+.2f}%  基准 {v['bh_total_ret']:+.2f}%  超额 {v['excess_pp']:+.2f}pp  "
              f"回撤 {v['max_dd']}%  持仓 {v['tim']}%  熊市持仓 {v['bear_tim']}%/{v['bear_months']}月  "
              f"笔数 {v['ntr']}  评分 {sc['total']}/100 {sc['parts']}")
        for t in v["trades"]:
            print(f"    {t['in_signal']} 买(PE分位{t['pe_pct_in']}%, ERP{t['erp_in']}) → "
                  f"{t['out_signal']} 卖  持{t['months']}月  {t['ret']:+.2f}%")


if __name__ == "__main__":
    main()
