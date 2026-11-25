import akshare as ak, time
codes = {"000688":"科创50","000922":"中证红利","H30269":"红利低波","930955":"红利低波100","000819":"中证有色","000300":"沪深300","000985":"中证全指"}
for c,n in codes.items():
    try:
        df = ak.index_hist_csindex(symbol=c, start_date="20150101", end_date="20251120")
        print(f"OK {c} {n} rows={len(df)} first={df['日期'].iloc[0]} last={df['日期'].iloc[-1]} cols={list(df.columns)[-3:]}")
    except Exception as e:
        print(f"ERR {c} {n} {type(e).__name__}: {str(e)[:120]}")
    time.sleep(1)
