# -*- coding: utf-8 -*-
"""线上极简服务：只提供指数走势接口 + 托管图表静态页。"""
import os
import sys
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import trend as T

app = FastAPI(title="指数估值走势", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True, "db": os.path.exists(T.DB)}


@app.get("/api/trend/meta")
def trend_meta():
    return T.meta()


@app.get("/api/trend")
def trend(code: str = "000300", range: str = "1Y", gran: str = "", mode: str = "pct",
          ind: str = "", pct_win: str = "3Y", bench: str = "", pct: str = ""):
    inds = [x for x in ind.split(",") if x]
    pcts = [x for x in pct.split(",") if x] if pct else None
    return T.trend(code=code, rng=range, gran=gran or None, mode=mode,
                   inds=inds, pct_win=pct_win, bench=bench, pct=pcts)


STATIC = os.path.join(HERE, "static")
if os.path.isdir(STATIC):
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")


def run():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
