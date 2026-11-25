from _probe import p, ak
import time
p("stock_summary_sse 20251120", lambda: ak.stock_summary_sse(date="20251120"))
p("stock_summary_szse 20251120", lambda: ak.stock_summary_szse(date="20251120"))
p("interest_rate_repo_hist_cm 20250101-20251231", lambda: ak.interest_rate_repo_hist_cm(start_date="20250101", end_date="20251231"))
