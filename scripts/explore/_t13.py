import akshare as ak, pandas as pd
for per in ["2025-","2015-"]:
    try:
        df = ak.macro_china_nbs_nation(kind="月度数据", path="工业 > 工业企业主要经济指标", period=per)
        print("OK period=",per, df.shape)
        idx = df.iloc[:,0].astype(str)
        hit = [r for r in idx if "利润" in r]
        print("rows with 利润:", hit[:12])
        print("cols sample:", list(df.columns)[:6], "...", list(df.columns)[-3:])
    except Exception as e:
        print("ERR", per, type(e).__name__, str(e)[:200])
    print("-"*60)
