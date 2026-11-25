from _probe import p, ak
import pandas as pd
def sw(sym, s, e):
    df = ak.index_analysis_daily_sw(symbol=sym, start_date=s, end_date=e)
    print("cols:", list(df.columns)); return df
p("sw 一级行业 20251101-20251120", lambda: sw("一级行业","20251101","20251120"))
p("sw 风格指数 20251101-20251120", lambda: sw("风格指数","20251101","20251120"))
p("index_stock_cons 000922", lambda: ak.index_stock_cons(symbol="000922"))
