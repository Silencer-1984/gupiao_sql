import akshare as ak, json
print(json.dumps(ak.interface_info('stock_summary_sse'), ensure_ascii=False)[:700])
for y in [2015, 2016]:
    try:
        df = ak.interest_rate_repo_hist_cm(start_date=f"{y}0101", end_date=f"{y}1231")
        print(y, "FDR007 rows", df.shape, df['date'].iloc[0], df['date'].iloc[-1], "nan:", df['FDR007'].isna().sum())
    except Exception as e:
        print(y, "ERR", type(e).__name__, str(e)[:150])
