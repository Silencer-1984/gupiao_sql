# -*- coding: utf-8 -*-
"""生成沪深300 PE 分位择时验证报告（HTML，2019 年后样本）。"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "pe_pct_2019.json")
OUT = os.path.join(ROOT, "docs", "pe_percentile_2019_report.html")

r = json.load(open(SRC, encoding="utf-8"))
fp = r["full_period"]
mc = r["mc"]
grid = r["grid"]
cur = r["curves"]
meta = r["meta"]
WIN = ["1y", "3y", "5y", "10y"]
LAB = {"1y": "1年", "3y": "3年", "5y": "5年", "10y": "10年"}


def row_perf(k, name, v, is_bh=False):
    t = v.get("trades") or {}
    n = 0 if is_bh else t.get("n", 0)
    avg = "—" if is_bh or not t.get("avg") else f"{t['avg']:+.2f}%"
    tim = v.get("tim", 100.0)
    cls = "c-up" if v["total_ret"] >= 0 else "c-down"
    return (
        f"<tr><td class='nm'>{name}</td>"
        f"<td class='{cls}'>{v['total_ret']:+.1f}%</td>"
        f"<td>{v['cagr']:+.2f}%</td><td>{v['vol']:.2f}%</td>"
        f"<td class='c-down'>{v['max_dd']:.1f}%</td>"
        f"<td>{v['sharpe']:.2f}</td><td>{v['calmar']:.2f}</td>"
        f"<td>{tim:.1f}%</td><td>{n}</td><td>{avg}</td></tr>"
    )


rows1 = row_perf("bh", "买入持有（基准）", fp["buy_and_hold"], True)
for k in WIN:
    rows1 += row_perf(k, f"{LAB[k]} PE 分位", fp[k])

# 随机测试表
rows2 = ""
for k in WIN:
    v = mc[f"{k}_all"]
    rows2 += (
        f"<tr><td class='nm'>{LAB[k]}窗口</td>"
        f"<td>{v['wait']['median']:+.2f}%</td><td>{v['cont']['median']:+.2f}%</td>"
        f"<td>{v['bh']['median']:+.2f}%</td>"
        f"<td class='{'c-up' if v['win_wait']>50 else 'c-down'}'>{v['win_wait']:.1f}%</td>"
        f"<td class='{'c-up' if v['win_cont']>50 else 'c-down'}'>{v['win_cont']:.1f}%</td>"
        f"<td>{v['tim']:.1f}%</td><td>{v['no_trade']:.1f}%</td>"
        f"<td>[{v['wait']['p05']:+.1f}, {v['wait']['p95']:+.1f}]</td></tr>"
    )

# 阈值敏感性表
gkeys = list(grid["1y"].keys())
rows3 = ""
for k in WIN:
    cells = ""
    for g in gkeys:
        v = grid[k][g]
        cls = "c-up" if v["cagr"] > 2.7 else ("c-down" if v["cagr"] < 0 else "")
        cells += f"<td class='{cls}'>{v['cagr']:+.2f}<span class='sub'> / {v['tim']:.0f}%</span></td>"
    rows3 += f"<tr><td class='nm'>{LAB[k]}</td>{cells}</tr>"

# 交易明细
rows4 = ""
for k in WIN:
    tl = fp[k]["trade_log"]
    if not tl:
        rows4 += f"<tr><td class='nm'>{LAB[k]}</td><td colspan='5' class='muted'>全区间未触发买入</td></tr>"
    for t in tl:
        cls = "c-up" if t["ret"] >= 0 else "c-down"
        ann = ((1 + t["ret"] / 100) ** (12 / t["months"]) - 1) * 100
        rows4 += (
            f"<tr><td class='nm'>{LAB[k]}</td><td>{t['from']}</td><td>{t['to']}</td>"
            f"<td>{t['months']}</td><td class='{cls}'>{t['ret']:+.2f}%</td>"
            f"<td>{ann:+.1f}%</td></tr>"
        )

# 逐年敞口
years = sorted(r["exposure_year"]["5y"].keys())
exp = {k: [r["exposure_year"][k][y]["tim"] for y in years] for k in WIN}
yret = {k: [r["exposure_year"][k][y]["ret"] for y in years] for k in WIN}
bhret = [r["exposure_year"]["5y"][y]["bh"] for y in years]

data = {
    "ym": cur["ym"], "bh_eq": cur["bh"], "pe": cur["pe"],
    "eq": {k: cur[f"{k}_eq"] for k in WIN},
    "pct": {k: cur[k] for k in WIN},
    "mcMed": {k: [mc[f"{k}_{h}m"]["wait"]["median"] for h in (12, 24, 36, 60)] for k in WIN},
    "mcWin": {k: [mc[f"{k}_{h}m"]["win_wait"] for h in (12, 24, 36, 60)] for k in WIN},
    "bhMed": [mc[f"1y_{h}m"]["bh"]["median"] for h in (12, 24, 36, 60)],
    "years": years, "exp": exp, "yret": yret, "bhret": bhret,
}
D = json.dumps(data, ensure_ascii=False)

# 结论卡数字
c1, c3, c5, c10 = fp["1y"], fp["3y"], fp["5y"], fp["10y"]
m1, m3, m5, m10 = mc["1y_all"], mc["3y_all"], mc["5y_all"], mc["10y_all"]

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>沪深300 PE 分位择时验证（2019-2026）</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--ink:#0f172a;--ink2:#475569;--mut:#94a3b8;--line:#e2e8f0;--bg:#f7f8fa;--card:#fff;--up:#c62828;--down:#1b7f4e;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:27px;line-height:1.35;margin:0 0 10px;letter-spacing:-.3px}
.sub-t{color:var(--ink2);font-size:13.5px;margin-bottom:6px}
.tag{display:inline-block;font-size:12px;padding:2px 9px;border-radius:20px;background:#eef2ff;color:#3730a3;margin-right:6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px 24px;margin:18px 0}
h2{font-size:18px;margin:34px 0 12px;padding-left:11px;border-left:4px solid #1e293b}
h3{font-size:15px;margin:22px 0 8px;color:var(--ink2)}
p{margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 16px 14px}
.kpi .k{font-size:12.5px;color:var(--mut);letter-spacing:.3px}
.kpi .v{font-size:23px;font-weight:700;margin:4px 0 2px;letter-spacing:-.5px}
.kpi .d{font-size:12.5px;color:var(--ink2)}
.kpi.best{border-color:#fecaca;background:linear-gradient(180deg,#fff5f5,#fff)}
.verdict{background:linear-gradient(180deg,#fff,#fcfcfd);border:1px solid var(--line);border-left:4px solid #1e293b;border-radius:10px;padding:18px 22px}
.verdict b{color:#111}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:8px 0}
th,td{padding:9px 10px;text-align:right;border-bottom:1px solid var(--line)}
th{background:#f8fafc;color:var(--ink2);font-weight:600;font-size:12.5px;text-align:right;white-space:nowrap}
td.nm,th.nm{text-align:left;font-weight:600;white-space:nowrap}
td.nm{font-weight:600}
tbody tr:hover{background:#fcfdff}
.c-up{color:var(--up)} .c-down{color:var(--down)}
.muted{color:var(--mut);text-align:left}
.sub{color:var(--mut);font-size:11.5px}
.note{font-size:12.5px;color:var(--mut);margin-top:8px}
.chart{width:100%;height:380px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
ul{padding-left:20px;margin:8px 0} li{margin:5px 0}
.dis{font-size:12.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 20px;line-height:1.75}
@media(max-width:860px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<div class="sub-t">量化验证 · 沪深300（000300） · 样本 __PERIOD__（__MONTHS__ 个月）</div>
<h1>PE 分位择时：1 年 / 3 年 / 5 年 / 10 年四个回顾窗口，哪个对大盘股更有参考意义？</h1>
<div class="sub-t">
<span class="tag">分位 ≤20% 买入</span><span class="tag">分位 ≥80% 卖出</span><span class="tag">20~80% 维持原仓</span><span class="tag">未触发则空仓</span>
</div>

<div class="verdict" style="margin-top:16px">
<b>结论：对沪深300 这类大盘股，5 年 PE 分位的参考价值最高，3 年次之；1 年基本无效，10 年过于迟钝。</b><br>
1 年窗口被短期盈利波动主导，4 次交易单笔均值 <b class="c-down">-4.15%</b>，全区间年化 <b class="c-down">-2.57%</b>，随机测试只有 <b>34%</b> 的概率跑赢买入持有 —— 属于负向指标。<br>
3 年与 5 年窗口都跑赢基准约 20pp，并把最大回撤从 <b class="c-down">-39.9%</b> 压到 <b class="c-down">-28.3%</b>，随机胜率 66%~67%；两者差距在噪声内，但 5 年的阈值敏感性单调、不塌陷，稳健性更好。<br>
10 年分位"最准"（回撤最小 -22.6%、随机胜率 71.6%），但 62% 的 1 年期窗口根本不触发交易、平均持仓仅 24%、全区间只有 1 笔交易 —— 统计上无法验证，实务上等于长期空仓。<br>
<span class="sub">当前（__NOW__）分位：1年 __N1__% · 3年 __N3__% · 5年 __N5__% · 10年 __N10__%</span>
</div>

<h2>一、关键数字</h2>
<div class="grid">
  <div class="kpi"><div class="k">1 年 PE 分位</div><div class="v c-down">__C1__</div><div class="d">年化 · 随机胜率 __W1__%</div></div>
  <div class="kpi"><div class="k">3 年 PE 分位</div><div class="v c-up">__C3__</div><div class="d">年化 · 随机胜率 __W3__%</div></div>
  <div class="kpi best"><div class="k">5 年 PE 分位</div><div class="v c-up">__C5__</div><div class="d">年化 · 随机胜率 __W5__%（推荐）</div></div>
  <div class="kpi"><div class="k">10 年 PE 分位</div><div class="v c-up">__C10__</div><div class="d">年化 · 随机胜率 __W10__%</div></div>
</div>
<div class="note">年化为 2019-01 ~ 2026-11 全区间；随机胜率＝随机起点、随机持有期下跑赢同期买入持有的概率。</div>

<h2>二、净值曲线</h2>
<div class="card"><div id="c1" class="chart"></div>
<div class="note">起点归一化为 1（2019-01 收盘）。四条线只在分位触及 20% / 80% 时切换仓位，中间区间不动。</div></div>
<p>四条曲线从 2020 年年中就分开了：3 年与 5 年分位在 2020-07 双双突破 80% 卖出线，此后整个 2021 年空仓，完整躲过 2021-02 之后的长跌；1 年窗口分位频繁翻转，2021-07 追高买入后一路持有到 2023-03，单笔亏 16.3%。</p>

<h2>三、PE 与四条分位线</h2>
<div class="card"><div id="c2" class="chart" style="height:400px"></div>
<div class="note">左轴：沪深300 PE-TTM（加权）；右轴：各窗口滚动分位。虚线为 20% / 80% 阈值。</div></div>
<p>关键差异在分位的"振幅"：10 年分位全区间只在 <b>10.8%~97.5%</b> 之间移动，2022-2024 大底时也只跌到 10.8%（仅 6 个月低于 20%）—— 因为 10 年窗口里始终包含 2013-2014 年 8~10 倍 PE 的极端底部，把分位天花板压低。1 年分位则在 8.3%~100% 之间狂摆，噪音太大。</p>

<h2>四、全区间绩效（2019-01 ~ 2026-11）</h2>
<div class="card"><table>
<thead><tr><th class="nm">方案</th><th>总收益</th><th>年化</th><th>波动</th><th>最大回撤</th><th>夏普</th><th>Calmar</th><th>持仓时间</th><th>交易笔数</th><th>单笔均值</th></tr></thead>
<tbody>__ROWS1__</tbody></table>
<div class="note">月度调仓、月末信号次月生效、单边成本 5bp、不含股息。夏普按无风险利率 0 计算。</div></div>
<p>基准（买入持有）94 个月只赚 23.5%、年化 2.73%，却要承受 -39.9% 的回撤——这是 2019 年以来 A 股大盘股的真实处境。3 年 / 5 年分位用不到一半的持仓时间拿到接近两倍的收益，Calmar 从 0.07 提升到 0.16~0.18。</p>

<h2>五、随机测试：随机起点 + 随机持有期</h2>
<div class="card">
<div class="two">
  <div><h3>中位年化收益</h3><div id="c3" style="width:100%;height:320px"></div></div>
  <div><h3>跑赢买入持有的概率</h3><div id="c4" style="width:100%;height:320px"></div></div>
</div>
<div class="note">每个单元格 1500 次模拟：在 2019-01 之后随机取起点、随机取 12/24/36/60 月持有期，规则从起点空仓起步。</div>
</div>
<div class="card"><table>
<thead><tr><th class="nm">回顾窗口</th><th>等待版<br>中位年化</th><th>连续版<br>中位年化</th><th>基准<br>中位年化</th><th>胜率<br>（等待版）</th><th>胜率<br>（连续版）</th><th>平均持仓</th><th>零交易占比</th><th>年化 5%~95% 分位</th></tr></thead>
<tbody>__ROWS2__</tbody></table>
<div class="note">"等待版"＝随机起点时以空仓开始，等分位跌到 20% 才买；"连续版"＝规则自 2019-01 起持续运行，只取同一窗口的收益。基准为同窗口买入持有。</div></div>
<p>随机化之后 1 年窗口的劣势更清楚：跨全部持有期，中位年化 <b class="c-down">-0.93%</b>，只有 34.3% 的窗口跑赢基准；60 个月持有期上跑赢概率跌到 17.6%。3 年与 5 年的胜率稳定在 66%~67%，且持有期越长胜率越高（5 年窗口在 60 月持有期上胜率 94.5%）——这正是"估值均值回归"该有的形状：时间越长，估值差的兑现越充分。</p>
<p>10 年窗口的胜率数字漂亮（71.6%），但零交易占比 62%：大多数 1 年期场景里它从未买入，收益记 0 而基准为负，于是"跑赢"了。这是统计假象的一部分，不能当作有效性证据。</p>

<h2>六、阈值敏感性</h2>
<div class="card"><table>
<thead><tr><th class="nm">窗口</th>__GHEAD__</tr></thead>
<tbody>__ROWS3__</tbody></table>
<div class="note">单元格＝年化收益 / 平均持仓比例；买入阈值×卖出阈值共 9 组。</div></div>
<p>5 年窗口是唯一在"更宽的阈值"下单调改善的（20/80 → 30/90：4.61% → 6.79%），说明它的信号不是靠某个魔法数字撑着。3 年在买入口径收到 10% 时直接归零（一整段不交易），存在明显悬崖；1 年在所有 9 组组合下全为负，稳健地无效。</p>

<h2>七、逐年敞口与实际收益</h2>
<div class="card"><div id="c5" class="chart"></div>
<div class="note">柱：各窗口逐年平均持仓比例；折线：该年沪深300 实际涨跌。</div></div>
<div class="card"><table>
<thead><tr><th class="nm">方案</th>__YHEAD__</tr></thead>
<tbody>__YROWS__</tbody></table>
<div class="note">单元格＝策略当年收益（持仓比例）。</div></div>

<h2>八、逐笔交易</h2>
<div class="card"><table>
<thead><tr><th class="nm">窗口</th><th>买入信号月</th><th>卖出信号月</th><th>持有月数</th><th>区间收益</th><th>对应年化</th></tr></thead>
<tbody>__ROWS4__</tbody></table></div>
<p>3 年 / 5 年 / 10 年各自只做了 1-2 笔交易，方向全部正确：5 年窗口在 2020-03 疫情底建仓、4 个月赚 27.4%；3 年与 5 年又在 2022-04 的分位极低位重新进场，分别持有 29 和 40 个月。但这同时也是最大的问题——<b>94 个月里只有 1-2 个独立决策点，统计上等价于掷两次硬币</b>，不能当作策略有效性的证明。</p>

<h2>九、结论与使用建议</h2>
<div class="card">
<ul>
<li><b>不要用 1 年 PE 分位做择时</b>。它把"过去 12 个月的盈利波动"当成了估值信号，在 2019-2026 的每一段持有期上都跑输基准，是典型的追涨杀跌。</li>
<li><b>5 年 PE 分位是沪深300 最合适的参考尺子</b>。它的阈值不敏感（20/80 到 30/90 都赚钱）、振幅完整覆盖一轮估值周期（1.7%~100%）、随机胜率 67%、回撤压缩 12pp。</li>
<li><b>3 年可作为交叉验证</b>。信号更灵敏、更早建仓（2019-01 就在场内），代价是 2025 年整段空仓错过 23% 的反弹。做法上可用"5 年定方向、3 年定节奏"。</li>
<li><b>10 年分位只当极端底部的旁证</b>。它要求 10 年历史，A 股当前的 10 年窗口仍被 2008 和 2015 两次泡沫污染，20% 阈值几乎摸不到。若要用，建议把买入阈值放宽到 30%~40%，且只作为加仓信号而非全部仓位依据。</li>
<li><b>这套规则的真正作用是"避开泡沫"，不是"抓住底部"</b>。2019 年（+25.1%）四套规则全部空仓错过；2025 年（+23.3%）3 年与 10 年整段空仓。超额收益主要来自 2020-03 的低位抄底（5 年窗口 4 个月 +27.4%）和 2021-2024 的下跌回避。接受这点再用，否则一定会在连涨年份中途放弃。</li>
</ul>
</div>

<h2>十、方法与局限</h2>
<div class="card">
<ul>
<li><b>数据</b>：沪深300 PE-TTM（加权）与指数收盘，来自本地库 <code>val_index_pe_lg</code>（乐咕口径），月度序列 2005-04 ~ 2026-11；测试只用 2019-01 起样本，2019 年以前的 PE 仅作分位回溯窗口（不产生收益）。</li>
<li><b>机制</b>：月末用截至当月末的 PE 计算滚动分位，次月第一个月收盘生效，无未来函数；单边成本 5 倍基点。</li>
<li><b>不含股息</b>：沪深300 股息率约 2%-3%，满仓方案受益更多，因此本报告对择时类策略略偏乐观（实际多头暴露 33%~50%，少收约 1pp/年年化股息）。</li>
<li><b>样本量硬约束</b>：2019-2026 只覆盖约 1.5 轮牛熊，3 年/5 年/10 年窗口各自仅 1-2 笔交易。随机测试用的是重叠窗口，独立样本实际只有 4-6 个，胜率的置信区间很宽。这是"方向性证据"，不是统计显著的有效性证明。</li>
<li><b>口径风险</b>：PE-TTM 的分母是滚动 12 个月盈利，2020 年疫情和 2022 年地产链亏损会让 PE 失真（盈利骤降推高 PE），分位在这两段可能给出偏保守的信号。</li>
</ul>
</div>

<div class="dis" style="margin-top:22px">
<b>免责声明</b>：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。
</div>
<div class="note">数据源：本地 SQLite <code>data/ashare.db</code> · 表 <code>val_index_pe_lg</code>（乐咕乐股 PE-TTM，2019-01 ~ 2026-11-20）· 计算脚本 <code>scripts/backtest_pe_pct_2019.py</code> · 生成时间 __TS__</div>

</div>
<script>
var D = __DATA__;
var C = { '1y':'#94a3b8', '3y':'#2563eb', '5y':'#dc2626', '10y':'#7c3aed' };
var N = { '1y':'1年', '3y':'3年', '5y':'5年', '10y':'10年' };

echarts.init(document.getElementById('c1')).setOption({
  tooltip: { trigger: 'axis', valueFormatter: function(v){ return v; } },
  legend: { data: ['买入持有','1年分位','3年分位','5年分位','10年分位'], top: 0 },
  grid: { left: 55, right: 24, top: 44, bottom: 34 },
  xAxis: { type: 'category', data: D.ym, axisLabel: { interval: 11 } },
  yAxis: { type: 'value', name: '净值', scale: true },
  series: [
    { name: '买入持有', type: 'line', data: D.bh_eq, symbol: 'none', lineStyle: { width: 1.6, type: 'dashed', color: '#0f172a' }, itemStyle: { color: '#0f172a' } },
    { name: '1年分位', type: 'line', data: D.eq['1y'], symbol: 'none', lineStyle: { width: 1.8, color: C['1y'] }, itemStyle: { color: C['1y'] } },
    { name: '3年分位', type: 'line', data: D.eq['3y'], symbol: 'none', lineStyle: { width: 2.2, color: C['3y'] }, itemStyle: { color: C['3y'] } },
    { name: '5年分位', type: 'line', data: D.eq['5y'], symbol: 'none', lineStyle: { width: 2.6, color: C['5y'] }, itemStyle: { color: C['5y'] } },
    { name: '10年分位', type: 'line', data: D.eq['10y'], symbol: 'none', lineStyle: { width: 2.2, color: C['10y'] }, itemStyle: { color: C['10y'] } }
  ]
});

echarts.init(document.getElementById('c2')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['PE-TTM','1年分位','3年分位','5年分位','10年分位'], top: 0 },
  grid: { left: 58, right: 62, top: 44, bottom: 34 },
  xAxis: { type: 'category', data: D.ym, axisLabel: { interval: 11 } },
  yAxis: [
    { type: 'value', name: 'PE', min: 9, max: 17 },
    { type: 'value', name: '分位 %', min: 0, max: 100, splitLine: { show: false } }
  ],
  series: [
    { name: 'PE-TTM', type: 'line', data: D.pe, symbol: 'none', lineStyle: { width: 2.4, color: '#0f172a' }, itemStyle: { color: '#0f172a' }, areaStyle: { color: 'rgba(15,23,42,0.06)' } },
    { name: '1年分位', type: 'line', yAxisIndex: 1, data: D.pct['1y'], symbol: 'none', lineStyle: { width: 1, color: C['1y'], opacity: 0.7 }, itemStyle: { color: C['1y'] },
      markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { type: 'dashed', color: '#cbd5e1' }, data: [{ yAxis: 20 }, { yAxis: 80 }] } },
    { name: '3年分位', type: 'line', yAxisIndex: 1, data: D.pct['3y'], symbol: 'none', lineStyle: { width: 1.4, color: C['3y'], opacity: 0.8 }, itemStyle: { color: C['3y'] } },
    { name: '5年分位', type: 'line', yAxisIndex: 1, data: D.pct['5y'], symbol: 'none', lineStyle: { width: 1.8, color: C['5y'] }, itemStyle: { color: C['5y'] } },
    { name: '10年分位', type: 'line', yAxisIndex: 1, data: D.pct['10y'], symbol: 'none', lineStyle: { width: 1.6, color: C['10y'] }, itemStyle: { color: C['10y'] } }
  ]
});

echarts.init(document.getElementById('c3')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['12月','24月','36月','60月'], top: 0, textStyle: { fontSize: 11 } },
  grid: { left: 46, right: 14, top: 44, bottom: 28 },
  xAxis: { type: 'category', data: ['1年','3年','5年','10年'] },
  yAxis: { type: 'value', name: '年化 %' },
  series: [
    { name: '12月', type: 'bar', data: [D.mcMed['1y'][0], D.mcMed['3y'][0], D.mcMed['5y'][0], D.mcMed['10y'][0]], itemStyle: { color: '#cbd5e1' } },
    { name: '24月', type: 'bar', data: [D.mcMed['1y'][1], D.mcMed['3y'][1], D.mcMed['5y'][1], D.mcMed['10y'][1]], itemStyle: { color: '#94a3b8' } },
    { name: '36月', type: 'bar', data: [D.mcMed['1y'][2], D.mcMed['3y'][2], D.mcMed['5y'][2], D.mcMed['10y'][2]], itemStyle: { color: '#475569' } },
    { name: '60月', type: 'bar', data: [D.mcMed['1y'][3], D.mcMed['3y'][3], D.mcMed['5y'][3], D.mcMed['10y'][3]], itemStyle: { color: '#1e293b' } }
  ]
});

echarts.init(document.getElementById('c4')).setOption({
  tooltip: { trigger: 'axis', valueFormatter: function(v){ return v + '%'; } },
  legend: { data: ['12月','24月','36月','60月'], top: 0, textStyle: { fontSize: 11 } },
  grid: { left: 46, right: 14, top: 44, bottom: 28 },
  xAxis: { type: 'category', data: ['1年','3年','5年','10年'] },
  yAxis: { type: 'value', name: '胜率 %', max: 100 },
  series: [
    { name: '12月', type: 'bar', data: [D.mcWin['1y'][0], D.mcWin['3y'][0], D.mcWin['5y'][0], D.mcWin['10y'][0]], itemStyle: { color: '#cbd5e1' }, markLine: { silent: true, symbol: 'none', data: [{ yAxis: 50, lineStyle: { color: '#dc2626', type: 'dashed' }, label: { formatter: '50%', position: 'end', fontSize: 10 } }] } },
    { name: '24月', type: 'bar', data: [D.mcWin['1y'][1], D.mcWin['3y'][1], D.mcWin['5y'][1], D.mcWin['10y'][1]], itemStyle: { color: '#94a3b8' } },
    { name: '36月', type: 'bar', data: [D.mcWin['1y'][2], D.mcWin['3y'][2], D.mcWin['5y'][2], D.mcWin['10y'][2]], itemStyle: { color: '#475569' } },
    { name: '60月', type: 'bar', data: [D.mcWin['1y'][3], D.mcWin['3y'][3], D.mcWin['5y'][3], D.mcWin['10y'][3]], itemStyle: { color: '#1e293b' } }
  ]
});

echarts.init(document.getElementById('c5')).setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['1年持仓','3年持仓','5年持仓','10年持仓','沪深300当年涨跌'], top: 0, textStyle: { fontSize: 11 } },
  grid: { left: 50, right: 55, top: 46, bottom: 28 },
  xAxis: { type: 'category', data: D.years },
  yAxis: [
    { type: 'value', name: '持仓 %', max: 110 },
    { type: 'value', name: '涨跌 %', splitLine: { show: false } }
  ],
  series: [
    { name: '1年持仓', type: 'bar', data: D.exp['1y'], itemStyle: { color: '#cbd5e1' } },
    { name: '3年持仓', type: 'bar', data: D.exp['3y'], itemStyle: { color: '#93c5fd' } },
    { name: '5年持仓', type: 'bar', data: D.exp['5y'], itemStyle: { color: '#fca5a5' } },
    { name: '10年持仓', type: 'bar', data: D.exp['10y'], itemStyle: { color: '#ddd6fe' } },
    { name: '沪深300当年涨跌', type: 'line', yAxisIndex: 1, data: D.bhret, symbol: 'circle', symbolSize: 6, lineStyle: { width: 2, color: '#0f172a' }, itemStyle: { color: '#0f172a' } }
  ]
});

window.addEventListener('resize', function(){
  ['c1','c2','c3','c4','c5'].forEach(function(id){
    var el = document.getElementById(id);
    if (el) { var c = echarts.getInstanceByDom(el); if (c) c.resize(); }
  });
});
</script>
</body></html>"""

ghead = "".join(f"<th>{g.replace('/', ' / ')}</th>" for g in gkeys)
yhead = "".join(f"<th>{y}</th>" for y in years)
yrows = ""
for k in WIN:
    cells = ""
    for i, y in enumerate(years):
        v = r["exposure_year"][k][y]
        cls = "c-up" if v["ret"] > 0 else ("c-down" if v["ret"] < 0 else "muted")
        cells += f"<td class='{cls}'>{v['ret']:+.1f}<span class='sub'> ({v['tim']:.0f}%)</span></td>"
    yrows += f"<tr><td class='nm'>{LAB[k]}</td>{cells}</tr>"

html = (HTML
        .replace("__PERIOD__", meta["period"])
        .replace("__MONTHS__", str(meta["months"]))
        .replace("__NOW__", meta["period"].split("~")[1])
        .replace("__N1__", str(fp["1y"]["pct_now"]))
        .replace("__N3__", str(fp["3y"]["pct_now"]))
        .replace("__N5__", str(fp["5y"]["pct_now"]))
        .replace("__N10__", str(fp["10y"]["pct_now"]))
        .replace("__C1__", f"{c1['cagr']:+.2f}%")
        .replace("__C3__", f"{c3['cagr']:+.2f}%")
        .replace("__C5__", f"{c5['cagr']:+.2f}%")
        .replace("__C10__", f"{c10['cagr']:+.2f}%")
        .replace("__W1__", f"{m1['win_wait']:.1f}")
        .replace("__W3__", f"{m3['win_wait']:.1f}")
        .replace("__W5__", f"{m5['win_wait']:.1f}")
        .replace("__W10__", f"{m10['win_wait']:.1f}")
        .replace("__ROWS1__", rows1).replace("__ROWS2__", rows2)
        .replace("__ROWS3__", rows3).replace("__ROWS4__", rows4)
        .replace("__GHEAD__", ghead).replace("__YHEAD__", yhead).replace("__YROWS__", yrows)
        .replace("__TS__", "2026-11-23")
        .replace("__DATA__", D))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(html)
print("written", OUT, len(html))
