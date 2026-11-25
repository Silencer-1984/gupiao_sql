from _probe import p, ak
import time, json
print(json.dumps(ak.interface_info('stock_margin_szse_js'), ensure_ascii=False)[:500])
p("stock_margin_szse_js", lambda: ak.stock_margin_szse_js())
time.sleep(1)
p("stock_hsgt_hist_em 北向", lambda: ak.stock_hsgt_hist_em(symbol="北向资金"))
time.sleep(1)
p("fund_etf_scale_szse 20251120", lambda: ak.fund_etf_scale_szse(date="20251120"))
