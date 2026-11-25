# -*- coding: utf-8 -*-
"""生成 2013-2026 逐笔复盘与评分报告。"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "review_2013.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "docs", "review_2013_report.html")
S = R["strategies"]
MAIN = S["S_5y_ERP"]
SC = R["scores"]["S_5y_ERP"]


def trade_cards():
    out = ""
    for i, t in enumerate(MAIN["trades"], 1):
        out += (f"<div class='trade'><div class='tn'>第 {i} 笔</div>"
                f"<div class='tp'><b>{t['in_signal']}</b> 买入<br>"
                f"<span>PE 分位 {t['pe_pct_in']}% · ERP {t['erp_in']}pp · PB {t['pb_in']}</span></div>"
                f"<div class='arrow'>→</div>"
                f"<div class='tp'><b>{t['out_signal']}</b> 卖出<br><span>PE 分位回到 80%</span></div>"
                f"<div class='td'>持有 <b>{t['months']}</b> 个月</div>"
                f"<div class='tr c-up'>{t['ret']:+.2f}%</div></div>")
    return out


def cmp_table():
    out = ""
    for name, v in S.items():
        label = {"S_5y_ERP": "5y PE + ERP（本次策略）", "C_5y_base": "5y PE 基线（无 ERP）",
                 "C_3y_ERP": "3y PE + ERP"}[name]
        cls = "hl" if name == "S_5y_ERP" else ""
        out += (f"<tr class='{cls}'><td class='nm'>{label}</td><td class='c-up'>{v['total_ret']:+.2f}%</td>"
                f"<td>{v['excess_pp']:+.2f}pp</td><td>{v['max_dd']:+.1f}%</td>"
                f"<td>{v['ntr']}</td><td>{v['tim']:.1f}%</td>"
                f"<td>{R['scores'][name]['total']}/100</td></tr>")
    out += (f"<tr><td class='nm'>买入持有</td><td class='c-up'>{MAIN['bh_total_ret']:+.2f}%</td>"
            f"<td>—</td><td>-39.9%</td><td>—</td><td>100%</td><td>13/100</td></tr>")
    return out


def score_table():
    parts = SC["parts"]
    full = {"收益": 30, "回撤": 25, "熊市规避": 20, "执行效率": 15, "资金利用": 10}
    basis = {
        "收益": "累计 +204.18%，超额 +157pp ≥50pp 门槛",
        "回撤": "最大回撤 -22.6%，落在 -20%~-30% 档",
        "熊市规避": "熊市 83 个月中持仓 51.8%，落在 45~60% 档",
        "执行效率": "13.8 年仅 3 笔，落在 2~5 笔最优档",
        "资金利用": "持仓时间 46.1%，落在 40~65% 档",
    }
    out = ""
    for k, v in parts.items():
        pct = v / full[k] * 100
        color = "#c62828" if pct >= 80 else ("#f59e0b" if pct >= 50 else "#64748b")
        out += (f"<tr><td class='nm'>{k}</td><td>{v} / {full[k]}</td>"
                f"<td style='width:40%'><div class='bar'><div style='width:{pct}%;background:{color}'></div></div></td>"
                f"<td class='sm'>{basis[k]}</td></tr>")
    out += f"<tr class='hl'><td class='nm'>总分</td><td colspan='3'><b>{SC['total']} / 100</b> —— 优秀，但熊市规避一项是结构性短板</td></tr>"
    return out


D = json.dumps({
    "ym": MAIN["ym"], "eq": MAIN["eq_curve"], "bh": MAIN["bh_curve"],
    "b5": S["C_5y_base"]["eq_curve"], "e3": S["C_3y_ERP"]["eq_curve"],
    "holds": [{"in": t["in_signal"], "out": t["out_signal"], "ret": t["ret"]}
              for t in MAIN["trades"]],
}, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>2013-2026 策略逐笔复盘与评分</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--ink:#0f172a;--ink2:#475569;--mut:#94a3b8;--line:#e2e8f0;--bg:#f7f8fa;--card:#fff;--up:#c62828;--down:#1b7f4e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:26px;margin:0 0 10px;line-height:1.35;letter-spacing:-.3px}
h2{font-size:18px;margin:34px 0 12px;padding-left:11px;border-left:4px solid #1e293b}
.sub-t{color:var(--ink2);font-size:13.5px;margin-bottom:6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:16px 0}
.verdict{background:#fff;border:1px solid var(--line);border-left:4px solid #c62828;border-radius:10px;padding:18px 22px;margin:18px 0}
.score{display:flex;align-items:baseline;gap:16px;background:#fff;border:1px solid var(--line);border-left:5px solid #c62828;border-radius:12px;padding:16px 22px;margin:16px 0}
.score .n{font-size:44px;font-weight:700;color:var(--up);line-height:1}
.score .t{font-size:14px;color:var(--ink2)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px 16px}
.kpi .k{font-size:12.5px;color:var(--mut)} .kpi .v{font-size:22px;font-weight:700;margin:3px 0;letter-spacing:-.4px}
.kpi .d{font-size:12px;color:var(--ink2)}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
th,td{padding:8px 9px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{background:#f8fafc;color:var(--ink2);font-size:11.5px;font-weight:600}
th.nm,td.nm{text-align:left;font-weight:600} td.sm{text-align:left;font-size:11.5px;color:var(--ink2);white-space:normal}
tr.hl{background:#fff7f7} tr.hl td{font-weight:600}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.bar{height:9px;background:#eef2f7;border-radius:5px;overflow:hidden} .bar div{height:100%;border-radius:5px}
.trade{display:grid;grid-template-columns:70px 1fr 40px 1fr 105px 90px;gap:10px;align-items:center;
  border-bottom:1px solid var(--line);padding:13px 0;font-size:13px}
.trade:last-child{border-bottom:0}
.tn{font-weight:700;color:var(--ink2)} .tp b{font-size:14px} .tp span{font-size:11px;color:var(--mut)}
.arrow{color:var(--mut);font-size:17px;text-align:center}
.td{text-align:center;color:var(--ink2)} .tr{text-align:right;font-weight:700;font-size:15px}
.note{font-size:12px;color:var(--mut);margin-top:7px}
.chart{width:100%;height:390px}
ul{padding-left:20px;margin:8px 0} li{margin:6px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:880px){.grid{grid-template-columns:repeat(2,1fr)}.trade{grid-template-columns:1fr 1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">沪深300 · 2013-01 ~ 2026-11（167 个月）· 5 年 PE 分位 ≤20% 买 / ≥80% 卖 + ERP≥6.5pp · 月末信号次月生效 · 单边 5bp</div>
<h1>十三年只做三笔：每次持有多久、赚了多少、该打几分</h1>

<div class="verdict">
买入规则在 13 年里只触发 <b>3 次</b>，每次都拿到 1.6~2.9 年。累计收益 <b class="c-up">+204.18%</b>，同期买入持有 <b>+47.18%</b>，超额 <b class="c-up">+157 个百分点</b>，最大回撤 <b>-22.6%</b>（买入持有 -39.9%）。三笔全胜，但第三笔只赚 18.18%、持有近三年，效率明显低于前两笔。
</div>

<div class="score">
<div class="n">79<span style="font-size:20px;color:var(--mut)">/100</span></div>
<div class="t"><b>总体评价：优秀</b><br>收益、执行效率、资金利用三项满分；回撤扣 7 分；熊市规避只拿到 6/20 —— 这是逆向估值策略的固有特征，它会刻意在下跌中持仓。</div>
</div>

<div class="grid">
  <div class="kpi"><div class="k">累计收益</div><div class="v c-up">+204.18%</div><div class="d">期末净值 3.04（起点 1）</div></div>
  <div class="kpi"><div class="k">买入持有</div><div class="v">+47.18%</div><div class="d">期末净值 1.47</div></div>
  <div class="kpi"><div class="k">超额</div><div class="v c-up">+157pp</div><div class="d">三笔交易总贡献</div></div>
  <div class="kpi"><div class="k">总持仓时间</div><div class="v">77 个月</div><div class="d">占 13.8 年的 46.1%</div></div>
</div>

<h2>一、三笔交易全部明细</h2>
<div class="card">
__TRADES__
<div class="note">"买入月"是信号发出月，收益从次月开始计算；"卖出月"是 PE 分位回到 80% 的信号月。持有月数含信号月到卖出月之间的完整月份。三笔合计持有 23+19+35 = 77 个月，与 46.1% 的持仓比例一致。</div>
</div>

<div class="card">
<h3>净值走势（起点 = 1）</h3>
<div id="eq" class="chart"></div>
</div>

<h2>二、三种方案对比（同一 13 年）</h2>
<div class="card">
<table><thead><tr><th class="nm">方案</th><th>累计收益</th><th>超额</th><th>最大回撤</th><th>交易笔数</th><th>持仓占比</th><th>评分</th></tr></thead><tbody>__CMP__</tbody></table>
<div class="note">此处只列累计收益，不计算年化。买入持有的评分按同一评分规则估算：超额 0、回撤 -39.9%、熊市满仓、无交易决策。</div>
</div>

<h2>三、评分依据</h2>
<div class="card">
<table><thead><tr><th class="nm">维度</th><th>得分</th><th>完成度</th><th>依据</th></tr></thead><tbody>__SCORE__</tbody></table>
<h3>评分规则（满分 100）</h3>
<ul>
<li>收益 30 分：超额 ≥50pp=30，≥30=24，≥10=18，≥0=12，负数=0</li>
<li>回撤 25 分：优于 -20%=25，-20~-30=18，-30~-40=10，劣于 -40=0</li>
<li>熊市规避 20 分：熊市持仓 ≤15%=20，≤30=16，≤45=11，≤60=6，&gt;60=0</li>
<li>执行效率 15 分：2~5 笔=15，6~8=10，9~12=5，其他=0</li>
<li>资金利用 10 分：持仓 40~65%=10，30~40 或 65~75=7，20~30 或 75~85=4，其他=1</li>
</ul>
</div>

<h2>四、怎么看这 79 分</h2>
<div class="card">
<ul>
<li><b>赚到的钱几乎全在两笔里：</b>2013-04 那笔 +65.54%、2018-12 那笔 +55.95%，两笔复利贡献约 2.57 倍；第三笔 35 个月只赚 18.18%，把曲线拉平了。这套策略依赖"泡沫级别的便宜"，不是每年都给机会。</li>
<li><b>2015 年那次卖出是关键：</b>2015-03 信号离场，避开了随后 A 股的急跌；2015-03 到 2018-12 整整空仓 45 个月。</li>
<li><b>熊市持仓 51.8% 不是失误，是代价：</b>策略在价格下跌、估值变便宜时买入并持有，必然在"按价格定义的熊市"里高仓位。它躲的是高估值，不是下跌趋势。若要规避价格熊市，就得接受错过低位建仓，两者不可兼得。</li>
<li><b>评分是规则化的，不是主观打分：</b>同一套评分也用来给基线和买入持有打分，便于横向比较。</li>
</ul>
</div>

<div class="dis">免责声明：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。</div>

</div><script>
var D = __DATA__;
var marks = D.holds.map(function(h){
  return [{'name':'持有 '+h.in_signal, 'xAxis':h.in_signal,
           'itemStyle':{'color':'rgba(198,40,40,0.06)'},
           'label':{'show':true,'formatter':h.ret>0?'+'+h.ret.toFixed(1)+'%':'',
                    'color':'#c62828','fontSize':10,'position':'insideTop'}},
          {'xAxis':h.out_signal}];
});
echarts.init(document.getElementById('eq')).setOption({
  grid:{left:52,right:28,top:46,bottom:52},tooltip:{trigger:'axis'},legend:{top:6},
  xAxis:{type:'category',data:D.ym,axisLabel:{fontSize:10,interval:17}},
  yAxis:{type:'value',name:'净值',min:0.8,max:3.2},
  series:[
    {name:'买入持有',type:'line',data:D.bh,symbol:'none',lineStyle:{width:1.4,color:'#94a3b8',type:'dashed'}},
    {name:'5y基线',type:'line',data:D.b5,symbol:'none',lineStyle:{width:1.3,color:'#93c5fd'}},
    {name:'3y+ERP',type:'line',data:D.e3,symbol:'none',lineStyle:{width:1.3,color:'#3b82f6'}},
    {name:'5y+ERP（本次）',type:'line',data:D.eq,symbol:'none',lineStyle:{width:2.6,color:'#c62828'},
     markArea:{silent:true,data:marks}}
  ]
});
</script></body></html>"""

HTML = (HTML.replace("__TRADES__", trade_cards()).replace("__CMP__", cmp_table())
        .replace("__SCORE__", score_table()).replace("__DATA__", D))
with open(OUT, "w", encoding="utf-8") as fp:
    fp.write(HTML)
print("written", OUT, len(HTML))
