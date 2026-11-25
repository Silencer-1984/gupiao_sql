from _probe import p, ak
import time
p("futures_foreign_commodity_subscribe_exchange_symbol", lambda: ak.futures_foreign_commodity_subscribe_exchange_symbol())
time.sleep(1)
p("futures_inventory_em 铜", lambda: ak.futures_inventory_em(symbol="铜"))
time.sleep(2)
p("stock_profit_forecast_em 半导体", lambda: ak.stock_profit_forecast_em(symbol="半导体"))
