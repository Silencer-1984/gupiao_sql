# 操作流水（step log）

记录本项目「数据准备阶段」每一步实际做了什么、结果如何、产生什么文件。
目的：任何结论都能追溯到现在这一步是怎么来的。

---

## Step 0 · 环境与项目基线（2026-11-22 16:58）

| 项目 | 值 |
|---|---|
| 工作目录 | `C:\Users\1\Desktop\test\panduan` |
| 初始状态 | 空目录，无任何既有代码或成果（已确认，不存在覆盖风险） |
| Python | 3.13.12（`uv venv --python 3.13`） |
| 虚拟环境 | `.venv/` |
| 依赖 | `akshare==1.20.65`、`pandas==3.1.1`、`pyyaml` |
| 安装方式 | `uv pip install --python .venv/Scripts/python.exe akshare pandas pyyaml` |
| 操作系统 | win32（Windows 11） |

产物：`.venv/`、目录 `docs/ scripts/ config/ data/`

---

## Step 1 · 检查 AkShare 版本与接口文档形态

- `ak.__version__` = **1.20.65**（该版本内置 `ak.interface_info(name)`、`ak.renamed_info()` 反射能力，
  可直接读取单个接口的 `params / outputs / limit_desc / url`，本项目的字段清单以此为准，不依赖网页文档）。
- 发现多处**接口改名**，旧名调用会抛 `AttributeError` 并提示新名：
  - `stock_zh_index_daily_em` → `index_zh_daily_em`
  - `macro_china_money_supply` → `macro_china_money_supply_em`
  - 旧名如照文档写脚本会直接失败，故配置中只写已验证的新名。
- 可用函数总数 992 个，逐个按关键词枚举后确定候选清单（见 `config/data_sources.yaml`）。

产物：候选接口清单（后续固化进 yaml）

---

## Step 2 · 接口连通性与限流实测

用 `scripts/_probe.py` / `_t*.py` 做一次性探针测试（探针文件仅为调试用，正式逻辑全部收敛到
`scripts/verify_data_sources.py`）。关键发现：

1. **东方财富 push2 行情服务器对本机 IP 限流**
   - `index_zh_hist_em`、`index_zh_daily_em`、`fund_etf_hist_em` 多次返回
     `Push2RateLimitError`（提示首次约 5 分钟恢复、反复触发可能 40 分钟以上）。
   - 结论：**行情主来源改为中证指数官网 / 国证 / 新浪 / 腾讯**，东方财富行情降级为备用，
     并在配置中保留该接口用于记录失败状态。
   - 东方财富**数据中心**（`datacenter-web`，如 `stock_yjbb_em`、`macro_china_money_supply_em`）不受此限流影响，可正常使用。
2. 中证指数官网 `index_hist_csindex` 稳定，且**自带「滚动市盈率」列**（指数级 PE-TTM 日频序列），
   这是意外收获：指数估值不必依赖第三方。
3. 申万宏源 `index_analysis_daily_sw`（含行业 PE/PB/股息率/**成交额占比**）在本版本**实际调用失败**：
   `KeyError: '发布日期'`，一级行业/风格指数均失败。→ 记录为「接口异常」，不作为可用来源。
4. `futures_inventory_em` 只返回近约 60 个交易日；`stock_summary_sse` 只返回最近一个交易日。
5. `interest_rate_repo_hist_cm` 单次查询区间不得超过 1 年，需按年循环。

产物：`config/data_sources.yaml` 中的来源取舍（每条 notes 记录原因）

---

## Step 3 · 建立候选字段清单与配置

按任务的六大类别（行情/成长/价值/周期/宏观/资金）整理出 **28 个数据集**，
每个数据集在 `config/data_sources.yaml` 中固定记录：

中文名称、英文字段名、类别、AkShare 接口、参数、循环参数、返回字段（英文映射）、
数据频率、表名、主键、单位口径、已知缺陷。

设计取舍（遵守任务「数据设计原则」）：

- 不采集高度重复指标。例：指数成交额只在 1 个来源取（中证官方），腾讯只用来补充**换手率**。
- 只采原始数据，不在此阶段计算分位数/动量/拥挤度/广度等衍生因子。
- 成长/价值/周期共用 `fin_yjbb`（全市场季度面板）+ 指数行情 + 宏观 + 资金；
  各自追加差异化指标（成长→PS/研发，价值→股息/分红明细，周期→商品/库存/PPI）。
- 明确标注两处「同名不同口径」陷阱：
  - `stock_margin_sse`（元）vs `stock_margin_szse`（亿元）vs `stock_margin_szse_js`（元）
  - 中证涨跌幅（百分数）vs 国证涨跌幅（小数）

产物：`config/data_sources.yaml`

---

## Step 4 · 编写并执行验证脚本

`scripts/verify_data_sources.py` 的能力：

1. 逐数据集、逐代码真实调用接口（不推测）；
2. 记录状态 / 实际返回列 / 起止日期 / 行数 / 重复主键 / 空值率 / 异常类型与原文 / 耗时；
3. **原始返回（未改名）gzip 归档进 `raw_archive` 表**，一次下载不丢弃；
4. 清洗后按主键覆盖写入业务表，可反复运行；
5. 自动生成 `docs/data_catalog.md`（数据本身说明）与 `data/verification_report.json`。

执行命令与日志：

```
.venv/Scripts/python.exe scripts/verify_data_sources.py            # 全量
.venv/Scripts/python.exe scripts/verify_data_sources.py --only ID  # 单跑
```

- 首次全量运行日志：`data/run_full_1.log`
- 结果明细：`data/verification_report.json`、SQLite `meta_fetch` 表

> 后续若新增或修复接口，只需改 yaml 再重跑 `--only <id>`，旧数据保留在库中，可增量更新。

### Step 4.1 · 首轮全量运行（run_id=20261122_170844）与 3 个缺陷修复

首轮结果：38 个数据集，verified 34 / partial 3 / failed 1。随后逐个排查落库异常：

| 现象 | 根因 | 修复 |
|---|---|---|
| `dim_trade_calendar` / `val_a_dividend_yield` 行数变成 2 倍 | 主键去重失效：旧表从 SQLite 读回 `str`，新数据为 `Timestamp`，`drop_duplicates` 视为不同值 | 新增 `key_series()`，主键一律字符串化后再去重 |
| `px_index_cons` 5,767 行去重后只剩 2,569 行 | ① 新浪接口本身有 3,198 行重复；② 主键未含 `include_date` | 主键改为 `(index_code, stock_code, include_date)`；改换官方源（下） |
| `flow_margin_sse` 只有 2,000 行、日期为整型 | SSE 接口单次返回有行数上限；`信用交易日期` 是 int | 改为按年循环；新增 `normalize_date_cols()` 把整型日期转字符串 |
| `macro_industrial_profit` 列名对不上 | NBS 返回「指标 × 月份」宽表 | 新增 `pivot` 配置，melt 为 `indicator / stat_month / value` 长表 |
| `val_index_pe_lg`/`pb_lg` 对「创业板指」报 KeyError | 乐咕只支持 4 个宽基 | 改为 沪深300/上证50/中证500/上证180，并在 notes 写明限制 |
| `fin_disclosure` 缺 `report_period` 列 | `LOOP_COLUMN` 未登记该数据集，注入了列名 `date` | 补充映射；表已 `ALTER TABLE ... RENAME COLUMN` 就地修正 |

### Step 4.2 · 补采（发现缺口后追加，不是凑数）

| 追加数据集 | 触发原因 | 结果 |
|---|---|---|
| `px_index_cons_csi`（`index_stock_cons_weight_csindex`） | 新浪成分股重复 3,198 行、沪深300 只有 289 只 | 官方源 7/7 成功，沪深300=300、全指=5,117，数量正确 |
| `fin_disclosure`（`stock_yysj_em`） | 发现 `stock_yjbb_em` 的「最新公告日期」系统性滞后约 1 年（2025Q1 有 98.0% 落在 2026 年），直接用会造成严重时点错误 | 47 期、187,503 行，`actual_date` 仅 2 条为空；成为回测的 PIT 基准 |
| `fin_dividend_detail_sina`（`stock_history_dividend_detail`） | 巨潮接口对招行/紫金/宝钢报 `KeyError: 'records'` | 5/5 成功，作为兜底 |

> 探针脚本（`_probe.py`、`_t1~t21.py`）是一次性调查工具，已归档到 `scripts/explore/`，
> 正式逻辑全部收敛在 `scripts/verify_data_sources.py`。

首轮全量日志：`data/run_full_1.log`；披露补采日志：`data/run_disclosure.log`。

---

## Step 5 · 整理文档

- `docs/data_dictionary.md` —— 字段级数据字典（六类，含来源/接口/参数/频率/起始日/验证状态）
- `docs/data_source_report.md` —— 数据源调研结论（能取/需替代源/不可得/不稳定）
- `docs/data_quality_report.md` —— 数据质量验证（成功率/缺失/连续性/重复/异常/覆盖/风险）
- `docs/data_catalog.md` —— 自动生成的「库里到底有什么数据」
- `docs/step_log.md` —— 本文件

---

## Step 6 · 数据库产物

`data/ashare.db`（SQLite，WAL 模式）表结构：

| 表 | 作用 |
|---|---|
| `meta_run` | 每次运行的 run_id、AkShare 版本、Python 版本、起止时间 |
| `meta_fetch` | 每次接口调用的状态、参数、行数、日期范围、重复键、空值率、错误原文、耗时（254 条调用记录） |
| `raw_archive` | 每次接口返回的**原始 DataFrame**（gzip JSON，245 份、约 37 MB），保证可回溯、可重放 |
| `px_* / val_* / fin_* / macro_* / flow_* / cyc_* / dim_*` | 清洗后的业务表（英文字段+主键），共 40 张，**716,987 行** |

查询示例：

```sql
-- 哪些接口失败过、为什么
SELECT dataset_id, loop_value, status, error_type, substr(error_msg,1,80), fetched_at
FROM meta_fetch WHERE status <> 'verified' ORDER BY dataset_id;

-- 各表覆盖情况
SELECT dataset_id, table_name, SUM(rows) rows, MIN(date_min), MAX(date_max)
FROM meta_fetch WHERE status='verified' GROUP BY dataset_id;
```

---

## 最终状态（2026-11-22 17:24）

| 项 | 结果 |
|---|---|
| 数据集 | 41 个，verified 39 / partial 1（巨潮分红）/ failed 1（东财 push2 行情） |
| 接口调用 | 254 次，成功 245 次（96.5%） |
| 数据库 | `data/ashare.db` 142 MB，40 张业务表（716,987 行）+ 3 张元数据表 + 原始归档 245 份 |
| 文档 | 数据字典 / 数据源报告 / 数据质量报告 / 数据目录 / 本流水 |

## 待办（下一阶段，本次不做）

- 全市场个股日行情面板（打开「风格广度」与个股加权估值）
- 全市场批量财务指标（`fin_indicator_sina` 目前仅 9 只代表股）
- 红利 100 只成分股分红明细（自建历史股息率）
- 历史成分股月度快照留档（当前只有最新一期）
- 指数基日/基期、H30269 与 930955 发布日（官网手工补）
- 宏观 PIT 表（按发布日历生成可得日，纯计算，无新数据）
