import akshare as ak
tests = [
 ("月度数据","工业 > 工业企业主要经济指标 > 利润总额"),
 ("月度数据","工业 > 规模以上工业 > 利润总额"),
 ("月度数据","工业 > 工业企业主要经济指标"),
 ("月度数据","国民经济核算 > 国内生产总值"),
]
for kind,path in tests:
    try:
        df = ak.macro_china_nbs_nation(kind=kind, path=path, period="last5")
        print("OK", path, df.shape, list(df.columns)[:10])
        print(df.head(3).to_string()[:400])
    except Exception as e:
        print("ERR", path, type(e).__name__, str(e)[:160])
    print("-"*60)
