# -*- coding: utf-8 -*-
"""用 Edge CDP 验证图表页：切换标的无崩溃、分位线默认不显示、对比图隔离。"""
import asyncio
import json
import subprocess
import time
import urllib.request

import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9333
URL = "http://127.0.0.1:8123/"


async def cdp(ws, method, params=None, timeout=10):
    await ws.send(json.dumps({"id": cdp.seq, "method": method, "params": params or {}}))
    cdp.seq += 1
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get("id") == cdp.seq - 1:
            return msg


cdp.seq = 1


async def evaluate(ws, expr):
    r = await cdp(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("result", {}).get("value")


async def main():
    p = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--remote-debugging-port=%d" % PORT,
        "--user-data-dir=%s" % ("C:/Users/1/AppData/Local/Temp/edge_cdp_chart"),
        "--window-size=1400,1000", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        tabs = None
        for _ in range(30):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT, timeout=2))
                break
            except Exception:
                await asyncio.sleep(0.5)
        if not tabs:
            print("CDP 未就绪")
            return

        ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
        async with websockets.connect(ws_url) as ws:
            await cdp(ws, "Page.enable")
            await cdp(ws, "Runtime.enable")
            await cdp(ws, "Page.navigate", {"url": URL})
            await asyncio.sleep(4)

            # 初始化：记录默认状态
            init = await evaluate(ws, "document.querySelectorAll('.ds-chip').length")
            print("初始 chip 数:", init)
            pct_default = await evaluate(ws, "Array.from(document.querySelectorAll('.ds-chip-ghost')).filter(e=>e.classList.contains('is-on')).length")
            print("默认分位线选中数:", pct_default, "(期望 0)")

            async def click_chip(text):
                expr = """(()=>{const b=Array.from(document.querySelectorAll('.ds-chip')).find(e=>e.textContent.includes(%s)); if(b){b.click();return true} return false})()""" % json.dumps(text)
                return await evaluate(ws, expr)

            # 逐个标的切换，检查是否崩溃（根节点仍有内容 + 无错误文案）
            for name in ["纳斯达克100", "中国电信", "中国移动", "沪深300", "红利低波", "科创50", "港股创新药", "中证有色", "上证指数"]:
                ok = await click_chip(name)
                await asyncio.sleep(1.2)
                alive = await evaluate(ws, "!!document.querySelector('.ds-page') && document.body.innerText.length>200")
                err = await evaluate(ws, "document.body.innerText.includes('加载失败')")
                print("切换 %-8s click=%s 页面存活=%s 报错=%s" % (name, ok, alive, err))

            # 指标曲线单独选：分位线仍应保持不选
            await click_chip("沪深300")
            await asyncio.sleep(1)
            await click_chip("股息率")
            await asyncio.sleep(1)
            pct_after = await evaluate(ws, "Array.from(document.querySelectorAll('.ds-chip-ghost')).filter(e=>e.classList.contains('is-on')).length")
            print("选指标曲线后分位线选中数:", pct_after, "(期望 0)")

            # 对比图切换：主图 DOM 是否保持不变
            before = await evaluate(ws, "document.querySelector('.ds-card .echarts-for-react, .ds-card canvas') ? document.querySelector('.ds-stats').innerText : ''")
            await evaluate(ws, """(()=>{const s=document.querySelector('.ant-select-selector'); if(s){s.click();return true} return false})()""")
            await asyncio.sleep(0.5)
            opts = await evaluate(ws, "Array.from(document.querySelectorAll('.ant-select-item-option')).map(e=>e.textContent)")
            print("对比下拉选项:", opts[:4])
            if opts:
                await evaluate(ws, """(()=>{const o=document.querySelector('.ant-select-item-option'); if(o){o.click();return true} return false})()""")
                await asyncio.sleep(1.5)
            after = await evaluate(ws, "document.querySelector('.ds-stats') ? document.querySelector('.ds-stats').innerText : ''")
            print("对比切换后主图统计区是否变化:", before != after)
            print("对比图是否存在:", await evaluate(ws, "document.body.innerText.includes('指数对比')"))
    finally:
        p.terminate()


if __name__ == "__main__":
    asyncio.run(main())
