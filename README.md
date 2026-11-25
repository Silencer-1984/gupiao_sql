# A股风格轮动研究仓 · 纳指ETF溢价实验

本地数据仓（SQLite 59 表 / 128.0 万行）+ FastAPI 看板 + 50 份策略文档（按主题分类在 `strategies/`）。
核心问题：**QDII 场内 ETF 的溢价，到底会不会影响定投收益？**

---

## 快速开始

```bash
uv sync                        # 装依赖
uv run dash                    # 起看板 → http://127.0.0.1:8000
start.bat                      # Windows 一键（自动同步、建前端、找空闲端口、开浏览器）
uv run python scripts/daily_job.py   # 跑一次每日任务（采集舆情 + 生成总结 + 存快照）
```

> 环境：Python 3.13 + uv + pnpm。**不要用 pip / 全局 python。**

---

## 数据资产

| 项 | 规模 |
|---|---|
| 数据库 | `data/ashare.db`，**221 MB** |
| 表 | **58 张**，1,275,964 行 |
| 时间跨度 | 1990-12 ~ 2026-11（主要研究区间 2015-2026） |
| 指数 | A 股 11 个 + 美股 2 个（纳指100/纳指综合） |
| 个股 | 174 只（红利成分股 + 中国移动/电信）日线 45.8 万行 |
| 财报面板 | 沪深 A 股 5,233 只 × 47 个报告期 |
| 宏观 | 10 个指标（PMI/CPI/PPI/货币/社融/利率） |
| 衍生（自建） | 恐慌度 2.4 万行、QVIX 1.1 万行、股息率 1.1 万行、溢价对齐 2,740 行 |

分类明细见 [`docs/db_inventory.md`](docs/db_inventory.md)。

---

## 核心结论（六条）

**1. 溢价是乘数，不是成本**

```
你的收益 = (1 + 指数涨跌) × (1 + 卖出溢价) / (1 + 买入溢价)
```

两端溢价相同 → 完全中性；卖时更高 → 增益；卖时更低 → 损失。

**2. 场内 ETF 没有品种优势，每年还少赚 0.60pp**
汇率 + 管理费 + 跟踪误差 + 买卖价差。溢价不变时，它就是稳定小输。

**3. 过去几年"跑赢纳指"全部来自溢价上涨**
`场内 − 纳指 ≈ 1.05 × 溢价变化 − 0.60`（124 个一年期窗口，corr 0.594）。
溢价横盘的 2020-2024：场内胜率仅 45%，每年 −0.44pp。

**4. 十年三阶段**
2015-2019 折价/零溢价 → 2020-2024 横盘（2020-09 曾冲 18.6% 后回落）→ 2025-2026 结构性抬升（均值 0.97% → 10.58%，现在 18.8~21.5%）。

**5. 溢价由 QDII 额度决定，不由纳指决定**
额度堵死 → 套利机制失效 → 溢价能长期存在。与纳指涨跌相关仅 −0.06。

**6. 最优定投策略：溢价 ≤5% 投、>5% 暂停、最多等 3 月**
三年期均值 42.33%，35 个窗口里胜无脑 ETF 33 次（94%）。

---

## 文档索引

### 结论与方法
| 文档 | 讲什么 |
|---|---|
| [`strategies/01_nasdaq_dca/us_etf_premium_llm.md`](strategies/01_nasdaq_dca/us_etf_premium_llm.md) | **美股/纳指ETF 研究总纲：数据+方法+全部结果（LLM 首选）** |
| [`strategies/01_nasdaq_dca/conclusion_summary.md`](strategies/01_nasdaq_dca/conclusion_summary.md) | 所有结论汇总（人读版） |
| [`strategies/01_nasdaq_dca/learning_premium_10years.md`](strategies/01_nasdaq_dca/learning_premium_10years.md) | 溢价为什么影响收益（大白话 + 术语小抄） |
| [`strategies/01_nasdaq_dca/premium_trend_attribution.md`](strategies/01_nasdaq_dca/premium_trend_attribution.md) | 超额收益归因：253 个窗口的证据 |
| [`strategies/01_nasdaq_dca/premium_regime_2026.md`](strategies/01_nasdaq_dca/premium_regime_2026.md) | 政策前后溢价变化 + 未来情景预测 |

### 定投回测
| 文档 | 结论 |
|---|---|
| [`strategies/01_nasdaq_dca/backtest_dca_159941.md`](strategies/01_nasdaq_dca/backtest_dca_159941.md) | 5年/3年/半年：场内 +71% vs 纳指 +43% |
| [`strategies/01_nasdaq_dca/backtest_mc_dca.md`](strategies/01_nasdaq_dca/backtest_mc_dca.md) | 随机 3000 组：优势消失，A≈C |
| [`strategies/01_nasdaq_dca/backtest_1y_2021_2026.md`](strategies/01_nasdaq_dca/backtest_1y_2021_2026.md) | 60 个一年期窗口：胜率 58.3% |
| [`strategies/01_nasdaq_dca/backtest_threshold_strategy.md`](strategies/01_nasdaq_dca/backtest_threshold_strategy.md) | **阈值策略（推荐）** |
| [`strategies/01_nasdaq_dca/backtest_hybrid_dca.md`](strategies/01_nasdaq_dca/backtest_hybrid_dca.md) | 混合策略（最抗跌） |
| [`strategies/01_nasdaq_dca/backtest_long3y.md`](strategies/01_nasdaq_dca/backtest_long3y.md) | 三年期 5 策略 + 高低点入场 |
| [`strategies/01_nasdaq_dca/backtest_tier_dca.md`](strategies/01_nasdaq_dca/backtest_tier_dca.md) | 分档加码为什么无效 |

### 数据与看板
| 文档 | 内容 |
|---|---|
| [`docs/db_inventory.md`](docs/db_inventory.md) | 58 张表全量清点 |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | 字段级说明与数据源 |
| [`strategies/07_other_research/fear_report.md`](strategies/07_other_research/fear_report.md) | 恐慌度体系（QVIX + RV） |
| [`strategies/07_other_research/northbound_report.md`](strategies/07_other_research/northbound_report.md) | 北向资金（2024-08 断供） |
| [`docs/web_dashboard.md`](docs/web_dashboard.md) | 看板网站说明 |

---

## 看板长什么样

打开 http://127.0.0.1:8000 ：

- **顶部三卡**：风格策略（今日建议 + 相对强弱）、市场温度（0-100 仪表盘）、市场行情（上证/深证/成交额/量能/小盘风格）
- **风格建议**：成长（科创50+有色） vs 价值（红利），各自 0-100 分 + 档位
- **重点关注**：12 张行情小卡（含中国移动/电信/港股创新药/纳指+159941溢价），日周月年切换
- **舆情指数**：情绪分拆成「看法层（千股评+快讯多空）+ 表现层（涨跌）」
- **总结**：日/周/月，每晚 20:00 生成一次，其他时间读缓存

---

## 目录结构

```
panduan/
├── data/ashare.db          # 唯一数据源（221 MB）
├── server/                 # FastAPI（main.py 路由 + analytics.py 计算）
├── web/                    # React + ECharts 前端
├── scripts/                # 抓数 + 回测 + 每日任务
├── strategies/             # 50 份策略报告（7 类，先看 README.md）
│   ├── 01_nasdaq_dca/      # 纳指定投与溢价（20）
│   ├── 02_dividend/        # 红利策略（4）
│   ├── 03_kc50/            # 科创50（10）
│   ├── 04_telecom/         # 电信/移动（1）
│   ├── 05_nonferrous/      # 有色金属（1）
│   ├── 06_hs300_timing/    # 沪深300择时（8）
│   └── 07_other_research/  # 其他研究（6）
├── docs/                   # 9 份数据/工程文档
├── AGENTS.md               # 给 AI 的上手说明（新窗口先读这个）
├── start.bat / start.sh    # 一键启动
└── pyproject.toml          # uv 依赖
```

---

## 重要提醒

1. **159941 在 2022-07-05 做过 4:1 份额拆分**，算收益必须用复权序列 `close_adj` / `nav_adj`。
2. **溢价字段本身是百分数**（8.2 = 8.2%），别再乘 100。
3. **北向日频数据 2024-08-19 起停止披露**，接口返 0 是标志位不是真值。
4. 看板属本机自用，无登录、无鉴权，不要暴露到公网。

---

数据仅供研究，不构成投资建议。
