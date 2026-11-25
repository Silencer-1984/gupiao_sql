from _probe import p, ak
p("index_analysis_daily_sw 一级行业 20150101-20150115", lambda: ak.index_analysis_daily_sw(symbol="一级行业", start_date="20150101", end_date="20150115"))
p("stock_margin_sse 20150105-20150109", lambda: ak.stock_margin_sse(start_date="20150105", end_date="20150109"))
p("stock_margin_szse 20251120", lambda: ak.stock_margin_szse(date="20251120"))
p("index_stock_cons_csindex 000922", lambda: ak.index_stock_cons_csindex(symbol="000922"))
p("stock_zh_index_spot?", lambda: ak.index_stock_info())
