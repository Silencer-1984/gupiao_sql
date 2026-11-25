import akshare as ak, json
for fn in ["interest_rate_repo_hist_cm","stock_margin_sse","stock_margin_szse","index_zh_hist_em","index_hist_csindex","index_value_csindex","stock_yjbb_em","stock_profit_forecast_em","fund_etf_hist_em","macro_china_nbs_nation","stock_zh_a_spot_em","futures_inventory_em","stock_financial_analysis_indicator","stock_dividend_cninfo","index_analysis_daily_sw","fund_etf_scale_sse"]:
    try:
        info=ak.interface_info(fn)
        print(f"## {fn}: desc={info.get('desc')}")
        print("   params:", [(p['name'],p['desc'][:90]) for p in info.get('params',[])])
        print("   outputs:", [o['name'] for o in info.get('outputs',[])][:25])
    except Exception as e:
        print(f"## {fn}: INFO-ERR {type(e).__name__} {str(e)[:100]}")
