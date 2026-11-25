from _probe import p, ak
import time
p("stock_yjbb_em 20200331", lambda: ak.stock_yjbb_em(date="20200331"))
time.sleep(3)
p("index_zh_hist_em 000688", lambda: ak.index_zh_hist_em(symbol="000688", period="daily", start_date="20150101", end_date="20251120"))
time.sleep(3)
p("fund_etf_hist_em 510880", lambda: ak.fund_etf_hist_em(symbol="510880", period="daily", start_date="20150101", end_date="20251120", adjust=""))
