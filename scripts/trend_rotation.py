"""趋势周期与资金交接（尝试性报告）。

不用周/月切刀、不用外部锚点、不设收益或时长硬阈值。
做法：多尺度平滑 -> 局部极值 -> 多尺度一致的趋势拐点 -> 两条线的趋势段重叠。
用法: uv run python scripts/trend_rotation.py
产出: strategies/07_other_research/trend_rotation.md（唯一报告）
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "ashare.db"
OUT = ROOT / "strategies" / "07_other_research" / "trend_rotation.md"
START, END = "2021-01-01", "2026-11-20"
SCALES = (20, 40, 60, 90, 120)  # 交易日平滑尺度；仅用于去噪，不是时间单位
TOL_DAYS = 20                   # 多尺度拐点聚类的日历容差（不是趋势时长标准）
MIN_SCALES = 2                  # 至少几个平滑尺度认可同一拐点
MIN_OVERLAP_DAYS = 1        # 仅排除同一天的伪重叠

lines: list[str] = []


def add(text: str = "") -> None:
    lines.append(text)


def fmt(x, d=1) -> str:
    return "n/a" if pd.isna(x) else f"{x:.{d}f}"


def load_index(conn, code: str) -> pd.Series:
    df = pd.read_sql(
        "select trade_date, close from px_index_daily_csi "
        "where index_code=? and trade_date between ? and ? order by trade_date",
        conn, params=(code, START, END))
    s = df.set_index("trade_date")["close"].astype(float)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def load_stock(conn, code: str) -> pd.Series:
    """不复权价 + 除息现金加回（库内无复权价；bonus/transfer 均为 0）。"""
    df = pd.read_sql(
        "select trade_date, close from px_stock_daily "
        "where stock_code=? and trade_date between ? and ? order by trade_date",
        conn, params=(code, START, END))
    s = df.set_index("trade_date")["close"].astype(float)
    div = pd.read_sql(
        "select ex_date, cash_div_per10 from fin_dividend_detail_all "
        "where stock_code=? and progress='实施' and ex_date between ? and ?",
        conn, params=(code, START, END))
    for _, r in div.iterrows():
        if pd.Timestamp(r["ex_date"]) in s.index:
            s.loc[pd.Timestamp(r["ex_date"])] += float(r["cash_div_per10"]) / 10
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def find_pivots(s: pd.Series, w: int) -> tuple[pd.Series, pd.Series]:
    """平滑序列上的局部高/低点；回看长度随尺度变，不固定时间单位。"""
    k = max(3, w // 2)
    roll = s.rolling(2 * k + 1, center=True, min_periods=2 * k + 1)
    hi = s[(s == roll.max()) & s.notna()]
    lo = s[(s == roll.min()) & s.notna()]
    return hi, lo


def clean_same(pts: list[tuple]) -> list[tuple]:
    """相邻同类型拐点只保留更极端的一个。"""
    out: list[tuple] = []
    for d, v, t in sorted(pts, key=lambda x: x[0]):
        if out and out[-1][2] == t:
            if (t == "hi" and v <= out[-1][1]) or (t == "lo" and v >= out[-1][1]):
                continue
            out[-1] = (d, v, t)
        else:
            out.append((d, v, t))
    return out


def turning_points(price: pd.Series) -> list[tuple]:
    """多尺度一致确认的拐点列表 [(date, type, price)]。"""
    cands = []
    for w in SCALES:
        sm = price.rolling(w, min_periods=w).mean()
        hi, lo = find_pivots(sm, w)
        for d, v in hi.items():
            cands.append((d, float(v), "hi", w))
        for d, v in lo.items():
            cands.append((d, float(v), "lo", w))
    cands.sort(key=lambda x: x[0])
    groups = []
    for c in cands:
        d, _, t, _ = c
        if groups and groups[-1]["type"] == t and (d - groups[-1]["last"]).days <= TOL_DAYS:
            groups[-1]["members"].append(c)
            groups[-1]["last"] = d
        else:
            groups.append({"type": t, "members": [c], "last": d})
    kept = []
    for g in groups:
        if len({m[3] for m in g["members"]}) < MIN_SCALES:
            continue
        pick = (max(g["members"], key=lambda m: m[1]) if g["type"] == "hi"
                else min(g["members"], key=lambda m: m[1]))
        kept.append((pick[0], g["type"], pick[1]))
    return clean_same(kept)


def make_segments(price: pd.Series, turns: list[tuple]) -> list[dict]:
    segs = []
    for (d0, t0, _), (d1, t1, _) in zip(turns, turns[1:]):
        if t0 == t1:
            continue
        segs.append({
            "start": d0, "end": d1,
            "dir": "上涨" if t0 == "lo" else "下跌",
            "days": (d1 - d0).days,
            "ret": (price.asof(d1) / price.asof(d0) - 1) * 100,
        })
    return segs


def overlap(sa: dict, sb: dict, pa: pd.Series, pb: pd.Series) -> dict | None:
    s, e = max(sa["start"], sb["start"]), min(sa["end"], sb["end"])
    if (e - s).days < MIN_OVERLAP_DAYS:
        return None
    return {
        "start": s, "end": e, "days": (e - s).days,
        "ret_a": (pa.asof(e) / pa.asof(s) - 1) * 100,
        "ret_b": (pb.asof(e) / pb.asof(s) - 1) * 100,
        "lead": (sb["start"] - sa["start"]).days,  # 正 = 红利拐点晚于成长拐点
        "seg_a_ret": sa["ret"], "seg_b_ret": sb["ret"],
        "seg_a_days": sa["days"], "seg_b_days": sb["days"],
    }


def pair_episodes(gseg: list[dict], vseg: list[dict], pg: pd.Series,
                  pv: pd.Series) -> dict[str, list[dict]]:
    out = {"资金进成长": [], "资金回红利": [], "同涨": [], "同跌": []}
    for a in gseg:
        for b in vseg:
            o = overlap(a, b, pg, pv)
            if o is None:
                continue
            # 趋势段负责定位区间，实际涨跌负责确认方向；避免拐点误差造成表里方向矛盾
            ra, rb = o["ret_a"], o["ret_b"]
            if ra > 0 and rb < 0:
                out["资金进成长"].append(o)
            elif ra < 0 and rb > 0:
                out["资金回红利"].append(o)
            elif ra > 0 and rb > 0:
                out["同涨"].append(o)
            elif ra < 0 and rb < 0:
                out["同跌"].append(o)
    for k in out:
        out[k].sort(key=lambda x: x["days"], reverse=True)
    return out


def dur_stats(eps: list[dict]) -> str:
    if not eps:
        return "无"
    d = np.array([e["days"] for e in eps])
    return (f"n={len(eps)}，最短 {int(d.min())} 天 / 中位 {int(np.median(d))} 天 / "
            f"最长 {int(d.max())} 天，合计 {int(d.sum())} 天")


def ep_table(eps: list[dict], a_name: str, b_name: str, limit: int = 12) -> None:
    add("| 起始 | 结束 | 持续(日历天) | 成长涨跌 | 红利涨跌 | 红利拐点相对成长(天) | 成长所在趋势段(参考) | 红利所在趋势段(参考) |")
    add("|---|---|---:|---:|---:|---:|---:|---:|")
    for e in eps[:limit]:
        add(f"| {e['start'].date()} | {e['end'].date()} | {e['days']} | "
            f"{e['ret_a']:+.1f}% | {e['ret_b']:+.1f}% | {e['lead']:+d} | "
            f"{e['seg_a_ret']:+.1f}% / {e['seg_a_days']}天 | "
            f"{e['seg_b_ret']:+.1f}% / {e['seg_b_days']}天 |")
    if not eps:
        add("| （无） | - | - | - | - | - | - | - |")


def main() -> None:
    conn = sqlite3.connect(DB)
    series = {
        "科创50": load_index(conn, "000688"),
        "红利低波": load_index(conn, "H30269"),
        "中国电信": load_stock(conn, "601728"),
        "中国移动": load_stock(conn, "600941"),
    }
    turns = {k: turning_points(v) for k, v in series.items()}
    segs = {k: make_segments(series[k], turns[k]) for k in series}

    add("# 趋势周期与资金交接：尝试性报告")
    add()
    add(f"- 区间：{START} ~ {END}（科创50 有效起点 2020-11；电信 2021-08；移动 2022-01）")
    add("- **不用周/月切刀，不用上证指数锚点，不设收益或时长硬阈值。**")
    add("- 做法：对价格做 20/40/60/90/120 交易日多尺度平滑 → 找局部高低点 → "
        "至少 2 个尺度在 20 日历天内一致的才算拐点 → 拐点之间即一个趋势段。"
        "两条线的趋势段重叠 = 一次交接。")
    add("- 尺度与容差只用于去噪与确认拐点，**不定义「多久算长期」**；"
        "时长完全由识别出的拐点决定，以自然日计。")
    add("- 趋势段负责定位交接区间，区间内**实际涨跌方向**负责确认是「钱进成长」还是「钱回红利」，"
        "避免拐点误差造成表里方向矛盾。")
    add("- 个股用除息日现金加回后的价格（库内无复权价）。")
    add()

    add("## 1. 识别出的趋势段")
    add()
    add("| 标的 | 拐点数 | 上涨段 | 下跌段 | 上涨段中位时长 | 下跌段中位时长 |")
    add("|---|---:|---:|---:|---:|---:|")
    for k in series:
        up = [s for s in segs[k] if s["dir"] == "上涨"]
        dn = [s for s in segs[k] if s["dir"] == "下跌"]
        add(f"| {k} | {len(turns[k])} | {len(up)} | {len(dn)} | "
            f"{int(np.median([s['days'] for s in up])) if up else 0} 天 | "
            f"{int(np.median([s['days'] for s in dn])) if dn else 0} 天 |")
    add()

    add("## 2. 科创50 × 红利低波：交接明细")
    add()
    eps = pair_episodes(segs["科创50"], segs["红利低波"], series["科创50"], series["红利低波"])
    for key, title in [("资金进成长", "2.1 成长涨 / 红利跌（钱流向成长）"),
                       ("资金回红利", "2.2 成长跌 / 红利涨（钱回流红利）"),
                       ("同涨", "2.3 两者同向上涨"),
                       ("同跌", "2.4 两者同向下跌")]:
        add(f"### {title}")
        add()
        add(dur_stats(eps[key]))
        add()
        ep_table(eps[key], "科创50", "红利低波", 12 if key != "同涨" and key != "同跌" else 6)
        add()
    add("> 「红利拐点相对成长」为正 = 红利拐点晚于成长拐点（成长先动）；"
        "数值远大于交接时长时说明两方拐点并不同步，交接证据较弱。"
        "「所在趋势段」仅表示定位用的整段涨跌与时长，可能与重叠期实际方向不同，"
        "判断交接方向以表内「成长涨跌 / 红利涨跌」为准。")
    add()

    add("## 3. 中国电信 / 中国移动 × 科创50")
    add()
    for code in ["中国电信", "中国移动"]:
        e = pair_episodes(segs["科创50"], segs[code], series["科创50"], series[code])
        add(f"### {code}")
        add()
        for key in ["资金进成长", "资金回红利", "同涨", "同跌"]:
            add(f"- {key}：{dur_stats(e[key])}")
        add()
        add("最长 5 次交接：")
        add()
        ep_table(e["资金进成长"] + e["资金回红利"], "科创50", code, 5)
        add()

    add("## 4. 尝试性结论")
    add()
    for key, label in [("资金进成长", "钱进成长"), ("资金回红利", "钱回红利")]:
        add(f"- **{label}**：{dur_stats(eps[key])}。")
    same = eps["同涨"] + eps["同跌"]
    opp = eps["资金进成长"] + eps["资金回红利"]
    add(f"- 反向交接共 {len(opp)} 次（钱进成长 {len(eps['资金进成长'])}、钱回红利 {len(eps['资金回红利'])}）；"
        f"同向段共 {len(same)} 次（同涨 {len(eps['同涨'])}、同跌 {len(eps['同跌'])}）。")
    if opp:
        add(f"- 交接时长跨度：最短 {min(x['days'] for x in opp)} 天、最长 {max(x['days'] for x in opp)} 天；"
            "这就是「趋势交接能持续多久」的数据回答，不预设周或月。")
        leads = [x["lead"] for x in opp]
        add(f"- 红利拐点相对成长：中位 {int(np.median(leads)):+d} 天"
            f"（正 = 成长先动），范围 {min(leads):+d} ~ {max(leads):+d} 天。")
    add()
    add("### 局限")
    add()
    add("- 多尺度一致只能近似人眼判断，拐点日期会有若干天误差。")
    add("- 重叠区间可能重复计数同一段大趋势；结论以「明细表」而非合计天数为准。")
    add("- 价格序列无法直接证明资金流，先后顺序只是间接证据。")
    add("- 电信/移动上市晚于科创50，样本较短；三者有成分股重叠。")
    add()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    for k in series:
        print(k, "turns", len(turns[k]), "segments", len(segs[k]))
    conn.close()


if __name__ == "__main__":
    main()
