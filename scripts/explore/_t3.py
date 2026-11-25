from _probe import p, ak
p("macro_china_money_supply_em", lambda: ak.macro_china_money_supply_em())
p("macro_china_fixed_asset_investment", lambda: ak.macro_china_fixed_asset_investment())
p("bond_zh_us_yield_em", lambda: ak.bond_zh_us_yield_em())
p("interest_rate_repo_hist_cm CNHDR007", lambda: ak.interest_rate_repo_hist_cm(symbol="CNHDR007"))
p("spot_hist_sge Au99.99", lambda: ak.spot_hist_sge(symbol="Au99.99"))
p("futures_foreign_hist_sina CAD", lambda: ak.futures_foreign_hist_sina(symbol="CAD"))
