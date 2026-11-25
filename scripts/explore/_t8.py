from _probe import p, ak
import time
p("fund_etf_hist_sina 510880", lambda: ak.fund_etf_hist_sina(symbol="sh510880"))
time.sleep(1)
p("index_zh_daily_tx sh000688", lambda: ak.index_zh_daily_tx(symbol="sh000688"))
time.sleep(1)
p("index_hist_cni 399006", lambda: ak.index_hist_cni(symbol="399006", start_date="20150101", end_date="20251120"))
time.sleep(1)
p("stock_financial_analysis_indicator 600016 2015", lambda: ak.stock_financial_analysis_indicator(symbol="600016", start_year="2015"))
