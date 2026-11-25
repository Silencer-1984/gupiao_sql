import akshare as ak
df = ak.macro_china_nbs_nation(kind="月度数据", path="工业 > 工业企业主要经济指标", period="2015-")
labels=[str(x) for x in df.iloc[:,0].tolist()]
for i,l in enumerate(labels): print(i,l)
print("cols head/tail:", list(df.columns)[:3], list(df.columns)[-2:])
