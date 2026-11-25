# 数据目录（数据本身说明）

- 生成时间：2026-11-22 17:25:25
- 运行编号：`20261122_172525`
- 数据库：`data/ashare.db`（SQLite）
- 本文件由 `scripts/verify_data_sources.py` 自动生成，只描述「已经下载到库里的数据」，
  不描述研究设计。研究口径见 `docs/data_dictionary.md`。

## 1. 表清单总览

| 数据集 | 类别 | AkShare 接口 | SQLite 表 | 状态 | 行数 | 列数 | 覆盖起始 | 覆盖终止 |
|---|---|---|---|---|---|---|---|---|
| 中证指数日行情（官方） | 行情 | `index_hist_csindex` | `px_index_daily_csi` | verified | 19003 | 16 | 2015-01-01 | 2026-11-20 |
| 国证指数日行情 | 行情 | `index_hist_cni` | `px_index_daily_cni` | verified | 5774 | 11 | 2015-01-05 | 2026-11-20 |
| 指数日行情（腾讯，含换手率） | 行情 | `index_zh_daily_tx` | `px_index_daily_tx` | verified | 22410 | 11 | 2005-04-08 | 2026-11-20 |
| 指数日行情（东方财富，备用） | 行情 | `index_zh_hist_em` | `px_index_daily_em` | failed | 0 | 0 | - | - |
| ETF 日行情（新浪） | 行情 | `fund_etf_hist_sina` | `px_etf_daily` | verified | 14043 | 11 | 2007-01-18 | 2026-11-20 |
| 指数基本信息（发布日） | 行情 | `index_stock_info` | `px_index_meta` | verified | 732 | 5 | 1991-04-04 | 2025-07-21 |
| 指数成分股与权重（中证官方） | 行情 | `index_stock_cons_weight_csindex` | `px_index_cons_csi` | verified | 5767 | 10 | 2026-10-30 | 2026-10-30 |
| 指数成分股（当前快照，新浪口径） | 行情 | `index_stock_cons` | `px_index_cons` | verified | 2569 | 6 | - | - |
| 中证指数估值（PE/股息率） | 估值 | `index_value_csindex` | `val_index_value_csi` | verified | 140 | 8 | 2026-10-26 | 2026-11-20 |
| 指数市盈率（乐咕，月度） | 估值 | `stock_index_pe_lg` | `val_index_pe_lg` | verified | 1025 | 11 | 2005-01-31 | 2026-11-20 |
| 指数市净率（乐咕，月度） | 估值 | `stock_index_pb_lg` | `val_index_pb_lg` | verified | 1025 | 8 | 2005-01-31 | 2026-11-20 |
| 全 A 股股息率 | 估值 | `stock_a_gxl_lg` | `val_a_dividend_yield` | verified | 5314 | 4 | 2005-01-04 | 2026-11-20 |
| 市场拥挤度（乐咕） | 估值 | `stock_a_congestion_lg` | `val_congestion_lg` | verified | 3687 | 5 | 2011-09-05 | 2026-11-20 |
| 个股估值（PE/PB/PS） | 估值 | `stock_value_em` | `val_stock_value_em` | verified | 18675 | 14 | 2018-01-02 | 2026-11-20 |
| 业绩报表（东财，按报告期） | 基本面 | `stock_yjbb_em` | `fin_yjbb` | verified | 357176 | 18 | 20150331 | 20260930 |
| 业绩预约披露与实际披露时间（point-in-time） | 基本面 | `stock_yysj_em` | `fin_disclosure` | verified | 187503 | 10 | 20150331 | 20260930 |
| 财务指标（新浪，按股票） | 基本面 | `stock_financial_analysis_indicator` | `fin_indicator_sina` | verified | 411 | 16 | 2015-03-31 | 2026-09-30 |
| 分析师盈利预测（当前快照） | 基本面 | `stock_profit_forecast_em` | `fin_profit_forecast` | verified | 141 | 5 | - | - |
| 分红统计（全市场） | 基本面 | `stock_history_dividend` | `fin_dividend_stat` | verified | 5675 | 10 | - | - |
| 个股历史分红明细（巨潮） | 基本面 | `stock_dividend_cninfo` | `fin_dividend_detail` | partial | 103 | 12 | 2000年报 | 2026半年报 |
| 个股历史分红明细（新浪，备用） | 基本面 | `stock_history_dividend_detail` | `fin_dividend_detail_sina` | verified | 132 | 10 | 2001-06-12 | 2026-10-26 |
| 申万行业分类变更历史 | 基本面 | `stock_industry_clf_hist_sw` | `fin_industry_clf_sw` | verified | 12940 | 6 | 1990-01-01 | 2026-11-20 |
| 制造业与非制造业 PMI | 宏观 | `macro_china_pmi` | `macro_pmi` | verified | 226 | 7 | 2008年01月份 | 2026年10月份 |
| CPI | 宏观 | `macro_china_cpi` | `macro_cpi` | verified | 226 | 7 | 2008年01月份 | 2026年10月份 |
| PPI | 宏观 | `macro_china_ppi` | `macro_ppi` | verified | 250 | 6 | 2006年01月份 | 2026年10月份 |
| 货币供应量 M0/M1/M2 | 宏观 | `macro_china_money_supply_em` | `macro_money_supply` | verified | 226 | 9 | 2008年01月份 | 2026年10月份 |
| 社会融资规模增量 | 宏观 | `macro_china_social_financing` | `macro_social_financing` | verified | 136 | 7 | 201501 | 202604 |
| 工业增加值同比 | 宏观 | `macro_china_industrial_value_added` | `macro_industrial_value_added` | verified | 207 | 6 | 2008年02月份 | 2026年10月份 |
| 规模以上工业企业主要经济指标（含利润总额） | 宏观 | `macro_china_nbs_nation` | `macro_industrial_profit` | verified | 6858 | 5 | 2015年10月 | 2026年9月 |
| 固定资产投资 | 宏观 | `macro_china_fixed_asset_investment` | `macro_fixed_asset_investment` | verified | 163 | 7 | 2012年02月份 | 2026年10月份 |
| 中债国债收益率曲线（含 10 年） | 宏观 | `bond_zh_us_yield_em` | `macro_bond_yield` | verified | 9393 | 8 | 1990-12-19 | 2026-11-20 |
| 银行间回购定盘利率（DR007） | 宏观 | `interest_rate_repo_hist_cm` | `macro_dr007` | verified | 2963 | 10 | 2015-01-04 | 2026-11-20 |
| 上交所融资融券汇总 | 资金 | `stock_margin_sse` | `flow_margin_sse` | verified | 2887 | 10 | 20150105 | 20261120 |
| 深交所融资融券（全历史） | 资金 | `stock_margin_szse_js` | `flow_margin_szse` | verified | 3829 | 9 | 2010-03-31 | 2026-11-05 |
| 北向资金历史 | 资金 | `stock_hsgt_hist_em` | `flow_northbound` | verified | 2794 | 8 | 2014-11-17 | 2026-11-20 |
| 深交所市场总貌（成交额/流通市值） | 资金 | `stock_summary_szse` | `flow_szse_summary` | verified | 14 | 7 | - | - |
| 上交所 ETF 份额 | 资金 | `fund_etf_scale_sse` | `flow_etf_scale_sse` | verified | 927 | 7 | 2026-11-20 | 2026-11-20 |
| 外盘商品期货（铜/铝/黄金/白银） | 周期 | `futures_foreign_hist_sina` | `cyc_futures_foreign` | verified | 10305 | 11 | 2016-11-22 00:00:00 | 2026-11-20 00:00:00 |
| 上金所黄金现货（Au99.99） | 周期 | `spot_hist_sge` | `cyc_sge_gold` | verified | 2407 | 7 | 2016-12-19 | 2026-11-20 |
| 期货库存（沪铜/沪铝） | 周期 | `futures_inventory_em` | `cyc_inventory` | verified | 134 | 6 | 2026-08-12 | 2026-11-20 |
| 交易日历 | 行情 | `calendar_trade_date_hist_sina` | `dim_trade_calendar` | verified | 8797 | 3 | 1990-12-19 | 2026-12-31 |

## 2. 各表字段与样例

### 中证指数日行情（官方）（`px_index_daily_csi`）

- 接口：`ak.index_hist_csindex`　类别：行情　状态：verified（成功 7/7 次调用）
- 行数：19003　列数：16　频率：日
- 日期范围：2015-01-01 ~ 2026-11-20（日期列 `trade_date`）
- 单位：成交量=股/份；成交金额=亿元；涨跌幅=%；pe_ttm=倍
- 说明：中证指数公司官方接口。含滚动市盈率(指数级PE-TTM)，是本项目指数估值的主来源。节假日/停市日可能出现与前一日完全重复的行，需按日期去重。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | 日期 | str | 100.0% |
| `index_code` | 指数代码 | str | 100.0% |
| `index_name_cn` | 指数中文全称 | str | 100.0% |
| `index_name_short` | 指数中文简称 | str | 100.0% |
| `open` | 开盘 | float64 | 94.0% |
| `high` | 最高 | float64 | 94.0% |
| `low` | 最低 | float64 | 94.0% |
| `close` | 收盘 | float64 | 100.0% |
| `change` | 涨跌 | float64 | 96.3% |
| `pct_chg` | 涨跌幅 | float64 | 100.0% |
| `volume` | 成交量 | float64 | 100.0% |
| `amount` | 成交金额 | float64 | 100.0% |
| `sample_size` | 样本数量 | float64 | 96.3% |
| `pe_ttm` | 滚动市盈率 | float64 | 96.4% |

数据样例（前 3 行）：

```
   trade_date index_code index_name_cn index_name_short     open     high      low  ...  pct_chg        volume  amount  sample_size  pe_ttm             _source          _fetched_at
0  2015-01-01     000300       沪深300指数            沪深300  3566.09  3669.04  3551.51  ...     3.05  4.511981e+10  5198.5        300.0   14.28  index_hist_csindex  2026-11-22T17:09:10
1  2015-01-05     000300       沪深300指数            沪深300  3566.09  3669.04  3551.51  ...     3.05  4.511981e+10  5198.5        300.0   14.28  index_hist_csindex  2026-11-22T17:09:10
2  2015-01-06     000300       沪深300指数            沪深300  3608.43  3683.23  3587.23  ...    -0.01  4.209622e+10  4985.3        300.0   14.29  index_hist_csindex  2026-11-22T17:09:10
```

### 国证指数日行情（`px_index_daily_cni`）

- 接口：`ak.index_hist_cni`　类别：行情　状态：verified（成功 2/2 次调用）
- 行数：5774　列数：11　频率：日
- 日期范围：2015-01-05 ~ 2026-11-20（日期列 `trade_date`）
- 单位：涨跌幅为小数(0.0512=+5.12%)，与中证接口的百分数口径不同；成交量=万手；成交额=亿元
- 说明：创业板指(399006)、创业板成长/创成长(399296)只能从国证接口取，中证接口不覆盖。单位口径与中证不同，入库后需统一换算。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `index_code` | - | str | 100.0% |
| `trade_date` | 日期 | str | 100.0% |
| `open` | 开盘价 | float64 | 100.0% |
| `high` | 最高价 | float64 | 100.0% |
| `low` | 最低价 | float64 | 100.0% |
| `close` | 收盘价 | float64 | 100.0% |
| `pct_chg_ratio` | 涨跌幅 | float64 | 100.0% |
| `volume` | 成交量 | float64 | 100.0% |
| `amount` | 成交额 | float64 | 100.0% |

数据样例（前 3 行）：

```
  index_code  trade_date       open       high        low      close  pct_chg_ratio   volume  amount         _source          _fetched_at
0     399006  2015-01-05  1470.5783  1470.5783  1429.0841  1464.7741        -0.0047   804.88  179.95  index_hist_cni  2026-11-22T17:09:29
1     399006  2015-01-06  1458.5736  1542.1515  1454.1379  1539.8283         0.0512  1100.24  257.33  index_hist_cni  2026-11-22T17:09:29
2     399006  2015-01-07  1542.4005  1547.2492  1517.3717  1523.3872        -0.0107   851.11  206.28  index_hist_cni  2026-11-22T17:09:29
```

### 指数日行情（腾讯，含换手率）（`px_index_daily_tx`）

- 接口：`ak.index_zh_daily_tx`　类别：行情　状态：verified（成功 6/6 次调用）
- 行数：22410　列数：11　频率：日
- 日期范围：2005-04-08 ~ 2026-11-20（日期列 `trade_date`）
- 单位：turnover=换手率(小数)；amount=元
- 说明：换手率的补充来源。腾讯接口早期年份换手率可能为 0 或缺失，需与成交额/流通市值交叉校验。东方财富同源接口(index_zh_hist_em)字段最全但存在 IP 限流，故降级为备用。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `index_code` | - | str | 100.0% |
| `trade_date` | date | str | 100.0% |
| `open` | open | float64 | 100.0% |
| `close` | close | float64 | 100.0% |
| `high` | high | float64 | 100.0% |
| `low` | low | float64 | 100.0% |
| `volume` | volume | float64 | 100.0% |
| `turnover` | turnover | float64 | 100.0% |
| `amount` | amount | float64 | 100.0% |

数据样例（前 3 行）：

```
  index_code  trade_date     open    close     high     low        volume  turnover        amount            _source          _fetched_at
0   sh000300  2005-04-08   984.67  1003.45  1003.70  979.53  1.476253e+09    0.0140  9.151350e+09  index_zh_daily_tx  2026-11-22T17:09:35
1   sh000300  2005-04-11  1003.88   995.42  1008.74  992.77  1.593607e+09    0.0151  1.043623e+10  index_zh_daily_tx  2026-11-22T17:09:35
2   sh000300  2005-04-12   993.71   978.70   993.71  978.20  1.022619e+09    0.0097  6.479564e+09  index_zh_daily_tx  2026-11-22T17:09:35
```

### 指数日行情（东方财富，备用）（`px_index_daily_em`）

表不存在：Execution failed on sql 'SELECT * FROM "px_index_daily_em"': no such table: px_index_daily_em

### ETF 日行情（新浪）（`px_etf_daily`）

- 接口：`ak.fund_etf_hist_sina`　类别：行情　状态：verified（成功 5/5 次调用）
- 行数：14043　列数：11　频率：日
- 日期范围：2007-01-18 ~ 2026-11-20（日期列 `trade_date`）
- 说明：用于后续研究真实可交易标的，不能替代指数本身表现。ETF 存在成立日，成立前无数据；prev_close 多为空。510880 自 2007 年、588000 自 2020 年起。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `etf_code` | - | str | 100.0% |
| `trade_date` | date | str | 100.0% |
| `prev_close` | prevclose | float64 | 0.0% |
| `open` | open | float64 | 100.0% |
| `high` | high | float64 | 100.0% |
| `low` | low | float64 | 100.0% |
| `close` | close | float64 | 100.0% |
| `volume` | volume | int64 | 100.0% |
| `amount` | amount | int64 | 100.0% |

数据样例（前 3 行）：

```
   etf_code  trade_date  prev_close   open   high    low  close     volume     amount             _source          _fetched_at
0  sh510880  2007-01-18       2.027  2.019  2.023  1.926  1.997  236005974  466070565  fund_etf_hist_sina  2026-11-22T17:09:52
1  sh510880  2007-01-19         NaN  1.996  2.042  1.993  2.040   98642834  199196018  fund_etf_hist_sina  2026-11-22T17:09:52
2  sh510880  2007-01-22         NaN  2.051  2.128  2.051  2.128   56172127  117685923  fund_etf_hist_sina  2026-11-22T17:09:52
```

### 指数基本信息（发布日）（`px_index_meta`）

- 接口：`ak.index_stock_info`　类别：行情　状态：verified（成功 1/1 次调用）
- 行数：732　列数：5　频率：快照
- 日期范围：1991-04-04 ~ 2025-07-21（日期列 `publish_date`）
- 说明：仅提供发布日，不提供基日。基日/基期需从中证、国证官网单独取得（本项目标记为缺口）。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `index_code` | index_code | str | 100.0% |
| `index_name` | display_name | str | 100.0% |
| `publish_date` | publish_date | str | 100.0% |

数据样例（前 3 行）：

```
  index_code index_name publish_date           _source          _fetched_at
0     000001       上证指数   1991-07-15  index_stock_info  2026-11-22T17:09:53
1     000002       A股指数   1992-02-21  index_stock_info  2026-11-22T17:09:53
2     000003       B股指数   1992-02-21  index_stock_info  2026-11-22T17:09:53
```

### 指数成分股与权重（中证官方）（`px_index_cons_csi`）

- 接口：`ak.index_stock_cons_weight_csindex`　类别：行情　状态：verified（成功 7/7 次调用）
- 行数：5767　列数：10　频率：快照
- 日期范围：2026-10-30 ~ 2026-10-30（日期列 `as_of_date`）
- 说明：中证官网口径，含成分股权重与快照日期，数量完整（沪深300=300只），优于 index_stock_cons。仍为当前快照，历史各期成分股需按月留档才能还原。官方文件接口偶发超时，重试即可。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `symbol` | - | str | 100.0% |
| `as_of_date` | 日期 | str | 100.0% |
| `index_code` | 指数代码 | str | 100.0% |
| `index_name` | 指数名称 | str | 100.0% |
| `stock_code` | 成分券代码 | str | 100.0% |
| `stock_name` | 成分券名称 | str | 100.0% |
| `exchange` | 交易所 | str | 100.0% |
| `weight` | 权重 | float64 | 100.0% |

数据样例（前 3 行）：

```
   symbol  as_of_date index_code index_name stock_code stock_name exchange  weight                          _source          _fetched_at
0  000300  2026-10-30     000300      沪深300     000001       平安银行  深圳证券交易所   0.498  index_stock_cons_weight_csindex  2026-11-22T17:17:16
1  000300  2026-10-30     000300      沪深300     000002        万科A  深圳证券交易所   0.096  index_stock_cons_weight_csindex  2026-11-22T17:17:16
2  000300  2026-10-30     000300      沪深300     000063       中兴通讯  深圳证券交易所   0.389  index_stock_cons_weight_csindex  2026-11-22T17:17:16
```

### 指数成分股（当前快照，新浪口径）（`px_index_cons`）

- 接口：`ak.index_stock_cons`　类别：行情　状态：verified（成功 7/7 次调用）
- 行数：2569　列数：6　频率：快照
- 日期范围：无日期列 ~ 
- 说明：只有当前成分股 + 纳入日期，不能还原历史每期成分股。实测该接口返回大量重复行：沪深300 返回 300 行但仅 289 个不同代码，中证全指返回 5117 行但仅 1930 个不同代码，成分股不完整，故仅作补充，主用 px_index_cons_csi。回测中若用当前成分股回溯 2015 年会产生前视偏差，必须自建历史成分股快照。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `index_code` | - | str | 100.0% |
| `stock_code` | 品种代码 | str | 100.0% |
| `stock_name` | 品种名称 | str | 100.0% |
| `include_date` | 纳入日期 | str | 100.0% |

数据样例（前 3 行）：

```
  index_code stock_code stock_name include_date           _source          _fetched_at
0     000300     002294        信立泰   2026-10-19  index_stock_cons  2026-11-22T17:16:16
1     000300     600221       海航控股   2026-06-15  index_stock_cons  2026-11-22T17:16:16
2     000300     002532       天山铝业   2026-06-15  index_stock_cons  2026-11-22T17:16:16
```

### 中证指数估值（PE/股息率）（`val_index_value_csi`）

- 接口：`ak.index_value_csindex`　类别：估值　状态：verified（成功 7/7 次调用）
- 行数：140　列数：8　频率：日（仅最近约 20 个交易日）
- 日期范围：2026-10-26 ~ 2026-11-20（日期列 `trade_date`）
- 说明：只能取最近约 20 个交易日，无历史序列。红利指数的历史股息率因此无法用免费接口还原（重要缺口）。股息率1/2 分别对应不同计算口径（近12个月现金分红/预测），不可混用。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | 日期 | str | 100.0% |
| `index_code` | 指数代码 | str | 100.0% |
| `pe_static` | 市盈率1 | float64 | 100.0% |
| `pe_ttm` | 市盈率2 | float64 | 100.0% |
| `div_yield_1` | 股息率1 | float64 | 100.0% |
| `div_yield_2` | 股息率2 | float64 | 100.0% |

数据样例（前 3 行）：

```
   trade_date index_code  pe_static  pe_ttm  div_yield_1  div_yield_2              _source          _fetched_at
0  2026-11-20        300      13.78   14.89         3.04         2.75  index_value_csindex  2026-11-22T17:10:12
1  2026-11-19        300      13.77   15.00         3.04         2.73  index_value_csindex  2026-11-22T17:10:12
2  2026-11-18        300      13.78   14.99         3.04         2.73  index_value_csindex  2026-11-22T17:10:12
```

### 指数市盈率（乐咕，月度）（`val_index_pe_lg`）

- 接口：`ak.stock_index_pe_lg`　类别：估值　状态：verified（成功 4/4 次调用）
- 行数：1025　列数：11　频率：月
- 日期范围：2005-01-31 ~ 2026-11-20（日期列 `trade_date`）
- 说明：月度频率，2005 年起。实测仅支持 沪深300/上证50/中证500/上证180，创业板指会抛 KeyError；不含中证红利/红利低波/有色，这些指数估值只能用中证官方口径。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `index_name` | - | str | 100.0% |
| `trade_date` | 日期 | str | 100.0% |
| `index_close` | 指数 | float64 | 100.0% |
| `pe_static_ew` | 等权静态市盈率 | float64 | 100.0% |
| `pe_static` | 静态市盈率 | float64 | 100.0% |
| `pe_static_median` | 静态市盈率中位数 | float64 | 100.0% |
| `pe_ttm_ew` | 等权滚动市盈率 | float64 | 100.0% |
| `pe_ttm` | 滚动市盈率 | float64 | 100.0% |
| `pe_ttm_median` | 滚动市盈率中位数 | float64 | 100.0% |

数据样例（前 3 行）：

```
  index_name  trade_date  index_close  pe_static_ew  pe_static  pe_static_median  pe_ttm_ew  pe_ttm  pe_ttm_median            _source          _fetched_at
0      沪深300  2005-04-29       932.40         33.66      14.48             20.36      31.53   13.99          20.27  stock_index_pe_lg  2026-11-22T17:16:32
1      沪深300  2005-05-31       855.95         32.25      13.17             19.14      31.23   12.58          19.01  stock_index_pe_lg  2026-11-22T17:16:32
2      沪深300  2005-06-30       878.69         31.92      13.35             19.25      30.95   12.76          19.31  stock_index_pe_lg  2026-11-22T17:16:32
```

### 指数市净率（乐咕，月度）（`val_index_pb_lg`）

- 接口：`ak.stock_index_pb_lg`　类别：估值　状态：verified（成功 4/4 次调用）
- 行数：1025　列数：8　频率：月
- 日期范围：2005-01-31 ~ 2026-11-20（日期列 `trade_date`）
- 说明：月度频率。中证官方接口不提供指数 PB 序列，指数级 PB 历史基本只能靠此源。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `index_name` | - | str | 100.0% |
| `trade_date` | 日期 | str | 100.0% |
| `index_close` | 指数 | float64 | 100.0% |
| `pb` | 市净率 | float64 | 100.0% |
| `pb_ew` | 等权市净率 | float64 | 100.0% |
| `pb_median` | 市净率中位数 | float64 | 100.0% |

数据样例（前 3 行）：

```
  index_name  trade_date  index_close    pb  pb_ew  pb_median            _source          _fetched_at
0      沪深300  2005-04-29       932.40  1.89   1.92       1.71  stock_index_pb_lg  2026-11-22T17:17:20
1      沪深300  2005-05-31       855.95  1.69   1.77       1.61  stock_index_pb_lg  2026-11-22T17:17:20
2      沪深300  2005-06-30       878.69  1.75   1.79       1.60  stock_index_pb_lg  2026-11-22T17:17:20
```

### 全 A 股股息率（`val_a_dividend_yield`）

- 接口：`ak.stock_a_gxl_lg`　类别：估值　状态：verified（成功 1/1 次调用）
- 行数：5314　列数：4　频率：日
- 日期范围：2005-01-04 ~ 2026-11-20（日期列 `trade_date`）
- 说明：全市场口径，非红利指数口径，仅用于市场整体无风险溢价对比。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | 日期 | str | 100.0% |
| `div_yield` | 股息率 | float64 | 100.0% |

数据样例（前 3 行）：

```
   trade_date  div_yield         _source          _fetched_at
0  2005-01-04       2.03  stock_a_gxl_lg  2026-11-22T17:16:35
1  2005-01-05       2.05  stock_a_gxl_lg  2026-11-22T17:16:35
2  2005-01-06       2.07  stock_a_gxl_lg  2026-11-22T17:16:35
```

### 市场拥挤度（乐咕）（`val_congestion_lg`）

- 接口：`ak.stock_a_congestion_lg`　类别：估值　状态：verified（成功 1/1 次调用）
- 行数：3687　列数：5　频率：日
- 日期范围：2011-09-05 ~ 2026-11-20（日期列 `trade_date`）
- 说明：全市场口径拥挤度，非风格层面。近期尾部存在空值，可用性不稳定。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | date | str | 100.0% |
| `index_close` | close | float64 | 98.6% |
| `congestion` | congestion | float64 | 98.6% |

数据样例（前 3 行）：

```
   trade_date  index_close  congestion                _source          _fetched_at
0  2011-09-05      2478.74      0.3167  stock_a_congestion_lg  2026-11-22T17:10:19
1  2011-09-06      2470.52      0.3418  stock_a_congestion_lg  2026-11-22T17:10:19
2  2011-09-07      2516.09      0.3349  stock_a_congestion_lg  2026-11-22T17:10:19
```

### 个股估值（PE/PB/PS）（`val_stock_value_em`）

- 接口：`ak.stock_value_em`　类别：估值　状态：verified（成功 9/9 次调用）
- 行数：18675　列数：14　频率：日
- 日期范围：2018-01-02 ~ 2026-11-20（日期列 `trade_date`）
- 说明：个股级 PE-TTM/PB/PS-TTM/市现率，是成长风格 PS 估值的唯一免费来源。历史起点约 2018 年初，无法覆盖 2015-2017。全市场采集需按股票循环，成本较高。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stock_code` | - | str | 100.0% |
| `trade_date` | 数据日期 | str | 100.0% |
| `close` | 当日收盘价 | float64 | 100.0% |
| `pct_chg` | 当日涨跌幅 | float64 | 100.0% |
| `total_mv` | 总市值 | float64 | 100.0% |
| `float_mv` | 流通市值 | float64 | 100.0% |
| `total_shares` | 总股本 | int64 | 100.0% |
| `float_shares` | 流通股本 | int64 | 100.0% |
| `pb` | 市净率 | float64 | 100.0% |
| `peg` | PEG值 | float64 | 100.0% |
| `pcf` | 市现率 | float64 | 100.0% |
| `ps_ttm` | 市销率 | float64 | 100.0% |

数据样例（前 3 行）：

```
  stock_code  trade_date  close    pct_chg      total_mv      float_mv  total_shares  float_shares        pb       peg        pcf    ps_ttm         _source          _fetched_at
0     300750  2018-06-11  36.20  43.993636  7.864222e+10  7.864223e+09    2172437000     217243733  3.128442 -1.576767 -70.039924  3.533828  stock_value_em  2026-11-22T17:10:19
1     300750  2018-06-12  39.82  10.000000  8.650644e+10  8.650645e+09    2172437000     217243733  3.441286 -1.734444 -77.043917  3.887211  stock_value_em  2026-11-22T17:10:19
2     300750  2018-06-13  43.80   9.994977  9.515274e+10  9.515276e+09    2172437000     217243733  3.785242 -1.907801 -84.744439  4.275737  stock_value_em  2026-11-22T17:10:19
```

### 业绩报表（东财，按报告期）（`fin_yjbb`）

- 接口：`ak.stock_yjbb_em`　类别：基本面　状态：verified（成功 47/47 次调用）
- 行数：357176　列数：18　频率：季度
- 日期范围：20150331 ~ 20260930（日期列 `report_period`）
- 说明：全市场季度面板，含最新公告日期(announce_date)，可用于构造 point-in-time 财报可用时点，避免未来函数。缺扣非净利润、研发费用、净利率（需另接口或由利润表计算）。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `report_period` | - | str | 100.0% |
| `stock_code` | 股票代码 | str | 100.0% |
| `stock_name` | 股票简称 | str | 100.0% |
| `eps` | 每股收益 | float64 | 98.8% |
| `revenue` | 营业总收入-营业总收入 | float64 | 99.9% |
| `revenue_yoy` | 营业总收入-同比增长 | float64 | 93.7% |
| `revenue_qoq` | 营业总收入-季度环比增长 | float64 | 65.4% |
| `net_profit` | 净利润-净利润 | float64 | 100.0% |
| `net_profit_yoy` | 净利润-同比增长 | float64 | 94.1% |
| `net_profit_qoq` | 净利润-季度环比增长 | float64 | 65.5% |
| `bps` | 每股净资产 | float64 | 95.8% |
| `roe` | 净资产收益率 | float64 | 97.1% |
| `ocf_ps` | 每股经营现金流量 | float64 | 96.4% |
| `gross_margin` | 销售毛利率 | float64 | 97.4% |
| `industry_em` | 所处行业 | str | 63.8% |
| `announce_date` | 最新公告日期 | str | 100.0% |

数据样例（前 3 行）：

```
  report_period stock_code stock_name     eps       revenue  revenue_yoy  revenue_qoq  ...   roe    ocf_ps  gross_margin  industry_em  announce_date        _source          _fetched_at
0      20150331     300094       国联水产 -0.0600  3.870006e+08   -23.672234     -18.2696  ... -1.29  0.052708      7.899259           渔业     2021-02-03  stock_yjbb_em  2026-11-22T17:10:24
1      20150331     002715       登云股份 -0.0410  6.393140e+07   -17.979867     -18.1509  ...  0.09 -0.107356     23.300546        汽车零部件     2018-04-25  stock_yjbb_em  2026-11-22T17:10:24
2      20150331     000713       国投丰乐  0.0679  1.908950e+08   -24.568739     -73.7318  ...  1.50 -0.221211     35.407550          种植业     2017-10-21  stock_yjbb_em  2026-11-22T17:10:24
```

### 业绩预约披露与实际披露时间（point-in-time）（`fin_disclosure`）

- 接口：`ak.stock_yysj_em`　类别：基本面　状态：verified（成功 47/47 次调用）
- 行数：187503　列数：10　频率：季度
- 日期范围：20150331 ~ 20260930（日期列 `report_period`）
- 说明：本项目的 point-in-time 基准表。stock_yjbb_em 的『最新公告日期』实测系统性滞后约 1 年（如 2025Q1 有 98% 显示 2026 年公告），不可用于回测；必须用本表的『实际披露时间』作为财报可得日。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `report_period` | - | str | 100.0% |
| `stock_code` | 股票代码 | str | 100.0% |
| `stock_name` | 股票简称 | str | 100.0% |
| `first_plan_date` | 首次预约时间 | str | 100.0% |
| `change_date_1` | 一次变更日期 | str | 9.3% |
| `change_date_2` | 二次变更日期 | str | 0.5% |
| `change_date_3` | 三次变更日期 | str | 0.0% |
| `actual_date` | 实际披露时间 | str | 100.0% |

数据样例（前 3 行）：

```
  report_period stock_code stock_name first_plan_date change_date_1 change_date_2 change_date_3 actual_date        _source          _fetched_at
0      20150331     300055        万邦达      2015-04-07           NaN           NaN           NaN  2015-04-07  stock_yysj_em  2026-11-22T17:22:13
1      20150331     002270       华明装备      2015-04-08           NaN           NaN           NaN  2015-04-08  stock_yysj_em  2026-11-22T17:22:13
2      20150331     300305       裕兴股份      2015-04-08           NaN           NaN           NaN  2015-04-08  stock_yysj_em  2026-11-22T17:22:13
```

### 财务指标（新浪，按股票）（`fin_indicator_sina`）

- 接口：`ak.stock_financial_analysis_indicator`　类别：基本面　状态：verified（成功 9/9 次调用）
- 行数：411　列数：16　频率：季度
- 日期范围：2015-03-31 ~ 2026-09-30（日期列 `report_date`）
- 说明：86 列，含净利率、扣非净利润、股息发放率。缺陷：无公告日期，只有报告期，直接用会产生未来函数；需与 fin_yjbb.announce_date 关联后才能用于回测。全市场采集为 5000+ 次请求，本阶段仅验证代表股票。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stock_code` | - | str | 100.0% |
| `report_date` | 日期 | str | 100.0% |
| `eps` | 摊薄每股收益(元) | float64 | 99.5% |
| `bps` | 每股净资产_调整后(元) | float64 | 97.3% |
| `ocf_ps` | 每股经营性现金流(元) | float64 | 97.6% |
| `gross_margin` | 销售毛利率(%) | float64 | 31.4% |
| `net_margin` | 销售净利率(%) | float64 | 86.1% |
| `roe` | 净资产收益率(%) | float64 | 99.3% |
| `roe_weighted` | 加权净资产收益率(%) | float64 | 94.6% |
| `revenue_yoy` | 主营业务收入增长率(%) | float64 | 84.4% |
| `net_profit_yoy` | 净利润增长率(%) | float64 | 98.1% |
| `net_profit_deducted` | 扣除非经常性损益后的净利润(元) | float64 | 94.4% |
| `payout_ratio` | 股息发放率(%) | float64 | 58.6% |
| `debt_ratio` | 资产负债率(%) | float64 | 99.5% |

数据样例（前 3 行）：

```
  stock_code report_date     eps   bps  ocf_ps  gross_margin  net_margin  ...  revenue_yoy  net_profit_yoy  net_profit_deducted  payout_ratio  debt_ratio                             _source          _fetched_at
0     300750  2015-12-31  1.9776  0.89     NaN       38.6415     16.6684  ...     557.9343       1610.7923         8.800957e+08           NaN     82.7241  stock_financial_analysis_indicator  2026-11-22T17:13:10
1     300750  2016-12-31  4.6498  8.42     NaN       43.7004     19.6145  ...     160.9028        207.0161         2.786451e+09           NaN     44.7637  stock_financial_analysis_indicator  2026-11-22T17:13:10
2     300750  2017-03-31     NaN   NaN     NaN       37.7566      1.1342  ...          NaN             NaN        -1.293230e+08           NaN         NaN  stock_financial_analysis_indicator  2026-11-22T17:13:10
```

### 分析师盈利预测（当前快照）（`fin_profit_forecast`）

- 接口：`ak.stock_profit_forecast_em`　类别：基本面　状态：verified（成功 1/1 次调用）
- 行数：141　列数：5　频率：快照
- 日期范围：无日期列 ~ 
- 说明：只有当前时点的预测 EPS 与评级分布，没有历史预测序列、没有上调/下调修正。未来 12 个月净利润预测及修正数据在免费源中不可得，列为缺失项。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stock_code` | 代码 | str | 100.0% |
| `stock_name` | 名称 | str | 100.0% |
| `report_count` | 研报数 | int64 | 100.0% |

数据样例（前 3 行）：

```
  stock_code stock_name  report_count                   _source          _fetched_at
0     002371       北方华创            25  stock_profit_forecast_em  2026-11-22T17:13:17
1     688041       海光信息            23  stock_profit_forecast_em  2026-11-22T17:13:17
2     600584       长电科技            21  stock_profit_forecast_em  2026-11-22T17:13:17
```

### 分红统计（全市场）（`fin_dividend_stat`）

- 接口：`ak.stock_history_dividend`　类别：基本面　状态：verified（成功 1/1 次调用）
- 行数：5675　列数：10　频率：快照
- 日期范围：无日期列 ~ 
- 说明：只有累计口径统计，没有逐年分红明细；无法直接算连续分红年数与分红支付率。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stock_code` | 代码 | str | 100.0% |
| `stock_name` | 名称 | str | 100.0% |
| `list_date` | 上市日期 | str | 100.0% |
| `dividend_cum` | 累计股息 | float64 | 100.0% |
| `dividend_avg` | 年均股息 | float64 | 100.0% |
| `dividend_count` | 分红次数 | int64 | 100.0% |
| `financing_total` | 融资总额 | float64 | 100.0% |
| `financing_count` | 融资次数 | int64 | 100.0% |

数据样例（前 3 行）：

```
  stock_code stock_name   list_date  dividend_cum  dividend_avg  dividend_count  financing_total  financing_count                 _source          _fetched_at
0     000550       江铃汽车  1993-12-01         220.1          6.88              53           0.0000                0  stock_history_dividend  2026-11-22T17:13:18
1     000541       佛山照明  1993-11-23         195.7          6.12              58          10.8842                1  stock_history_dividend  2026-11-22T17:13:18
2     000429       粤高速A  1998-02-20         179.6          6.41              52          16.3350                1  stock_history_dividend  2026-11-22T17:13:18
```

### 个股历史分红明细（巨潮）（`fin_dividend_detail`）

- 接口：`ak.stock_dividend_cninfo`　类别：基本面　状态：partial（成功 2/5 次调用）
- 行数：103　列数：12　频率：事件（按次）
- 日期范围：2000年报 ~ 2026半年报（日期列 `report_period`）
- 说明：含派息比例(每10股派息)、除权日、报告期，可重建过去12个月实际现金分红(TTM股息率)与连续分红年数。需逐股请求，红利指数 100 只成分股约 100 次调用，可接受。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stock_code` | - | str | 100.0% |
| `announce_date` | 实施方案公告日期 | str | 100.0% |
| `bonus_ratio` | 送股比例 | object | 0.0% |
| `transfer_ratio` | 转增比例 | float64 | 2.9% |
| `cash_div_per10` | 派息比例 | float64 | 100.0% |
| `record_date` | 股权登记日 | str | 100.0% |
| `ex_date` | 除权日 | str | 99.0% |
| `pay_date` | 派息日 | str | 100.0% |
| `dividend_type` | 分红类型 | str | 100.0% |
| `report_period` | 报告时间 | str | 99.0% |

数据样例（前 3 行）：

```
  stock_code announce_date bonus_ratio  transfer_ratio  cash_div_per10 record_date     ex_date    pay_date dividend_type report_period                _source          _fetched_at
0     601899    2008-07-11        None             NaN             0.9  2008-07-17  2008-07-18  2008-07-25          年度分红        2007年报  stock_dividend_cninfo  2026-11-22T17:13:19
1     601899    2009-05-25        None             NaN             1.0  2009-06-02  2009-06-03  2009-06-10          年度分红        2008年报  stock_dividend_cninfo  2026-11-22T17:13:19
2     601899    2010-06-04        None             NaN             1.0  2010-06-09  2010-06-10  2010-06-22          年度分红        2009年报  stock_dividend_cninfo  2026-11-22T17:13:19
```

### 个股历史分红明细（新浪，备用）（`fin_dividend_detail_sina`）

- 接口：`ak.stock_history_dividend_detail`　类别：基本面　状态：verified（成功 5/5 次调用）
- 行数：132　列数：10　频率：事件（按次）
- 日期范围：2001-06-12 ~ 2026-10-26（日期列 `ex_date`）
- 说明：巨潮接口(stock_dividend_cninfo)对部分股票返回 KeyError: 'records'（实测招商银行/紫金矿业/宝钢失败），新浪接口可作为兜底。缺陷：无报告期字段、无派息日，只能按公告日/除权日定位。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `symbol` | - | str | 100.0% |
| `announce_date` | 公告日期 | str | 100.0% |
| `bonus_ratio` | 送股 | int64 | 100.0% |
| `transfer_ratio` | 转增 | float64 | 100.0% |
| `cash_div_per10` | 派息 | float64 | 100.0% |
| `progress` | 进度 | str | 100.0% |
| `ex_date` | 除权除息日 | str | 97.7% |
| `record_date` | 股权登记日 | str | 97.7% |

数据样例（前 3 行）：

```
   symbol announce_date  bonus_ratio  transfer_ratio  cash_div_per10 progress     ex_date record_date                        _source          _fetched_at
0  600036    2026-07-04            0             0.0           10.03       实施  2026-07-10  2026-07-09  stock_history_dividend_detail  2026-11-22T17:18:21
1  600036    2026-01-10            0             0.0           10.13       实施  2026-01-16  2026-01-15  stock_history_dividend_detail  2026-11-22T17:18:21
2  600036    2025-12-30            0             0.0           10.13       预案         NaN         NaN  stock_history_dividend_detail  2026-11-22T17:18:21
```

### 申万行业分类变更历史（`fin_industry_clf_sw`）

- 接口：`ak.stock_industry_clf_hist_sw`　类别：基本面　状态：verified（成功 1/1 次调用）
- 行数：12940　列数：6　频率：事件
- 日期范围：1990-01-01 ~ 2026-11-20（日期列 `start_date`）
- 说明：解决『历史行业分类变化』要求：每只股票在不同区间归属不同申万行业，回测时须按 start_date 取当时分类，不能用今天的分类回溯。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stock_code` | symbol | str | 100.0% |
| `start_date` | start_date | str | 100.0% |
| `industry_code` | industry_code | str | 100.0% |
| `update_time` | update_time | str | 100.0% |

数据样例（前 3 行）：

```
  stock_code  start_date industry_code update_time                     _source          _fetched_at
0     000001  1991-04-03        440101  2015-10-27  stock_industry_clf_hist_sw  2026-11-22T17:13:19
1     000001  2014-02-21        480101  2024-09-27  stock_industry_clf_hist_sw  2026-11-22T17:13:19
2     000001  2021-07-30        480301  2025-12-15  stock_industry_clf_hist_sw  2026-11-22T17:13:19
```

### 制造业与非制造业 PMI（`macro_pmi`）

- 接口：`ak.macro_china_pmi`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：226　列数：7　频率：月
- 日期范围：2008年01月份 ~ 2026年10月份（日期列 `stat_month`）
- 说明：stat_month 形如『2026年10月份』，为统计月份而非发布日。PMI 于次月首个工作日左右发布，回测须滞后 1 个月使用。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stat_month` | 月份 | str | 100.0% |
| `pmi_manufacturing` | 制造业-指数 | float64 | 100.0% |
| `pmi_manufacturing_yoy` | 制造业-同比增长 | float64 | 100.0% |
| `pmi_non_manufacturing` | 非制造业-指数 | float64 | 100.0% |
| `pmi_non_manufacturing_yoy` | 非制造业-同比增长 | float64 | 100.0% |

数据样例（前 3 行）：

```
  stat_month  pmi_manufacturing  pmi_manufacturing_yoy  pmi_non_manufacturing  pmi_non_manufacturing_yoy          _source          _fetched_at
0  2026年10月份               49.3               0.612245                   49.7                  -0.798403  macro_china_pmi  2026-11-22T17:16:35
1  2026年09月份               50.1               0.602410                   50.2                   0.400000  macro_china_pmi  2026-11-22T17:16:35
2  2026年08月份               49.8               0.809717                   49.0                  -2.584493  macro_china_pmi  2026-11-22T17:16:35
```

### CPI（`macro_cpi`）

- 接口：`ak.macro_china_cpi`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：226　列数：7　频率：月
- 日期范围：2008年01月份 ~ 2026年10月份（日期列 `stat_month`）
- 说明：无发布日字段；CPI 通常次月中旬发布。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stat_month` | 月份 | str | 100.0% |
| `cpi_index` | 全国-当月 | float64 | 100.0% |
| `cpi_yoy` | 全国-同比增长 | float64 | 100.0% |
| `cpi_mom` | 全国-环比增长 | float64 | 100.0% |
| `cpi_ytd` | 全国-累计 | float64 | 100.0% |

数据样例（前 3 行）：

```
  stat_month  cpi_index  cpi_yoy  cpi_mom  cpi_ytd          _source          _fetched_at
0  2026年10月份      100.7      0.7      0.0    100.9  macro_china_cpi  2026-11-22T17:13:20
1  2026年09月份      100.9      0.9      0.2    100.9  macro_china_cpi  2026-11-22T17:13:20
2  2026年08月份      100.8      0.8      0.4    100.9  macro_china_cpi  2026-11-22T17:13:20
```

### PPI（`macro_ppi`）

- 接口：`ak.macro_china_ppi`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：250　列数：6　频率：月
- 日期范围：2006年01月份 ~ 2026年10月份（日期列 `stat_month`）
- 说明：周期风格核心指标。无发布日字段，须按统计局发布节奏（次月 9 日左右）滞后使用。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stat_month` | 月份 | str | 100.0% |
| `ppi_index` | 当月 | float64 | 100.0% |
| `ppi_yoy` | 当月同比增长 | float64 | 100.0% |
| `ppi_ytd` | 累计 | float64 | 100.0% |

数据样例（前 3 行）：

```
  stat_month  ppi_index  ppi_yoy  ppi_ytd          _source          _fetched_at
0  2026年10月份      105.7      5.7    102.7  macro_china_ppi  2026-11-22T17:13:20
1  2026年09月份      105.0      5.0    102.3  macro_china_ppi  2026-11-22T17:13:20
2  2026年08月份      103.8      3.8    102.0  macro_china_ppi  2026-11-22T17:13:20
```

### 货币供应量 M0/M1/M2（`macro_money_supply`）

- 接口：`ak.macro_china_money_supply_em`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：226　列数：9　频率：月
- 日期范围：2008年01月份 ~ 2026年10月份（日期列 `stat_month`）
- 说明：旧名 macro_china_money_supply 已废弃。M1-M2 剪刀差可作为风格轮动的流动性代理变量。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stat_month` | 月份 | str | 100.0% |
| `m2_amount` | 货币和准货币(M2)-数量(亿元) | float64 | 100.0% |
| `m2_yoy` | 货币和准货币(M2)-同比增长 | float64 | 100.0% |
| `m1_amount` | 货币(M1)-数量(亿元) | float64 | 100.0% |
| `m1_yoy` | 货币(M1)-同比增长 | float64 | 100.0% |
| `m0_amount` | 流通中的现金(M0)-数量(亿元) | float64 | 100.0% |
| `m0_yoy` | 流通中的现金(M0)-同比增长 | float64 | 100.0% |

数据样例（前 3 行）：

```
  stat_month   m2_amount  m2_yoy   m1_amount  m1_yoy  m0_amount  m0_yoy                      _source          _fetched_at
0  2026年10月份  3590550.61     7.1  1168959.97     4.4  149971.13    10.7  macro_china_money_supply_em  2026-11-22T17:13:20
1  2026年09月份  3596289.70     7.2  1167563.84     3.2  150169.14    10.6  macro_china_money_supply_em  2026-11-22T17:13:20
2  2026年08月份  3568083.60     7.5  1157741.43     4.1  148311.98    11.2  macro_china_money_supply_em  2026-11-22T17:13:20
```

### 社会融资规模增量（`macro_social_financing`）

- 接口：`ak.macro_china_social_financing`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：136　列数：7　频率：月
- 日期范围：201501 ~ 202604（日期列 `stat_month`）
- 说明：stat_month 为 YYYYMM 字符串。该源最新月份存在滞后/异常排序，入库后须按月份重新排序校验。社融存量同比增速需自行由增量累加计算。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stat_month` | 月份 | str | 100.0% |
| `sf_increment` | 社会融资规模增量 | int64 | 100.0% |
| `sf_rmb_loan` | 其中-人民币贷款 | int64 | 100.0% |
| `sf_corp_bond` | 其中-企业债券 | int64 | 100.0% |
| `sf_equity` | 其中-非金融企业境内股票融资 | float64 | 100.0% |

数据样例（前 3 行）：

```
  stat_month  sf_increment  sf_rmb_loan  sf_corp_bond  sf_equity                       _source          _fetched_at
0     201501         20516        14708          1868      526.0  macro_china_social_financing  2026-11-22T17:13:21
1     201502         13609        11437           716      542.0  macro_china_social_financing  2026-11-22T17:13:21
2     201503         12433         9920          1344      639.0  macro_china_social_financing  2026-11-22T17:13:21
```

### 工业增加值同比（`macro_industrial_value_added`）

- 接口：`ak.macro_china_industrial_value_added`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：207　列数：6　频率：月
- 日期范围：2008年02月份 ~ 2026年10月份（日期列 `stat_month`）
- 说明：虽有『发布时间』字段，但实为统计月首日（伪发布日），不可直接当可得日使用。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stat_month` | 月份 | str | 100.0% |
| `iva_yoy` | 同比增长 | float64 | 94.2% |
| `iva_ytd` | 累计增长 | float64 | 100.0% |
| `publish_date` | 发布时间 | str | 100.0% |

数据样例（前 3 行）：

```
  stat_month  iva_yoy  iva_ytd publish_date                             _source          _fetched_at
0  2008年02月份     15.4     15.4   2008-02-01  macro_china_industrial_value_added  2026-11-22T17:13:21
1  2008年03月份     17.8     16.4   2008-03-01  macro_china_industrial_value_added  2026-11-22T17:13:21
2  2008年04月份     15.7     16.3   2008-04-01  macro_china_industrial_value_added  2026-11-22T17:13:21
```

### 规模以上工业企业主要经济指标（含利润总额）（`macro_industrial_profit`）

- 接口：`ak.macro_china_nbs_nation`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：6858　列数：5　频率：月
- 日期范围：2015年10月 ~ 2026年9月（日期列 `stat_month`）
- 说明：国家统计局直连。返回为『指标 × 月份』宽表(76 行 × 129 列)，入库前需 unpivot 成长表。含利润总额、营业收入、亏损企业数等。缺陷：无发布日，且部分指标历史为空。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `indicator` | - | str | 100.0% |
| `stat_month` | - | str | 100.0% |
| `value` | - | float64 | 100.0% |

数据样例（前 3 行）：

```
     indicator stat_month     value                 _source          _fetched_at
0  企业单位数本月末(个)    2026年9月  513505.0  macro_china_nbs_nation  2026-11-22T17:13:27
1   亏损企业本月末(个)    2026年9月  149095.0  macro_china_nbs_nation  2026-11-22T17:13:27
2  亏损企业上年同期(个)    2026年9月  141230.0  macro_china_nbs_nation  2026-11-22T17:13:27
```

### 固定资产投资（`macro_fixed_asset_investment`）

- 接口：`ak.macro_china_fixed_asset_investment`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：163　列数：7　频率：月
- 日期范围：2012年02月份 ~ 2026年10月份（日期列 `stat_month`）
- 说明：仅自 2012 年起，早期存在空值。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `stat_month` | 月份 | str | 100.0% |
| `fai_amount` | 当月 | float64 | 90.8% |
| `fai_yoy` | 同比增长 | float64 | 84.7% |
| `fai_mom` | 环比增长 | float64 | 81.6% |
| `fai_ytd` | 自年初累计 | float64 | 100.0% |

数据样例（前 3 行）：

```
  stat_month  fai_amount  fai_yoy  fai_mom   fai_ytd                             _source          _fetched_at
0  2026年10月份     30709.0   -17.84   -25.14  364824.0  macro_china_fixed_asset_investment  2026-11-22T17:13:28
1  2026年09月份     41023.0    -9.69    25.21  334115.0  macro_china_fixed_asset_investment  2026-11-22T17:13:28
2  2026年08月份     32764.0   -13.51    -3.52  293092.0  macro_china_fixed_asset_investment  2026-11-22T17:13:28
```

### 中债国债收益率曲线（含 10 年）（`macro_bond_yield`）

- 接口：`ak.bond_zh_us_yield_em`　类别：宏观　状态：verified（成功 1/1 次调用）
- 行数：9393　列数：8　频率：日
- 日期范围：1990-12-19 ~ 2026-11-20（日期列 `trade_date`）
- 说明：1990 年起日频，是红利股『股息率-国债收益率』利差的核心输入。同时含美债收益率，可作为全球利率环境参考。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | 日期 | str | 100.0% |
| `cn_2y` | 中国国债收益率2年 | float64 | 66.2% |
| `cn_5y` | 中国国债收益率5年 | float64 | 66.2% |
| `cn_10y` | 中国国债收益率10年 | float64 | 66.2% |
| `cn_30y` | 中国国债收益率30年 | float64 | 66.2% |
| `cn_10y_2y_spread` | 中国国债收益率10年-2年 | float64 | 66.2% |

数据样例（前 3 行）：

```
   trade_date  cn_2y  cn_5y  cn_10y  cn_30y  cn_10y_2y_spread              _source          _fetched_at
0  1990-12-19    NaN    NaN     NaN     NaN               NaN  bond_zh_us_yield_em  2026-11-22T17:13:30
1  1990-12-20    NaN    NaN     NaN     NaN               NaN  bond_zh_us_yield_em  2026-11-22T17:13:30
2  1990-12-21    NaN    NaN     NaN     NaN               NaN  bond_zh_us_yield_em  2026-11-22T17:13:30
```

### 银行间回购定盘利率（DR007）（`macro_dr007`）

- 接口：`ak.interest_rate_repo_hist_cm`　类别：宏观　状态：verified（成功 12/12 次调用）
- 行数：2963　列数：10　频率：日
- 日期范围：2015-01-04 ~ 2026-11-20（日期列 `trade_date`）
- 说明：FDR007 为存款类机构 7 天回购定盘利率，即 DR007 的近似。接口限制单次区间不超过 1 年，需按年循环。实测 2015-2016 年 FDR007 全为空，实际起点晚于 2017。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `year` | - | int64 | 100.0% |
| `trade_date` | date | str | 100.0% |
| `fr001` | FR001 | float64 | 100.0% |
| `fr007` | FR007 | float64 | 100.0% |
| `fr014` | FR014 | float64 | 100.0% |
| `fdr001` | FDR001 | float64 | 79.8% |
| `fdr007` | FDR007 | float64 | 79.8% |
| `fdr014` | FDR014 | float64 | 79.8% |

数据样例（前 3 行）：

```
   year  trade_date  fr001  fr007  fr014  fdr001  fdr007  fdr014                     _source          _fetched_at
0  2015  2015-01-04   3.61   4.89   5.79     NaN     NaN     NaN  interest_rate_repo_hist_cm  2026-11-22T17:13:30
1  2015  2015-01-05   3.30   4.49   4.80     NaN     NaN     NaN  interest_rate_repo_hist_cm  2026-11-22T17:13:30
2  2015  2015-01-06   3.03   4.06   4.97     NaN     NaN     NaN  interest_rate_repo_hist_cm  2026-11-22T17:13:30
```

### 上交所融资融券汇总（`flow_margin_sse`）

- 接口：`ak.stock_margin_sse`　类别：资金　状态：verified（成功 12/12 次调用）
- 行数：2887　列数：10　频率：日
- 日期范围：20150105 ~ 20261120（日期列 `trade_date`）
- 单位：单位：元
- 说明：单次查询返回行数有上限（实测约 2000 行，即 8 年左右），故按年循环抓取；仅沪市，需与深市合并得全市场两融。返回的『信用交易日期』为整型(YYYYMMDD)，入库已统一为字符串。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | 信用交易日期 | str | 100.0% |
| `margin_balance` | 融资余额 | int64 | 100.0% |
| `margin_buy` | 融资买入额 | int64 | 100.0% |
| `short_volume` | 融券余量 | int64 | 100.0% |
| `short_amount` | 融券余量金额 | int64 | 100.0% |
| `short_sell_volume` | 融券卖出量 | int64 | 100.0% |
| `margin_total` | 融资融券余额 | int64 | 100.0% |
| `year` | - | float64 | 100.0% |

数据样例（前 3 行）：

```
  trade_date  margin_balance   margin_buy  short_volume  short_amount  short_sell_volume  margin_total           _source          _fetched_at    year
0   20151231    680522261155  26481517358     389898016    2110497327           25617261  682632758482  stock_margin_sse  2026-11-22T17:18:01  2015.0
1   20151230    690624418175  34774521611     387461740    2134120717           26235283  692758538892  stock_margin_sse  2026-11-22T17:18:01  2015.0
2   20151229    689699599137  28878201901     384517703    2141562769           32745600  691841161906  stock_margin_sse  2026-11-22T17:18:01  2015.0
```

### 深交所融资融券（全历史）（`flow_margin_szse`）

- 接口：`ak.stock_margin_szse_js`　类别：资金　状态：verified（成功 1/1 次调用）
- 行数：3829　列数：9　频率：日
- 日期范围：2010-03-31 ~ 2026-11-05（日期列 `trade_date`）
- 单位：单位：元
- 说明：一次返回 2010 年至今全历史，优于 stock_margin_szse（后者仅支持单日，且单位为亿元）。注：同为深市两融，两个接口单位口径不同，不可混用。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | 日期 | str | 100.0% |
| `margin_buy` | 融资买入额 | float64 | 100.0% |
| `margin_balance` | 融资余额 | float64 | 100.0% |
| `short_sell_volume` | 融券卖出量 | float64 | 65.5% |
| `short_volume` | 融券余量 | float64 | 65.5% |
| `short_amount` | 融券余额 | float64 | 100.0% |
| `margin_total` | 融资融券余额 | float64 | 100.0% |

数据样例（前 3 行）：

```
   trade_date  margin_buy  margin_balance  short_sell_volume  short_volume  short_amount  margin_total               _source          _fetched_at
0  2010-03-31    684569.0        670796.0             4000.0        3900.0       70895.0      741691.0  stock_margin_szse_js  2026-11-22T17:13:33
1  2010-04-08   6713260.0      14467758.0             2100.0        3100.0       56023.0    14523781.0  stock_margin_szse_js  2026-11-22T17:13:33
2  2010-04-09   9357095.0      19732998.0             6700.0        5400.0      108362.0    19841360.0  stock_margin_szse_js  2026-11-22T17:13:33
```

### 北向资金历史（`flow_northbound`）

- 接口：`ak.stock_hsgt_hist_em`　类别：资金　状态：verified（成功 1/1 次调用）
- 行数：2794　列数：8　频率：日
- 日期范围：2014-11-17 ~ 2026-11-20（日期列 `trade_date`）
- 说明：2024-08 起沪深港通停止披露日频净买入，尾部字段大面积为空。历史段（2014-11 至 2024-08）可用，之后不可用，构成结构性断点。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | 日期 | str | 100.0% |
| `net_buy` | 当日成交净买额 | float64 | 81.0% |
| `buy_amount` | 买入成交额 | float64 | 81.0% |
| `sell_amount` | 卖出成交额 | float64 | 81.0% |
| `net_buy_cum` | 历史累计净买额 | float64 | 81.0% |
| `hs300_close` | 沪深300 | float64 | 100.0% |

数据样例（前 3 行）：

```
   trade_date   net_buy  buy_amount  sell_amount  net_buy_cum  hs300_close             _source          _fetched_at
0  2014-11-17  120.8233    120.8233          NaN     0.012082      2474.01  stock_hsgt_hist_em  2026-11-22T17:13:34
1  2014-11-18   47.1967     49.4367       2.2400     0.016802      2456.37  stock_hsgt_hist_em  2026-11-22T17:13:34
2  2014-11-19   24.9677     26.6951       1.7274     0.019299      2450.99  stock_hsgt_hist_em  2026-11-22T17:13:34
```

### 深交所市场总貌（成交额/流通市值）（`flow_szse_summary`）

- 接口：`ak.stock_summary_szse`　类别：资金　状态：verified（成功 1/1 次调用）
- 行数：14　列数：7　频率：快照（单日）
- 日期范围：无日期列 ~ 
- 说明：仅支持单日查询，要得到历史序列需逐日循环(2015 年至今约 2600 次)，成本高。可用于校验由指数成交额推算的全市场换手率。上交所对应接口 stock_summary_sse 只返回最近交易日，无历史。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `sec_type` | 证券类别 | str | 100.0% |
| `count` | 数量 | int64 | 100.0% |
| `amount` | 成交金额 | float64 | 100.0% |
| `total_mv` | 总市值 | float64 | 78.6% |
| `float_mv` | 流通市值 | float64 | 78.6% |

数据样例（前 3 行）：

```
  sec_type  count        amount      total_mv      float_mv             _source          _fetched_at
0       股票   2941  7.207150e+11  3.403813e+13  2.901348e+13  stock_summary_szse  2026-11-22T17:13:34
1     主板A股   1494  3.810404e+11  2.079428e+13  1.844572e+13  stock_summary_szse  2026-11-22T17:13:34
2     主板B股     36  7.609065e+07  3.352203e+10  3.350755e+10  stock_summary_szse  2026-11-22T17:13:34
```

### 上交所 ETF 份额（`flow_etf_scale_sse`）

- 接口：`ak.fund_etf_scale_sse`　类别：资金　状态：verified（成功 1/1 次调用）
- 行数：927　列数：7　频率：快照（单日）
- 日期范围：2026-11-20 ~ 2026-11-20（日期列 `stat_date`）
- 说明：单日快照，历史需逐日循环。ETF 份额变化是观察风格资金流入的可靠代理，但无法一次性取得长历史。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `fund_code` | 基金代码 | str | 100.0% |
| `fund_name` | 基金简称 | str | 100.0% |
| `etf_type` | ETF类型 | str | 100.0% |
| `stat_date` | 统计日期 | str | 100.0% |
| `shares` | 基金份额 | float64 | 100.0% |

数据样例（前 3 行）：

```
  fund_code fund_name etf_type   stat_date       shares             _source          _fetched_at
0    510010     治理ETF       单市  2026-11-20  127524400.0  fund_etf_scale_sse  2026-11-22T17:13:34
1    510020     超大ETF       单市  2026-11-20   36848000.0  fund_etf_scale_sse  2026-11-22T17:13:34
2    510030     价值ETF       单市  2026-11-20  118729800.0  fund_etf_scale_sse  2026-11-22T17:13:34
```

### 外盘商品期货（铜/铝/黄金/白银）（`cyc_futures_foreign`）

- 接口：`ak.futures_foreign_hist_sina`　类别：周期　状态：verified（成功 4/4 次调用）
- 行数：10305　列数：11　频率：日
- 日期范围：2016-11-22 00:00:00 ~ 2026-11-20 00:00:00（日期列 `trade_date`）
- 单位：HG=COMEX铜(美分/磅)；AHD=COMEX铝(美元/吨)；GC=COMEX黄金(美元/盎司)；SI=COMEX白银(美元/盎司)
- 说明：均为外盘，计价单位为美元，与国内沪铜/沪铝存在汇率与内外盘价差。volume/position 大量为 0，不宜做量能分析。历史起点约 2016-11，无法覆盖 2015 年。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `symbol` | - | str | 100.0% |
| `trade_date` | date | str | 100.0% |
| `open` | open | float64 | 100.0% |
| `high` | high | float64 | 100.0% |
| `low` | low | float64 | 100.0% |
| `close` | close | float64 | 100.0% |
| `volume` | volume | int64 | 100.0% |
| `position` | position | int64 | 100.0% |
| `settlement` | settlement | float64 | 75.4% |

数据样例（前 3 行）：

```
  symbol           trade_date    open    high     low   close  volume  position  settlement                    _source          _fetched_at
0     HG  2016-11-22 00:00:00  251.85  257.55  251.65  254.40       0         0         0.0  futures_foreign_hist_sina  2026-11-22T17:13:35
1     HG  2016-11-23 00:00:00  254.80  262.50  252.00  261.60       0         0         0.0  futures_foreign_hist_sina  2026-11-22T17:13:35
2     HG  2016-11-24 00:00:00  261.55  269.90  261.25  265.85       0         0         0.0  futures_foreign_hist_sina  2026-11-22T17:13:35
```

### 上金所黄金现货（Au99.99）（`cyc_sge_gold`）

- 接口：`ak.spot_hist_sge`　类别：周期　状态：verified（成功 1/1 次调用）
- 行数：2407　列数：7　频率：日
- 日期范围：2016-12-19 ~ 2026-11-20（日期列 `trade_date`）
- 单位：元/克，人民币计价
- 说明：人民币金价，已含汇率因素，适合与 A 股周期板块对照。起点 2016-12。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | date | str | 100.0% |
| `open` | open | float64 | 100.0% |
| `close` | close | float64 | 100.0% |
| `low` | low | float64 | 100.0% |
| `high` | high | float64 | 100.0% |

数据样例（前 3 行）：

```
   trade_date    open   close     low    high        _source          _fetched_at
0  2016-12-19  262.45  262.76  262.02  263.50  spot_hist_sge  2026-11-22T17:13:36
1  2016-12-20  262.88  262.06  261.42  263.70  spot_hist_sge  2026-11-22T17:13:36
2  2016-12-21  262.40  260.97  258.60  262.65  spot_hist_sge  2026-11-22T17:13:36
```

### 期货库存（沪铜/沪铝）（`cyc_inventory`）

- 接口：`ak.futures_inventory_em`　类别：周期　状态：verified（成功 2/2 次调用）
- 行数：134　列数：6　频率：日（仅近约 60 个交易日）
- 日期范围：2026-08-12 ~ 2026-11-20（日期列 `trade_date`）
- 说明：仅返回近约 60 个交易日，无历史序列，无法用于 2015 年以来的库存周期研究。库存长历史需 Paid 源或交易所周报。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `symbol` | - | str | 100.0% |
| `trade_date` | 日期 | str | 100.0% |
| `inventory` | 库存 | int64 | 100.0% |
| `inventory_chg` | 增减 | float64 | 98.5% |

数据样例（前 3 行）：

```
  symbol  trade_date  inventory  inventory_chg               _source          _fetched_at
0     沪铜  2026-08-12      24131            NaN  futures_inventory_em  2026-11-22T17:13:36
1     沪铜  2026-08-13      27208         3077.0  futures_inventory_em  2026-11-22T17:13:36
2     沪铜  2026-08-14      33676         6468.0  futures_inventory_em  2026-11-22T17:13:36
```

### 交易日历（`dim_trade_calendar`）

- 接口：`ak.calendar_trade_date_hist_sina`　类别：行情　状态：verified（成功 1/1 次调用）
- 行数：8797　列数：3　频率：日
- 日期范围：1990-12-19 ~ 2026-12-31（日期列 `trade_date`）
- 说明：用于对齐各源日期、剔除伪交易日（如中证接口在元旦等出现的重复行）。

| 字段 | 含义/英文名 | 类型 | 非空率 |
|---|---|---|---|
| `trade_date` | trade_date | str | 100.0% |

数据样例（前 3 行）：

```
   trade_date                        _source          _fetched_at
0  1990-12-19  calendar_trade_date_hist_sina  2026-11-22T17:16:35
1  1990-12-20  calendar_trade_date_hist_sina  2026-11-22T17:16:35
2  1990-12-21  calendar_trade_date_hist_sina  2026-11-22T17:16:35
```

