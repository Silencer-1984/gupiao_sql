# 图表页 · 数据与每日任务

> 线上只保留指数走势图表（PE / 股息率 / 溢价 / 分位），不含监测与策略。
> 目录 `deploy/chart/`，精简库 `data/chart.db`（7.6 MB）。

## 1. 标的（9 个）

| 类型 | 标的 | 代码 | 第二 Y 轴 |
|---|---|---|---|
| 宽基 | 沪深300 | 000300 | PE-TTM / 股债性价比 / 成交额 / 恐慌度 / 波动 |
| 宽基 | 上证指数 | 000001 | PE-TTM / 股债性价比 / 成交额 / 波动 |
| 价值 | 红利低波 | H30269 | 股息率 / 利差 / PE-TTM / 波动 |
| 成长 | 科创50 | 000688 | PE-TTM / 恐慌度 / 波动 |
| 成长 | 港股创新药 | 931787 | PE-TTM / 恐慌度 / 波动 |
| 周期 | 中证有色 | 000819 | PE-TTM / 恐慌度 / 波动 |
| 海外 | 纳斯达克100 | .NDX | **159941 溢价** / 波动 |
| 个股 | 中国电信 | 601728 | **股息率 / PE-TTM** / 波动 |
| 个股 | 中国移动 | 600941 | **股息率 / PE-TTM** / 波动 |

## 2. 最小数据名单（只需 9 张表）

| 表 | 图表用途 | 行数 | 更新来源 |
|---|---|---:|---|
| `px_index_daily_csi` | 6 个 A 股指数行情 + PE-TTM | 15,474 | 新浪日线 + 中证官网 PE |
| `px_index_daily_us` | 纳指 100 行情 | 3,210 | 纳指日线 |
| `val_index_dividend_yield` | 红利低波股息率 | 2,887 | `scripts/fetch_dividend_yield.py` |
| `mkt_fear_daily` | 恐慌度副轴 | 12,585 | `scripts/fetch_fear_index.py` |
| `macro_bond_yield` | 股债性价比 / 利差（10Y 国债） | 9,393 | 国债收益率 |
| `val_stock_dividend_yield_focus` | 电信/移动股息率 | 2,452 | `scripts/fetch_dividend_yield.py` |
| `val_stock_pe_daily` | 电信/移动 PE-TTM | 1,855 | `deploy/chart/fetch_stock_pe.py` |
| `px_stock_daily` | 电信/移动股价 | 2,452 | `scripts/fetch_dividend_yield.py` |
| `px_lof_daily` | 159941 溢价（premium_lag） | 2,740 | `scripts/fetch_nasdaq_premium.py` |

不再需要：`px_index_daily_cni`（无国证指数）、舆情/总结/快照等 `web_*` 表、其余 40+ 表。

## 3. 每日任务清单（一天一次）

```bash
# 一条命令跑完全部
uv run python deploy/chart/daily_update.py
```

内部顺序：

| # | 步骤 | 数据 | 失败影响 |
|---|---|---|---|
| 1 | 指数行情+PE（中证官网） | 沪深300 / 红利低波 / 科创50 / 港股创新药 / 中证有色 | 价格与 PE 不更新 |
| 1b | 上证指数（新浪） | 000001 收盘价 | 上证曲线不更新 |
| 2 | 159941 溢价 | `px_lof_daily.premium_lag` | 纳指溢价轴不更新 |
| 3 | 指数股息率 | 红利低波 `div_yield` | 红利股息轴不更新 |
| 4 | 个股 PE | `val_stock_pe_daily`（百度估值） | 电信/移动 PE 轴不更新 |
| 5 | 重建精简库 | `deploy/chart/data/chart.db` | 线上仍是旧库 |
| 6 | 构建前端 | `deploy/chart/static/` | 页面不更新 |

> 931787（港股创新药）与 H30269（红利低波）新浪无收录，行情由 `fetch_fear_index.py` / 中证官网补；缺失时该标的曲线停在上次日期，不影响其他标的。

## 4. 发布

```bash
# 构建产物已就绪后，让 AI 重新发布 deploy/chart 目录（覆盖同一链接）
```

线上地址：https://index-valuation-trend.app.workbuddy.host

## 5. 手动命令

```bash
uv run python deploy/chart/fetch_stock_pe.py     # 只补个股 PE
uv run python deploy/chart/build_db.py           # 只重建精简库
cd web && pnpm exec vite build --config vite.chart.config.js   # 只构建前端
```

## 6. 口径提醒

- 溢价用 `premium_lag`（A 股收盘时可观测），字段已是百分数。
- 个股 PE 来自百度股市通「市盈率(TTM)」，与中证指数 PE 口径不完全一致。
- 个股股息率来自滚动 252 交易日已实施分红 / 不复权收盘价。
- 159941 在 2022-07-05 做过 4:1 拆分；本页只用溢价，不涉及复权收益。
