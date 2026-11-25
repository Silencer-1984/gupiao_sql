from _probe import p, ak
import time
p("stock_index_pe_lg 沪深300", lambda: ak.stock_index_pe_lg(symbol="沪深300"))
time.sleep(1)
p("stock_index_pb_lg 沪深300", lambda: ak.stock_index_pb_lg(symbol="沪深300"))
time.sleep(1)
p("stock_a_gxl_lg", lambda: ak.stock_a_gxl_lg(symbol="上证A股"))
time.sleep(1)
p("stock_a_congestion_lg", lambda: ak.stock_a_congestion_lg())
