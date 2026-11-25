# -*- coding: utf-8 -*-
"""
PE≤20% 买入机会事件研究（2019 年后，沪深300）

- 统计 3 年 / 5 年 PE 分位 <=20% 的独立机会（连续月份合并为一次）
- 每次机会若立刻买入，持有 3/6/12/24/36/48/60 月及至今的收益
- 同期基准：① 从 2019-01 买入持有到同一时点 ② 全样本无条件平均前瞻收益
- 卖出时机：首次分位 >=80% / >=90% 离场 vs 一直持有至今
- 年度对比：把每次信号各投 1 元的平均净值 vs 2019-01 买入 1 元
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from backtest_pe_pct_2019 import load_monthly, rolling_pct

OUT = os.path.join(ROOT, "data", "pe_entry_events.json")
OUT_CSV = os.path.join(ROOT, "data", "pe_entry_events.csv")
START = "2019-01"
HOR = [3, 6, 12, 24, 36, 48, 60]


def clusters(mask):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    out, cur = [], [idx[0]]
    for i in idx[1:]:
        if i == cur[-1] + 1:
            cur.append(i)
        else:
            out.append(cur)
            cur = [i]
    out.append(cur)
    return out


def main():
    m = load_monthly()
    ym = m.ym.astype(str).values
    pe = m.pe_ttm.values.astype(float)
    close = m.index_close.values.astype(float)
    lo = int(np.searchsorted(ym, START))
    hi = len(m) - 1
    pcts = {3: rolling_pct(pe, 36), 5: rolling_pct(pe, 60)}

    # 无条件前瞻收益基线（2019 后所有起点）
    base = {}
    for h in HOR:
        vals = [close[i + h] / close[i] - 1 for i in range(lo, hi - h + 1)]
        base[h] = round(float(np.mean(vals)) * 100, 2)

    res = {"meta": {
        "period": f"{ym[lo]}~{ym[hi]}", "months": int(hi - lo), "start_close": float(close[lo]),
        "end_close": float(close[hi]), "source": "val_index_pe_lg 沪深300 PE-TTM 加权",
        "unconditional_fwd": base,
        "note": "买入价=信号月收盘；卖出价=首次分位≥阈值的次月收盘；基准A=2019-01 买入持有到同一时点；基准B=全样本无条件平均前瞻收益",
    }, "events": {}, "yearly": {}, "summary": {}}

    all_events = []
    for y in (3, 5):
        p = pcts[y]
        cl = clusters(p[lo:hi + 1] <= 0.20)
        evs = []
        for k, g in enumerate(cl, 1):
            i = lo + g[0]
            jlast = lo + g[-1]
            e = {
                "no": k, "entry": ym[i], "entry_end": ym[jlast], "months_below20": len(g),
                "pe": round(float(pe[i]), 2), "pct": round(float(p[i]) * 100, 1),
                "close": round(float(close[i]), 1),
                "fwd": {}, "bench_fixed": {},
            }
            for h in HOR:
                if i + h <= hi:
                    e["fwd"][str(h)] = round(float(close[i + h] / close[i] - 1) * 100, 1)
                    e["bench_fixed"][str(h)] = round(float(close[i + h] / close[lo] - 1) * 100, 1)
            if i < hi:
                e["fwd"]["now"] = round(float(close[hi] / close[i] - 1) * 100, 1)
                e["bench_fixed"]["now"] = round(float(close[hi] / close[lo] - 1) * 100, 1)
            # 卖出时机
            for th in (0.80, 0.90):
                js = np.where(p[i + 1:hi] >= th)[0]
                if len(js):
                    j = i + 1 + int(js[0])
                    out_i = min(j + 1, hi)
                    e[f"exit{int(th*100)}"] = round(float(close[out_i] / close[i] - 1) * 100, 1)
                    e[f"exit{int(th*100)}_m"] = out_i - i
                    e[f"exit{int(th*100)}_date"] = ym[out_i]
                else:
                    e[f"exit{int(th*100)}"] = None
                    e[f"exit{int(th*100)}_m"] = None
                    e[f"exit{int(th*100)}_date"] = "未触发"
            evs.append(e)
            all_events.append({**e, "window": f"{y}y"})
        res["events"][f"{y}y"] = evs

    # 年度对比：每次信号各投 1 元，取平均净值
    year_ends = {}
    for i in range(lo, hi + 1):
        yr = ym[i][:4]
        year_ends[yr] = i           # 逐年最后一个有数据的月
    years = sorted(year_ends)
    rows = []
    for yr in years:
        i = year_ends[yr]
        row = {"year": yr, "ym": ym[i], "bench_eq": round(float(close[i] / close[lo]), 4)}
        for y in (3, 5):
            es = [e for e in res["events"][f"{y}y"]]
            # 该时点之前（含）已经出现的信号
            avail = [e for e in es if e["entry"] <= ym[i]]
            if avail:
                vals = [close[i] / e["close"] for e in avail]
                row[f"sig{y}_eq"] = round(float(np.mean(vals)), 4)
                row[f"sig{y}_n"] = len(avail)
            else:
                row[f"sig{y}_eq"] = None
                row[f"sig{y}_n"] = 0
        rows.append(row)
    # 年度涨跌
    for idx, row in enumerate(rows):
        prev = rows[idx - 1] if idx > 0 else {"bench_eq": 1.0, "sig3_eq": 1.0, "sig5_eq": 1.0}
        for k in ("bench_eq", "sig3_eq", "sig5_eq"):
            row[k.replace("eq", "ret")] = (round((row[k] / prev[k] - 1) * 100, 1)
                                           if row[k] is not None and prev.get(k) is not None else None)
    res["yearly"]["rows"] = rows

    # 汇总
    for y in (3, 5):
        es = res["events"][f"{y}y"]
        ex80 = [e["exit80"] for e in es if e["exit80"] is not None]
        ex90 = [e["exit90"] for e in es if e["exit90"] is not None]
        nowr = [e["fwd"].get("now") for e in es if e["fwd"].get("now") is not None]
        f12 = [e["fwd"]["12"] for e in es if "12" in e["fwd"]]
        b12 = [e["bench_fixed"]["12"] for e in es if "12" in e["bench_fixed"]]
        res["summary"][f"{y}y"] = {
            "n_events": len(es),
            "n_months": sum(e["months_below20"] for e in es),
            "avg_fwd12": round(float(np.mean(f12)), 1) if f12 else None,
            "avg_bench12": round(float(np.mean(b12)), 1) if b12 else None,
            "uncond12": base[12],
            "avg_now": round(float(np.mean(nowr)), 1) if nowr else None,
            "avg_exit80": round(float(np.mean(ex80)), 1) if ex80 else None,
            "avg_exit80_m": round(float(np.mean([e["exit80_m"] for e in es if e["exit80_m"]])), 1),
            "avg_exit90": round(float(np.mean(ex90)), 1) if ex90 else None,
            "avg_exit90_m": round(float(np.mean([e["exit90_m"] for e in es if e["exit90_m"]])), 1),
            "best": max(es, key=lambda e: e["fwd"].get("now", -999))["entry"],
            "worst": min(es, key=lambda e: e["fwd"].get("now", 999))["entry"],
        }

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    pd.DataFrame(all_events).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    # 打印
    print(f"区间 {res['meta']['period']}  起点收盘 {close[lo]:.0f} -> 终点 {close[hi]:.0f} "
          f"({(close[hi]/close[lo]-1)*100:+.1f}%)")
    print("无条件平均前瞻收益:", base, "\n")
    for y in (3, 5):
        s = res["summary"][f"{y}y"]
        print(f"【{y}年PE ≤20%】独立机会 {s['n_events']} 次，累计 {s['n_months']} 个月")
        for e in res["events"][f"{y}y"]:
            f = e["fwd"]
            print(f"  #{e['no']} {e['entry']}~{e['entry_end']} ({e['months_below20']}月) "
                  f"PE {e['pe']:>5.2f} 分位 {e['pct']:>4.1f}% 收盘 {e['close']:>6.0f} | "
                  f"12月 {f.get('12','--'):>5}% 24月 {f.get('24','--'):>5}% 36月 {f.get('36','--'):>5}% "
                  f"至今 {f.get('now','--'):>6}% | 80%卖 {e['exit80']}({e['exit80_m']}月) "
                  f"90%卖 {e['exit90']}({e['exit90_m']}月)")
        print(f"  平均: 12月 {s['avg_fwd12']}% vs 同期基准 {s['avg_bench12']}% vs 无条件 {s['uncond12']}%  "
              f"至今 {s['avg_now']}%  80%卖 {s['avg_exit80']}% ({s['avg_exit80_m']}月)  "
              f"90%卖 {s['avg_exit90']}% ({s['avg_exit90_m']}月)\n")

    print("【年度：信号平均净值 vs 2019-01 买入持有】")
    print(f"{'年':>6} {'月末':>8} {'基准净值':>8} {'基准当年':>8} {'3y信号净值':>10} {'3y当年':>8} "
          f"{'5y信号净值':>10} {'5y当年':>8} {'信号数3/5':>10}")
    def fmt(v, spec):
        return format(v, spec) if v is not None else "     —"
    for r in rows:
        print(f"{r['year']:>6} {r['ym']:>8} {fmt(r['bench_eq'],'>8.3f')} {fmt(r['bench_ret'],'>7.1f')}% "
              f"{fmt(r['sig3_eq'],'>10.3f')} {fmt(r['sig3_ret'],'>7.1f')}% {fmt(r['sig5_eq'],'>10.3f')} "
              f"{fmt(r['sig5_ret'],'>7.1f')}% {r['sig3_n']:>4}/{r['sig5_n']:<4}")
    print(f"\n输出 {OUT}\n     {OUT_CSV}")


if __name__ == "__main__":
    main()
