# -*- coding: utf-8 -*-
"""生成「PE 分位阈值放宽 + 牛熊偏移」报告。"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "pe_threshold_regime.json")
OUT = os.path.join(ROOT, "docs", "pe_threshold_regime_report.html")

r = json.load(open(SRC, encoding="utf-8"))
meta = r["meta"]
BUYS = [10, 15, 20, 25, 30, 35, 40]
SELLS = [55, 60, 65, 70, 75, 80, 85, 90]
KEYS = ["20/80", "25/75", "30/70", "35/65", "20/90", "35/90"]
C5 = r["candidates"]["5y"]
C3 = r["candidates"]["3y"]

# 热力图数据
heat = {}
for y in ("3y", "5y"):
    mat = r["grid"][y]["matrix"]
    arr = []
    for bi, b in enumerate(BUYS):
        for si, s in enumerate(SELLS):
            cell = mat[str(b)][str(s)]
            if cell is not None:
                arr.append([si, bi, cell["cagr"]])
    heat[y] = arr

# 候选表
def cand_rows(src):
    out = ""
    for k in KEYS:
        v = src[k]
        cls = "c-up" if v["cagr"] >= 4.5 else ("c-down" if v["cagr"] < 3 else "")
        logs = " / ".join(f"{x['in']}→{x['out']} ({x['ret']:+.1f}%)" for x in v["log"])
        out += (
            f"<tr><td class='nm {cls}'>{k}</td><td class='{cls}'>{v['cagr']:+.2f}%</td>"
            f"<td>{v['max_dd']:+.1f}%</td><td>{v['sharpe']:.2f}</td><td>{v['tim']:.1f}%</td>"
            f"<td>{v['ntr']}</td><td>{v['trades_per_year']:.2f}</td>"
            f"<td>{v['avg_hold_m']:.0f}月</td><td class='sm'>{logs}</td></tr>"
        )
    return out

# 随机表
def mc_rows(y):
    out = ""
    for k in KEYS:
        v = r["mc"][f"{y}_{k}"]
        cls = "c-up" if v["win"] >= 66 else ("c-down" if v["win"] < 62 else "")
        out += (
            f"<tr><td class='nm {cls}'>{k}</td><td class='{cls}'>{v['win']:.1f}%</td>"
            f"<td>{v['ret']['median']:+.2f}%</td><td>{v['bh']['median']:+.2f}%</td>"
            f"<td>{v['exc']:+.2f}pp</td><td>{v['tim']:.1f}%</td><td>{v['no_trade']:.1f}%</td></tr>"
        )
    return out

# 捕获率表
def cap_rows(y):
    out = ""
    for k in KEYS:
        v = r["capture"][f"{y}_{k}"]
        bull = v.get("牛市", {})
        bear = v.get("熊市", {})
        out += (
            f"<tr><td class='nm'>{k}</td><td>{v['up_capture']:.2f}</td><td>{v['down_capture']:.2f}</td>"
            f"<td>{v['up_capture']-v['down_capture']:+.2f}</td>"
            f"<td>{v['up_participation']:.1f}%</td><td>{v['down_participation']:.1f}%</td>"
            f"<td>{bull.get('tim',0):.1f}%</td><td>{bull.get('strat_m',0):+.2f}%</td>"
            f"<td>{bear.get('tim',0):.1f}%</td><td>{bear.get('strat_m',0):+.2f}%</td></tr>"
        )
    return out

# 段落表
def ep_rows(key):
    out = ""
    for e in r["episodes"][key]:
        cls = "c-up" if e["strat"] > e["bh"] else "c-down"
        out += (
            f"<tr><td class='nm'>{e['type']}</td><td>{e['from']}~{e['to']}</td><td>{e['months']}</td>"
            f"<td>{e['bh']:+.1f}%</td><td class='{cls}'>{e['strat']:+.1f}%</td>"
            f"<td>{e['tim_first3']:.0f}%</td><td>{'-' if e['tim_rest'] is None else format(e['tim_rest'],'.0f')+'%'}</td></tr>"
        )
    return out

data = {
    "buys": [str(x) for x in BUYS], "sells": [str(x) for x in SELLS],
    "heat3": heat["3y"], "heat5": heat["5y"],
    "ym": r["curves"]["ym"], "bh": r["curves"]["bh"],
    "curves": {k: r["curves"][f"5y_{k}"] for k in KEYS},
    "mc5win": [r["mc"][f"5y_{k}"]["win"] for k in KEYS],
    "mc5med": [r["mc"][f"5y_{k}"]["ret"]["median"] for k in KEYS],
    "up5": [r["capture"][f"5y_{k}"]["up_capture"] for k in KEYS],
    "dn5": [r["capture"][f"5y_{k}"]["down_capture"] for k in KEYS],
    "up3": r["capture"]["3y_20/80"]["up_capture"],
    "dn3": r["capture"]["3y_20/80"]["down_capture"],
}
D = json.dumps(data, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>沪深300 PE 分位：阈值放宽与牛熊偏移</title>
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

<div class="sub-t">沪深300（000300） · 测试区间 __PERIOD__（__MONTHS__ 个月 / __Y__ 年） · 月度 PE-TTM 加权</div>
<h1>20/80 是否过保守？25/75 能否提高年化？以及牛熊里有没有系统性偏移</h1>

<div class="verdict">
<b>结论一：25% 买 / 75% 卖不是"适度放宽"，而是明确变差。</b>5 年窗口全区间年化从 <b>4.61% → 1.96%</b>，随机胜率 <b>66.5% → 59.1%</b>；3 年窗口 4.99% → 4.32%、胜率 66.3% → 60.8%。原因是它提前了卖出（2025-08 → 2024-09），把 +11.96% 的一段拿成了 -4.85%。<br>
<b>结论二：真正有效的是"只放宽卖出侧"。</b>保持 20% 买入、把卖出从 80% 抬到 90%：5 年年化 <b class="c-up">4.61% → 5.56%</b>、随机胜率 <b class="c-up">66.5% → 69.5%</b>；3 年 4.99% → 5.33%、胜率 66.3% → 67.2%。两个窗口、样本内外同时改善。<br>
<b>结论三：不是交易太多，是信号太少。</b>20/80 在 7.8 年里只做 <b>2 笔</b>（0.26 笔/年），持仓时间约 47%~50%；25/75 仍是 2 笔。要提高到 3 笔得放宽到 35/65，但那会牺牲收益。<br>
<b>结论四：策略天然低配牛市、超配低位震荡/熊市。</b>5 年 20/80 的上行捕获 0.58、下行捕获 0.44；放宽卖出到 90% 后上行捕获升到 0.63、下行只升到 0.45 —— 这才是"少牺牲涨、多躲开跌"的方向。
</div>

<div class="grid">
  <div class="kpi"><div class="k">5年 20/80 年化</div><div class="v c-up">+4.61%</div><div class="d">2 笔 · 持仓 46.8%</div></div>
  <div class="kpi"><div class="k">5年 25/75 年化</div><div class="v c-down">+1.96%</div><div class="d">2 笔 · 持仓 40.4%</div></div>
  <div class="kpi" style="border-color:#fecaca"><div class="k">5年 20/90 年化</div><div class="v c-up">+5.56%</div><div class="d">2 笔 · 随机胜率 69.5%</div></div>
  <div class="kpi"><div class="k">交易频率</div><div class="v">0.26 笔/年</div><div class="d">20/80，非高频</div></div>
</div>

<h2>一、阈值网格：收益最高的格子在哪</h2>
<div class="card"><div class="two">
  <div><h3>3 年 PE 窗口（年化 %）</h3><div id="h3" class="chart" style="height:330px"></div></div>
  <div><h3>5 年 PE 窗口（年化 %）</h3><div id="h5" class="chart" style="height:330px"></div></div>
</div><div class="note">横轴＝卖出分位，纵轴＝买入分位。红＝年化高，绿＝年化低/负。空格表示不满足买&lt;卖-20pp 的组合。</div></div>
<p>网格暴露出一个反直觉事实：<b>买入侧放宽几乎没用，卖出侧放宽才值钱</b>。5 年窗口里买 20→25 会让年化从 4.61% 掉到 3.44%（卖 80 不变），而卖 80→90 能把 4.61% 抬到 5.56%。3 年窗口同理：买 20→25 从 4.99% 掉到 4.32%，卖 80→90 抬到 5.33%。</p>

<h2>二、候选阈值：全区间表现与逐笔交易</h2>
<div class="card"><h3>5 年 PE 窗口</h3><table>
<thead><tr><th class="nm">买/卖</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>持仓</th><th>笔数</th><th>笔/年</th><th>平均持有</th><th class="nm">逐笔（进→出，收益）</th></tr></thead>
<tbody>__C5__</tbody></table></div>
<div class="card"><h3>3 年 PE 窗口</h3><table>
<thead><tr><th class="nm">买/卖</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>持仓</th><th>笔数</th><th>笔/年</th><th>平均持有</th><th class="nm">逐笔（进→出，收益）</th></tr></thead>
<tbody>__C3__</tbody></table></div>
<p>25/75 的失败可以精确定位：5 年窗口第二次交易从 2022-03 买到 2024-09，收益 <b class="c-down">-4.85%</b>；而 20/80 从 2022-04 买到 2025-08，收益 <b class="c-up">+11.96%</b>。晚买一个月、晚卖十一个月，差了 16.8 个百分点。买入阈值放宽 5pp 提前接飞刀，卖出阈值收紧 5pp 提前离场，两头都吃亏。</p>

<h2>三、净值曲线</h2>
<div class="card"><div id="eq" class="chart"></div>
<div class="note">起点归一化 1。20/90 在 2025-08 之后继续持有到 2026-01 才卖出，多吃到一段反弹；25/75 则在 2024-09 已离场。</div></div>

<h2>四、随机测试：放宽后是否仍稳健</h2>
<div class="card"><div id="mc" class="chart"></div>
<div class="note">每个阈值 1500×4＝6000 次模拟：随机起点 + 随机持有期 12/24/36/60 月，与同窗口买入持有对比。</div></div>
<div class="card"><h3>5 年窗口</h3><table>
<thead><tr><th class="nm">买/卖</th><th>胜率</th><th>中位年化</th><th>基准中位</th><th>超额中位</th><th>平均持仓</th><th>零交易</th></tr></thead>
<tbody>__M5__</tbody></table>
<h3>3 年窗口</h3><table>
<thead><tr><th class="nm">买/卖</th><th>胜率</th><th>中位年化</th><th>基准中位</th><th>超额中位</th><th>平均持仓</th><th>零交易</th></tr></thead>
<tbody>__M3__</tbody></table></div>
<p>样本内的最高年化是 5 年 35/90（<b>+6.79%</b>），但随机胜率只有 <b>64.8%</b>、中位年化 2.11%，都不如 20/90（69.5% / 2.73%）。这说明样本内最高点<b>带过拟合味道</b>：它依赖 2019 年一整段在场。跨起点验证后，20/90 才是"样本内外一致更好"的阈值。</p>

<h2>五、牛熊偏移与捕获率</h2>
<div class="card"><div id="cap" class="chart"></div>
<div class="note">上行/下行捕获率＝上涨月（或下跌月）里策略平均收益 ÷ 基准平均收益。1.0 表示完全跟随。</div></div>
<div class="card"><table>
<thead><tr><th class="nm">买/卖</th><th>上行捕获</th><th>下行捕获</th><th>差值</th><th>上涨月持仓</th><th>下跌月持仓</th><th>牛市持仓</th><th>牛市月均</th><th>熊市持仓</th><th>熊市月均</th></tr></thead>
<tbody>__CAP5__</tbody></table>
<div class="note">牛熊为事前划分：36 月滚动峰值算回撤，收盘&gt;12 月均线且回撤&gt;-15% 为牛，回撤≤-20% 为熊，其余震荡。基准牛市月均 +0.57%、熊市月均 +0.73%、震荡月均 -0.73%。</div></div>
<p><b>偏移是结构性的，不是运气。</b>PE 分位是逆向指标：越跌越便宜→越该买，越涨越贵→越该卖。所以策略天然在上涨月只参与约 40%~50%、在下跌月只参与 30%~45%，在牛市里系统性低配。5 年 20/80 的牛市持仓只有 18.6%，牛市月均 +0.51% 略低于基准 +0.57%；而震荡段（基准月均 -0.73%）策略月均 +0.39%，超额全靠这里。</p>
<p>放宽买入侧会加重偏移：25/75 的上行捕获掉到 0.51、下行捕获升到 0.47，几乎是"涨跌都少赚"，失去择时意义。放宽卖出侧则相反：20/90 上行捕获 0.63、下行 0.45，差值从 0.14 扩到 0.18。</p>

<h2>六、牛熊段落：入场是否迟到、离场是否过早</h2>
<div class="card"><table>
<thead><tr><th class="nm">状态</th><th>区间</th><th>月数</th><th>基准</th><th>20/80</th><th>前3月持仓</th><th>后续持仓</th></tr></thead>
<tbody>__EP__</tbody></table>
<div class="note">5 年窗口、20/80 阈值。前 3 月持仓低＝进场滞后；后续持仓骤降＝牛市中提前离场。</div></div>
<p>两段牛市都暴露了"早退"：2020-06~2021-07 基准 +15.5%、策略 +12.6%，前 3 个月只持仓 33%；2025-05~2026-07 基准 +19.5%、策略 +17.0%，前 3 个月满仓但之后清零。反过来，熊市 2022-07~2024-09 策略与基准同为 -3.7%，满仓扛着——这套规则躲的是"高估值"，不是"下跌趋势"本身。</p>

<h2>七、操作含义</h2>
<div class="card"><ul>
<li><b>不要把 20/80 同时放宽到 25/75。</b>它会把卖出提前约 11 个月，样本内外一致变差。</li>
<li><b>若追求年化，建议改为"买 20% 不变、卖 85%~90%"</b>。5 年 20/90 的最佳组合来自 2 笔交易，仍需接受样本量极小的风险；保守做法可用 85%（年化 5.00%、随机胜率介于两者）。</li>
<li><b>3 年窗口同样适用</b>：20/90 年化 5.33%、随机胜率 67.2%，比 20/80 略好但改善幅度小于 5 年。</li>
<li><b>要接受牛市跑输</b>。这套规则在上涨月的捕获率只有 0.58~0.63，牛市必然跑不满；它的价值在震荡/下跌前的高估值阶段。若无法忍受连续一年空仓看着指数上涨，这套方法不适用。</li>
<li><b>交易频率不是问题</b>。20/80 每年 0.26 笔、25/75 也只有 2 笔，不存在换手过高或成本侵蚀；真正稀缺的是独立决策点（7.8 年 2 次），任何阈值优化都逃不开这个样本量约束。</li>
</ul></div>

<div class="dis" style="margin-top:22px">
<b>免责声明</b>：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。
</div>
<div class="note">数据源：本地 SQLite <code>data/ashare.db</code> → <code>val_index_pe_lg</code>（沪深300 PE-TTM 加权，2019-01~2026-11-20）· 脚本 <code>scripts/backtest_pe_thresholds.py</code> · 生成 2026-11-23</div>

</div>
<script>
var D = __DATA__;
function heatOpt(id, arr, title){
  return {
    tooltip: { position: 'top', formatter: function(p){ return '买 ' + D.buys[p.value[1]] + '% / 卖 ' + D.sells[p.value[0]] + '% : ' + p.value[2].toFixed(2) + '%'; } },
    grid: { left: 52, right: 14, top: 14, bottom: 34 },
    xAxis: { type: 'category', data: D.sells, name: '卖出%', splitArea: { show: true } },
    yAxis: { type: 'category', data: D.buys, name: '买入%', splitArea: { show: true } },
    visualMap: { min: -1, max: 7, calculable: false, orient: 'horizontal', left: 'center', bottom: 0,
      itemWidth: 12, itemHeight: 100, text: ['高', '低'],
      inRange: { color: ['#1b7f4e', '#d1d5db', '#fca5a5', '#c62828'] } },
    series: [{ name: title, type: 'heatmap', data: arr,
      label: { show: true, fontSize: 10, formatter: function(p){ return p.value[2].toFixed(1); } },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.3)' } } }]
  };
}
echarts.init(document.getElementById('h3')).setOption(heatOpt('h3', D.heat3, '3年'));
echarts.init(document.getElementById('h5')).setOption(heatOpt('h5', D.heat5, '5年'));

echarts.init(document.getElementById('eq')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['买入持有','20/80','25/75','20/90','35/90'], top: 0 },
  grid: { left: 52, right: 24, top: 44, bottom: 32 },
  xAxis: { type: 'category', data: D.ym, axisLabel: { interval: 11 } },
  yAxis: { type: 'value', name: '净值', scale: true },
  series: [
    { name: '买入持有', type: 'line', data: D.bh, symbol: 'none', lineStyle: { width: 1.6, type: 'dashed', color: '#0f172a' }, itemStyle: { color: '#0f172a' } },
    { name: '20/80', type: 'line', data: D.curves['20/80'], symbol: 'none', lineStyle: { width: 2, color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
    { name: '25/75', type: 'line', data: D.curves['25/75'], symbol: 'none', lineStyle: { width: 2, color: '#1b7f4e' }, itemStyle: { color: '#1b7f4e' } },
    { name: '20/90', type: 'line', data: D.curves['20/90'], symbol: 'none', lineStyle: { width: 2.8, color: '#c62828' }, itemStyle: { color: '#c62828' } },
    { name: '35/90', type: 'line', data: D.curves['35/90'], symbol: 'none', lineStyle: { width: 1.6, color: '#7c3aed', type: 'dotted' }, itemStyle: { color: '#7c3aed' } }
  ]
});

var TH = ['20/80','25/75','30/70','35/65','20/90','35/90'];
echarts.init(document.getElementById('mc')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['随机胜率','中位年化'], top: 0 },
  grid: { left: 52, right: 62, top: 44, bottom: 32 },
  xAxis: { type: 'category', data: TH },
  yAxis: [
    { type: 'value', name: '胜率 %', min: 50, max: 75 },
    { type: 'value', name: '年化 %', splitLine: { show: false } }
  ],
  series: [
    { name: '随机胜率', type: 'bar', data: D.mc5win, itemStyle: { color: '#93c5fd' },
      markLine: { silent: true, symbol: 'none', data: [{ yAxis: 66.5, lineStyle: { color: '#cbd5e1', type: 'dashed' }, label: { formatter: '20/80基准', fontSize: 10 } }] } },
    { name: '中位年化', type: 'line', yAxisIndex: 1, data: D.mc5med, symbol: 'circle', symbolSize: 7,
      lineStyle: { width: 2.4, color: '#c62828' }, itemStyle: { color: '#c62828' } }
  ]
});

echarts.init(document.getElementById('cap')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['上行捕获','下行捕获'], top: 0 },
  grid: { left: 52, right: 20, top: 44, bottom: 32 },
  xAxis: { type: 'category', data: TH },
  yAxis: { type: 'value', name: '捕获率', max: 1 },
  series: [
    { name: '上行捕获', type: 'bar', data: D.up5, itemStyle: { color: '#c62828' },
      markLine: { silent: true, symbol: 'none', data: [{ yAxis: 1, lineStyle: { color: '#94a3b8', type: 'dashed' }, label: { formatter: '完全跟随', fontSize: 10 } }] } },
    { name: '下行捕获', type: 'bar', data: D.dn5, itemStyle: { color: '#1b7f4e' } }
  ]
});

window.addEventListener('resize', function(){
  ['h3','h5','eq','mc','cap'].forEach(function(id){
    var el = document.getElementById(id);
    if (el) { var c = echarts.getInstanceByDom(el); if (c) c.resize(); }
  });
});
</script>
</body></html>"""

html = (HTML
        .replace("__PERIOD__", meta["period"])
        .replace("__MONTHS__", str(meta["months"]))
        .replace("__Y__", str(meta["years"]))
        .replace("__C5__", cand_rows(C5)).replace("__C3__", cand_rows(C3))
        .replace("__M5__", mc_rows("5y")).replace("__M3__", mc_rows("3y"))
        .replace("__CAP5__", cap_rows("5y"))
        .replace("__EP__", ep_rows("5y_20/80"))
        .replace("__DATA__", D))
open(OUT, "w", encoding="utf-8").write(html)
print("written", OUT, len(html))
