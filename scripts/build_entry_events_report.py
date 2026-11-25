# -*- coding: utf-8 -*-
"""生成「PE≤20% 买入机会事件研究」HTML 报告。"""
import os
import sys
import json
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from backtest_pe_pct_2019 import load_monthly, rolling_pct

SRC = os.path.join(ROOT, "data", "pe_entry_events.json")
OUT = os.path.join(ROOT, "docs", "pe_entry_events_report.html")
r = json.load(open(SRC, encoding="utf-8"))
meta, ev, yearly, summ = r["meta"], r["events"], r["yearly"]["rows"], r["summary"]

# 图表数据：分位线
m = load_monthly()
ym = m.ym.astype(str).values
pe = m.pe_ttm.values.astype(float)
lo = int(np.searchsorted(ym, "2019-01"))
hi = len(m) - 1
xym = [ym[i] for i in range(lo, hi + 1)]
p3 = [round(float(x) * 100, 1) for x in rolling_pct(pe, 36)[lo:hi + 1]]
p5 = [round(float(x) * 100, 1) for x in rolling_pct(pe, 60)[lo:hi + 1]]

# 事件表
def ev_rows(y):
    out = ""
    for e in ev[f"{y}y"]:
        f = e["fwd"]
        def g(k):
            v = f.get(k)
            return "—" if v is None else f"{v:+.1f}%"
        cls = "c-up" if (f.get("now") or -1) > 0 else "c-down"
        out += (
            f"<tr><td class='nm'>#{e['no']}</td><td>{e['entry']}</td><td>{e['entry_end']}</td>"
            f"<td>{e['months_below20']}</td><td>{e['pe']:.2f}</td><td>{e['pct']:.1f}%</td>"
            f"<td>{e['close']:.0f}</td><td>{g('12')}</td><td>{g('24')}</td><td>{g('36')}</td>"
            f"<td class='{cls}'>{g('now')}</td>"
            f"<td>{e['exit80']:+.1f}% / {e['exit80_m']}月</td>"
            f"<td>{e['exit90']:+.1f}% / {e['exit90_m']}月</td></tr>"
        )
    return out

# 年度表
def yr_rows():
    out = ""
    for v in yearly:
        def s(k, suf=""):
            return "—" if v[k] is None else f"{v[k]:.3f}{suf}"
        def p(k):
            return "—" if v[k] is None else f"{v[k]:+.1f}%"
        cls = "c-up" if (v["sig5_eq"] is not None and v["bench_eq"] >= v["sig5_eq"]) else "c-down"
        out += (
            f"<tr><td class='nm'>{v['year']}</td><td>{v['ym']}</td><td>{s('bench_eq')}</td>"
            f"<td>{p('bench_ret')}</td><td>{s('sig3_eq')}</td><td>{p('sig3_ret')}</td>"
            f"<td class='{cls}'>{s('sig5_eq')}</td><td>{p('sig5_ret')}</td>"
            f"<td>{v['sig3_n']}/{v['sig5_n']}</td></tr>"
        )
    return out

data = {
    "ym": xym, "p3": p3, "p5": p5,
    "mark3": [[e["entry"], e["pct"]] for e in ev["3y"]],
    "mark5": [[e["entry"], e["pct"]] for e in ev["5y"]],
    "years": [v["year"] for v in yearly],
    "bench": [v["bench_eq"] for v in yearly],
    "sig3": [v["sig3_eq"] for v in yearly],
    "sig5": [v["sig5_eq"] for v in yearly],
    "labels5": [f"#{e['no']} {e['entry']}" for e in ev["5y"]],
    "fwd12_5": [e["fwd"].get("12") for e in ev["5y"]],
    "fwd12_3": [e["fwd"].get("12") for e in ev["3y"]],
    "uncond12": meta["unconditional_fwd"]["12"],
    "comp": ["持有至今", "首次80%卖出", "首次90%卖出"],
    "comp3": [summ["3y"]["avg_now"], summ["3y"]["avg_exit80"], summ["3y"]["avg_exit90"]],
    "comp5": [summ["5y"]["avg_now"], summ["5y"]["avg_exit80"], summ["5y"]["avg_exit90"]],
}
D = json.dumps(data, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>沪深300 PE≤20% 买入机会事件研究</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--ink:#0f172a;--ink2:#475569;--mut:#94a3b8;--line:#e2e8f0;--bg:#f7f8fa;--card:#fff;--up:#c62828;--down:#1b7f4e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:26px;margin:0 0 10px;line-height:1.35;letter-spacing:-.3px}
h2{font-size:18px;margin:34px 0 12px;padding-left:11px;border-left:4px solid #1e293b}
h3{font-size:14.5px;margin:20px 0 6px;color:var(--ink2)}
.sub-t{color:var(--ink2);font-size:13.5px;margin-bottom:6px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:16px 0}
.verdict{background:#fff;border:1px solid var(--line);border-left:4px solid #c62828;border-radius:10px;padding:18px 22px;margin:18px 0}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px 16px}
.kpi .k{font-size:12.5px;color:var(--mut)} .kpi .v{font-size:22px;font-weight:700;margin:3px 0;letter-spacing:-.4px}
.kpi .d{font-size:12px;color:var(--ink2)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
th,td{padding:8px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{background:#f8fafc;color:var(--ink2);font-size:11.5px;font-weight:600}
th.nm,td.nm{text-align:left;font-weight:600}
tbody tr:hover{background:#fcfdff}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.note{font-size:12px;color:var(--mut);margin-top:7px}
.chart{width:100%;height:360px}
.sm{font-size:11.5px;color:var(--ink2)}
ul{padding-left:20px;margin:8px 0} li{margin:6px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">沪深300（000300） · __PERIOD__ · 数据源 val_index_pe_lg（PE-TTM 加权）</div>
<h1>2019 年以来，PE≤20% 的买入机会有多少次？买了拿到今天，每年比大盘强多少？</h1>

<div class="verdict">
<b>机会数</b>：3 年 PE 分位 ≤20% 共 <b>9 次</b>独立机会（21 个月）；5 年 PE ≤20% 共 <b>7 次</b>（20 个月）。连续低于 20% 的月份合并算一次。<br>
<b>只买不卖，结果是失败的</b>：在这些时点各投 1 元持有到今天，3 年平均只赚 <b class="c-down">+4.7%</b>、5 年 <b class="c-down">+3.7%</b>（累计，非年化），而 2019-01 买入大盘拿到今天是 <b class="c-up">+23.5%</b>。9 次里有 3 次亏损。原因：2022-2023 年 PE 分位持续低于 20%，信号在下跌途中反复触发，属于"越买越套"。<br>
<b>收益几乎全部来自卖出纪律</b>：同样在这些时点买入、但首次分位回到 80% 就卖出，3 年平均 <b class="c-up">+14.6%</b>（平均 17.3 个月）、5 年 <b class="c-up">+22.4%</b>（平均 25.9 个月）。5 年口径卖在 90% 还能再好一点（+23.1%）。<br>
<b>对"周期性大盘"的含义</b>：沪深300 不是长期成长盘，择时的价值不在"找到便宜买点"，而在"贵了必须走"。买入信号只提供微弱优势（12 个月前瞻收益 3 年 7.1%、5 年 5.4%，无条件平均 4.15%），但胜率仅 56% / 43%，单靠入场择时不足以稳定跑赢。
</div>

<div class="grid">
  <div class="kpi"><div class="k">3 年窗口机会</div><div class="v">9 次</div><div class="d">21 个月处于 20% 以下</div></div>
  <div class="kpi"><div class="k">5 年窗口机会</div><div class="v">7 次</div><div class="d">20 个月处于 20% 以下</div></div>
  <div class="kpi"><div class="k">买入后持有至今</div><div class="v c-down">+4.7%</div><div class="d">3 年窗口平均累计</div></div>
  <div class="kpi" style="border-color:#fecaca"><div class="k">首破 80% 卖出</div><div class="v c-up">+22.4%</div><div class="d">5 年窗口平均累计</div></div>
</div>

<h2>一、什么时候出现了 20% 买入机会</h2>
<div class="card"><div id="sig" class="chart" style="height:390px"></div>
<div class="note">折线＝滚动 PE 分位；圆点＝独立买入机会的首次触发月。3 年 / 5 年分别画在两条线上。</div></div>
<p>两类机会高度重叠：2020-03、2022-04、2022-07、2023-05、2023-08 这五次两边同时触发。区别在于 3 年窗口多抓了 2019 年的三次（2019-01 / 05 / 11）和 2023-02，5 年窗口多抓了 2024-08。3 年窗口反应更快、机会更多；5 年窗口更严格、噪声更少。</p>

<h2>二、每次机会买入后，逐年发生了什么</h2>
<div class="card"><h3>5 年窗口：7 次机会的前瞻收益</h3><table>
<thead><tr><th class="nm">机会</th><th>买入月</th><th>结束月</th><th>月数</th><th>PE</th><th>分位</th><th>收盘</th><th>+12月</th><th>+24月</th><th>+36月</th><th>至今</th><th>80%卖</th><th>90%卖</th></tr></thead>
<tbody>__EV5__</tbody></table></div>
<div class="card"><h3>3 年窗口：9 次机会</h3><table>
<thead><tr><th class="nm">机会</th><th>买入月</th><th>结束月</th><th>月数</th><th>PE</th><th>分位</th><th>收盘</th><th>+12月</th><th>+24月</th><th>+36月</th><th>至今</th><th>80%卖</th><th>90%卖</th></tr></thead>
<tbody>__EV3__</tbody></table>
<div class="note">"80%卖 / 90%卖"＝买入后首次分位回到该阈值时离场的收益与持有月数；"至今"＝持有到 2026-11。</div></div>

<div class="card"><div id="fw" class="chart"></div>
<div class="note">5 年窗口 7 次机会的 +12 月收益。红色虚线为全样本无条件平均 +4.15%（任意月份买入的 12 个月平均收益）。</div></div>
<p>最成功的两次是 <b>2020-03</b>（12 个月 +37.0%）和 <b>2024-08</b>（+35.4%），共同点是指数刚经历急跌、PE 快速压缩到 10.9 倍附近。最差的是 <b>2023-02</b>（-13.6%），当时 PE 也低，但企业盈利在下滑，低估值只是"价值陷阱"的起点。可见<b>低分位本身不足以判定买点</b>。</p>

<h2>三、每年对比大盘：涨幅差距怎么变</h2>
<div class="card"><div id="eq" class="chart"></div>
<div class="note">基准＝2019-01 投入 1 元买入沪深300 并持有；信号净值＝每次 20% 机会各投 1 元，按已出现信号数取平均。2024 年后没有新信号，两条线的年度涨跌完全一致，差距不再变化。</div></div>
<div class="card"><table>
<thead><tr><th class="nm">年份</th><th>月末</th><th>大盘净值</th><th>大盘当年</th><th>3y信号净值</th><th>3y当年</th><th>5y信号净值</th><th>5y当年</th><th>累计信号数 3y/5y</th></tr></thead>
<tbody>__YR__</tbody></table></div>
<p>2019 年末大盘 +28.0%，3 年信号组合只有 +15.9%——因为它在 2019-05 和 2019-11 又追加了两次，买在了更高的位置。2022-2023 年信号持续触发，净值被一路摊薄到 0.878~0.909，而大盘还有 1.072。到 2026-11，大盘净值 1.235，信号组合只有 1.047 / 1.037。<b>差距是在 2019-2023 的"反复买入"中拉开的，不是在 2024 年之后的持有阶段。</b></p>

<h2>四、买入 vs 卖出：哪个更重要</h2>
<div class="card"><div id="cmp" class="chart"></div>
<div class="note">同一批 20% 买入机会，三种退出方式的平均累计收益。</div></div>
<p>结论非常清楚：<b>买入时点只贡献微弱优势，卖出时点决定成败</b>。5 年窗口从"持有至今 +3.7%"变成"首次 80% 卖出 +22.4%"，差 18.7 个百分点；3 年从 +4.7% 到 +14.6%，差 9.9 个百分点。这也解释了为什么之前的完整回测里，20/80 规则能做到年化 4.61%~4.99%，而单纯的低 PE 买入做不到。</p>

<h2>五、对"稳定性前提下追求最大收益"的回答</h2>
<div class="card"><ul>
<li><b>买入侧：20% 是合理阈值，但需要过滤。</b>3 年窗口 12 个月前瞻收益 7.1%、5 年 5.4%，都高于无条件平均 4.15%，但胜率只有 56% / 43%。建议把"第一次跌破 20%"当作机会，而非每次跌破都买——连续下跌途中的重复信号（2022-07~12、2023-08~2024-01）是主要亏损来源。</li>
<li><b>卖出侧：80% 是必须执行的纪律。</b>没有卖出规则，低 PE 买入在沪深300 上几乎没有意义；有卖出规则，同样的买点平均收益提升 10~19 个百分点。5 年窗口可放宽到 85%~90%，3 年窗口 80% 已经够好。</li>
<li><b>沪深300 的周期性要这样用</b>：它长期不涨（2019-01 到 2026-11 年化仅 2.73%），但波动巨大（2019-2020 两年 +62%，2021-2023 三年 -30%）。这种形态下，择时收益来自"高位不持有"，不是"低位精准抄底"。</li>
<li><b>不要追求"每次都买在最低"</b>。9 次机会中最深的 5.6% 分位（2022-04）12 个月只赚 0.3%；而 11.7% 分位的 2020-03 赚 37%。深度分位不等于好收益。</li>
</ul></div>

<div class="dis" style="margin-top:22px">
<b>免责声明</b>：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。
</div>
<div class="note">数据源：本地 SQLite <code>data/ashare.db</code> → <code>val_index_pe_lg</code>（2019-01~2026-11-20）· 脚本 <code>scripts/backtest_pe_entry_events.py</code> · 生成 2026-11-23 · 不含股息、单边成本未计入事件收益</div>

</div>
<script>
var D = __DATA__;
echarts.init(document.getElementById('sig')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['3年分位','5年分位','3年买入信号','5年买入信号'], top: 0 },
  grid: { left: 52, right: 22, top: 44, bottom: 32 },
  xAxis: { type: 'category', data: D.ym, axisLabel: { interval: 11 } },
  yAxis: { type: 'value', name: '分位 %', min: 0, max: 100 },
  series: [
    { name: '3年分位', type: 'line', data: D.p3, symbol: 'none', lineStyle: { width: 1.2, color: '#93c5fd' },
      markLine: { silent: true, symbol: 'none', label: { formatter: '20%', fontSize: 10, position: 'end' },
        lineStyle: { color: '#cbd5e1', type: 'dashed' }, data: [{ yAxis: 20 }] } },
    { name: '5年分位', type: 'line', data: D.p5, symbol: 'none', lineStyle: { width: 2, color: '#c62828' } },
    { name: '3年买入信号', type: 'scatter', data: D.mark3, symbolSize: 11, itemStyle: { color: '#2563eb' } },
    { name: '5年买入信号', type: 'scatter', data: D.mark5, symbolSize: 14, symbol: 'diamond', itemStyle: { color: '#c62828' } }
  ]
});

echarts.init(document.getElementById('fw')).setOption({
  tooltip: { trigger: 'axis' },
  grid: { left: 52, right: 20, top: 20, bottom: 74 },
  xAxis: { type: 'category', data: D.labels5, axisLabel: { rotate: 30, fontSize: 10 } },
  yAxis: { type: 'value', name: '+12月收益 %' },
  series: [{ type: 'bar', data: D.fwd12_5,
    itemStyle: { color: function(p){ return p.value >= 0 ? '#c62828' : '#1b7f4e'; } },
    markLine: { silent: true, symbol: 'none',
      data: [{ yAxis: D.uncond12, lineStyle: { color: '#475569', type: 'dashed' },
        label: { formatter: '无条件均值 4.15%', fontSize: 10, position: 'end' } }] } }]
});

echarts.init(document.getElementById('eq')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['大盘(2019-01投入)','3年信号平均','5年信号平均'], top: 0 },
  grid: { left: 52, right: 20, top: 44, bottom: 32 },
  xAxis: { type: 'category', data: D.years },
  yAxis: { type: 'value', name: '净值' },
  series: [
    { name: '大盘(2019-01投入)', type: 'line', data: D.bench, symbol: 'circle', symbolSize: 7,
      lineStyle: { width: 2.6, color: '#0f172a' }, itemStyle: { color: '#0f172a' } },
    { name: '3年信号平均', type: 'line', data: D.sig3, symbol: 'circle', symbolSize: 6,
      lineStyle: { width: 2, color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
    { name: '5年信号平均', type: 'line', data: D.sig5, symbol: 'circle', symbolSize: 6,
      lineStyle: { width: 2, color: '#c62828' }, itemStyle: { color: '#c62828' } }
  ]
});

echarts.init(document.getElementById('cmp')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['3年窗口','5年窗口'], top: 0 },
  grid: { left: 52, right: 20, top: 44, bottom: 32 },
  xAxis: { type: 'category', data: D.comp },
  yAxis: { type: 'value', name: '平均累计收益 %' },
  series: [
    { name: '3年窗口', type: 'bar', data: D.comp3, itemStyle: { color: '#93c5fd' },
      label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11 } },
    { name: '5年窗口', type: 'bar', data: D.comp5, itemStyle: { color: '#c62828' },
      label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11 } }
  ]
});

window.addEventListener('resize', function(){
  ['sig','fw','eq','cmp'].forEach(function(id){
    var el = document.getElementById(id);
    if (el) { var c = echarts.getInstanceByDom(el); if (c) c.resize(); }
  });
});
</script>
</body></html>"""

html = (HTML.replace("__PERIOD__", meta["period"])
        .replace("__EV5__", ev_rows("5")).replace("__EV3__", ev_rows("3"))
        .replace("__YR__", yr_rows()).replace("__DATA__", D))
open(OUT, "w", encoding="utf-8").write(html)
print("written", OUT, len(html))
