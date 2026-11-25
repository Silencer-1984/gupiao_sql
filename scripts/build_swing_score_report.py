# -*- coding: utf-8 -*-
"""生成 6 波段起点/终点打分对比报告。"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "swing_scores.json"), encoding="utf-8"))
M, S, ROWS = R["meta"], R["summary"], R["rows"]

INS = [x for x in ROWS if x["tag"] == "IN"]
OUTS = [x for x in ROWS if x["tag"] == "OUT"]
LAB = {"A": "A 2022-05", "B": "B 2022-10", "C": "C 2024-02",
       "D": "D 2024-09", "E": "E 2025-01", "F": "F 2026-04"}


def score_cls(v):
    return "c-up" if v >= 60 else ("c-down" if v < 30 else "")


def dec_cls(d):
    return "c-up" if "买入" in d else ("c-down" if "不买" in d else "")


def table_rows(group):
    out = ""
    for x in group:
        p = x["parts"]
        out += (
            f"<tr><td class='nm'>{LAB[x['seg']]}</td><td>{x['date']}</td>"
            f"<td class='{score_cls(x['score'])}' style='font-weight:700'>{x['score']:.0f}</td>"
            f"<td class='{dec_cls(x['decision'])}'>{x['decision']}</td>"
            f"<td>{p['ERP']:.0f}/{p['PE分位']:.0f}/{p['MA60偏离']:.0f}/{p['连跌两融']:.0f}/{p['回撤']:.0f}</td>"
            f"<td>{x['erp']:+.2f}</td><td>{x['pe_pct5y']:.1f}%</td>"
            f"<td>{x['ma60_dev']:+.1f}%</td><td>{x['down_streak']}</td>"
            f"<td>{'—' if x['margin_chg20'] is None else format(x['margin_chg20'],'+.1f')+'%'}</td>"
            f"<td>{'✓' if x['hard_buy'] else '—'}</td><td>{'✓' if x['hard_sell'] else '—'}</td></tr>"
        )
    return out


DATA = {
    "labels": [LAB[x["seg"]] for x in INS],
    "in": [x["score"] for x in INS],
    "out": [x["score"] for x in OUTS],
    "parts_in": {
        k: [x["parts"][k] for x in INS] for k in ["ERP", "PE分位", "MA60偏离", "连跌两融", "回撤"]
    },
    "parts_out": {
        k: [x["parts"][k] for x in OUTS] for k in ["ERP", "PE分位", "MA60偏离", "连跌两融", "回撤"]
    },
    "in_mean": S["in_mean"], "out_mean": S["out_mean"],
}
DJ = json.dumps(DATA, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>沪深300 六波段起点/终点买入推荐度打分</title>
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
table{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0}
th,td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{background:#f8fafc;color:var(--ink2);font-size:11px;font-weight:600}
th.nm,td.nm{text-align:left;font-weight:600}
tbody tr:hover{background:#fcfdff}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.note{font-size:12px;color:var(--mut);margin-top:7px}
.chart{width:100%;height:360px}
ul{padding-left:20px;margin:8px 0} li{margin:6px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:880px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">沪深300 · 用户从 K 线识别的 6 个上升波段 · 日频因子 · 打分口径 0~100（越高越该买）</div>
<h1>把 6 个波段的起点与终点带入模型：推荐度打分</h1>

<div class="verdict">
<b>模型给出明确区分：起点均分 <span class="c-up">__INM__</span>，终点均分 <span class="c-down">__OUTM__</span>，相差 __GAP__ 分。</b><br>
6 个起点中 <b>4 个</b>达到"建议买入"以上（≥60 分），其中 <b>3 个</b>同时满足严格闸门（5y PE 分位≤20% 且 ERP≥6.5）；
A（2022-05）和 F（2026-04）虽被打分模型判为"强烈买入/接近买入"，但 <b>ERP 不达标、按严格策略仍不该买</b>。<br>
6 个终点全部落在"不买/接近卖出区"（≤24 分），其中 E、F 终点触发卖出闸门（5y 分位≥80%）。<b>打分模型能识别"该走"，但卖出信号普遍滞后于价格高点。</b>
</div>

<div class="grid">
  <div class="kpi"><div class="k">起点平均推荐度</div><div class="v c-up">__INM__</div><div class="d">满分100 · 4/6 ≥60</div></div>
  <div class="kpi"><div class="k">终点平均推荐度</div><div class="v c-down">__OUTM__</div><div class="d">6/6 &lt;30</div></div>
  <div class="kpi"><div class="k">起点严格闸门通过</div><div class="v">__INHARD__/6</div><div class="d">B / C / D</div></div>
  <div class="kpi"><div class="k">终点卖出闸门触发</div><div class="v">__OUTSELL__/6</div><div class="d">E / F（分位≥80%）</div></div>
</div>

<h2>一、打分卡构成</h2>
<div class="card">
<p style="margin:0 0 8px">只用前面研究里<b>通过检验</b>的因子；已证伪因子（恐慌度、股息率−国债、M1、拥挤度、隐含 EPS 增速）全部剔除。权重为研究者设定，<b>不是统计拟合出来的</b>——这是可解释评分卡，不是预测模型。</p>
<table><thead><tr><th class="nm">维度</th><th>满分</th><th class="nm">打分逻辑</th><th class="nm">依据</th></tr></thead><tbody>
<tr><td class="nm">ERP 股债性价比</td><td>35</td><td class="nm">≥7.0→35，6.5~7→30，6.0~6.5→18，5.5~6→10，&lt;5.5→0</td><td class="nm">全历史三样本唯一稳定有效因子</td></tr>
<tr><td class="nm">5y PE 分位</td><td>25</td><td class="nm">≤20%→25，20~40→16，40~60→9，60~80→3，≥80→0</td><td class="nm">高位保护；10年窗口被泡沫污染故不用</td></tr>
<tr><td class="nm">MA60 偏离</td><td>20</td><td class="nm">≤-8%→20，-8~-5→15，-5~-3→10，-3~0→5，&gt;0→0</td><td class="nm">6 波段起点一致性最高的因子（92.0）</td></tr>
<tr><td class="nm">连跌 + 两融降</td><td>10</td><td class="nm">两者都满足→10，其一→5，都不满足→0</td><td class="nm">波段组合信号，四条件去重后 60 日 +13.5%</td></tr>
<tr><td class="nm">60 日回撤</td><td>10</td><td class="nm">≤-12%→10，-12~-8→7，-8~-4→4，&gt;-4→0</td><td class="nm">位置确认</td></tr>
</tbody></table>
<div class="note">决策带：≥75 强烈建议买入 / 60~74 建议买入 / 45~59 观望小仓 / 30~44 持有不加仓 / &lt;30 不买接近卖出区。严格闸门另行列示，不与打分混用。</div>
</div>

<h2>二、起点 vs 终点：推荐度对比</h2>
<div class="card"><div id="c1" class="chart"></div>
<div class="note">红线＝买入推荐线（60）。起点普遍在线上、终点全部在线下。A 起点 75 分但 ERP 仅 5.59；F 起点 27 分——这段"上涨"完全不符合价值买入标准。</div></div>

<h2>三、分项拆解：为什么起点得分高</h2>
<div class="card"><div class="two">
<div><h3>起点分项</h3><div id="c2" class="chart" style="height:330px"></div></div>
<div><h3>终点分项</h3><div id="c3" class="chart" style="height:330px"></div></div>
</div><div class="note">起点得分主要来自 MA60 深跌、60 日回撤和 PE 低分位；ERP 只有 B/C/D 达标。终点的估值与时机分同时归零。</div></div>

<h2>四、逐点明细</h2>
<div class="card"><h3>起点（买入时刻）</h3><table>
<thead><tr><th class="nm">波段</th><th>日期</th><th>总分</th><th class="nm">决策</th><th class="nm">分项(ERP/分位/MA60/连跌/回撤)</th><th>ERP</th><th>5y分位</th><th>MA60偏离</th><th>连跌</th><th>两融20日</th><th>严格买</th><th>严格卖</th></tr></thead>
<tbody>__INROWS__</tbody></table></div>
<div class="card"><h3>终点（卖出时刻）</h3><table>
<thead><tr><th class="nm">波段</th><th>日期</th><th>总分</th><th class="nm">决策</th><th class="nm">分项(ERP/分位/MA60/连跌/回撤)</th><th>ERP</th><th>5y分位</th><th>MA60偏离</th><th>连跌</th><th>两融20日</th><th>严格买</th><th>严格卖</th></tr></thead>
<tbody>__OUTROWS__</tbody></table></div>

<h2>五、怎么解读这张打分表</h2>
<div class="card"><ul>
<li><b>模型能抓住 B / C / D 三次"价值买点"</b>：起点 95 / 87 / 92 分，ERP 6.72 / 7.40 / 7.12，5y 分位 0~6%，四项全达标。这三次也是最干净的低位。</li>
<li><b>A（2022-05）是"急跌反弹"，不是价值买点</b>：75 分全靠 MA60 -9%、回撤 -16%、连跌 2 天撑起来，ERP 只有 5.59。严格闸门拒绝，但事后涨了 14.27%——这是模型必然错过的类型。</li>
<li><b>E（2025-01）59 分是唯一"观望档"起点</b>：ERP 6.45 差 0.05 没过线、5y 分位已 42%。事后涨 27.5% 且持续 242 交易日，是 6 段里第二强——但按价值框架它不该满仓买。</li>
<li><b>F（2026-04）27 分，模型明确拒绝</b>：5y 分位 71%、ERP 5.42，只是 MA60 深跌的技术性反弹。事后仍涨 11.28%。</li>
<li><b>终点全部低分，但卖出信号滞后</b>：A/C/D 终点分位 41%/41%/63%，还没到 80% 卖出线；只有 E、F 终点分位 82%/94% 触发。打分模型比严格闸门更早提示"该走"，但仍跟不上价格顶。</li>
<li><b>核心矛盾再次出现</b>：打分最高的三次（B/C/D）事后涨幅 18.1%/15.1%/29.9%，而模型拒绝的 A/E/F 也涨了 14.3%/27.5%/11.3%。<b>这套模型筛的是"赔率最好的买点"，不是"所有会涨的点"</b>——想抓住后者需要另一套趋势/政策框架。</li>
</ul></div>

<div class="dis">__DISCLAIM__</div>
</div>
<script>
const D=__DATA__;
const UP='#c62828', DOWN='#1b7f4e', INK='#0f172a', MUT='#94a3b8', GRID='#e2e8f0';
function bar(id,series,title,extra){
  const el=document.getElementById(id); if(!el) return;
  const ch=echarts.init(el);
  ch.setOption({
    title:{text:title,left:'center',textStyle:{fontSize:13,color:'#475569'}},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    legend:{bottom:0,textStyle:{fontSize:11}},
    grid:{left:48,right:16,top:36,bottom:44},
    xAxis:{type:'category',data:D.labels,axisLabel:{fontSize:11,color:'#475569'}},
    yAxis:{type:'value',max:100,splitLine:{lineStyle:{color:GRID}},axisLabel:{fontSize:11}},
    series:series
  });
  if(extra) extra(ch);
}
bar('c1',[
  {name:'起点推荐度',type:'bar',data:D.in,itemStyle:{color:UP},label:{show:true,position:'top',fontSize:11},
   markLine:{silent:true,symbol:'none',label:{formatter:'买入线 60',fontSize:10},
     lineStyle:{color:INK,type:'dashed'},data:[{yAxis:60}]}},
  {name:'终点推荐度',type:'bar',data:D.out,itemStyle:{color:DOWN},label:{show:true,position:'top',fontSize:11}}
],'起点 vs 终点：买入推荐度（满分100）');

const KEYS=['ERP','PE分位','MA60偏离','连跌两融','回撤'];
const COL=['#c62828','#ea580c','#0891b2','#7c3aed','#1b7f4e'];
function stack(id,src,title){
  const el=document.getElementById(id); if(!el) return;
  const ch=echarts.init(el);
  ch.setOption({
    title:{text:title,left:'center',textStyle:{fontSize:12.5,color:'#475569'}},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    legend:{bottom:0,textStyle:{fontSize:10}},
    grid:{left:38,right:12,top:34,bottom:46},
    xAxis:{type:'category',data:D.labels,axisLabel:{fontSize:10,color:'#475569'}},
    yAxis:{type:'value',max:100,splitLine:{lineStyle:{color:GRID}},axisLabel:{fontSize:10}},
    series:KEYS.map((k,i)=>({name:k,type:'bar',stack:'s',data:src[k],
      itemStyle:{color:COL[i]}}))
  });
}
stack('c2',D.parts_in,'起点分项堆叠（合计=总分）');
stack('c3',D.parts_out,'终点分项堆叠（合计=总分）');
</script></body></html>
"""

DIS = ("免责声明：以上为基于历史数据的可解释评分卡与描述性统计，权重由研究者设定，"
       "非统计拟合，不构成投资建议。波段由事后 K 线识别，存在选择偏差。市场有风险，投资需谨慎。")

html = (HTML.replace("__INM__", str(S["in_mean"]))
        .replace("__OUTM__", str(S["out_mean"]))
        .replace("__GAP__", str(round(S["in_mean"] - S["out_mean"], 1)))
        .replace("__INHARD__", str(S["in_hard_buy"]))
        .replace("__OUTSELL__", str(S["out_hard_sell"]))
        .replace("__INROWS__", table_rows(INS))
        .replace("__OUTROWS__", table_rows(OUTS))
        .replace("__DATA__", DJ)
        .replace("__DISCLAIM__", DIS))

out = os.path.join(ROOT, "docs", "swing_score_report.html")
with open(out, "w", encoding="utf-8") as fp:
    fp.write(html)
print("written", out, "bytes", len(html))
