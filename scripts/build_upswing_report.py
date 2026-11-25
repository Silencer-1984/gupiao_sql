# -*- coding: utf-8 -*-
"""生成 6 上升波段因子验证报告。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "upswing_factor_report.html")
U = json.load(open(os.path.join(ROOT, "data", "upswing_analysis.json"), encoding="utf-8"))
S = json.load(open(os.path.join(ROOT, "data", "upswing_signals.json"), encoding="utf-8"))


def seg_rows():
    out = ""
    for s in S["segments"]:
        out += (f"<tr><td class='nm'>{s['id']}</td><td>{s['date']}</td><td>{s['end']}</td>"
                f"<td>{s['days']}</td><td class='c-up'>+{s['ret']:.2f}%</td>"
                f"<td>{s['erp']:.2f}</td><td>{s['ma60_dev']:+.1f}%</td>"
                f"<td>{s['down_streak']}</td><td>{s['margin_chg20']:+.1f}%</td>"
                f"<td>{s['pe_pct5y']:.1f}%</td></tr>")
    return out


def single_rows():
    out = ""
    b = S["bench"]
    for k, v in S["singles"].items():
        good = v["fwd60"] and v["fwd60"] > b["fwd60"] + 2
        bad = v["fwd60"] and v["fwd60"] < b["fwd60"]
        cls = "c-up" if good else ("c-down" if bad else "")
        out += (f"<tr><td class='nm {cls}'>{v['label']}</td><td>{v['n_clusters']}</td>"
                f"<td class='{cls}'>{v['fwd60']:+.2f}%</td>"
                f"<td>{v['win60']:.1f}%</td><td>{v['fwd120']:+.2f}%</td>"
                f"<td>{v['win120']:.1f}%</td></tr>")
    out += (f"<tr><td class='nm'><b>全样本基准</b></td><td>—</td>"
            f"<td><b>{b['fwd60']:+.2f}%</b></td><td>{b['win60']:.1f}%</td>"
            f"<td>{b['fwd120']:+.2f}%</td><td>{b['win120']:.1f}%</td></tr>")
    return out


def combo_rows():
    out = ""
    for k, v in S["combos"].items():
        cls = "c-up" if v["unique_fwd60"] and v["unique_fwd60"] > 8 else ""
        out += (f"<tr><td class='nm {cls}'>{k}</td><td>{v['n_cluster']}</td><td>{v['n_unique']}</td>"
                f"<td class='{cls}'>{v['unique_fwd60']:+.2f}%</td>"
                f"<td>{v['unique_win60']:.1f}%</td><td>{v['unique_fwd120']:+.2f}%</td></tr>")
    return out


def factor_rows():
    out = ""
    rank = sorted([(v["consistency"], k, v) for k, v in U["factors"].items()
                   if v["consistency"] is not None], reverse=True)
    for score, k, v in rank[:20]:
        pcts = " ".join(f"<span class='pill'>{p:.0f}</span>" if p is not None
                        else "<span class='pill'>—</span>" for p in v["pcts"])
        out += (f"<tr><td class='nm'>{v['label']}</td><td>{score:.1f}</td>"
                f"<td class='sm'>{pcts}</td>"
                f"<td>{v['base_median']}</td></tr>")
    return out


D = {
    "seg_names": [s["id"] for s in S["segments"]],
    "seg_ret": [s["ret"] for s in S["segments"]],
    "seg_erp": [s["erp"] for s in S["segments"]],
    "seg_ma": [s["ma60_dev"] for s in S["segments"]],
    "single_labels": [v["label"] for v in S["singles"].values()],
    "single_fwd": [v["fwd60"] for v in S["singles"].values()],
    "bench60": S["bench"]["fwd60"],
    "combo_labels": list(S["combos"].keys()),
    "combo_fwd": [v["unique_fwd60"] for v in S["combos"].values()],
    "combo_win": [v["unique_win60"] for v in S["combos"].values()],
    "mc": S["mc"],
}

HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>6 个上升波段的因子验证</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--ink:#0f172a;--ink2:#475569;--mut:#94a3b8;--line:#e2e8f0;--bg:#f7f8fa;--card:#fff;--up:#c62828;--down:#1b7f4e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:26px;margin:0 0 10px;line-height:1.35}
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
th.nm,td.nm{text-align:left;font-weight:600} td.sm{text-align:left;font-size:11.5px;color:var(--ink2)}
.pill{display:inline-block;min-width:24px;text-align:center;background:#f1f5f9;border-radius:4px;padding:1px 4px;margin:0 1px;font-size:11px}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.note{font-size:12px;color:var(--mut);margin-top:7px}
.chart{width:100%;height:350px}
ul{padding-left:20px;margin:8px 0} li{margin:6px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:880px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">沪深300（000300） · 日频因子 · 波段由用户从 K 线识别，本页做验证与归因</div>
<h1>6 个上升波段的因子验证：什么真正促成了上涨</h1>

<div class="verdict">
<b>一、6 个波段全部真实。</b>涨幅 +11.28%~+29.91%，持续 34~242 个交易日；其中 D（2024-09）最强 +29.91%。<br>
<b>二、起点的共性不是"低估值"，而是"急跌超跌"。</b>6 个起点 MA60 偏离全在 -4.7%~-10.9%（历史 1~15% 分位），连跌 1~3 天，两融 20 日全部下降。但 PE 分位分化极大：A~D 仅 0.3%~9.5%，E 已 42.2%、F 高达 70.6%。<br>
<b>三、单因子检验里 ERP 是唯一稳定有效的。</b>ERP≥6.0 的未来 60 日 +5.04%、胜率 68.2%（基准 +1.11%）；而"破 MA60 深"单用只有 +1.02%，"股息差≥1.0"甚至 -0.17%，"QVIX 恐慌分位≥60"也只有 +2.57%。<br>
<b>四、组合信号很强，但不能当独立验证。</b>"ERP≥6.0 + 破 MA60 + 连跌 + 两融降"去重后 8 个事件，60 日均值 <b class="c-up">+13.47%</b>、胜率 100%，随机模拟 p=0.000。但这些条件是从你给的 6 个波段倒推出来的，8 个事件又集中在 6 段行情里——<b>属于描述性发现，不是可交易的验证结论</b>。
</div>

<div class="grid">
  <div class="kpi"><div class="k">波段平均涨幅</div><div class="v c-up">+19.3%</div><div class="d">6 段，34~242 交易日</div></div>
  <div class="kpi"><div class="k">起点 MA60 偏离</div><div class="v">-7.4%</div><div class="d">全在历史最低 15% 分位</div></div>
  <div class="kpi"><div class="k">起点 ERP 范围</div><div class="v">5.42~7.40</div><div class="d">A/F 低于 6.0 门槛</div></div>
  <div class="kpi"><div class="k">四条件 60 日</div><div class="v c-up">+13.47%</div><div class="d">8 独立事件 · 随机 p=0</div></div>
</div>

<h2>一、波段验证与起点快照</h2>
<div class="card"><table>
<thead><tr><th class="nm">波段</th><th>起点</th><th>终点</th><th>交易日</th><th>涨幅</th><th>ERP</th><th>MA60偏离</th><th>连跌日</th><th>两融20日</th><th>PE5y分位</th></tr></thead>
<tbody>__SEG__</tbody></table>
<div class="note">起点取当日或之前最近交易日。PE 用日频 <code>px_index_daily_csi.pe_ttm</code>，与月频 <code>val_index_pe_lg</code> 加权口径不同，分位数值不可直接比较。A（2022-05）与 F（2026-04）的 ERP 仅 5.59 / 5.42，不满足此前策略 6.5 门槛——这两段是"急跌反弹"，不是"价值买点"。</div></div>

<div class="card"><div class="two">
  <div><h3>六段涨幅</h3><div id="seg" class="chart" style="height:320px"></div></div>
  <div><h3>起点 ERP 与 MA60 偏离</h3><div id="scatter" class="chart" style="height:320px"></div></div>
</div></div>

<h2>二、起点因子在历史中的位置</h2>
<p>把每个起点的因子值放到 2016 年以来全样本中算分位。一致度＝6 个起点向假设方向靠拢的平均程度（100 为完全一致）。</p>
<div class="card"><table>
<thead><tr><th class="nm">因子</th><th>一致度</th><th class="nm">6 起点分位（%）</th><th>全样本中位</th></tr></thead>
<tbody>__FACTOR__</tbody></table>
<div class="note">分位数字越小＝越低于历史常态（对"偏低"类因子越好）。均线偏离与短期动量一致度最高（91~92），其次是连跌天数（89.7）与 ERP（88.2）。宏观因子（M1/PMI/社融）没有一致性，成交量也没有。</div></div>

<h2>三、单因子真的能促涨吗</h2>
<div class="card"><table>
<thead><tr><th class="nm">条件（事件簇去重）</th><th>簇数</th><th>未来60日</th><th>胜率</th><th>未来120日</th><th>胜率</th></tr></thead>
<tbody>__SINGLE__</tbody></table></div>
<div class="card"><div id="single" class="chart"></div>
<div class="note">红色＝优于基准，绿色＝劣于基准。事件簇：连续满足算一次，避免重叠日重复计数。</div></div>

<p>三个反直觉结论：</p>
<ul>
<li><b>"急跌"本身不值钱。</b>MA60 偏离≤-5% 有 57 簇，未来 60 日仅 +1.02%，几乎等同基准 +1.11%；MA20 偏离≤-3% 更是 -1.06%。你找的 6 个起点都符合"急跌"，但全市场急跌 57 次里大多数没有变成上升波段。</li>
<li><b>恐慌度不是买点信号。</b>QVIX 恐慌分位≥60 未来 60 日 +2.57%，恐慌度≥55 为 +3.76%，都远不如 ERP；此前月频研究也显示恐慌度只在高分位后跑输。恐慌是结果，不是原因。</li>
<li><b>股息率−国债再次失效。</b>≥1.0pp 的未来 60 日 -0.17%、胜率 42.9%。这与上一份低利率报告的结论一致：该利差在低利率时代失去区分度。</li>
</ul>

<h2>四、组合信号：强，但要打折看</h2>
<div class="card"><table>
<thead><tr><th class="nm">组合</th><th>原始簇</th><th>30日去重簇</th><th>60日均值</th><th>胜率</th><th>120日均值</th></tr></thead>
<tbody>__COMBO__</tbody></table></div>
<div class="card"><div id="combo" class="chart" style="height:340px"></div></div>

<p>四条件去重后 8 个事件：2016-01-28(+10.6%)、2018-12-26(+29.0%)、2022-10-10(+4.5%)、2024-01-08(+6.6%)、2024-08-05(+20.4%)、2024-09-09(+24.9%)、2025-01-10(+0.8%)、2025-04-07(+10.9%)。随机抽 8 个间隔≥30 日的日期，2000 次模拟的 60 日均值中位仅 +1.01%、P99 为 +8.5%，观测 +13.47% 的 p 值为 0.000。</p>
<div class="card"><b>但这不能当作策略验证：</b>
<ul>
<li>四条件是从你给的 6 个起点倒推的，存在数据窥探偏差；换一批波段，最一致的因子可能完全不同。</li>
<li>8 个事件落在 6 段行情里，2018 与 2024 各贡献两次，实际独立样本更少。</li>
<li>A、F 两段不满足 ERP 条件，四条件只解释了 6 段中的 3 段——它<b>没有覆盖你找到的全部上升点</b>。</li>
<li>2026-10 之后还有 5 个新信号，但 60 日尚未走完，未纳入统计。</li>
</ul></div>

<h2>五、可以怎么用</h2>
<div class="card">
<ul>
<li><b>把"急跌"当入场时机，把 ERP 当准入资格。</b>两者单用都弱：急跌 57 簇 60 日 +1.02%，ERP≥6.0 有 24 簇 +5.04%；叠加后 13 簇 +10.14%、胜率 91.7%。这是本次检验里最稳的增量。</li>
<li><b>不要加恐慌度和股息率差。</b>两者在 2016-2026 的前瞻收益都不如基准，与"恐慌买入""高股息买入"的直觉相反。</li>
<li><b>接受有些波段抓不到。</b>2022-05 与 2026-04 两段 ERP 只有 5.59/5.42，按价值标准不该买。想抓这类反弹需要另一套逻辑（趋势/政策），不能用估值框架强行解释。</li>
<li><b>当前信号：</b>2026-11-13 四条件再次触发，但 ERP 已回落、60 日窗口尚未走完。按既有策略（5 年 PE 分位 76.7%、ERP 6.27）仍不满足买入。</li>
</ul></div>

<div class="dis"><b>免责声明</b>：本报告为历史数据的描述性统计与因子探索，不构成投资建议。样本量极小且条件由样本反推，存在过拟合风险。市场有风险，投资需谨慎。过往表现不预示未来收益。</div>

</div><script>
const D=__DATA__;
const C={up:'#c62828',down:'#1b7f4e',mut:'#94a3b8',line:'#e2e8f0'};
const base={textStyle:{fontFamily:'-apple-system,PingFang SC,Microsoft YaHei,sans-serif'},
  grid:{left:52,right:26,top:36,bottom:46},tooltip:{trigger:'axis',backgroundColor:'#fff',borderColor:C.line}};
echarts.init(document.getElementById('seg')).setOption({...base,
  xAxis:{type:'category',data:D.seg_names},yAxis:{type:'value',name:'涨幅 %'},
  series:[{type:'bar',data:D.seg_ret.map(v=>({value:v,itemStyle:{color:C.up}})),
    label:{show:true,position:'top',fontSize:11,formatter:p=>p.value.toFixed(1)+'%'}}]});
echarts.init(document.getElementById('scatter')).setOption({...base,
  xAxis:{type:'value',name:'MA60 偏离 %',min:-12,max:0},
  yAxis:{type:'value',name:'ERP',min:5,max:8},
  series:[{type:'scatter',symbolSize:18,data:D.seg_names.map((n,i)=>[D.seg_ma[i],D.seg_erp[i]]),
    itemStyle:{color:C.up},label:{show:true,formatter:p=>D.seg_names[p.dataIndex],position:'top',fontSize:11}}]});
echarts.init(document.getElementById('single')).setOption({...base,
  grid:{left:150,right:40,top:16,bottom:36},
  xAxis:{type:'value',name:'未来60日 %'},
  yAxis:{type:'category',data:D.single_labels.slice().reverse(),axisLabel:{fontSize:10}},
  series:[{type:'bar',data:D.single_fwd.slice().reverse().map(v=>({value:v,
    itemStyle:{color:v>D.bench60?C.up:C.down}})),
    label:{show:true,position:'right',fontSize:10,formatter:p=>p.value.toFixed(1)},
    markLine:{silent:true,symbol:'none',lineStyle:{color:'#0f172a',type:'dashed'},
      label:{formatter:'基准',fontSize:10},data:[{xAxis:D.bench60}]}}]});
echarts.init(document.getElementById('combo')).setOption({...base,
  grid:{left:170,right:50,top:16,bottom:36},
  xAxis:{type:'value',name:'60日均值 %'},
  yAxis:{type:'category',data:D.combo_labels.slice().reverse(),axisLabel:{fontSize:10}},
  series:[{type:'bar',data:D.combo_fwd.slice().reverse().map((v,i)=>({value:v,
    itemStyle:{color:v>8?C.up:(v>3?'#f59e0b':C.down)}})),
    label:{show:true,position:'right',fontSize:10,formatter:p=>p.value.toFixed(1)+'%'}}]});
</script></html>'''

rep = {"SEG": seg_rows(), "FACTOR": factor_rows(), "SINGLE": single_rows(), "COMBO": combo_rows()}
for k, v in rep.items():
    HTML = HTML.replace("__" + k + "__", v)
HTML = HTML.replace("__DATA__", json.dumps(D, ensure_ascii=False))
with open(OUT, "w", encoding="utf-8") as fp:
    fp.write(HTML)
print("written", OUT, len(HTML))
