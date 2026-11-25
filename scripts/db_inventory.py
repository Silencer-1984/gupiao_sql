# -*- coding: utf-8 -*-
"""生成数据库清点文档 docs/db_inventory.md（可重复运行）。"""
import os, sqlite3, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "ashare.db")
OUT = os.path.join(ROOT, "docs", "db_inventory.md")

# 表 -> (中文名, 分类, 粒度/说明)
CATALOG = {
    # A 行情
    "px_index_daily_csi": ("中证指数日行情（含 PE-TTM）", "A 行情", "指数×交易日"),
    "px_index_daily_cni": ("国证指数日行情（创业板系列）", "A 行情", "指数×交易日"),
    "px_index_daily_tx": ("指数换手率（腾讯）", "A 行情", "指数×交易日"),
    "px_index_daily_us": ("美股指数日行情（纳指100/纳指综合）", "A 行情", "指数×交易日"),
    "px_etf_daily": ("ETF 日行情", "A 行情", "ETF×交易日"),
    "px_lof_daily": ("LOF/ETF 价+净值+溢价率", "A 行情", "基金×交易日"),
    "px_stock_daily": ("个股不复权日行情（成分股）", "A 行情", "个股×交易日"),
    # B 维度
    "px_index_cons_csi": ("指数成分股与权重（中证官方）", "B 维度", "指数×成分股（当前快照）"),
    "px_index_cons": ("指数成分股（新浪，有重复，弃用）", "B 维度", "指数×成分股"),
    "px_index_meta": ("指数基本信息（发布日）", "B 维度", "指数"),
    "dim_trade_calendar": ("交易日历", "B 维度", "日期"),
    "fin_industry_clf_sw": ("申万行业分类历史", "B 维度", "个股×生效区间"),
    # C 财务
    "fin_yjbb": ("全市场业绩报表（季频面板）", "C 财务", "股票×报告期"),
    "fin_disclosure": ("财报实际披露日期（PIT 基准）", "C 财务", "股票×报告期"),
    "fin_indicator_sina": ("个股财务指标（净利率/扣非等）", "C 财务", "股票×报告期"),
    "fin_dividend_stat": ("分红汇总（累计口径快照）", "C 财务", "股票"),
    "fin_dividend_detail": ("分红明细（巨潮，部分失败）", "C 财务", "股票×除权日"),
    "fin_dividend_detail_sina": ("分红明细（新浪，5 只样本）", "C 财务", "股票×除权日"),
    "fin_dividend_detail_all": ("分红明细（174 只成分股，自建）", "C 财务", "股票×除权日"),
    "fin_profit_forecast": ("分析师盈利预测（当前快照）", "C 财务", "股票"),
    # D 估值
    "val_index_value_csi": ("指数估值（中证，仅最近20日）", "D 估值", "指数×交易日"),
    "val_index_pe_lg": ("宽基指数 PE（乐咕，月频）", "D 估值", "指数×月"),
    "val_index_pb_lg": ("宽基指数 PB（乐咕，月频）", "D 估值", "指数×月"),
    "val_stock_value_em": ("个股估值（PE/PB/PS/市值）", "D 估值", "股票×交易日"),
    "val_a_dividend_yield": ("全 A 股息率（日频）", "D 估值", "交易日"),
    "val_congestion_lg": ("全市场拥挤度（乐咕）", "D 估值", "交易日"),
    # E 宏观
    "macro_pmi": ("PMI", "E 宏观", "月"),
    "macro_cpi": ("CPI", "E 宏观", "月"),
    "macro_ppi": ("PPI", "E 宏观", "月"),
    "macro_money_supply": ("M0/M1/M2 货币供应", "E 宏观", "月"),
    "macro_social_financing": ("社会融资", "E 宏观", "月"),
    "macro_industrial_value_added": ("工业增加值", "E 宏观", "月"),
    "macro_industrial_profit": ("工业企业利润", "E 宏观", "指标×月"),
    "macro_fixed_asset_investment": ("固定资产投资", "E 宏观", "月"),
    "macro_bond_yield": ("国债收益率曲线", "E 宏观", "交易日"),
    "macro_dr007": ("银行间回购利率（FR/FDR）", "E 宏观", "交易日"),
    # F 资金
    "flow_margin_sse": ("沪市两融", "F 资金", "交易日"),
    "flow_margin_szse": ("深市两融", "F 资金", "交易日"),
    "flow_northbound": ("北向资金（2024-08 后断供）", "F 资金", "交易日"),
    "flow_hsgt_branch": ("沪深港通分项（沪/深股通 + 南向港股通）", "F 资金", "通道×交易日"),
    "flow_etf_scale_sse": ("沪市 ETF 份额（单日快照）", "F 资金", "基金×单日"),
    "flow_szse_summary": ("深市市场总貌（单日）", "F 资金", "板块×单日"),
    # G 商品周期
    "cyc_futures_foreign": ("外盘商品期货（铜/铝/金/银）", "G 商品", "品种×交易日"),
    "cyc_sge_gold": ("上金所黄金现货", "G 商品", "交易日"),
    "cyc_inventory": ("期货库存（近60日）", "G 商品", "品种×交易日"),
    # H 衍生自建
    "val_index_dividend_yield": ("【自建】红利指数日频股息率", "H 衍生", "指数×交易日"),
    "val_stock_dividend_yield_focus": ("【自建】中国移动/电信个股股息率", "H 衍生", "股票×交易日"),
    "val_qdii_ndx_compare": ("【自建】纳指ETF溢价率+纳指对齐", "H 衍生", "基金×交易日"),
    "mkt_vol_qvix": ("【自建】QVIX 隐含波动率（9 个标的）", "H 衍生", "标的×交易日"),
    "mkt_vol_vxn": ("【Cboe】VXN 纳指100波动率指数日线", "H 衍生", "交易日"),
    "mkt_fear_daily": ("【自建】各指数恐慌度（RV/QVIX/合成）", "H 衍生", "指数×交易日"),
    "meta_premium_stats": ("【自建】溢价率统计指标", "H 衍生", "基金×指标"),
    "web_daily_snapshot": ("【网站】每日温度/行情/舆情/结论快照", "H 衍生", "交易日"),
    "web_daily_summary": ("【网站】日/周/月总结正文（JSON）", "H 衍生", "交易日×周期"),
    "web_sentiment": ("【网站】舆情明细（热度榜+百度热搜）", "F 资金", "自然日×排名"),
    "web_sentiment_meta": ("【网站】舆情聚合结果（情绪分/分项）", "F 资金", "自然日"),
    # I 元数据
    "meta_run": ("运行记录", "I 元数据", "每次采集"),
    "meta_fetch": ("接口调用审计", "I 元数据", "每次调用"),
    "raw_archive": ("原始返回归档（gzip）", "I 元数据", "每次调用"),
}

DATE_COLS = ["trade_date", "stat_date", "as_of_date", "report_period", "report_date",
             "ex_date", "stat_month", "start_date", "announce_date", "issue_date"]
KEY_COLS = ["index_code", "stock_code", "etf_code", "fund_code", "symbol", "index_name",
            "sec_type", "indicator", "dataset_id"]


def main():
    c = sqlite3.connect(DB)
    tabs = [r[0] for r in c.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
    rows = []
    total = 0
    by_cat = {}
    for t in tabs:
        cols = [r[1] for r in c.execute(f"pragma table_info('{t}')")]
        n = c.execute(f'select count(*) from "{t}"').fetchone()[0]
        total += n
        dcol = next((x for x in DATE_COLS if x in cols), None)
        dmin = dmax = "-"
        if dcol:
            r = c.execute(f'select min("{dcol}"), max("{dcol}") from "{t}"').fetchone()
            dmin, dmax = (str(r[0])[:10] if r[0] else "-", str(r[1])[:10] if r[1] else "-")
        kcol = next((x for x in KEY_COLS if x in cols), None)
        nent = "-"
        if kcol:
            nent = c.execute(f'select count(distinct "{kcol}") from "{t}"').fetchone()[0]
        name, cat, gran = CATALOG.get(t, (t, "Z 其他", "-"))
        rows.append(dict(t=t, name=name, cat=cat, gran=gran, n=n, cols=len(cols),
                         nent=nent, dmin=dmin, dmax=dmax))
        by_cat.setdefault(cat, [0, 0])
        by_cat[cat][0] += 1
        by_cat[cat][1] += n

    size = os.path.getsize(DB) / 1048576
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    L = []
    A = L.append
    A("# 数据库清点（data/ashare.db）")
    A("")
    A(f"> 生成时间：{now}　脚本：`scripts/db_inventory.py`（可重复运行）")
    A(f"> 文件大小 **{size:.1f} MB**　表数 **{len(tabs)}**　总行数 **{total:,}**")
    A("")
    a_share = c.execute(
        "select count(distinct stock_code) from fin_yjbb "
        "where substr(stock_code,1,2) in ('60','00','30','68')").fetchone()[0]
    A(f"**一句话**：{len(tabs)} 张表、{total:,} 行、{size:.0f} MB；核心是 2015–2026 的日频行情与估值、"
      f"47 期全市场财报、10 项宏观、174 只成分股个股面板。可直接支撑「成长 / 红利 / 有色 / 纳指」四条线的因子计算。")
    A("")
    A("---")
    A("")
    A("## 1. 按类别汇总")
    A("")
    A("| 类别 | 表数 | 行数 | 占比 | 说明 |")
    A("|---|---:|---:|---:|---|")
    desc = {
        "A 行情": "价格与成交，指数/ETF/个股日线",
        "B 维度": "成分股、权重、交易日历、行业归属",
        "C 财务": "财报、披露日期、分红明细",
        "D 估值": "PE/PB/PS/股息率/拥挤度",
        "E 宏观": "PMI/CPI/PPI/货币/利率",
        "F 资金": "两融、北向、ETF 份额",
        "G 商品": "铜铝金银价格与库存",
        "H 衍生": "本项目自己算出来的序列",
        "I 元数据": "采集审计与原始归档",
        "Z 其他": "",
    }
    for cat in sorted(by_cat, key=lambda x: x[0]):
        n_t, n_r = by_cat[cat]
        A(f"| **{cat}** | {n_t} | {n_r:,} | {n_r/total*100:.1f}% | {desc.get(cat,'')} |")
    A(f"| **合计** | **{len(tabs)}** | **{total:,}** | 100% | — |")
    A("")
    A("---")
    A("")

    A("## 2. 明细清单")
    A("")
    for cat in sorted(by_cat, key=lambda x: x[0]):
        A(f"### {cat}")
        A("")
        A("| 表名 | 内容 | 行数 | 字段 | 实体数 | 时间范围 | 粒度 |")
        A("|---|---|---:|---:|---:|---|---|")
        for r in [x for x in rows if x["cat"] == cat]:
            rng = f"{r['dmin']} ~ {r['dmax']}" if r["dmin"] != "-" else "—"
            A(f"| `{r['t']}` | {r['name']} | {r['n']:,} | {r['cols']} | {r['nent']} | {rng} | {r['gran']} |")
        A("")

    A("---")
    A("")
    A("## 3. 覆盖的主体数量")
    A("")
    def one(sql):
        try:
            return c.execute(sql).fetchone()[0]
        except Exception:
            return "-"
    A("| 主体 | 数量 | 明细 |")
    A("|---|---:|---|")
    A(f"| 指数（A股） | {one('select count(distinct index_code) from px_index_daily_csi')} | 000300/000985/000015/000922/H30269/930955/000819/000688 |")
    A(f"| 指数（创业板系列） | {one('select count(distinct index_code) from px_index_daily_cni')} | 399006/399296 |")
    A(f"| 美股指数 | {one('select count(distinct index_code) from px_index_daily_us')} | .NDX/.IXIC |")
    A(f"| 个股（行情） | {one('select count(distinct stock_code) from px_stock_daily')} | 4 个红利指数成分股去重 + 中国移动/中国电信 |")
    A(f"| 个股（财报面板） | {one('select count(distinct stock_code) from fin_yjbb')} | 47 个报告期，含北交所/新三板/B 股 |")
    A(f"| 其中沪深 A 股 | {a_share} | 60x/00x/30x/68x，研究实际使用范围 |")
    A(f"| ETF | {one('select count(distinct etf_code) from px_etf_daily')} | 510880/512400/512890/588000/159915 |")
    A(f"| 场内基金 | {one('select count(distinct fund_code) from px_lof_daily')} | 270042(净)/159941(ETF)/161130(LOF) |")
    A(f"| 交易日 | {one('select count(*) from dim_trade_calendar'):,} | 1990-12-19 ~ 2026-12-31（含未来排定） |")
    A("")
    A("---")
    A("")
    A("## 4. 数据频率分布")
    A("")
    A("| 频率 | 表 | 用途 |")
    A("|---|---|---|")
    A("| **日频**（约 2,887 天，2015 起） | px_* / val_* / macro_bond_yield / macro_dr007 / flow_margin_* | 因子计算、择时 |")
    A("| **季频**（47 个报告期） | fin_yjbb / fin_disclosure / fin_indicator_sina | 景气与估值聚合 |")
    A("| **月频**（约 226~263 期） | macro_pmi / cpi / ppi / money_supply / social_financing / val_index_pe_lg / pb_lg | 宏观状态 |")
    A("| **事件型**（不定期） | fin_dividend_detail_all / fin_industry_clf_sw | 分红、行业变更 |")
    A("| **单日快照** | px_index_cons_csi / flow_etf_scale_sse / flow_szse_summary / fin_profit_forecast / val_index_value_csi(20日) | 无历史，只能当前值 |")
    A("")
    A("---")
    A("")
    A("## 5. 使用须知（踩过的坑，直接照做）")
    A("")
    A("1. **快照类数据不能回溯**：成分股、ETF 份额、分析师预测只有当前一期，回测会产生存活偏差。")
    A("2. **两套涨跌幅口径**：中证=`百分数`（3.87=+3.87%），国证=`小数`（0.0512=+5.12%）；两融 `stock_margin_sse`=元、`szse`=亿元。")
    A("3. **统计月份 ≠ 可得日期**：财报用 `fin_disclosure.actual_date`（`fin_yjbb.announce_date` 滞后约 1 年，禁用）；宏观按发布节奏滞后一个月（见 `data_dictionary.md` §5.1）。")
    A("4. **`fin_yjbb` 含非 A 股标的**：11,662 个代码里包含北交所/新三板（83xx/87xx/43xx/40xx/42xx/92xx 共约 6,300 个）与 B 股（900xx/200xx 约 77 个）。")
    A("   做沪深 A 股研究时必须过滤，只保留 `60x / 00x / 30x / 68x` 开头，否则市值加权会被新三板小票污染。")
    A("5. **指数表的伪交易日**：中证接口会返回 2015-01-01、2018-06-18 等非交易日行，必须按 `dim_trade_calendar` 过滤。")
    A("6. **交易日历含未来日期**：`dim_trade_calendar` 排到 2026-12-31，算序列时必须截断到 `max(实际行情日期)`，否则生成假数据。")
    A("7. **`px_index_daily_csi` / `px_index_cons_csi` 无主键**：写入前必须先 DELETE 再 INSERT，`INSERT OR REPLACE` 会重复。")
    A("")
    A("---")
    A("")
    A("## 6. 尚未入库（明确缺口）")
    A("")
    A("| 数据 | 原因 |")
    A("|---|---|")
    A("| 逐期历史成分股 | 接口只有当前快照 |")
    A("| 指数 PB（红利/有色） | 免费源仅 4 个宽基月度 |")
    A("| 研发费用率 | 需逐股取利润表，成本高 |")
    A("| 分析师预期修正历史 | 只有当前快照 |")
    A("| 有色供需平衡表 / 工业金属库存长历史 | 无免费源 |")
    A("| 风格广度（成分股上涨比例） | 缺全市场个股日行情（当前仅 174 只） |")
    A("")

    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print(f"written {OUT}")
    print(f"tables={len(tabs)} rows={total:,} size={size:.1f}MB")
    for cat in sorted(by_cat):
        print(f"  {cat}: {by_cat[cat][0]} 表 / {by_cat[cat][1]:,} 行")


if __name__ == "__main__":
    main()
