# -*- coding: utf-8 -*-
"""低利率新常态下的自适应买卖区间筛选。

在 2013-01 ~ 2026-11 上比较多种买入/卖出规则，输出累计收益、持有月数、回撤、当前信号。
不计算年化（按用户口径）。月末信号次月生效，单边 5bp。
"""
import json
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from factor_timing_data import load_factor_panel, rolling_pct as rp
from backtest_pe_pct_2019 import apply_pos

START, END = "2013-01", "2026-11"
OUT = os.path.join(ROOT, "data", "adaptive_rules.json")


def build():
    f = load_factor_panel()
    f["pe_pct3"] = rp(f.pe, 36)
    f["pe_pct5"] = rp(f.pe, 60)
    f["pb_pct5"] = rp(f.pb, 60)
    f["erp_pct60"] = rp(f.erp, 60)
    f["ey"] = 100.0 / f.pe
    f["dy_spread"] = f.div_yield - f.cn_10y
    f["dy_spread_pct60"] = rp(f.dy_spread, 60)
    s = f.index_close
    f["dd24"] = s / s.rolling(24, min_periods=18).max() - 1
    f["up24"] = s / s.rolling(24, min_periods=18).min() - 1
    f["ma12_dev"] = s / s.rolling(12, min_periods=12).mean() - 1
    return f


# 买入规则：返回 bool Series
def mk_buy(name):
    def f(r):
        p5 = r.pe_pct5
        if name == "原策略_20+ERP6.5": return p5 <= 0.20 and r.erp >= 6.5
        if name == "纯20": return p5 <= 0.20
        if name == "纯25": return p5 <= 0.25
        if name == "纯30": return p5 <= 0.30
        if name == "纯35": return p5 <= 0.35
        if name == "30+ERP6.0": return p5 <= 0.30 and r.erp >= 6.0
        if name == "30+ERP5.5": return p5 <= 0.30 and r.erp >= 5.5
        if name == "35+ERP6.0": return p5 <= 0.35 and r.erp >= 6.0
        if name == "25+ERP6.0": return p5 <= 0.25 and r.erp >= 6.0
        if name == "30+股息差1.0": return p5 <= 0.30 and r.dy_spread >= 1.0
        if name == "35+股息差1.0": return p5 <= 0.35 and r.dy_spread >= 1.0
        if name == "40+股息差1.0": return p5 <= 0.40 and r.dy_spread >= 1.0
        if name == "纯股息差1.0": return r.dy_spread >= 1.0
        if name == "30+股息差分位80": return p5 <= 0.30 and r.dy_spread_pct60 >= 0.80
        if name == "40+股息差分位80": return p5 <= 0.40 and r.dy_spread_pct60 >= 0.80
        if name == "30+ERP分位70": return p5 <= 0.30 and r.erp_pct60 >= 0.70
        if name == "40+ERP分位80": return p5 <= 0.40 and r.erp_pct60 >= 0.80
        if name == "ERP分位80": return r.erp_pct60 >= 0.80
        if name == "30+恐慌50": return p5 <= 0.30 and r.fear_composite >= 50
        if name == "35+恐慌50": return p5 <= 0.35 and r.fear_composite >= 50
        if name == "30+熊市确认": return p5 <= 0.30 and r.dd24 <= -0.20
        if name == "40+熊市确认": return p5 <= 0.40 and r.dd24 <= -0.20
        if name == "EY8(PE≤12.5)": return r.ey >= 8.0
        if name == "EY9(PE≤11.1)": return r.ey >= 9.0
        if name == "30+EY8": return p5 <= 0.30 and r.ey >= 8.0
        if name == "35+EY7.5": return p5 <= 0.35 and r.ey >= 7.5
        raise ValueError(name)
    return f


SELLS = {
    "PE≥70": lambda r: r.pe_pct5 >= 0.70,
    "PE≥75": lambda r: r.pe_pct5 >= 0.75,
    "PE≥80": lambda r: r.pe_pct5 >= 0.80,
    "PE≥85": lambda r: r.pe_pct5 >= 0.85,
    "PE≥90": lambda r: r.pe_pct5 >= 0.90,
    "PE≥95": lambda r: r.pe_pct5 >= 0.95,
    "牛市确认": lambda r: r.up24 >= 0.20 and r.ma12_dev > 0,
    "股息差分位≤20": lambda r: r.dy_spread_pct60 <= 0.20,
}

BUYS = ["原策略_20+ERP6.5", "纯20", "纯25", "纯30", "纯35",
        "30+ERP6.0", "30+ERP5.5", "35+ERP6.0", "25+ERP6.0",
        "30+股息差1.0", "35+股息差1.0", "40+股息差1.0", "纯股息差1.0",
        "30+股息差分位80", "40+股息差分位80",
        "30+ERP分位70", "40+ERP分位80", "ERP分位80",
        "30+恐慌50", "35+恐慌50", "30+熊市确认", "40+熊市确认",
        "EY8(PE≤12.5)", "EY9(PE≤11.1)", "30+EY8", "35+EY7.5"]


def simulate(f, buy_name, sell_name="PE≥80", start=START):
    ym = f.index.values.astype(str)
    lo = int(np.searchsorted(ym, start))
    hi = min(int(np.searchsorted(ym, END)) + 1, len(f))
    buy, sell = mk_buy(buy_name), SELLS[sell_name]
    pos = np.zeros(len(f))
    s = 0.0
    for i in range(lo, hi):
        r = f.iloc[i]
        if s == 0.0:
            try: ok = bool(buy(r))
            except Exception: ok = False
            if ok: s = 1.0
        else:
            try: out = bool(sell(r))
            except Exception: out = False
            if out: s = 0.0
        pos[i] = s
    close = f.index_close.values.astype(float)
    ret = np.concatenate([close[1:] / close[:-1] - 1, [np.nan]])
    rr = apply_pos(pos[lo:hi], ret[lo:hi])
    eq = np.cumprod(1 + rr)
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    segs = []
    i = lo
    while i < hi:
        if pos[i] == 1 and (i == lo or pos[i - 1] == 0):
            j = i
            while j + 1 < hi and pos[j + 1] == 1:
                j += 1
            seg_ret = float(np.prod(1 + np.nan_to_num(ret[i:j + 1])) - 1) * 100
            segs.append({"in": str(f.index[i]), "out": str(f.index[min(j + 1, hi - 1)]),
                         "months": j - i + 1, "ret": round(seg_ret, 2),
                         "pe_pct": round(float(f.pe_pct5.iloc[i]) * 100, 1)})
            i = j + 1
        else:
            i += 1
    bh = float(np.prod(1 + np.nan_to_num(ret[lo:hi])))
    # 当前信号
    last = f.iloc[-1]
    try: sig = bool(buy(last))
    except Exception: sig = False
    return {
        "total_ret": round(float(eq[-1] - 1) * 100, 2),
        "bh_ret": round((bh - 1) * 100, 2),
        "excess": round((eq[-1] - bh) * 100, 2),
        "max_dd": round(mdd * 100, 1),
        "tim": round(float(pos[lo:hi].mean()) * 100, 1),
        "ntr": len(segs), "trades": segs,
        "now_signal": sig, "buy": buy_name, "sell": sell_name,
        "eq_curve": [round(float(x), 4) for x in eq],
        "ym": [str(x) for x in f.index[lo:hi]],
    }


def main():
    f = build()
    res = {"meta": {"period": f"{START}~{END}", "note": "月末信号次月生效，单边5bp；不计算年化",
                    "sell_fixed": "PE≥80"},
           "buy_scan": {}, "sell_scan": {}, "curves": {}}
    for name in BUYS:
        r = simulate(f, name)
        res["buy_scan"][name] = {k: v for k, v in r.items() if k not in ("eq_curve", "ym")}
        res["curves"]["BUY_" + name] = r["eq_curve"]
    # 对三个候选买入测不同卖出
    for b in ["原策略_20+ERP6.5", "30+ERP6.0", "35+ERP6.0", "30+股息差1.0"]:
        res["sell_scan"][b] = {}
        for s in SELLS:
            r = simulate(f, b, s)
            res["sell_scan"][b][s] = {k: v for k, v in r.items() if k not in ("eq_curve", "ym")}
    res["curves"]["ym"] = simulate(f, "原策略_20+ERP6.5")["ym"]
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1)

    print("=== 买入规则扫描（卖出固定 PE≥80）===")
    print(f"{'规则':<20s} {'累计':>8s} {'超额':>8s} {'回撤':>7s} {'持仓':>6s} {'笔':>3s} {'当前':>5s}")
    for name, v in res["buy_scan"].items():
        print(f"{name:<20s} {v['total_ret']:>+7.1f}% {v['excess']:>+7.1f}pp {v['max_dd']:>6.1f}% "
              f"{v['tim']:>5.1f}% {v['ntr']:>3d} {'是' if v['now_signal'] else '否':>5s}")
    print("\n=== 卖出规则扫描 ===")
    for b, d in res["sell_scan"].items():
        print(" ", b)
        for s, v in d.items():
            print(f"    {s:<14s} 累计{v['total_ret']:>+7.1f}% 超额{v['excess']:>+7.1f}pp "
                  f"回撤{v['max_dd']:>6.1f}% 笔{v['ntr']} 持仓{v['tim']}%")


if __name__ == "__main__":
    main()
