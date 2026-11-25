import akshare as ak, time
print(list(ak.futures_foreign_commodity_subscribe_exchange_symbol()['代码']))
try:
    df=ak.futures_inventory_em(symbol="沪铜"); print("inventory 沪铜", df.shape, list(df.columns)); print(df.tail(3))
except Exception as e: print("ERR inv 沪铜", type(e).__name__, str(e)[:300])
