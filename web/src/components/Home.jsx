import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import OverviewCards from './OverviewCards.jsx'
import GridCards from './GridCards.jsx'
import StyleRow from './StyleRow.jsx'
import Sentiment from './Sentiment.jsx'
import Summary from './Summary.jsx'

export default function Home() {
  const [ov, setOv] = useState(null)
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)
  const [tick, setTick] = useState(0)
  const [msg, setMsg] = useState('')

  const load = useCallback(() => {
    setErr('')
    api.overview().then(setOv).catch((e) => setErr(String(e)))
  }, [])

  useEffect(() => { load() }, [load])

  const save = async () => {
    if (!window.confirm('将采集舆情并生成今日总结（每天一次即可，重复运行只覆盖）。继续？')) return
    setSaving(true)
    setMsg('')
    try {
      const r = await api.dailyJob()
      setMsg(`每日任务完成 ${r.ran_at.slice(11, 16)}`)
      setTick((t) => t + 1)
      load()
    } catch (e) {
      setMsg('运行失败：' + String(e))
    } finally {
      setSaving(false)
      setTimeout(() => setMsg(''), 5000)
    }
  }

  if (err) {
    return (
      <div className="card"><div className="card-body">
        <div className="empty">接口连接失败：{err}<br />请确认后端已启动（uvicorn server.main:app --port 8000）</div>
      </div></div>
    )
  }

  return (
    <>
      <div className="subhead">
        <div className="meta">
          {ov ? `${ov.date} 收盘 · 数据源 data/ashare.db` : '加载中…'}
          {msg ? ` · ${msg}` : ''}
        </div>
        <div className="spacer" />
        <div className="actions">
          <button onClick={load}>刷新</button>
          <button className="primary" onClick={save} disabled={saving}>
            {saving ? '运行中…' : '更新数据（采集+总结）'}
          </button>
        </div>
      </div>

      {ov ? <OverviewCards ov={ov} /> : <div className="loading">正在计算市场温度…</div>}

      <StyleRow sleeves={ov?.sleeves} />

      <div className="section">
        <GridCards />
      </div>

      <div className="section">
        <div className="section-head">
          <h2>舆情指数</h2>
          <span className="sub">个股热度与情绪方向</span>
        </div>
        <Sentiment tick={tick} />
      </div>

      <div className="section">
        <div className="section-head">
          <h2>总结</h2>
          <span className="sub">规则生成，可切换日 / 周 / 月</span>
        </div>
        <Summary tick={tick} />
      </div>

      <div className="foot">
        温度 = 100 − 全指恐慌度（RV20 与 QVIX 分位合成）　·　舆情 = 东财人气榜 + 百度热搜<br />
        数据仅供研究，不构成投资建议
      </div>
    </>
  )
}
