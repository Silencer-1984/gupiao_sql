import { useEffect, useMemo, useState } from 'react'
import EChart from './EChart.jsx'
import { api } from '../api.js'

const FREQ = [
  { k: 'D', label: '日' },
  { k: 'W', label: '周' },
  { k: 'M', label: '月' },
  { k: 'Y', label: '年' },
]

export default function WatchChart() {
  const [watch, setWatch] = useState([])
  const [code, setCode] = useState('000300')
  const [freq, setFreq] = useState('D')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.watch().then((r) => setWatch(r.items)).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    api.series(code, freq)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [code, freq])

  const name = watch.find((w) => w.code === code)?.name || code
  const pts = data?.points || []
  const last = pts[pts.length - 1]
  const prev = pts[pts.length - 2]
  const chg = last && prev ? (last.close / prev.close - 1) * 100 : 0

  const option = useMemo(() => {
    const dates = pts.map((p) => p.date)
    const closes = pts.map((p) => p.close)
    const amts = pts.map((p) => p.amount)
    const up = chg >= 0
    return {
      animationDuration: 500,
      grid: { left: 8, right: 8, top: 16, bottom: 46, containLabel: true },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,.97)',
        borderColor: '#e6ebf2',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: '#1f2733', fontSize: 12 },
        formatter: (ps) => {
          const i = ps[0].dataIndex
          const p = pts[i]
          if (!p) return ''
          const c = p.pct > 0 ? '#e04b4b' : p.pct < 0 ? '#129d5b' : '#1f2733'
          return `<div style="font-weight:600;margin-bottom:4px">${p.date}</div>
            <div>收盘 <b>${p.close}</b></div>
            <div>涨跌 <b style="color:${c}">${p.pct > 0 ? '+' : ''}${p.pct}%</b></div>
            ${p.amount ? `<div>成交额 ${p.amount} 亿</div>` : ''}
            ${p.pe ? `<div>PE-TTM ${p.pe}</div>` : ''}`
        },
      },
      axisPointer: { type: 'line', lineStyle: { color: '#c8d0dc', type: 'dashed' } },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#e6ebf2' } },
        axisTick: { show: false },
        axisLabel: { color: '#98a3b3', fontSize: 11, hideOverlap: true },
      },
      yAxis: [
        {
          type: 'value',
          scale: true,
          splitLine: { lineStyle: { color: '#f1f4f8' } },
          axisLabel: { color: '#98a3b3', fontSize: 11 },
        },
        { type: 'value', show: false, scale: true },
      ],
      series: [
        {
          name: '成交额',
          type: 'bar',
          yAxisIndex: 1,
          data: amts,
          itemStyle: { color: 'rgba(59,111,212,0.13)' },
          barWidth: '58%',
          silent: true,
        },
        {
          name: '收盘',
          type: 'line',
          data: closes,
          showSymbol: false,
          smooth: 0.15,
          lineStyle: { width: 2, color: up ? '#e04b4b' : '#129d5b' },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: up ? 'rgba(224,75,75,0.18)' : 'rgba(18,157,91,0.18)' },
                { offset: 1, color: 'rgba(255,255,255,0)' },
              ],
            },
          },
        },
      ],
    }
  }, [pts, chg])

  return (
    <div className="chart-card">
      <div className="chart-top">
        <div className="tabs">
          {watch.map((w) => (
            <button key={w.code} className={w.code === code ? 'on' : ''} onClick={() => setCode(w.code)}>
              {w.name}
            </button>
          ))}
        </div>
        <div className="spacer" style={{ flex: 1 }} />
        <div className="tabs">
          {FREQ.map((f) => (
            <button key={f.k} className={f.k === freq ? 'on' : ''} onClick={() => setFreq(f.k)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-top" style={{ marginTop: 2, marginBottom: 2 }}>
        <span className="price" style={{ color: chg >= 0 ? '#e04b4b' : '#129d5b' }}>
          {last ? last.close.toLocaleString() : '—'}
        </span>
        <span className="chg" style={{ color: chg >= 0 ? '#e04b4b' : '#129d5b' }}>
          {chg >= 0 ? '+' : ''}{chg.toFixed(2)}%
        </span>
        <span style={{ color: '#8a94a6', fontSize: 12.5 }}>
          {name} · {FREQ.find((f) => f.k === freq)?.label}线
          {last?.pe ? ` · PE ${last.pe}` : ''}
        </span>
        {loading && <span style={{ color: '#b9c2d0', fontSize: 12 }}>加载中…</span>}
      </div>

      {pts.length ? <EChart option={option} height={340} /> : <div className="empty">暂无数据</div>}
    </div>
  )
}
