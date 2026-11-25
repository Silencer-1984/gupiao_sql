from _probe import p, ak
p("index_zh_daily_em sh000688", lambda: ak.index_zh_daily_em(symbol="sh000688"))
p("index_zh_hist_em 000688", lambda: ak.index_zh_hist_em(symbol="000688", period="daily", start_date="20150101", end_date="20251120"))
p("index_hist_csindex 000922", lambda: ak.index_hist_csindex(symbol="000922", start_date="20150101", end_date="20251120"))
p("index_zh_daily_sina sh000688", lambda: ak.index_zh_daily_sina(symbol="sh000688"))
p("index_value_csindex H30374", lambda: ak.index_value_csindex(symbol="H30374"))
