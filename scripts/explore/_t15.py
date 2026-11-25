import akshare as ak
df = ak.macro_china_nbs_nation(kind="月度数据", path="工业 > 工业企业主要经济指标", period="2025-")
print("index.name:", df.index.name)
print("index[-5:]:", list(df.index[-5:]))
print("n cols:", len(df.columns))
print(df.iloc[-6:, :2])
