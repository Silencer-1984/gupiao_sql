import akshare as ak, json
info = ak.interface_info('macro_china_nbs_nation')
print(json.dumps(info, ensure_ascii=False)[:1500])
