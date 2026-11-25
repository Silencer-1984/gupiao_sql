# -*- coding: utf-8 -*-
"""识别 2010 年以来沪深300 技术性牛熊转折点，提取事前可见因子状态。

技术性定义（事前可判定）：
  牛市开始：自过去 24 月低点上涨 >= 20% 且 收盘 > MA12
  熊市开始：自过去 24 高点回撤 <= -20% 且 收盘 < MA12
  其余为震荡。状态切换需持续 3 个月确认（用 t-3 的状态作为已确认状态）。
输出：转折点前后因子快照 + 各状态下的因子分布。
"""
import json
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_timing_data import load_factor_panel, rolling_pct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "regime_turns.json")


def build():
    f = load_factor_panel()
    f["pe_pct5"] = rolling_pct(f.pe, 60)
    f["pe_pct3"] = rolling_pct(f.pe, 36)
    f["pb_pct5"] = rolling_pct(f.pb, 60)
    f["erp_pct60"] = rolling_pct(f.erp, 60)
    f["dy_spread"] = f.div_yield - f.cn_10y
    f["dy_spread_pct60"] = rolling_pct(f.dy_spread, 60)
    f["ey"] = 100.0 / f.pe
    s = f.index_close
    f["up24"] = s / s.rolling(24, min_periods=18).min() - 1
    f["dd24"] = s / s.rolling(24, min_periods=18).max() - 1
    f["ma12_dev"] = s / s.rolling(12, min_periods=12).mean() - 1
    f["ret12"] = s / s.shift(12) - 1
    f["ret3"] = s / s.shift(3) - 1

    # 原始状态
    st = np.full(len(f), "震荡", dtype=object)
    st[(f.up24.values >= 0.20) & (f.ma12_dev.values > 0)] = "牛市"
    st[(f.dd24.values <= -0.20) & (f.ma12_dev.values < 0)] = "熊市"
    f["state_raw"] = st

    # 确认状态：t-3 与 t 相同才切换，避免噪音
    conf = st.copy()
    for i in range(3, len(st)):
        if st[i] == st[i - 1] == st[i - 2] == st[i - 3]:
            conf[i] = st[i]
        else:
            conf[i] = conf[i - 1]
    f["state"] = conf
    return f


def turn_points(f):
    st = f.state.values
    out = []
    for i in range(1, len(f)):
        if st[i] != st[i - 1] and st[i] in ("牛市", "熊市"):
            out.append({"ym": str(f.index[i]), "i": i, "to": st[i], "from": st[i - 1]})
    return out


def snap(f, i):
    r = f.iloc[i]
    keys = ["index_close", "pe", "pb", "pe_pct5", "pe_pct3", "pb_pct5", "erp", "erp_pct60",
            "div_yield", "cn_10y", "dy_spread", "dy_spread_pct60", "fear_composite",
            "margin_yoy", "congestion", "m1_yoy", "dd36", "dd24", "up24", "ma12_dev",
            "ret12", "ret3", "eps_growth12"]
    return {k: (round(float(r[k]), 3) if pd.notna(r[k]) else None) for k in keys}


def main():
    f = build()
    tp = turn_points(f)
    turns = []
    for t in tp:
        i = t["i"]
        if i < 6 or i + 12 >= len(f):
            continue
        row = {
            "ym": t["ym"], "to": t["to"], "from": t["from"],
            "at": snap(f, i),
            "m3_before": snap(f, i - 3),
            "m3_after": snap(f, i + 3),
            "m12_after": snap(f, i + 12),
            "fwd3": round(float(f.index_close.iloc[i + 3] / f.index_close.iloc[i] - 1) * 100, 2),
            "fwd12": round(float(f.index_close.iloc[i + 12] / f.index_close.iloc[i] - 1) * 100, 2),
        }
        turns.append(row)

    # 公认的重要底部/顶部（事后标注，仅作对照）
    marks = {
        "2008-11": "大底", "2012-12": "底", "2014-03": "底", "2015-06": "大顶",
        "2016-02": "底", "2018-01": "顶", "2018-12": "底", "2019-01": "底",
        "2020-03": "急跌底", "2021-02": "大顶", "2022-04": "急跌底", "2022-10": "底",
        "2024-09": "政策底", "2025-04": "底",
    }
    marked = {}
    for p, lab in marks.items():
        pr = pd.Period(p)
        if pr in f.index:
            marked[p] = {"label": lab, "snap": snap(f, f.index.get_loc(pr))}

    # 各状态下的因子中位数（区分不同利率时代）
    sub = f.loc["2010":]
    dist = {}
    for era, sel in [("2010-2016", sub.loc["2010":"2016"]),
                     ("2017-2021", sub.loc["2017":"2021"]),
                     ("2022-2026", sub.loc["2022":])]:
        d = {}
        for stt in ["牛市", "熊市", "震荡"]:
            x = sel[sel.state == stt]
            if len(x) == 0:
                continue
            d[stt] = {k: (round(float(x[k].median()), 3) if pd.notna(x[k].median()) else None)
                      for k in ["pe", "pe_pct5", "erp", "dy_spread", "fear_composite",
                                "dd36", "ret12", "ma12_dev", "margin_yoy", "m1_yoy"]}
            d[stt]["n"] = len(x)
        dist[era] = d

    res = {
        "method": "技术性牛熊：24月低点+20%且站上MA12=牛；24月高点-20%且跌破MA12=熊；状态持续3月确认",
        "turns": turns, "marked": marked, "dist": dist,
        "state_series": [{"ym": str(f.index[i]), "state": f.state.iloc[i],
                          "close": round(float(f.index_close.iloc[i]), 2)}
                         for i in range(len(f))],
    }
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)

    print("转折点:", len(turns))
    for t in turns:
        a = t["at"]
        print(f"{t['ym']} {t['from']}->{t['to']:2s}  PE{a['pe']:5.1f} 分位5y{(a['pe_pct5'] or 0)*100:5.1f}% "
              f"ERP{a['erp']:5.2f} 股息差{a['dy_spread']:5.2f} 国债{a['cn_10y']:4.2f} "
              f"恐慌{a['fear_composite'] or 0:5.1f} 回撤36{(a['dd36'] or 0)*100:6.1f}% "
              f"后12月{t['fwd12']:+6.1f}%")
    print("\n各时代状态因子中位数:")
    for era, d in dist.items():
        print(" ", era)
        for stt, v in d.items():
            print(f"   {stt} n={v['n']:3d} PE{v['pe']:5.1f} 分位{(v['pe_pct5'] or 0)*100:5.1f}% "
                  f"ERP{v['erp']:5.2f} 股息差{v['dy_spread']:5.2f} 恐慌{v['fear_composite'] or 0:5.1f}")


if __name__ == "__main__":
    main()
