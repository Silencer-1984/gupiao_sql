# 策略文档总索引

> 整理时间：2026-11-24　共 50 份策略文档，从 `docs/` 移出按主题分 7 类。
> `docs/` 现在只剩 **9 份数据/工程文档**（数据字典、数据库清点、看板说明等）。
> 所有脚本输出路径已同步更新，重跑不会写回旧目录。

---

## 快速找策略

| 你想找什么 | 去哪个文件夹 | 从哪份开始读 |
|---|---|---|
| **定投纳指 / 159941 溢价** | [`01_nasdaq_dca/`](01_nasdaq_dca/) | `us_etf_premium_llm.md`（总纲，LLM 首选） |
| **红利怎么进场 / 什么时候离场** | [`02_dividend/`](02_dividend/) | `dividend_lowvol_strategy_draft.md`（v5 终稿） |
| **科创50 择时打法** | [`03_kc50/`](03_kc50/) | `kc50_strategy_llm.md`（总纲，读完即可复现） |
| **中国电信 / 中国移动** | [`04_telecom/`](04_telecom/) | `telecom_dual_dividend_stocks.md` |
| **有色金属** | [`05_nonferrous/`](05_nonferrous/) | `backtest_nonferrous_entry.md`（含 vs 科创50 对比） |
| **沪深300 择时** | [`06_hs300_timing/`](06_hs300_timing/) | `hs300_timing_summary.md` |
| **其他研究**（成长/价值轮动、恐慌度、北向、波段） | [`07_other_research/`](07_other_research/) | 按标题选 |

---

## 1. 纳指定投与溢价（20 份）

**总纲**：`us_etf_premium_llm.md`
**人读版结论**：`conclusion_summary.md`；**小白版**：`learning_premium_10years.md`

| 主题 | 文档 |
|---|---|
| 溢价机理 | `premium_trend_attribution.md`（超额 100% 来自溢价上涨）、`premium_regime_2026.md`（十年三阶段）、`ndx_premium_report.md`（历史溢价率） |
| 定投回测 | `backtest_dca_159941.md`（5/3年/半年）、`backtest_mc_dca.md`（随机3000组）、`backtest_1y_2021_2026.md`（60窗口）、`backtest_long3y.md`（三年5策略） |
| 策略变体 | `backtest_threshold_strategy.md`（**最优：溢价>5%暂停**）、`backtest_hybrid_dca.md`（最抗跌）、`backtest_tier_dca.md`（分档无效）、`backtest_reserve_fund.md`（备用金加码）、`backtest_intramonth_dip.md`（月内逢低）、`backtest_drawdown_vxn.md`（回撤阶梯+VXN）、`backtest_4strategies_ndx.md`（四类蒙特卡洛）、`dca_frequency_ndx.md`（月/周/日频率）、`relaxed_strategy_10y.md`（每年至少一次机会）、`verify_early_deploy.md`（早补是否=低点） |

## 2. 红利策略（4 份）

| 文档 | 内容 |
|---|---|
| `dividend_lowvol_strategy_draft.md` | **v5 终稿**：底仓入场/离场标准 |
| `dividend_score_log.md` | 每日打分日志（脚本 `scripts/dividend_score.py` 持续追加） |
| `dividend_yield_report.md` | 股息率 + 聚焦个股 + 纳指溢价率 |
| `strategy_logic_v1.md` | 买成长/买质量/什么时候卖——判断逻辑框架 |

## 3. 科创50（10 份）

**总纲**：`kc50_strategy_llm.md` — 读完这一页即可复现全部结论（S10进场+MA20离场，年化 11.84%，回撤 -28%）

| 主题 | 文档 |
|---|---|
| 因子与打分 | `kc50_factor_strategy.md`、`kc50_score_position_sizing.md`（移动止损+分批仓位） |
| 离场与止损 | `kc50_regime_stoploss.md`（分周期+移动止损5%→年化14.2%）、`kc50_hold_vs_timing.md`（一次性vs分批、底仓） |
| 实盘复盘 | `kc50_two_year_review.md`（2024-09~2026-11）、`kc50_vs_sse_comparison.md`（对比上证） |
| 事件/轮动 | `kc50_news_event_scoring.md`（AI新闻量化）、`kc50_rally_volume_analysis.md`（两次大涨量价）、`kc50_dividend_rotation.md`（离场→红利轮动） |

## 4. 电信/移动（1 份）

`telecom_dual_dividend_stocks.md` — 中国电信(601728) / 中国移动(600941)：非低波红利股分析

## 5. 有色金属（1 份）

`backtest_nonferrous_entry.md` — 入场时机策略 + 44次MA200逐笔明细 + **有色 vs 科创50 对比**（结论：科创50更适合）

## 6. 沪深300 择时（8 份）

`hs300_timing_summary.md`（汇总）、`backtest_pe_percentile_2019.md`、`backtest_pe_threshold_regime_2019.md`、`backtest_pe_entry_events_2019.md`、`backtest_factor_filters_2019.md`、`backtest_adaptive_interval_2013_2026.md`、`backtest_longhistory_2010_2026.md`、`backtest_review_2013_2026.md`

## 7. 其他研究（6 份）

`corr_growth_value.md`（成长/价值跷跷板）、`fear_report.md`（恐慌度体系）、`northbound_report.md`（北向资金）、`trend_rotation.md`（趋势周期）、`swing_point_scoring.md`、`upswing_factor_validation.md`（波段因子）

---

## docs/ 保留的 9 份（数据/工程，非策略）

`db_inventory.md`、`data_catalog.md`、`data_dictionary.md`、`data_quality_report.md`、`data_source_report.md`、`web_dashboard.md`、`gap_assessment.md`、`next_agent_prompt_v2.md`、`step_log.md`

---

## 维护规则

1. **新增策略报告**：放进对应分类文件夹，不要放 `docs/`。
2. **脚本输出路径**：已全部改为 `strategies/<分类>/xxx.md`，新增脚本照此写。
3. **用户偏好**：回测报告只输出 **一份 Markdown**，不生成 HTML / JSON / 图表（除非明确要求网页）。
4. 根目录 `AGENTS.md` / `README.md` 的文档地图已同步指向新路径。
