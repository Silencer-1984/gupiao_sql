from _probe import p, ak
import time
p("stock_value_em 600519", lambda: ak.stock_value_em(symbol="600519"))
time.sleep(1)
p("stock_history_dividend", lambda: ak.stock_history_dividend())
time.sleep(1)
p("futures_foreign_hist_sina HG", lambda: ak.futures_foreign_hist_sina(symbol="HG"))
time.sleep(1)
p("stock_industry_clf_hist_sw", lambda: ak.stock_industry_clf_hist_sw())
