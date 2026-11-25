# -*- coding: utf-8 -*-
"""生成「PE 分位择时的多因子修正」HTML 报告。"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = json.load(open(os.path.join(ROOT, "data", "factor_filters.json"), encoding="utf-8"))
S = json.load(open(os.path.join(ROOT, "data", "factor_sensitivity.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "docs", "factor_filters_report.html")

ORDER = ["基线(仅PE)", "PB分位≤20", "PB≤1.30", "PB≤1.40", "隐含EPS增速>0",
         "隐含EPS增速>5%", "股息率前20%", "ERP≥6.5%", "恐慌度≥50", "恐慌度≥70",
         "价格回撤≤-20%", "价格回撤≤-25%", "两融同比≤0", "M1同比≥5%",
         "拥挤度≤40%分位", "PB分位≤20且EPS>0", "回撤≤-20且EPS>0",
         "ERP≥6且恐慌≥50", "PB≤1.35且EPS>0"]
SHORT = {"基线(仅PE)": "基线（仅PE）", "PB分位≤20": "PB 分位≤20%", "PB≤1.30": "PB≤1.30",
         "PB≤1.40": "PB≤1.40", "隐含EPS增速>0": "隐含EPS增速>0", "隐含EPS增速>5%": "隐含EPS增速>5%",
         "股息率前20%": "股息率前20%", "ERP≥6.5%": "ERP≥6.5pp", "恐慌度≥50": "恐慌度≥50",
         "恐慌度≥70": "恐慌度≥70", "价格回撤≤-20%": "价格回撤≤-20%",
         "价格回撤≤-25%": "价格回撤≤-25%", "两融同比≤0": "两融同比≤0",
         "M1同比≥5%": "M1同比≥5%", "拥挤度≤40%分位": "拥挤度≤40%分位",
         "PB分位≤20且EPS>0": "PB低且EPS增", "回撤≤-20且EPS>0": "深跌且EPS增",
         "ERP≥6且恐慌≥50": "ERP≥6且恐慌≥50", "PB≤1.35且EPS>0": "PB≤1.35且EPS增"}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def factor_rows(y):
    out = ""
    for k in ORDER:
        e = F["entry"][y][k]
        g = F["signals"][y][k]
        mc = F["mc"][y][k]
        mcw = sum(mc["win"].values()) / len(mc["win"])
        c = "c-up" if e["cagr"] >= 4.8 else ("c-down" if e["cagr"] < 2.5 else "")
        m = "c-up" if mcw >= 72 else ("c-down" if mcw < 62 else "")
        out += (f"<tr><td class='nm'>{esc(SHORT[k])}</td>"
                f"<td class='{c}'>{e['cagr']:+.2f}%</td><td>{e['max_dd']:+.1f}%</td>"
                f"<td>{e['ntr']}</td><td>{e['tim']:.1f}%</td><td>{g['n_signal']}</td>"
                f"<td>{'-' if g['fwd12_mean'] is None else format(g['fwd12_mean'],'+.1f')+'%'}</td>"
                f"<td>{'-' if g['fwd12_win'] is None else format(g['fwd12_win'],'.0f')+'%'}</td>"
                f"<td class='{m}'>{mcw:.1f}%</td></tr>")
    return out


def combo_rows(y):
    out = ""
    for k, v in S["combos"][y].items():
        a, b = v["sell80"], v["sell90"]
        hi = v["mc"] >= 74
        cls = "c-up" if hi else ""
        out += (f"<tr><td class='nm'>{esc(k)}</td>"
                f"<td>{a['cagr']:+.2f}%</td><td>{a['max_dd']:+.1f}%</td><td>{a['ntr']}</td>"
                f"<td class='{cls}'>{v['mc']:.1f}%</td>"
                f"<td>{b['cagr']:+.2f}%</td><td>{b['max_dd']:+.1f}%</td><td>{b['ntr']}</td></tr>")
    return out


def log_rows():
    out = ""
    combos = [("3y 基线", F["entry"]["3y"]["基线(仅PE)"]),
              ("3y ERP+恐慌", S["combos"]["3y"]["ERP≥6.5且恐慌≥50"]["sell80"]),
              ("5y 基线", F["entry"]["5y"]["基线(仅PE)"]),
              ("5y ERP+恐慌", S["combos"]["5y"]["ERP≥6.5且恐慌≥50"]["sell80"]),
              ("5y ERP+恐慌+卖90", S["combos"]["5y"]["ERP≥6.5且恐慌≥50"]["sell90"])]
    for name, v in combos:
        logs = " / ".join(f"{t['in']}→{t['out']} {t['months']}月 {t['ret']:+.2f}%"
                          for t in v["log"]) or "无交易"
        out += (f"<tr><td class='nm'>{esc(name)}</td><td class='c-up'>{v['cagr']:+.2f}%</td>"
                f"<td>{v['max_dd']:+.1f}%</td><td>{v['tim']:.1f}%</td>"
                f"<td class='sm'>{esc(logs)}</td></tr>")
    return out


data = {
    "ym": S["curves"]["ym"], "bh": S["curves"]["bh"],
    "c3b": S["curves"]["3y_基线"], "c3f": S["curves"]["3y_ERP≥6.5且恐慌≥50"],
    "c3f90": S["curves"]["3y_ERP≥6.5且恐慌≥50_卖90"],
    "c5b": S["curves"]["5y_基线"], "c5f": S["curves"]["5y_ERP≥6.5且恐慌≥50"],
    "c5f90": S["curves"]["5y_ERP≥6.5且恐慌≥50_卖90"],
    "sweep3": S["erp_sweep"]["3y"], "sweep5": S["erp_sweep"]["5y"],
    "band3": S["erp_bands"]["3y"], "band5": S["erp_bands"]["5y"],
    "combokeys": list(S["combos"]["5y"].keys()),
    "combo3": [S["combos"]["3y"][k]["sell80"]["cagr"] for k in S["combos"]["5y"]],
    "combo5": [S["combos"]["5y"][k]["sell80"]["cagr"] for k in S["combos"]["5y"]],
    "combo5mc": [S["combos"]["5y"][k]["mc"] for k in S["combos"]["5y"]],
}
D = json.dumps(data, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>沪深300 PE 择时的多因子修正</title>
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
th.nm,td.nm{text-align:left;font-weight:600} td.sm{text-align:left;font-size:11.5px;color:var(--ink2);white-space:normal}
tbody tr:hover{background:#fcfdff}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.note{font-size:12px;color:var(--mut);margin-top:7px}
.chart{width:100%;height:360px}
ul{padding-left:20px;margin:8px 0} li{margin:6px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:880px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">沪深300（000300） · 2019-01 ~ 2026-11（95 个月）· 月末信号次月生效 · 单边 5bp · 无未来函数</div>
<h1>PE 分位不是万能尺：引入 ERP、恐慌度、PB 与盈利趋势后，策略变好了吗？</h1>

<div class="verdict">
<b>结论一：真正有效的修正只有两个 —— ERP 与恐慌度。</b>在 PE≤20% 买的基础上要求 <b>ERP≥6.5 个百分点</b> 且 <b>恐慌度≥50</b>，5 年窗口年化 <b class="c-up">4.56% → 6.36%</b>、最大回撤 <b class="c-up">-28.3% → -22.6%</b>、随机窗口胜率 <b class="c-up">66.0% → 80.0%</b>；3 年窗口 4.93% → 4.86%（基本持平），回撤同样收窄、胜率 65.1% → 78.8%。<br>
<b>结论二：你的"价格处于历史低位"直觉被数据否定。</b>要求价格距 36 月高点回撤≤-20% 后，5 年年化反而 <b class="c-down">4.56% → 1.43%</b>，随机胜率 <b class="c-down">66.0% → 45.8%</b>。低估值 + 深跌常常意味着盈利下修，不是买点。<br>
<b>结论三："营收涨、股价跌导致 PE 变低"这个逻辑在样本里几乎抓不到。</b>隐含 EPS 增速>0 的 3 年信号只有 4 个月、5 年只有 1 个月，全部集中在 2020-03；筛选后只剩 1 笔交易，年化看似不变但纯粹是幸存的单笔。不能当作独立因子使用。<br>
<b>结论四：PB 只能做弱确认，不能做硬门槛。</b>PB 分位≤20% 让随机胜率小幅提升（3 年 65.1→66.2、5 年 66.0→68.6），但交易不变；PB≤1.30 的绝对阈值会把两笔砍成一笔，年化反而下降。
</div>

<div class="grid">
  <div class="kpi"><div class="k">5y 基线年化</div><div class="v">+4.56%</div><div class="d">2 笔 · 回撤 -28.3% · MC 66.0%</div></div>
  <div class="kpi" style="border-color:#fecaca"><div class="k">5y ERP+恐慌</div><div class="v c-up">+6.36%</div><div class="d">2 笔 · 回撤 -22.6% · MC 80.0%</div></div>
  <div class="kpi" style="border-color:#fecaca"><div class="k">5y ERP+恐慌+卖90</div><div class="v c-up">+7.32%</div><div class="d">2 笔 · 第2笔 +34.13%</div></div>
  <div class="kpi"><div class="k">价格深跌过滤</div><div class="v c-down">+1.43%</div><div class="d">5y 年化，比基线差 3.1pp</div></div>
</div>

<h2>一、19 个买入侧修正因子的全量对比</h2>
<div class="card">
<div class="sub-t">买入条件：PE 分位≤20% <b>且</b>下表附加条件；卖出仍为 PE 分位≥80%。MC 胜率 = 1200 组随机起点 × {12,24,36,60} 月持有期中跑赢同期买入持有的比例。</div>
<h3>3 年 PE 窗口</h3>
<table><thead><tr><th class="nm">附加条件</th><th>年化</th><th>回撤</th><th>交易</th><th>持仓</th><th>信号月</th><th>前瞻12月</th><th>胜率</th><th>MC胜率</th></tr></thead><tbody>__R3__</tbody></table>
<h3>5 年 PE 窗口</h3>
<table><thead><tr><th class="nm">附加条件</th><th>年化</th><th>回撤</th><th>交易</th><th>持仓</th><th>信号月</th><th>前瞻12月</th><th>胜率</th><th>MC胜率</th></tr></thead><tbody>__R5__</tbody></table>
<div class="note">信号月数：2019 年以来满足"PE≤20% + 附加条件"的月份；前瞻 12 月收益为信号次月起 12 个月指数涨幅。信号月高度重叠（连续下跌），不等同独立样本。</div>
</div>

<h2>二、ERP 的机制：6.0~6.5 是明显的分水岭</h2>
<div class="card">
<div class="sub-t">ERP = 100 / PE-TTM(加权) − 10 年国债收益率，单位：百分点。越高代表股票相对债券越便宜。</div>
<div id="band" class="chart"></div>
<div class="note">所有 PE≤20% 的信号按月统计前瞻 12 月收益。3 年窗口 ERP 6.0~6.5 区间 7 个月平均 <b class="c-down">-7.71%</b>、胜率 14.3%；跨过 6.5 后 8 个月平均 <b class="c-up">+5.41%</b>、胜率 75%。5 年窗口同样：6.0~6.5 的 6 个月全部亏损（均值 -10.23%），6.5 以上 13 个月均值 +6.7%、胜率约 76%。这是本次研究里最清晰的一个非线性阈值。</div>
</div>

<h2>三、阈值敏感性：6.5 之后不能继续抬</h2>
<div class="card">
<div class="two">
<div><div id="sw3" class="chart"></div></div>
<div><div id="sw5" class="chart"></div></div>
</div>
<div class="note">ERP 从 5.0 抬到 6.5，随机胜率稳步上升；6.75 以上信号被砍到只剩 1 笔，年化反而塌陷。恐慌度阈值在 30~55 之间结果完全不变，60 以上只剩 1 笔 —— 说明 <b>6.5 / 50 不是精细调参出来的尖峰，而是一段平台</b>，这是抗过拟合的正面证据。</div>
</div>

<h2>四、组合规则与净值</h2>
<div class="card">
<div id="combo" class="chart"></div>
<table><thead><tr><th class="nm">买入规则</th><th>卖80年化</th><th>卖80回撤</th><th>笔数</th><th>MC胜率</th><th>卖90年化</th><th>卖90回撤</th><th>笔数</th></tr></thead><tbody>__CO__</tbody></table>
<div class="note">"ERP≥6.5 且恐慌≥50"在两个窗口、两种卖出线下同时改善年化与回撤，是唯一同时通过样本内和随机检验的组合。"ERP≥6.5 或 EPS>0"在 3 年窗口年化更高（5.65%），但它等价于把 2019 年的单笔大行情加回来，随机胜率只有 70.8%，不稳。</div>
</div>

<div class="card">
<h3>净值曲线（起点=1）</h3>
<div id="eq" class="chart" style="height:400px"></div>
<table><thead><tr><th class="nm">方案</th><th>年化</th><th>最大回撤</th><th>持仓</th><th>交易明细</th></tr></thead><tbody>__LOG__</tbody></table>
</div>

<h2>五、要明确否定的三个方向</h2>
<div class="card">
<ul>
<li><b>不要叠加"价格历史低位"。</b>价格回撤≤-20% 把 5 年年化砍到 1.43%、随机胜率 45.8%（低于抛硬币意义上的基准）；3 年看似持平，但 5 年窗口直接把 2020-03 的 +27.37% 那笔过滤掉了。低 PE + 深跌往往伴随盈利下修，是价值陷阱的高发区。</li>
<li><b>不要单独用 EPS 增速做门槛。</b>隐含 EPS = 指数点位 / PE-TTM。3 年窗口 EPS>0 的 4 个信号全在 2019 年和 2020-03；5 年窗口只有 2020-03 一个。它筛出的"好买点"和"2020 年疫情底"是同一件事，换个样本就不成立。</li>
<li><b>不要用 M1、拥挤度、两融同比做过滤。</b>三者随机胜率全部跌到 42%~50%，年化普遍腰斩。宏观流动性与杠杆情绪在 2019 年后与沪深300 的月度节奏不同步，反而会在底部把仓位挡在门外。</li>
</ul>
</div>

<h2>六、怎么用在实盘判断上</h2>
<div class="card">
<ul>
<li><b>买入三条件同时满足：</b>① PE 分位（3 年或 5 年）≤20%；② ERP≥6.5pp（相当于当前 PE 的盈利收益率比 10 年国债高 6.5 个百分点以上）；③ 恐慌度≥50（0~100，越高越恐慌）。PB 分位≤20% 可作加分项，不作硬门槛。</li>
<li><b>卖出：</b>PE 分位≥80% 为纪律线；≥90% 是样本内更优但交易更少的选择。PB 信号没有提供额外信息，不用叠加。</li>
<li><b>当前状态（2026-11）：</b>PE 分位 3 年 63.9% / 5 年 76.7%，ERP 6.27pp（<u>低于</u> 6.5 门槛），恐慌度 61.7，5 年 PB 1.33。**不满足买入**，且 5 年分位已接近卖出线 —— 与上一轮结论一致：现在不是建仓时点。</li>
<li><b>仓位：</b>回测全部按满仓、月末信号次月执行。实盘建议按信号分批建仓，因为单笔交易间隔可达两年以上，且本样本只有 2 笔独立决策。</li>
</ul>
</div>

<h2>七、必须承认的局限</h2>
<div class="card">
<ul>
<li><b>全部改善来自一个决策：</b>ERP+恐慌把 2022-04 的买点推迟到 2022-10，使 5 年窗口第二笔从 +11.96% 变成 +28.16%。2 笔交易无法证明统计显著性。</li>
<li><b>ERP 用的是全市场加权 PE-TTM 和 10 年国债，不是机构常用的沪深300 动态预测 EPS</b>，与真实机构口径有差距。</li>
<li><b>恐慌度由已实现波动率 + QVIX 构造，月末取值</b>，与盘中可观测值有轻微差异；M1 已滞后 1 月使用，其余因子取月末可得值。</li>
<li>样本区间 2019-2026 只有一轮完整的估值周期（2020 泡沫 + 2022-2024 熊市 + 2025 反弹），结构转换风险高。</li>
</ul>
</div>

<div class="dis">免责声明：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。</div>

</div><script>
var D = __DATA__;
var baseOpt = {grid:{left:52,right:52,top:48,bottom:52},tooltip:{trigger:'axis'},legend:{top:6,textStyle:{fontSize:11}}};
function lineOpt(series, x, ys, name, color){
  return Object.assign({}, baseOpt, {
    xAxis:{type:'category',data:x,axisLabel:{fontSize:10,interval:2}},
    yAxis:{type:'value',name:name},
    series:series
  });
}
// ERP 分段前瞻收益
echarts.init(document.getElementById('band')).setOption({
  grid:{left:52,right:62,top:48,bottom:52},tooltip:{trigger:'axis'},legend:{top:6},
  xAxis:{type:'category',data:['<5.5','5.5~6.0','6.0~6.5','6.5~7.0','≥7.0']},
  yAxis:[{type:'value',name:'前瞻12月均值 %'},{type:'value',name:'信号月数'}],
  series:[
    {name:'3年窗口',type:'bar',data:D.band3.map(function(x){return x.mean;}),itemStyle:{color:'#3b82f6'}},
    {name:'5年窗口',type:'bar',data:D.band5.map(function(x){return x.mean;}),itemStyle:{color:'#c62828'}},
    {name:'信号月数(5y)',type:'line',yAxisIndex:1,data:D.band5.map(function(x){return x.n;}),itemStyle:{color:'#64748b'},lineStyle:{type:'dashed'}}
  ]
});
// 阈值敏感性
function sweep(id, arr){
  echarts.init(document.getElementById(id)).setOption({
    grid:{left:46,right:46,top:42,bottom:44},tooltip:{trigger:'axis'},legend:{top:4,textStyle:{fontSize:10}},
    xAxis:{type:'category',data:arr.map(function(x){return String(x.th);}),axisLabel:{fontSize:9,interval:1}},
    yAxis:[{type:'value',name:'年化 %'},{type:'value',name:'MC胜率 %'}],
    series:[
      {name:'年化 卖80',type:'line',data:arr.map(function(x){return x.cagr;}),itemStyle:{color:'#c62828'},lineStyle:{width:2.4}},
      {name:'年化 卖90',type:'line',data:arr.map(function(x){return x.cagr90;}),itemStyle:{color:'#f59e0b'},lineStyle:{width:1.6,type:'dashed'}},
      {name:'MC胜率',type:'line',yAxisIndex:1,data:arr.map(function(x){return x.mc;}),itemStyle:{color:'#3b82f6'}}
    ]
  });
}
sweep('sw3', D.sweep3); sweep('sw5', D.sweep5);
// 组合
echarts.init(document.getElementById('combo')).setOption({
  grid:{left:48,right:50,top:48,bottom:86},tooltip:{trigger:'axis'},legend:{top:6},
  xAxis:{type:'category',data:D.combokeys,axisLabel:{fontSize:10,interval:0,rotate:28}},
  yAxis:[{type:'value',name:'年化 %'},{type:'value',name:'MC胜率 %'}],
  series:[
    {name:'3y 年化',type:'bar',data:D.combo3,itemStyle:{color:'#3b82f6'}},
    {name:'5y 年化',type:'bar',data:D.combo5,itemStyle:{color:'#c62828'}},
    {name:'5y MC胜率',type:'line',yAxisIndex:1,data:D.combo5mc,itemStyle:{color:'#0f172a'},lineStyle:{width:2}}
  ]
});
// 净值
echarts.init(document.getElementById('eq')).setOption({
  grid:{left:52,right:36,top:48,bottom:52},tooltip:{trigger:'axis'},legend:{top:6,textStyle:{fontSize:11}},
  xAxis:{type:'category',data:D.ym,axisLabel:{fontSize:10,interval:11}},
  yAxis:{type:'value',name:'净值',min:0.8,max:1.8},
  series:[
    {name:'买入持有',type:'line',data:D.bh,symbol:'none',lineStyle:{width:1.4,color:'#94a3b8',type:'dashed'}},
    {name:'3y 基线',type:'line',data:D.c3b,symbol:'none',lineStyle:{width:1.4,color:'#93c5fd'}},
    {name:'3y ERP+恐慌',type:'line',data:D.c3f,symbol:'none',lineStyle:{width:2,color:'#3b82f6'}},
    {name:'5y 基线',type:'line',data:D.c5b,symbol:'none',lineStyle:{width:1.4,color:'#fca5a5'}},
    {name:'5y ERP+恐慌',type:'line',data:D.c5f,symbol:'none',lineStyle:{width:2,color:'#c62828'}},
    {name:'5y ERP+恐慌+卖90',type:'line',data:D.c5f90,symbol:'none',lineStyle:{width:2,color:'#f59e0b'}}
  ]
});
window.addEventListener('resize',function(){
  ['band','sw3','sw5','combo','eq'].forEach(function(id){
    var el=document.getElementById(id); if(el){var c=echarts.getInstanceByDom(el); if(c)c.resize();}
  });
});
</script></body></html>"""

HTML = (HTML.replace("__R3__", factor_rows("3y")).replace("__R5__", factor_rows("5y"))
        .replace("__CO__", combo_rows("5y")).replace("__LOG__", log_rows())
        .replace("__DATA__", D))

with open(OUT, "w", encoding="utf-8") as fp:
    fp.write(HTML)
print("written", OUT, len(HTML))
