# -*- coding: utf-8 -*-
"""生成全历史随机检验报告。"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "longhistory_validation.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "docs", "longhistory_validation_report.html")
S = R["samples"]
NAMES = {"B3": "3y基线", "B5": "5y基线", "E3": "3y+ERP", "E5": "5y+ERP",
         "P3": "3y+ERP分位", "P5": "5y+ERP分位", "F3": "3y+ERP+恐慌", "F5": "5y+ERP+恐慌"}
KEYS = ["B3", "B5", "E3", "E5", "P3", "P5", "F3", "F5"]


def row(k, sn):
    v = S[sn]["rules"].get(k)
    if not v:
        return "<tr><td class='nm'>—</td><td colspan='8' class='sm'>恐慌度无 2015 前数据</td></tr>"
    m, mc, rw = v["metrics"], v["mc"], v["rolling60"]
    rww = sum(x["win"] for x in rw) / len(rw) * 100 if rw else None
    cls = "c-up" if mc["all"] >= 73 else ("c-down" if mc["all"] < 60 else "")
    return (f"<tr><td class='nm'>{NAMES[k]}</td><td class='{cls}'>{m['cagr']:+.2f}%</td>"
            f"<td>{m['max_dd']:+.1f}%</td><td>{m['ntr']}</td><td>{m['tim']:.1f}%</td>"
            f"<td class='{cls}'>{mc['all']:.1f}%</td><td>{mc['win']['12m']:.1f}%</td>"
            f"<td>{mc['win']['36m']:.1f}%</td><td>{mc['win']['60m']:.1f}%</td>"
            f"<td>{'-' if rww is None else format(rww,'.1f')+'%'}</td></tr>")


def table(sn):
    out = ""
    for k in KEYS:
        out += row(k, sn)
    return out


def sub_table():
    out = ""
    for k in ["B3", "B5", "E3", "E5", "F5"]:
        src = "P2015" if k == "F5" else "FULL"
        sub = S[src]["rules"][k]["subperiods"]
        cells = ""
        for p in ["2010-2014", "2015-2018", "2019-2022", "2023-2026"]:
            if p in sub:
                x = sub[p]
                cells += (f"<td>{x['mc']['all']:.0f}% <span class='mut'>/</span> "
                          f"{x['metrics']['cagr']:+.1f}%</td>")
            else:
                cells += "<td class='mut'>—</td>"
        out += f"<tr><td class='nm'>{NAMES[k]}</td>{cells}</tr>"
    return out


def log_table():
    out = ""
    for k in ["B5", "E5"]:
        for t in S["FULL"]["rules"][k]["metrics"]["log"]:
            out += (f"<tr><td class='nm'>{NAMES[k]}</td><td>{t['in']}</td><td>{t['out']}</td>"
                    f"<td>{t['months']} 月</td><td class='c-up'>{t['ret']:+.2f}%</td></tr>")
    return out


data = {
    "ym": R["curves"]["ym"], "bh": R["curves"]["bh"],
    "b5": R["curves"]["B5"], "e5": R["curves"]["E5"], "e3": R["curves"]["E3"],
    "samples": list(S.keys()),
    "hz": ["12m", "24m", "36m", "60m"],
    "b5win": [S[s]["rules"]["B5"]["mc"]["win"][h] for s in S for h in ["12m", "24m", "36m", "60m"]],
    "e5win": [S[s]["rules"]["E5"]["mc"]["win"][h] for s in S for h in ["12m", "24m", "36m", "60m"]],
    "f5win": [S[s]["rules"].get("F5", {}).get("mc", {}).get("win", {}).get(h) for s in S
              for h in ["12m", "24m", "36m", "60m"]],
    "subnames": ["2010-14", "2015-18", "2019-22", "2023-26"],
    "subb5": [S["FULL"]["rules"]["B5"]["subperiods"][p]["mc"]["all"]
              for p in ["2010-2014", "2015-2018", "2019-2022", "2023-2026"]],
    "sube5": [S["FULL"]["rules"]["E5"]["subperiods"][p]["mc"]["all"]
              for p in ["2010-2014", "2015-2018", "2019-2022", "2023-2026"]],
    "subf5": [None] + [S["P2015"]["rules"]["F5"]["subperiods"][p]["mc"]["all"]
                       for p in ["2015-2018", "2019-2022", "2023-2026"]],
}
D = json.dumps(data, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全历史随机检验：策略胜率是否稳健</title>
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
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:16px 0}
.verdict{background:#fff;border:1px solid var(--line);border-left:4px solid #c62828;border-radius:10px;padding:18px 22px;margin:18px 0}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px 16px}
.kpi .k{font-size:12.5px;color:var(--mut)} .kpi .v{font-size:22px;font-weight:700;margin:3px 0;letter-spacing:-.4px}
.kpi .d{font-size:12px;color:var(--ink2)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
th,td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{background:#f8fafc;color:var(--ink2);font-size:11.5px;font-weight:600}
th.nm,td.nm{text-align:left;font-weight:600} .mut{color:var(--mut)}
tbody tr:hover{background:#fcfdff}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.note{font-size:12px;color:var(--mut);margin-top:7px}
.chart{width:100%;height:370px}
ul{padding-left:20px;margin:8px 0} li{margin:6px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:880px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">沪深300 · 月频 2005-04 ~ 2026-11（260 月）· 随机检验样本：2010-06 起 · 3000 组随机起点 × {12,24,36,60} 月 · 单边 5bp</div>
<h1>把策略拉到 20 年：80% 的胜率还在吗？</h1>

<div class="verdict">
<b>结论一：80% 不成立 —— 那是"恐慌度"过滤在 2019+ 样本上的偶然高光。</b>"5y + ERP + 恐慌"在 2019+ 样本随机胜率 79.1%，但样本扩到 2015+ 后只有 <b class="c-down">61.5%</b>，几乎归零。<br>
<b>结论二：ERP 单独过滤才是稳定项。</b>"5y + ERP≥6.5pp"在三个样本里随机胜率 <b class="c-up">75.5% / 75.4% / 74.0%</b>，全历史年化 <b class="c-up">7.29%</b>（基准 2.66%），最大回撤 -22.6%（基准 -36.7%）。这是目前最经得起拉长样本的策略。<br>
<b>结论三：所谓"高胜率"本质是长周期胜利。</b>全历史 5y+ERP 在 12 月窗口胜率只有 <b>55.1%</b>、24 月 65.8%，到 36 月 89.0%、60 月 94.1%。<b>它不适合一年内的资金安排</b>；按三年以上周期持有才有统计优势。<br>
<b>结论四：3 年基线在早期不可靠。</b>2010-2014 子样本里 3 年基线随机胜率仅 14%，加上 ERP 后升到 74%。ERP 的价值在这一段体现得最明显。
</div>

<div class="grid">
  <div class="kpi"><div class="k">全历史基准年化</div><div class="v">+2.66%</div><div class="d">2010-06 ~ 2026-11 · 回撤 -36.7%</div></div>
  <div class="kpi" style="border-color:#fecaca"><div class="k">5y+ERP 年化</div><div class="v c-up">+7.29%</div><div class="d">回撤 -22.6% · 3 笔交易</div></div>
  <div class="kpi"><div class="k">5y+ERP 随机胜率</div><div class="v c-up">75.5%</div><div class="d">三个样本稳定在 74~76%</div></div>
  <div class="kpi"><div class="k">5y+ERP+恐慌 胜率</div><div class="v c-down">61.5%</div><div class="d">2015+ 样本，2019+ 曾为 79.1%</div></div>
</div>

<h2>一、全量对比：三个样本 × 八种规则</h2>
<div class="card">
<div class="sub-t">MC 胜率 = 随机起点与持有期下跑赢同期买入持有的比例；滚动60胜 = 每 6 个月滚动一个 60 月窗口的胜率。</div>
<h3>FULL：2010-06 ~ 2026-11（198 个月）</h3>
<table><thead><tr><th class="nm">规则</th><th>年化</th><th>回撤</th><th>笔数</th><th>持仓</th><th>MC总</th><th>12月</th><th>36月</th><th>60月</th><th>滚动60胜</th></tr></thead><tbody>__TF__</tbody></table>
<h3>P2015：2015-01 ~ 2026-11（143 个月）</h3>
<table><thead><tr><th class="nm">规则</th><th>年化</th><th>回撤</th><th>笔数</th><th>持仓</th><th>MC总</th><th>12月</th><th>36月</th><th>60月</th><th>滚动60胜</th></tr></thead><tbody>__T15__</tbody></table>
<h3>P2019：2019-01 ~ 2026-11（95 个月，原研究样本）</h3>
<table><thead><tr><th class="nm">规则</th><th>年化</th><th>回撤</th><th>笔数</th><th>持仓</th><th>MC总</th><th>12月</th><th>36月</th><th>60月</th><th>滚动60胜</th></tr></thead><tbody>__T19__</tbody></table>
<div class="note">P2019 的滚动 60 月胜率 100% 不可信：95 个月只能切出 8 个高度重叠的窗口，全部落在同一轮估值周期。样本越长这个指标越有区分度（FULL 有 24 个窗口）。</div>
</div>

<h2>二、胜率的真相：持有期越长越赢</h2>
<div class="card">
<div id="hz" class="chart"></div>
<div class="note">三样本 × 四持有期。5y+ERP 在 12 月窗口只有 51~57%（和抛硬币差不多），60 月窗口 87~100%。上次报告里 79.1% 的"总胜率"是四种持有期平均后的结果，其中长窗口贡献了绝大部分。资金期限不足三年的，不应该用这套规则。</div>
</div>

<div class="card">
<h3>全历史净值（2010-06 = 1）</h3>
<div id="eq" class="chart" style="height:390px"></div>
<table><thead><tr><th class="nm">规则</th><th>买入月</th><th>卖出月</th><th>持有</th><th>区间收益</th></tr></thead><tbody>__LOG__</tbody></table>
</div>

<h2>三、分年段稳定性（12/24 月随机窗口）</h2>
<div class="card">
<div id="sub" class="chart"></div>
<table><thead><tr><th class="nm">规则</th><th>2010-14 胜率/年化</th><th>2015-18 胜率/年化</th><th>2019-22 胜率/年化</th><th>2023-26 胜率/年化</th></tr></thead><tbody>__SUB__</tbody></table>
<div class="note">每段只做 12/24 月窗口，所以胜率数值低于上表（上表含 36/60 月）。用于横向比较，不与上表绝对值直接对比。2010-2014：3 年基线 14% → 加 ERP 后 74%，是全历史里最明显的改善；2023-2026：三种策略都在 50% 左右，没有稳定优势。</div>
</div>

<h2>四、修正后的最终结论</h2>
<div class="card">
<ul>
<li><b>保留：</b>PE 分位（5 年）≤20% 买、≥80% 卖 + <b>ERP≥6.5pp</b>。这是唯一在 198/143/95 个月三个样本里年化、回撤、胜率都一致改善的版本。全历史 3 笔交易：2012-07→2015-03 +73.65%、2018-12→2020-07 +55.95%、2022-09→2025-08 +18.18%。</li>
<li><b>降级：</b>恐慌度≥50。它在 2019+ 把胜率从 74% 抬到 79%，但 2015+ 反而从 75.4% 掉到 61.5%。可作为主观参考，不要写进硬规则。</li>
<li><b>放弃：</b>ERP 分位≥80%（滚动 60 月）。全历史年化 4.92%、胜率 63.9%，与基线（4.86% / 64.3%）几乎没有差别 —— 绝对阈值 6.5pp 优于相对分位。</li>
<li><b>明确使用边界：</b>这是 3 年以上周期的策略。12 个月尺度胜率约 55%，没有可靠优势；2010-2014 和 2023-2026 这类低波动 / 慢牛段任何版本都接近随机。</li>
<li><b>结构性提醒：</b>2010 年 10 年国债收益率约 3~4%，ERP≥6.5 当时要求 PE 低于 9~10 倍；如今国债 1.6%，同样阈值对应 PE 约 12.7 倍。绝对阈值会随利率中枢漂移，需定期复核，不能机械套用二十年。</li>
</ul>
</div>

<div class="dis">免责声明：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。</div>

</div><script>
var D = __DATA__;
function barHz(id){
  var cats=[]; for(var i=0;i<D.samples.length;i++){for(var j=0;j<4;j++)cats.push(D.samples[i]+' '+D.hz[j]);}
  echarts.init(document.getElementById(id)).setOption({
    grid:{left:48,right:24,top:44,bottom:66},tooltip:{trigger:'axis'},legend:{top:6},
    xAxis:{type:'category',data:cats,axisLabel:{fontSize:9,interval:0,rotate:32}},
    yAxis:{type:'value',name:'胜率 %',min:20,max:100},
    series:[
      {name:'5y基线',type:'bar',data:D.b5win,itemStyle:{color:'#cbd5e1'}},
      {name:'5y+ERP',type:'bar',data:D.e5win,itemStyle:{color:'#c62828'}},
      {name:'5y+ERP+恐慌',type:'bar',data:D.f5win,itemStyle:{color:'#3b82f6'}}
    ]
  });
}
barHz('hz');
echarts.init(document.getElementById('eq')).setOption({
  grid:{left:52,right:28,top:44,bottom:52},tooltip:{trigger:'axis'},legend:{top:6},
  xAxis:{type:'category',data:D.ym,axisLabel:{fontSize:10,interval:23}},
  yAxis:{type:'value',name:'净值',min:0.6,max:2.6},
  series:[
    {name:'买入持有',type:'line',data:D.bh,symbol:'none',lineStyle:{width:1.4,color:'#94a3b8',type:'dashed'}},
    {name:'3y+ERP',type:'line',data:D.e3,symbol:'none',lineStyle:{width:1.6,color:'#3b82f6'}},
    {name:'5y基线',type:'line',data:D.b5,symbol:'none',lineStyle:{width:1.4,color:'#93c5fd'}},
    {name:'5y+ERP',type:'line',data:D.e5,symbol:'none',lineStyle:{width:2.4,color:'#c62828'}}
  ]
});
echarts.init(document.getElementById('sub')).setOption({
  grid:{left:48,right:24,top:44,bottom:52},tooltip:{trigger:'axis'},legend:{top:6},
  xAxis:{type:'category',data:D.subnames},
  yAxis:{type:'value',name:'胜率 %',min:0,max:80},
  series:[
    {name:'5y基线',type:'bar',data:D.subb5,itemStyle:{color:'#cbd5e1'}},
    {name:'5y+ERP',type:'bar',data:D.sube5,itemStyle:{color:'#c62828'}},
    {name:'5y+ERP+恐慌',type:'bar',data:D.subf5,itemStyle:{color:'#3b82f6'}}
  ]
});
window.addEventListener('resize',function(){
  ['hz','eq','sub'].forEach(function(id){var el=document.getElementById(id);if(el){var c=echarts.getInstanceByDom(el);if(c)c.resize();}});
});
</script></body></html>"""

HTML = (HTML.replace("__TF__", table("FULL")).replace("__T15__", table("P2015"))
        .replace("__T19__", table("P2019")).replace("__LOG__", log_table())
        .replace("__SUB__", sub_table()).replace("__DATA__", D))
with open(OUT, "w", encoding="utf-8") as fp:
    fp.write(HTML)
print("written", OUT, len(HTML))
