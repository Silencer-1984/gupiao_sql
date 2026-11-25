# -*- coding: utf-8 -*-
"""图表页每日任务：更新主库 → 重建精简库 → 重建前端。

用法：uv run python deploy/chart/daily_update.py
只更新图表页真正用到的数据，跑完把 deploy/chart 重新发布一次即可。
"""
import os
import subprocess
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

# 中证官网历史接口：行情 + 滚动市盈率，口径与库内 pe_ttm 一致
CSI = {
    "000300": "沪深300", "H30269": "红利低波", "000688": "科创50",
    "931787": "港股创新药", "000819": "中证有色",
}
# 上证指数不属于中证，走新浪
SINA = {"000001": "sh000001"}


def step(name, fn):
    t0 = time.time()
    print("\n=== %s ===" % name)
    try:
        fn()
        print("[OK] %s %.1fs" % (name, time.time() - t0))
        return True
    except Exception as e:
        print("[FAIL] %s: %s: %s" % (name, type(e).__name__, e))
        traceback.print_exc(limit=2)
        return False


def _upsert(now, code, date, o, h, l, c0, pct, amount, pe, src):
    """写一行指数日线；已存在则覆盖（保留 pe_ttm 口径一致）。"""
    import sqlite3
    c = sqlite3.connect(os.path.join(ROOT, "data", "ashare.db"))
    row = c.execute("select 1 from px_index_daily_csi where index_code=? and trade_date=?",
                    (code, date)).fetchone()
    if row:
        c.execute("update px_index_daily_csi set open=?,high=?,low=?,close=?,pct_chg=?,amount=?,"
                  "pe_ttm=coalesce(?,pe_ttm),_fetched_at=? where index_code=? and trade_date=?",
                  (o, h, l, c0, pct, amount, pe, now, code, date))
    else:
        c.execute("insert into px_index_daily_csi (trade_date,index_code,index_name_cn,"
                  "open,high,low,close,pct_chg,amount,pe_ttm,_source,_fetched_at) "
                  "values (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (date, code, CSI.get(code, code), o, h, l, c0, pct, amount, pe, src, now))
    c.commit()
    c.close()


def update_index_csi():
    """中证官网：行情 + 滚动市盈率（近 30 日）。"""
    import datetime as dt
    import akshare as ak

    now = dt.datetime.now().isoformat(timespec="seconds")
    total = 0
    for code in CSI:
        df = ak.index_hist_csindex(symbol=code, start_date="20250101",
                                   end_date=(dt.date.today()).strftime("%Y%m%d"))
        for _, r in df.tail(40).iterrows():
            _upsert(now, code, str(r["日期"]), float(r["开盘"]), float(r["最高"]), float(r["最低"]),
                    float(r["收盘"]), float(r["涨跌幅"]), float(r["成交金额"]),
                    None if r["滚动市盈率"] != r["滚动市盈率"] else float(r["滚动市盈率"]),
                    "index_hist_csindex")
            total += 1
    print("csi upsert %d rows" % total)


def update_index_sina():
    """上证指数（非中证）：新浪日线。"""
    import datetime as dt
    import akshare as ak

    now = dt.datetime.now().isoformat(timespec="seconds")
    total = 0
    for code, sym in SINA.items():
        df = ak.index_zh_daily_sina(symbol=sym)
        df["date"] = df["date"].astype(str)
        for _, r in df.tail(20).iterrows():
            _upsert(now, code, r["date"], float(r["open"]), float(r["high"]), float(r["low"]),
                    float(r["close"]), None, float(r.get("amount") or 0), None, "sina")
            total += 1
    print("sina upsert %d rows" % total)


def run_script(rel):
    p = subprocess.run([PY, os.path.join(ROOT, rel)], cwd=ROOT)
    if p.returncode != 0:
        raise RuntimeError("%s exit %d" % (rel, p.returncode))


def build_frontend():
    web = os.path.join(ROOT, "web")
    subprocess.run(["pnpm", "exec", "vite", "build", "--config", "vite.chart.config.js"],
                   cwd=web, check=True)
    import shutil
    static = os.path.join(ROOT, "deploy", "chart", "static")
    shutil.copyfile(os.path.join(static, "chart.html"), os.path.join(static, "index.html"))


def main():
    results = []
    results.append(("指数+PE(中证)", step("指数+PE(中证)", update_index_csi)))
    results.append(("上证指数(新浪)", step("上证指数(新浪)", update_index_sina)))
    results.append(("159941溢价", step("159941溢价", lambda: run_script("scripts/fetch_nasdaq_premium.py"))))
    results.append(("指数股息率", step("指数股息率", lambda: run_script("scripts/fetch_dividend_yield.py"))))
    results.append(("个股PE", step("个股PE", lambda: run_script("deploy/chart/fetch_stock_pe.py"))))
    results.append(("重建精简库", step("重建精简库", lambda: run_script("deploy/chart/build_db.py"))))
    results.append(("构建前端", step("构建前端", build_frontend)))

    print("\n===== 汇总 =====")
    for n, ok in results:
        print("%-16s %s" % (n, "OK" if ok else "FAIL"))
    bad = [n for n, ok in results if not ok]
    print("\n下一步：把 deploy/chart 重新发布一次。")
    if bad:
        print("有失败项，精简库可能仍是旧数据：%s" % ", ".join(bad))
        sys.exit(1)


if __name__ == "__main__":
    main()
