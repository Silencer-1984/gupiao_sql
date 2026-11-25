# -*- coding: utf-8 -*-
"""生成「低利率新常态下的买卖区间重构」HTML 报告。"""
import json
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from backtest_adaptive_rules import build

OUT = os.path.join(ROOT, "docs", "adaptive_interval_report.html")
A = json.load(open(os.path.join(ROOT, "data", "adaptive_rules.json"), encoding="utf-8"))
T = json.load(open(os.path.join(ROOT, "data", "regime_turns.json"), encoding="utf-8"))
f = build()

BUY_ORDER = ["原策略_20+ERP6.5", "纯20", "纯25", "纯30", "纯35",
             "30+ERP6.0", "30+ERP5.5", "35+ERP6.0", "25+ERP6.0",
             "30+股息差1.0", "35+股息差1.0", "40+股息差1.0", "纯股息差1.0",
             "30+股息差分位80", "40+股息差分位80",
             "30+ERP分位70", "40+ERP分位80", "ERP分位80",
             "30+恐慌50", "35+恐慌50", "30+熊市确认", "40+熊市确认",
             "EY8(PE≤12.5)", "EY9(PE≤11.1)", "30+EY8", "35+EY7.5"]
SELLS = ["PE≥70", "PE≥75", "PE≥80", "PE≥85", "PE≥90", "PE≥95"]

# ---------- 表格 ----------
def buy_rows():
    out = ""
    for k in BUY_ORDER:
        v = A["buy_scan"][k]
        good = v["excess"] >= 100
        bad = v["excess"] < 0
        cls = "c-up" if good else ("c-down" if bad else "")
        out += (f"<tr><td class='nm {cls}'>{k}</td><td class='{cls}'>{v['total_ret']:+.1f}%</td>"
                f"<td>{v['excess']:+.1f}pp</td><td>{v['max_dd']:+.1f}%</td>"
                f"<td>{v['tim']:.1f}%</td><td>{v['ntr']}</td>"
                f"<td>{'是' if v['now_signal'] else '—'}</td></tr>")
    return out

def sell_rows():
    out = ""
    d = A["sell_scan"]["原策略_20+ERP6.5"]
    for k in SELLS:
        v = d[k]
        cls = "c-up" if k in ("PE≥90", "PE≥95") else ""
        logs = " / ".join(f"{x['in']}→{x['out']}({x['ret']:+.1f}%)" for x in v["trades"])
        out += (f"<tr><td class='nm {cls}'>{k}</td><td class='{cls}'>{v['total_ret']:+.1f}%</td>"
                f"<td>{v['excess']:+.1f}pp</td><td>{v['max_dd']:+.1f}%</td>"
                f"<td>{v['tim']:.1f}%</td><td>{v['ntr']}</td><td class='sm'>{logs}</td></tr>")
    return out

def drift_rows():
    out = ""
    for p in ["2013-04", "2018-12", "2022-09", "2026-11"]:
        r = f.loc[pd.Period(p)]
        cls = "c-up" if pd.Period(p) != pd.Period("2026-11") else "c-down"
        out += (f"<tr><td class='nm {cls}'>{p}{' ← 当前' if p=='2026-11' else ''}</td>"
                f"<td>{r.pe:.2f}</td><td>{r.pe_pct5*100:.1f}%</td>"
                f"<td>{r.cn_10y:.2f}%</td><td>{100/r.pe:.2f}%</td>"
                f"<td class='{cls}'>{r.erp:.2f}pp</td>"
                f"<td>{r.div_yield-r.cn_10y:+.2f}pp</td></tr>")
    return out

def bond_rows():
    out = ""
    for b in [3.6, 3.0, 2.5, 2.0, 1.6, 1.2, 1.0, 0.8]:
        cls = "c-up" if b <= 1.6 else ""
        out += (f"<tr><td class='{cls}'>{b:.1f}%</td><td class='{cls}'>≤{100/(6.5+b):.2f}</td>"
                f"<td>{(100/(6.5+b)/12.74-1)*100:+.1f}%</td></tr>")
    return out

def turn_rows():
    out = ""
    for t in T["turns"]:
        if t["ym"] < "2013-01":
            continue
        a = t["at"]
        cls = "c-up" if t["to"] == "牛市" else "c-down"
        out += (f"<tr><td class='nm'>{t['ym']}</td><td class='{cls}'>{t['to']}</td>"
                f"<td>{a['pe']:.1f}</td><td>{(a['pe_pct5'] or 0)*100:.1f}%</td>"
                f"<td>{a['erp']:.2f}</td><td>{a['dy_spread']:+.2f}</td>"
                f"<td>{a['fear_composite'] or 0:.1f}</td>"
                f"<td>{(a['dd36'] or 0)*100:.1f}%</td>"
                f"<td class='{cls}'>{t['fwd12']:+.1f}%</td></tr>")
    return out

def dist_rows():
    out = ""
    for era, d in T["dist"].items():
        for stt in ["牛市", "熊市", "震荡"]:
            if stt not in d:
                continue
            v = d[stt]
            cls = "c-up" if stt == "牛市" else ("c-down" if stt == "熊市" else "")
            out += (f"<tr><td class='nm'>{era}</td><td class='{cls}'>{stt}</td>"
                    f"<td>{(v['pe_pct5'] or 0)*100:.1f}%</td><td>{v['pe']:.1f}</td>"
                    f"<td>{v['erp']:.2f}</td><td class='{cls}'>{v['dy_spread']:+.2f}</td>"
                    f"<td>{v['fear_composite'] or 0:.1f}</td><td>{v['n']}</td></tr>")
    return out

def marked_rows():
    out = ""
    for p, v in T["marked"].items():
        if p < "2013-01":
            continue
        s = v["snap"]
        out += (f"<tr><td class='nm'>{p} <span style='color:#94a3b8'>{v['label']}</span></td>"
                f"<td>{s['pe']:.1f}</td><td>{(s['pe_pct5'] or 0)*100:.1f}%</td>"
                f"<td>{s['erp']:.2f}</td><td>{s['dy_spread']:+.2f}</td>"
                f"<td>{(s['dd36'] or 0)*100:.1f}%</td></tr>")
    return out

# ---------- 图表数据 ----------
ym = [str(x) for x in f.index]
idx = [i for i, x in enumerate(ym) if x >= "2012-01"]
data = {
    "ym": [ym[i] for i in idx],
    "bond": [round(float(f.cn_10y.iloc[i]), 2) for i in idx],
    "erp": [round(float(f.erp.iloc[i]), 2) for i in idx],
    "pe": [round(float(f.pe.iloc[i]), 2) for i in idx],
    "pct": [round(float(f.pe_pct5.iloc[i]) * 100, 1) if pd.notna(f.pe_pct5.iloc[i]) else None for i in idx],
    "dyspd": [round(float(f.div_yield.iloc[i] - f.cn_10y.iloc[i]), 2) for i in idx],
    "close": [round(float(f.index_close.iloc[i]), 1) for i in idx],
    "state": [T["state_series"][i]["state"] for i in idx],
    "buy_names": BUY_ORDER[:14],
    "buy_excess": [A["buy_scan"][k]["excess"] for k in BUY_ORDER[:14]],
    "sell_ths": [x.replace("PE≥", "") for x in SELLS],
    "sell_tot": [A["sell_scan"]["原策略_20+ERP6.5"][k]["total_ret"] for k in SELLS],
    "sell_dd": [A["sell_scan"]["原策略_20+ERP6.5"][k]["max_dd"] for k in SELLS],
    "eq_ym": A["curves"]["ym"],
    "eq_80": A["curves"]["BUY_原策略_20+ERP6.5"],
    "eq_bh": None,
}
# 新策略 20/90 曲线
sys.path.insert(0, HERE)
import backtest_adaptive_rules as AR
old = AR.SELLS
AR.SELLS = {**old, "PE≥90": lambda r: r.pe_pct5 >= 0.90}
data["eq_90"] = AR.simulate(f, "原策略_20+ERP6.5", "PE≥90")["eq_curve"]
AR.SELLS = old
bhr = np.concatenate([f.index_close.values[1:] / f.index_close.values[:-1] - 1, [np.nan]])
lo = data["eq_ym"].index("2013-01")
data["eq_bh"] = [round(float(x), 4) for x in np.cumprod(1 + np.nan_to_num(bhr[lo:lo + len(data["eq_ym"])]))]

HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>低利率新常态下的沪深300买卖区间重构</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--ink:#0f172a;--ink2:#475569;--mut:#94a3b8;--line:#e2e8f0;--bg:#f7f8fa;--card:#fff;--up:#c62828;--down:#1b7f4e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:26px;margin:0 0 10px;line-height:1.35;letter-spacing:-.3px}
h2{font-size:18px;margin:34px 0 12px;padding-left:11px;border-left:4px solid #1e293b}
h3{font-size:14.5px;margin:20px 0 6px;color:var(--ink2)}
.sub-t{color:var(--ink2);font-size:13.5px;margin-bottom:6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:16px 0}
.verdict{background:#fff;border:1px solid var(--line);border-left:4px solid #c62828;border-radius:10px;padding:18px 22px;margin:18px 0}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px 16px}
.kpi .k{font-size:12.5px;color:var(--mut)} .kpi .v{font-size:22px;font-weight:700;margin:3px 0;letter-spacing:-.4px}
.kpi .d{font-size:12px;color:var(--ink2)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}
th,td{padding:8px 9px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{background:#f8fafc;color:var(--ink2);font-size:12px;font-weight:600}
th.nm,td.nm{text-align:left;font-weight:600} td.sm{text-align:left;font-size:11.5px;color:var(--ink2);white-space:normal}
tbody tr:hover{background:#fcfdff}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.note{font-size:12px;color:var(--mut);margin-top:7px}
.chart{width:100%;height:370px}
ul{padding-left:20px;margin:8px 0} li{margin:6px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:880px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">沪深300（000300） · 2013-01 ~ 2026-11（167 个月） · 数据源：本地 ashare.db · 月末信号次月生效，单边 5bp</div>
<h1>低利率新常态下，是否再也等不到买点？<br>——牛熊转折因子复盘与买卖区间重构</h1>

<div class="verdict">
<b>结论一：悲观的前提搞反了。</b>ERP = 盈利收益率 − 国债收益率，<b>国债越低，ERP 越容易达标</b>。当前国债 1.58%、ERP 6.27pp，距 6.5 门槛只差 <b>0.23pp</b>；2026-10 的 ERP 曾达到 6.57pp，刚刚越线。真正拦住买入的是 5 年 PE 分位 76.7%——这是策略刻意保留的"高位不接"保护，不是参数失效。<br>
<b>结论二：三笔买点的绝对 PE 在抬升，ERP 却纹丝不动。</b>2013 年 PE 9.75 / 国债 3.43%、2018 年 PE 10.09 / 国债 3.23%、2022 年 PE 10.47 / 国债 2.76%，ERP 分别是 6.83 / 6.68 / 6.79pp。<b>ERP 本身就是自适应指标</b>，已经替你完成了"随利率调整绝对估值门槛"的工作。<br>
<b>结论三：买入侧放宽全部变差，卖出侧放宽才是真改进。</b>26 种买入规则横评，20%+ERP6.5 以累计 <b class="c-up">+204.2%</b> 排第一；25/30/35 分位无论加不加 ERP 都不如它。卖出线从 80% 抬到 90%，累计收益 <b class="c-up">+204.2% → +282.9%</b>，最大回撤始终 -22.6%。<br>
<b>结论四：机构与你看到的"便宜"不是一回事。</b>华泰/国泰海通等口径下沪深300 股债收益差约 6.1%、近十年 80% 分位，但 PE 分位只有 53%。前者是"相对债券便宜"，本策略看的是"相对自身历史便宜"——当前属于<b>前者高分、后者中高</b>，因此机构看多、策略仍不买。
</div>

<div class="grid">
  <div class="kpi"><div class="k">当前 ERP</div><div class="v">6.27<span style="font-size:14px">pp</span></div><div class="d">距 6.5 门槛仅 0.23pp</div></div>
  <div class="kpi" style="border-color:#fecaca"><div class="k">当前 5 年 PE 分位</div><div class="v c-down">76.7%</div><div class="d">买入线 20%，卖出线 80%</div></div>
  <div class="kpi"><div class="k">卖出 80% → 90%</div><div class="v c-up">+282.9%</div><div class="d">13 年累计，回撤不变</div></div>
  <div class="kpi"><div class="k">买入机会（2019+）</div><div class="v">7 次</div><div class="d">5 年分位 ≤20%，非"等不到"</div></div>
</div>

<h2>一、利率中枢下移，到底改变了什么</h2>
<div class="card"><h3>买点绝对估值的漂移</h3><table>
<thead><tr><th class="nm">月份</th><th>PE-TTM</th><th>5年分位</th><th>10年国债</th><th>盈利收益率</th><th>ERP</th><th>股息率−国债</th></tr></thead>
<tbody>__DRIFT__</tbody></table>
<div class="note">三笔实际买入的 ERP 高度稳定在 6.68~6.83pp，但对应 PE 从 9.75 抬到 10.47、国债从 3.43% 降到 2.76%。ERP 自动吸收了利率变化。当前股息率−国债已达 +1.28pp（历史最高区间），但 PE 分位 76.7% 仍不满足买入。</div></div>

<div class="card"><h3>ERP 6.5pp 门槛对应的 PE 上限，随国债自动抬升</h3><table>
<thead><tr><th>10 年国债</th><th>PE 需 ≤</th><th>相对当前 PE 12.74</th></tr></thead>
<tbody>__BOND__</tbody></table>
<div class="note">国债每降 0.4pp，ERP 门槛对应的 PE 上限就抬升约 0.6 倍。若国债降到 1.2%，PE≤12.99 即达标——"PE 特别便宜"的要求实际上在自动放宽，不会永远够不到。</div></div>

<div class="card"><div id="rate" class="chart"></div>
<div class="note">国债收益率（右轴）持续下行，ERP（左轴）在 2012-2014、2018-2020、2022-2025 三次冲上 6.5pp。低利率并不压缩 ERP，反而抬升它。</div></div>

<h2>二、牛熊转折节点的因子画像</h2>
<p>用事前可判定的技术性定义识别转折：自 24 月低点上涨 ≥20% 且站上 MA12 = 牛市；自 24 月高点回撤 ≤−20% 且跌破 MA12 = 熊市；状态持续 3 个月确认。2013 年以来共 __NTURN__ 次转折。</p>
<div class="card"><table>
<thead><tr><th class="nm">转折月</th><th>转入</th><th>PE</th><th>5年分位</th><th>ERP</th><th>股息差</th><th>恐慌度</th><th>36月回撤</th><th>后12月</th></tr></thead>
<tbody>__TURN__</tbody></table></div>

<div class="card"><h3>各时代、各状态下的因子中位数</h3><table>
<thead><tr><th class="nm">时代</th><th>状态</th><th>PE 5年分位</th><th>PE</th><th>ERP</th><th>股息差</th><th>恐慌度</th><th>月数</th></tr></thead>
<tbody>__DIST__</tbody></table>
<div class="note">关键变化：2010-2016 股息率−国债利差在牛市 -1.51、熊市 -0.47，区分清晰；到 2022-2026 变成牛市 +1.09、熊市 +1.21，<b>几乎完全失去区分度</b>。而 PE 5 年分位在低利率时代仍有牛市 80.8% vs 熊市 21.7% 的清晰分野。</div></div>

<div class="card"><h3>公认重要底部/顶部的因子快照（事后标注，仅作对照）</h3><table>
<thead><tr><th class="nm">月份 / 标记</th><th>PE</th><th>5年分位</th><th>ERP</th><th>股息差</th><th>36月回撤</th></tr></thead>
<tbody>__MARK__</tbody></table></div>

<p>三个可直接落地的观察：</p>
<ul>
<li><b>绝对股债指标在低利率时代失效。</b>2024-12 牛市确认时 ERP 6.53pp、股息差 +1.66pp 都处于历史高位，但 PE 分位已经 61.7%——"股债性价比高"和"该买"彻底脱钩。红利型因子只能做背景，不能当扳机。</li>
<li><b>PE 相对分位仍然是最稳的状态判别器。</b>低利率改变了绝对估值中枢，但没有改变"相对自身历史贵不贵"的含义。这是不随利率漂移的锚。</li>
<li><b>恐慌度只在极端时有用。</b>2022-10 恐慌 58.5、2023-11 恐慌 3.6，两次都在底部区域，但数值差别巨大；硬编码阈值会把第二次完全筛掉。</li>
</ul>

<h2>三、买入规则横评：26 种方案，原策略仍然第一</h2>
<div class="card"><table>
<thead><tr><th class="nm">买入规则（卖出固定 PE≥80）</th><th>13年累计</th><th>超额</th><th>回撤</th><th>持仓</th><th>笔数</th><th>当前信号</th></tr></thead>
<tbody>__BUY__</tbody></table></div>
<p>买入分位从 20% 一路放宽到 40%，只要保留 ERP≥6.5，结果<b>完全相同（+204.2%）</b>——因为在 46 个 ERP≥6.5 的月份里，32 个 PE 分位 ≤20%，只有 10 个 &gt;40%；ERP 才是真正的闸门，分位阈值在历史上从未单独构成约束。但分位闸门不能删：那 10 个 ERP 达标而分位偏高的月份，正是低利率时代会越来越多的"高估值+低利率"组合，它是唯一的高位保护。</p>
<p>失败最彻底的是<b>股息率−国债 ≥1.0pp</b>：13 年只买 1 笔、累计 +28.0%，跑输买入持有。它把 2013-2021 全部排除，只在 2022 年后触发——这恰好说明这个差值在新时代失去区分度。恐慌度硬过滤也把 2 笔砍成 1 笔（+49.6%）。</p>

<div class="card"><div id="buychart" class="chart" style="height:340px"></div>
<div class="note">相对买入持有的超额收益。红色为正、绿色为负（A 股习惯）。</div></div>

<h2>四、卖出规则：值得放宽的一侧</h2>
<div class="card"><table>
<thead><tr><th class="nm">卖出线</th><th>13年累计</th><th>超额</th><th>回撤</th><th>持仓</th><th>笔数</th><th class="nm">逐笔（买→卖）</th></tr></thead>
<tbody>__SELL__</tbody></table></div>
<p>从 70% 到 95% 是<b>单调改善</b>（+139.7% → +291.1%），最大回撤始终是 -22.6%。这不是尖峰调参，而是稳定的方向性证据：卖得太早会砍掉泡沫化末段。第一笔在 80% 卖出是 +65.54%，抬到 90% 变成 +94.09%；第二笔 +55.95% → +59.97%；第三笔 +18.18% → +23.69%。</p>
<p>但 <b>95% 不建议直接用</b>：第三笔要一直拿到 2026-04 才卖，已经贴近样本末端，带有边界效应。<b>85%~90% 是稳健区间</b>，其中 90% 改善最强且三笔交易都完整。</p>

<div class="card"><div id="sellchart" class="chart" style="height:330px"></div></div>
<div class="card"><div id="eqchart" class="chart"></div>
<div class="note">原策略 20/80（蓝）与改进版 20/90（红）的净值对比；灰色虚线为买入持有。卖出侧放宽不增加回撤，因为买入纪律没变。</div></div>

<h2>五、机构视角对照（2026 年 10-11 月公开观点）</h2>
<div class="card"><table>
<thead><tr><th class="nm">机构 / 来源</th><th class="nm">核心表述</th><th>ERP / 股债差</th><th>PE 分位</th></tr></thead>
<tbody>
<tr><td class="nm">华泰证券 王伟光</td><td class="sm">沪深300 PE 12.9、PB 1.37；股息率 2.8%，高出国债约 120bp；风险补偿处历史较高水平</td><td>约 6.1%，近十年 80% 分位</td><td>近十年 53%</td></tr>
<tr><td class="nm">国泰海通 方奕</td><td class="sm">低利率下股债比价优势明显，分红比例抬升，大盘蓝筹长期回报优势凸显</td><td>股息高于国债约 140bp</td><td>近十年 54%</td></tr>
<tr><td class="nm">东方财富证券 陈果</td><td class="sm">无风险利率是定价锚，1.6% 国债对业绩稳定增长的蓝筹是极有利的估值环境</td><td>近十年 72% 分位</td><td>静态 PE 13.6</td></tr>
<tr><td class="nm">新思哲 徐温泉</td><td class="sm">本轮调整是估值收缩而非盈利恶化，核心资产处于底部区间</td><td>近十年约 80% 分位</td><td>PB 近十年 &lt;30%</td></tr>
</tbody></table>
<div class="note">机构一致看多的依据是"相对债券便宜 + 盈利修复"，这与本策略的数据并不冲突：当前 ERP 绝对 6.27pp 确实高于十年均值，但 5 年 PE 分位 76.7% 说明相对自身仍不便宜。机构是配置视角（可以分批建仓），策略是择时视角（要等极端赔率），两者目标不同。</div></div>

<h2>六、最终建议：新买卖区间</h2>
<div class="card">
<h3>保留的部分（经 13 年 + 20 年检验）</h3>
<ul>
<li><b>买入：5 年 PE 分位 ≤20% 且 ERP ≥6.5pp</b>。不要因为担心等不到就放宽——26 种规则横评里它排第一，放宽买入在 2013-2026 全部变差。</li>
<li><b>ERP 用绝对阈值，不用滚动分位</b>。之前测过 ERP 60 月分位 ≥80%：累计 +149.7%，不如绝对阈值的 +204.2%。绝对阈值让"便宜"的标准随利率自动调整。</li>
</ul>
<h3>修改的部分</h3>
<ul>
<li><b>卖出：PE 5 年分位 ≥85%~90%（原 80%）</b>。13 年累计从 +204.2% 提升到 +267.2%~+282.9%，回撤不变。推荐 90%，85% 更保守。</li>
<li><b>不加入股息率−国债、恐慌度、牛市确认作为硬条件</b>。前者在低利率时代失效，后两者实测把收益砍半。</li>
</ul>
<h3>如果要缓解"等不到"的焦虑</h3>
<ul>
<li>可以<b>降低仓位而非降低标准</b>：满足买入条件投 100%，若 ERP 在 6.0~6.5 且 PE 5 年分位 ≤35%，可投 20%~30% 试探仓，剩余资金仍等极端点。注意这部分<b>未经回测验证</b>，属于风险偏好选择。</li>
<li><b>接受空仓是策略的一部分</b>：13.8 年里 3 笔交易、持仓 46%，2015-03~2018-12 连续空仓 45 个月。空仓不是失败。</li>
</ul>
</div>

<h2>七、必须承认的局限</h2>
<ul>
<li>13 年只有 3 笔独立交易，卖出线从 80% 调到 90% 的收益提升全部来自这 3 笔的边际延长，<b>不构成统计显著性</b>。</li>
<li>ERP 绝对阈值会随利率中枢漂移：这里的 6.5pp 是在国债 1.6%~4.2% 区间检验的。若进入零利率，需重新校准。</li>
<li>机构观点来自公开媒体报道，仅作视角对照，本报告的买卖决策完全基于本地数据库回测。</li>
<li>回测假设满仓、月末信号、单边 5bp；"少量购入"的实际收益按比例缩放。</li>
</ul>

<div class="dis"><b>免责声明</b>：以上内容基于公开数据与量化回测，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况与投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。</div>

</div><script>
const D = __DATA__;
const C={up:'#c62828',down:'#1b7f4e',ink:'#0f172a',mut:'#94a3b8',line:'#e2e8f0'};
const base={textStyle:{fontFamily:'-apple-system,PingFang SC,Microsoft YaHei,sans-serif'},
  grid:{left:52,right:52,top:44,bottom:52},
  tooltip:{trigger:'axis',backgroundColor:'#fff',borderColor:C.line,textStyle:{color:C.ink,fontSize:12}}};
echarts.init(document.getElementById('rate')).setOption({...base,
  legend:{data:['ERP','10年国债','股息率−国债'],top:6,textStyle:{fontSize:11}},
  xAxis:{type:'category',data:D.ym,axisLabel:{interval:23,fontSize:10}},
  yAxis:[{type:'value',name:'pp',min:-2,max:9},{type:'value',name:'国债 %',min:0,max:5,splitLine:{show:false}}],
  series:[
    {name:'ERP',type:'line',data:D.erp,symbol:'none',lineStyle:{width:2,color:C.up},
      markLine:{silent:true,symbol:'none',label:{formatter:'6.5pp',fontSize:10},lineStyle:{type:'dashed',color:C.up},data:[{yAxis:6.5}]}},
    {name:'10年国债',type:'line',yAxisIndex:1,data:D.bond,symbol:'none',lineStyle:{width:1.8,color:'#2563eb'}},
    {name:'股息率−国债',type:'line',data:D.dyspd,symbol:'none',lineStyle:{width:1.3,color:'#0f766e',opacity:.75}}
  ]});
echarts.init(document.getElementById('buychart')).setOption({...base,
  grid:{left:150,right:40,top:16,bottom:32},
  xAxis:{type:'value',name:'超额 pp'},yAxis:{type:'category',data:D.buy_names.slice().reverse(),axisLabel:{fontSize:10}},
  series:[{type:'bar',data:D.buy_excess.slice().reverse().map(v=>({value:v,itemStyle:{color:v>=0?C.up:C.down}})),
    label:{show:true,position:'right',fontSize:10,formatter:p=>p.value.toFixed(0)}}]});
echarts.init(document.getElementById('sellchart')).setOption({...base,
  legend:{data:['13年累计收益','最大回撤'],top:4,textStyle:{fontSize:11}},
  xAxis:{type:'category',data:D.sell_ths.map(x=>x+'%')},
  yAxis:[{type:'value',name:'累计 %'},{type:'value',name:'回撤 %',max:0,splitLine:{show:false}}],
  series:[
    {name:'13年累计收益',type:'bar',data:D.sell_tot,itemStyle:{color:C.up},label:{show:true,position:'top',fontSize:10,formatter:p=>p.value.toFixed(0)+'%'}},
    {name:'最大回撤',type:'line',yAxisIndex:1,data:D.sell_dd,lineStyle:{color:C.ink,width:2},symbol:'circle',symbolSize:6}
  ]});
echarts.init(document.getElementById('eqchart')).setOption({...base,
  legend:{data:['20/80 原策略','20/90 改进版','买入持有'],top:6,textStyle:{fontSize:11}},
  xAxis:{type:'category',data:D.eq_ym,axisLabel:{interval:17,fontSize:10}},
  yAxis:{type:'value',name:'净值',min:0.8},
  series:[
    {name:'买入持有',type:'line',data:D.eq_bh,symbol:'none',lineStyle:{width:1.4,type:'dashed',color:C.mut}},
    {name:'20/80 原策略',type:'line',data:D.eq_80,symbol:'none',lineStyle:{width:2,color:'#2563eb'}},
    {name:'20/90 改进版',type:'line',data:D.eq_90,symbol:'none',lineStyle:{width:2.4,color:C.up}}
  ]});
</script></html>'''

rep = {
    "DRIFT": drift_rows(), "BOND": bond_rows(), "TURN": turn_rows(),
    "DIST": dist_rows(), "MARK": marked_rows(), "BUY": buy_rows(), "SELL": sell_rows(),
    "NTURN": str(sum(1 for t in T["turns"] if t["ym"] >= "2013-01")),
}
for k, v in rep.items():
    HTML = HTML.replace("__" + k + "__", v)
HTML = HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
with open(OUT, "w", encoding="utf-8") as fp:
    fp.write(HTML)
print("written", OUT, len(HTML))
