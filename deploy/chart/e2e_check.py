# -*- coding: utf-8 -*-
"""CDP 端到端验证：切换标的无崩溃、分位线真正独立、对比图隔离。

验证方式：浏览器真实点击 → 读 URL 参数 → 用该参数请求接口，检查 ref_lines。
"""
import asyncio
import json
import subprocess
import urllib.parse
import urllib.request

import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9333
URL = "http://127.0.0.1:8123/"


async def cdp(ws, method, params=None):
    mid = cdp.seq
    cdp.seq += 1
    await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        if msg.get("id") == mid:
            return msg


cdp.seq = 1


async def evaluate(ws, expr):
    r = await cdp(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("result", {}).get("value")


def api_ref_lines(qs):
    """按页面 URL 的参数请求接口，返回分位线涉及的指标。"""
    try:
        with urllib.request.urlopen(URL + "api/trend?" + qs, timeout=10) as r:
            d = json.load(r)
        return sorted(set(x["ind"] for x in d.get("ref_lines", [])))
    except Exception as e:
        return ["ERR:%s" % e]


async def main():
    p = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--remote-debugging-port=%d" % PORT,
        "--user-data-dir=%s" % ("C:/Users/1/AppData/Local/Temp/edge_cdp_chart3"),
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

            async def click(text, ghost=False):
                sel = ".ds-chip-ghost" if ghost else ".ds-chip:not(.ds-chip-ghost)"
                expr = """(()=>{const b=Array.from(document.querySelectorAll(%s)).find(e=>e.textContent.includes(%s));if(b){b.click();return true}return false})()""" % (
                    json.dumps(sel), json.dumps(text))
                return await evaluate(ws, expr)

            async def state():
                return await evaluate(ws, """(()=>{
                  const q=new URLSearchParams(window.location.hash.split('?')[1]||'');
                  return {qs:q.toString(), pct:q.get('pct'), ind:q.get('ind'), code:q.get('code'),
                          pctOn:Array.from(document.querySelectorAll('.ds-chip-ghost')).filter(e=>e.classList.contains('is-on')).length,
                          alive:!!document.querySelector('.ds-page')&&document.body.innerText.length>200};
                })()""")

            s = await state()
            refs = api_ref_lines(s["qs"])
            print("① 初始:", s["code"], "pct=",repr(s["pct"]), "分位线:", refs)
            assert s["alive"] and refs == [], "初始不应有分位线"

            await click("红利低波")
            await asyncio.sleep(1.2)
            await click("股息率")
            await asyncio.sleep(1.2)
            s = await state()
            refs = api_ref_lines(s["qs"])
            print("② 点指标曲线股息率:", s["code"], "ind=",s["ind"], "pct=",repr(s["pct"]), "分位线:", refs)
            assert refs == [] and s["pctOn"] == 0, "点指标曲线不应带出分位线"

            await click("股息率", ghost=True)
            await asyncio.sleep(1.2)
            s = await state()
            refs = api_ref_lines(s["qs"])
            print("③ 勾选分位线:", s["code"], "pct=",repr(s["pct"]), "分位线:", refs)
            assert refs == ["div"] and s["pctOn"] == 1, "勾选后应出现 div 分位线"

            await click("股息率", ghost=True)
            await asyncio.sleep(1.2)
            s = await state()
            refs = api_ref_lines(s["qs"])
            print("④ 取消分位线:", "pct=",repr(s["pct"]), "分位线:", refs)
            assert refs == [], "取消后分位线应消失"

            for name in ["纳斯达克100", "中国电信", "中国移动", "沪深300", "红利低波",
                         "科创50", "港股创新药", "中证有色", "上证指数"]:
                await click(name)
                await asyncio.sleep(1)
                s = await state()
                refs = api_ref_lines(s["qs"])
                print("   切换 %-8s 存活=%s 分位=%s 选中=%d" % (
                    name, s["alive"], refs, s["pctOn"]))
                assert s["alive"], "切换 %s 后崩溃" % name
                assert refs == [], "切换 %s 后自动出现分位线" % name

            # 对比隔离：主图统计区文本在切换对比前后不变
            before = await evaluate(ws, "document.querySelector('.ds-stats') ? document.querySelector('.ds-stats').innerText : ''")
            await evaluate(ws, """(()=>{const s=document.querySelector('.ant-select-selector');if(s){s.click();return true}return false})()""")
            await asyncio.sleep(0.6)
            picked = await evaluate(ws, """(()=>{const o=document.querySelector('.ant-select-item-option');if(o){o.click();return true}return false})()""")
            await asyncio.sleep(1.5)
            after = await evaluate(ws, "document.querySelector('.ds-stats') ? document.querySelector('.ds-stats').innerText : ''")
            print("⑤ 对比切换 picked=%s 主图统计区未变=%s" % (picked, before == after))
            assert before == after, "切换对比标的不应影响主图"

            print("\n全部通过")
    finally:
        p.terminate()


if __name__ == "__main__":
    asyncio.run(main())
