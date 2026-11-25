# -*- coding: utf-8 -*-
"""FastAPI 服务：页面只读缓存，抓取走独立的采集接口，避免请求链路直连外部源。"""
import os
import sys
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analytics as A
import trend as T

app = FastAPI(title="A股风格轮动看板", version="1.1")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True, "db": os.path.exists(A.DB)}


@app.get("/api/overview")
def overview():
    return A.overview()


@app.get("/api/watch")
def watch():
    return A.watch_list()


@app.get("/api/grid")
def grid(freq: str = "D"):
    """重点关注小卡片：多周期涨跌幅 + 纳指ETF 溢价率。"""
    return A.grid_cards(freq)


@app.get("/api/series")
def series(code: str = Query(...), freq: str = "D", limit: int = 260):
    return A.get_series(code, freq, limit)


# ---- 指数走势 ----
@app.get("/api/trend/meta")
def trend_meta():
    """走势页筛选框元数据：可选指数、每类指数的推荐指标、区间与粒度。"""
    return T.meta()


@app.get("/api/trend")
def trend(code: str = "000300", range: str = "1Y", gran: str = "", mode: str = "pct",
          ind: str = "", pct_win: str = "3Y", bench: str = ""):
    """指数涨跌图：主序列 + 指标副轴 + 分位标准线 + 对比指数。"""
    inds = [x for x in ind.split(",") if x]
    return T.trend(code=code, rng=range, gran=gran or None, mode=mode,
                   inds=inds, pct_win=pct_win, bench=bench)


# ---- 只读接口：只读缓存，不触发任何抓取 ----
@app.get("/api/sentiment")
def sentiment():
    return A.get_sentiment_cached()


@app.get("/api/summary")
def summary(period: str = "day"):
    return A.get_summary(period)


@app.get("/api/temperature/history")
def temperature_history(freq: str = "D"):
    return A.temp_history(freq)


# ---- 采集接口：给自动化命令/手动调用，页面不调用 ----
@app.post("/api/collect/sentiment")
def collect_sentiment(force: int = 0):
    return A.collect_sentiment(force=bool(force))


@app.post("/api/collect/summary")
def collect_summary(period: str = "day"):
    return A.collect_summary(period)


@app.post("/api/snapshot")
def snapshot():
    return A.save_snapshot()


@app.post("/api/daily_job")
def daily_job(force_sentiment: int = 0):
    """一次跑完：采集舆情 → 日/周/月总结 → 快照。定时任务调这个。"""
    return A.daily_job(force_sentiment=bool(force_sentiment))


# 生产模式：若已构建前端则直接托管
DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist")
if os.path.isdir(DIST):
    app.mount("/", StaticFiles(directory=DIST, html=True), name="static")


def run():
    """uv run dash [--host H] [--port P] [--reload]"""
    import argparse
    import uvicorn

    p = argparse.ArgumentParser(prog="dash", description="A股风格轮动看板")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", help="开发模式，代码改动自动重启")
    a = p.parse_args()

    has_dist = os.path.isdir(DIST)
    print("=" * 60)
    print("  A股风格轮动看板")
    print(f"  页面   http://{a.host}:{a.port}/")
    print(f"  接口   http://{a.host}:{a.port}/api/overview")
    print(f"  前端   {'已构建 web/dist' if has_dist else '未构建（cd web && pnpm build）'}")
    print(f"  数据   data/ashare.db")
    print(f"  每日任务  uv run python scripts/daily_job.py")
    print("=" * 60)
    uvicorn.run("server.main:app", host=a.host, port=a.port, reload=a.reload)


if __name__ == "__main__":
    run()
