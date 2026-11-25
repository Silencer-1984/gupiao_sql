# AGENTS.md — 给 AI 的上手说明

> 新窗口打开本项目时，**先读这一页**，不要在目录里乱找。
> 最后更新：2026-11-23 16:50

---

## 0. 一句话

A 股风格轮动研究项目：本地 SQLite 数据仓（59 表 / 128.0 万行）+ FastAPI 看板 + 大量回测脚本。
核心研究对象是 **159941（纳指 ETF）的溢价如何影响定投收益**，附带红利/成长/有色/港股创新药/恐慌度体系。

---

## 1. 环境与启动（只用 uv，不要用 pip）

```bash
uv sync                                  # 同步依赖（pyproject.toml + uv.lock）
uv run dash                              # 起看板 http://127.0.0.1:8000（含已构建前端）
uv run dash --reload                     # 后端热重载
uv run python scripts/xxx.py             # 跑脚本
cd web && pnpm build                     # 改前端后必须重建，8000 端口才会更新
start.bat                                # Windows 一键：uv sync → 建前端 → 找空闲端口 → 开浏览器
```

- Python 3.13，venv 在 `.venv`，**不要 `python`/`pip` 全局调用**
- 后端入口 `server/main.py`（`run()` 解析 `--host/--port/--reload`）
- 前端 `web/`（React 18 + ECharts 5 + **Ant Design 6** + Vite），UI 组件用 antd，产物 `web/dist`

### ⚠️ 改完网页必须自动把项目跑起来（用户验收要求）

**只要改动了 `web/` 下的任何前端文件，收尾时必须自己启动/确保服务在跑，并给出可点开的预览地址**，不要让用户自己去敲命令：

```bash
cd web && pnpm build                       # 1. 先重建前端（不重建 8000 端口看不到改动）
# 2. 确认 8000 端口是否已有服务；没有就启动
curl -s -m 2 http://127.0.0.1:8000/api/health || (.venv/Scripts/python.exe -m uvicorn server.main:app --port 8000 > /tmp/dash8000.log 2>&1 &)
```

- Windows 上旧服务可能是 `uv run dash`（进程名不匹配 `uvicorn`），按端口查 PID 再停：
  `Get-NetTCPConnection -LocalPort 8000 -State Listen` → `Stop-Process -Id <PID> -Force`
- **后端代码也有改动时，必须重启服务**（不然跑的是旧代码，meta 缓存不会刷新）。
- 最后用 `present_files` 把 `http://127.0.0.1:8000/#/trend`（或对应页面）作为预览打开，方便用户直接验收。

---

## 2. 数据在哪、怎么查

**数据库：`data/ashare.db`（SQLite，221 MB，59 表）** — 唯一数据源，全部现成，不需要重新抓。

```python
import sqlite3, pandas as pd
c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("select * from px_lof_daily where fund_code='159941' order by trade_date", c)
```

### 最常用的 12 张表

| 表 | 行数 | 用途 | 关键字段 |
|---|---:|---|---|
| `px_lof_daily` | 8,364 | 159941 价 + 净值 + **溢价** | `fund_code, trade_date, close, nav, premium, premium_lag, close_adj, nav_adj` |
| `px_index_daily_csi` | 27,028 | 中证指数日线（含 PE-TTM） | `index_code, trade_date, close, pct_chg, amount, pe_ttm` |
| `px_index_daily_cni` | 11,548 | 国证指数（创业板/深证） | 同上，但涨跌幅字段是 `pct_chg_ratio`（小数！） |
| `px_index_daily_us` | 8,969 | 纳指 100（`.NDX`）/ 纳指综合（`.IXIC`） | `index_code, trade_date, close` |
| `px_stock_daily` | 458,223 | 174 只个股不复权日线 | `stock_code, trade_date, close` |
| `px_etf_daily` | 16,796 | ETF 日线（红利/有色/科创/港股创新药等） | `etf_code, trade_date, close` |
| `mkt_fear_daily` | 24,139 | 各指数恐慌度 | `index_code, rv20, rv60, dvol20, dd60, qvix, fear_rv_pct, fear_composite` |
| `mkt_vol_qvix` | 11,250 | 9 个标的的 QVIX 隐含波动率 | `qvix_code, trade_date, close` |
| `mkt_vol_vxn` | 4,327 | Cboe 官方 VXN 纳指100波动率指数日线（2009-09 起，与 .NDX 100% 对齐） | `trade_date, open, high, low, close` |
| `val_qdii_ndx_compare` | 2,740 | 溢价 + 纳指对齐表 | `premium_same, premium_lag, ndx_close, ndx_ret_5d` |
| `val_index_dividend_yield` | 11,548 | 【自建】红利指数日频股息率 | `index_code, trade_date, div_yield` |
| `flow_hsgt_branch` | 10,157 | 沪深港通分项（北向 2024-08 止，南向持续） | `branch, direction, net_buy` |
| `web_daily_snapshot` | 1 | 看板每日快照（温度/行情/舆情/结论） | `trade_date, temperature, sentiment_score` |

完整清单见 **`docs/db_inventory.md`**（按 9 类分组、每表行数/区间/粒度）。

### 常用片段

```sql
-- 159941 某日溢价（两种口径）
select trade_date, close, nav, premium as premium_same, premium_lag
from px_lof_daily where fund_code='159941' order by trade_date desc limit 10;

-- 任意指数区间收盘
select trade_date, close from px_index_daily_csi
where index_code='000300' and trade_date between '2025-01-01' and '2026-11-20' order by 1;

-- 纳指 100
select trade_date, close from px_index_daily_us where index_code='.NDX' order by trade_date desc limit 5;

-- 最新恐慌度
select index_code, rv20, qvix, fear_rv_pct, fear_composite from mkt_fear_daily
where trade_date=(select max(trade_date) from mkt_fear_daily) order by fear_composite desc;
```

---

## 3. 必须知道的口径与坑（踩过的）

1. **溢价两种口径，别混用**
   - `premium` = 收盘价/当日净值 − 1（行情软件口径，含 T 日美股涨跌）
   - `premium_lag` = 收盘价/前一日净值 − 1（A 股收盘时真正可观测，**做判断用这个**）
   - 字段本身已是**百分数**（8.2 表示 8.2%），不要再 ×100
2. **159941 在 2022-07-05 做过 4:1 份额拆分**：原始 `close`/`nav` 不连续。做收益计算必须用 `close_adj`（复权价）和 `nav_adj`（累计净值）。
3. **中证 vs 国证涨跌幅单位不同**：`px_index_daily_csi.pct_chg` 是百分数，`px_index_daily_cni.pct_chg_ratio` 是小数（0.0309 = 3.09%）。
4. **两融单位不同**：`flow_margin_sse` 单位元，`flow_margin_szse` 单位亿元。
5. **`fin_yjbb` 含北交所/新三板/B 股**（11,662 个代码，沪深 A 股只有 5,233）。研究沪深必须按前缀过滤 `60/00/30/68`。
6. **财报可得日**用 `fin_disclosure.actual_date`，不要用 `fin_yjbb.announce_date`（滞后约 1 年）。
7. **北向日频净买入 2024-08-19 起停止披露**，接口返回的 `0.000000` 是停披露标志，不是真零。南向仍在更新。
8. **交易日历含未来日期**（排到 2026-12-31），算序列要截断到实际行情日期。
9. **`px_index_daily_csi` / `px_index_daily_cni` 无主键**，写入前先 DELETE 再 INSERT，`INSERT OR REPLACE` 会重复。
10. **东财 push2 接口常态限流**：舆情主源（人气榜）失败时自动退到雪球讨论榜（无涨跌幅）。
11. **`web_*` 表是缓存**：页面只读缓存，抓取只在 `scripts/daily_job.py` 里发生，别在请求链路里调外部接口。
12. **`sh512890`（红利低波ETF）2021-10-25 做 2:1 份额拆分**：当日 `close` 从 1.639 腰斩到 0.801（指数当天仅 -1.95%）。算收益必须把 2021-10-25 前的 `close` 除以 2 复权，否则 2021 年算出 -39.8%（真实 +20.5%），日收益与指数相关性从 0.977 掉到 0.685。库中 ETF 代码带 `sh`/`sz` 前缀。

---

## 4. 脚本清单（都可重跑）

| 脚本 | 作用 | 备注 |
|---|---|---|
| `scripts/db_inventory.py` | 重新生成 `docs/db_inventory.md` | 加表后跑一次 |
| `scripts/fetch_ndx_compare.py` | 拉纳指 + 回填两种溢价口径 | 有网络才跑 |
| `scripts/fetch_fear_index.py` | 931787 行情 + QVIX + 恐慌度 | 有网络才跑 |
| `scripts/fetch_vxn.py` | Cboe 官方 CSV 抓 VXN（纳指100波动率）入库 | 有网络才跑；2009-09 起 |
| `scripts/fetch_northbound_detail.py` | 沪深港通四路分项 | 有网络才跑 |
| `scripts/backtest_dca.py` | 定投：场内 vs 净值 vs 纳指（5年/3年/半年） | 纯本地 |
| `scripts/backtest_mc.py` | 随机 3000 组定投 | 纯本地，~30s |
| `scripts/backtest_1y.py` | 2021-2026 一年期 60 窗口 | 纯本地 |
| `scripts/backtest_threshold.py` | 阈值策略（3/5/8/10% + 等 N 月） | 纯本地 |
| `scripts/backtest_hybrid_dca.py` | 低分位买 ETF / 否则买纳指 | 纯本地 |
| `scripts/backtest_long3y.py` | 三年期 × 5 策略 + 高低点场景 | 纯本地 |
| `scripts/premium_trend_test.py` | 溢价趋势归因（A−C ≈ 1.05ΔP − 0.60） | 纯本地 |
| `scripts/daily_job.py` | 每日任务：采集舆情 + 生成总结 + 快照 | `uv run python scripts/daily_job.py` |

> 回测输出统一写到 `data/*.json` + `data/*_windows.csv`，方便复用。

---

## 5. 文档地图（问什么看哪份）

> **先看 [`strategies/README.md`](strategies/README.md)**——50 份策略报告已按主题分 7 类，从 `docs/` 移出。
> `docs/` 现在只保留 9 份数据/工程文档。脚本输出路径已同步更新。

| 想了解 | 看 |
|---|---|
| **美股/纳指ETF 全量研究（LLM 首选，含全部数字）** | `strategies/01_nasdaq_dca/us_etf_premium_llm.md` |
| 所有结论汇总（人读版） | `strategies/01_nasdaq_dca/conclusion_summary.md` |
| 溢价为什么影响收益（小白版） | `strategies/01_nasdaq_dca/learning_premium_10years.md` |
| 溢价十年变化 + 政策后预测 | `strategies/01_nasdaq_dca/premium_regime_2026.md` |
| 超额收益归因（关键证据） | `strategies/01_nasdaq_dca/premium_trend_attribution.md` |
| 定投回测 5年/3年/半年 | `strategies/01_nasdaq_dca/backtest_dca_159941.md` |
| 随机 3000 组 | `strategies/01_nasdaq_dca/backtest_mc_dca.md` |
| 一年期 60 窗口 | `strategies/01_nasdaq_dca/backtest_1y_2021_2026.md` |
| 阈值策略（最优解） | `strategies/01_nasdaq_dca/backtest_threshold_strategy.md` |
| 混合策略（最抗跌） | `strategies/01_nasdaq_dca/backtest_hybrid_dca.md` |
| 三年期 5 策略对比 | `strategies/01_nasdaq_dca/backtest_long3y.md` |
| 分档加码（为什么无效） | `strategies/01_nasdaq_dca/backtest_tier_dca.md` |
| 数据库全量清点 | `docs/db_inventory.md` |
| 字段与数据源细节 | `docs/data_dictionary.md` |
| 恐慌度体系 | `strategies/07_other_research/fear_report.md` |
| 北向资金 | `strategies/07_other_research/northbound_report.md` |
| 看板网站 | `docs/web_dashboard.md` |

---

## 6. 已经确立的结论（不要重复研究）

> 完整版（含样本定义、回归、回测矩阵、复现脚本）见 `strategies/01_nasdaq_dca/us_etf_premium_llm.md`。

1. **溢价是乘数，不是成本**：`收益 = (1+指数涨跌) × (1+P卖)/(1+P买)`。两端相等时完全中性。
2. **ETF 无品种优势**：溢价不变时每年比纳指少 **0.60pp**（汇率+管理费+跟踪误差+价差）。
3. **超额收益 100% 来自溢价上涨**：`A−C ≈ 1.05×ΔP − 0.60`（n=124 个一年期窗口，corr 0.594）。
4. **十年三阶段**：2015-2019 折价/零溢价 → 2020-2024 横盘（ETF 输 0.44pp）→ 2025-2026 结构性抬升（0.97% → 10.58%）。
5. **溢价由 QDII 额度决定，与纳指涨跌无关**（相关 −0.06）；短期由反应滞后驱动（美股跌 >2%，次日溢价 +1.09pp）。
6. **最优定投策略 = 溢价 ≤5% 投、>5% 暂停、最多等 3 月**：3 年期均值 42.33%，胜无脑 ETF 94%。
7. **从定投预算里挪钱加码无效**；用**外部储备金**在低分位加仓才有效（60 日 +7.38% vs +2.64%）。
8. **恐慌度不能预测收益方向**（corr<0.1），但 >90 分位后 60 日跑输 2.72pp，可作仓位信号。
9. **当前溢价 18.8~21.5% 是历史极值**（前高 2020-09 的 18.6%），回归是主要风险。

---

## 7. 常见任务配方

**「帮我看看某指数最近怎么样」**
→ 查 `px_index_daily_csi`（中证）/ `px_index_daily_cni`（国证）/ `px_index_daily_us`（美股），或直接 `curl 127.0.0.1:8000/api/grid?freq=D`。

**「现在溢价多少」**
→ `select premium, premium_lag from px_lof_daily where fund_code='159941' order by trade_date desc limit 1`

**「跑个新回测」**
→ 复制 `scripts/backtest_long3y.py` 的结构：`load()` 取 close_adj/nav_adj → 按月生成买入日 → 三条轨累加份额 → 期末估值。

**「更新数据」**
→ 抓数脚本需要网络；改完跑 `uv run python scripts/db_inventory.py` 同步清点。

**「改网页 / 加页面」**
→ 改 `web/src/**` → `cd web && pnpm build` → 确认/启动 8000 端口服务 → 用 `present_files` 打开预览给用户验收（见第 1 节的强制约定）。后端也改了要重启服务。

---

## 8. 不要做

- 不要用 `pip` / `conda` / 全局 Python
- 不要删 `.workbuddy/`（项目记忆）
- 不要删 `data/ashare.db`（221 MB 数据，重抓要几小时）
- 不要把「溢价差」直接说成「收益」，指数涨跌是主体
- 不要在页面请求链路里加外部接口调用（会限流）
