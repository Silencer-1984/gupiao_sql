import { useEffect, useMemo, useState } from 'react'
import EChart from './EChart.jsx'
import { api } from '../api.js'

const PERIODS = [
  { k: 'day', label: '日' },
  { k: 'week', label: '周' },
  { k: 'month', label: '月' },
]

export default function Summary({ tick }) {
  const [period, setPeriod] = useState('day')
  const [d, setD] = useState(null)
  const [hist, setHist] = useState([])

  useEffect(() => {
    api.summary(period).then(setD).catch(() => setD(null))
  }, [period, tick])

  useEffect(() => {
    api.tempHistory('D').then((r) => setHist(r.points || [])).catch(() => setHist([]))
  }, [tick])

  const perfOpt = useMemo(() => {
    if (!d) return null
    const items = [...d.perf].sort((a, b) => a.ret - b.ret)
    return {
      animationDuration: 500,
      grid: { left: 8, right: 46, top: 6, bottom: 6, containLabel: true },
      xAxis: { type: 'value', axisLabel: { show: false }, splitLine: { show: false }, axisLine: { show: false } },
      yAxis: {
        type: 'category',
        data: items.map((x) => x.name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#5b6678', fontSize: 12 },
      },
      series: [
        {
          type: 'bar',
          data: items.map((x) => ({
            value: x.ret,
            itemStyle: { color: x.ret >= 0 ? '#e04b4b' : '#129d5b', borderRadius: [0, 4, 4, 0] },
          })),
          barWidth: 13,
          label: {
            show: true,
            position: 'right',
            formatter: (p) => `${p.value > 0 ? '+' : ''}${p.value.toFixed(2)}%`,
            color: '#5b6678',
            fontSize: 11.5,
          },
        },
      ],
    }
  }, [d])

  const tempOpt = useMemo(() => {
    if (!hist.length) return null
    const dates = hist.map((p) => p.date)
    const vals = hist.map((p) => p.temperature)
    const marks = []
    return {
      grid: { left: 6, right: 10, top: 14, bottom: 22, containLabel: true },
      tooltip: { trigger: 'axis', textStyle: { fontSize: 12 } },
      xAxis: {
        type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: '#e6ebf2' } }, axisTick: { show: false },
        axisLabel: { color: '#98a3b3', fontSize: 10.5, hideOverlap: true },
      },
      yAxis: {
        type: 'value', min: 0, max: 100,
        splitLine: { lineStyle: { color: '#f1f4f8' } },
        axisLabel: { color: '#98a3b3', fontSize: 10.5 },
      },
      visualMap: {
        show: false, dimension: 1, seriesIndex: 0, min: 0, max: 100,
        inRange: { color: ['#129d5b', '#f2b134', '#e04b4b'] },
      },
      series: [
        {
          type: 'line', data: vals, showSymbol: true, symbolSize: 5, smooth: 0.2,
          lineStyle: { width: 2 }, areaStyle: { opacity: 0.08 },
          markLine: {
            silent: true, symbol: 'none',
            lineStyle: { type: 'dashed', color: '#c8d0dc' },
            data: [{ yAxis: 50, label: { formatter: '中性', color: '#a9b3c2', fontSize: 10 } }],
          },
        },
      ],
    }
  }, [hist])

  if (!d) return <div className="chart-card"><div className="empty">总结缓存读取中…</div></div>

  if (d.pending || !d.headline) {
    return (
      <div className="chart-card">
        <div className="empty">
          {d.note || '今日总结尚未生成'}
          <br />
          生成时间：每晚 20:00（也可手动运行 uv run python scripts/daily_job.py）
        </div>
      </div>
    )
  }

  return (
    <div className="two">
      <div className="card">
        <div className="card-head">
          <div className="ico">📝</div>
          <div className="t">今日总结</div>
          <div className="d" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
            {d.stale ? (
              <span style={{ color: '#c98a2b', fontSize: 11.5 }}>{d.note || '显示上一期'}</span>
            ) : (
              <span style={{ fontSize: 11.5 }}>{d.generated_at ? `${d.generated_at.slice(5, 16)} 生成` : '已缓存'}</span>
            )}
            <div className="tabs">
              {PERIODS.map((p) => (
                <button key={p.k} className={p.k === period ? 'on' : ''} onClick={() => setPeriod(p.k)}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="card-body">
          <div className="sum-headline">{d.headline}</div>
          <ul className="sum-list">
            {d.bullets.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
          <div className="sum-concl">
            <b>结论：</b>{d.conclusion}
            {d.trend ? <div style={{ marginTop: 8, color: '#8a94a6' }}>温度变化：{d.trend}</div> : null}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <div className="ico">📈</div>
          <div className="t">区间表现</div>
          <div className="d" style={{ marginLeft: 'auto' }}>{period === 'day' ? '今日' : period === 'week' ? '近5日' : '近21日'}</div>
        </div>
        <div className="card-body" style={{ paddingTop: 8 }}>
          {perfOpt && <EChart option={perfOpt} height={190} />}
          <div style={{ marginTop: 10, borderTop: '1px dashed #eceff4', paddingTop: 10 }}>
            <div style={{ fontSize: 12.5, color: '#8a94a6', marginBottom: 6 }}>温度历史（需每日保存快照）</div>
            {tempOpt ? <EChart option={tempOpt} height={130} /> : (
              <div className="empty" style={{ padding: '14px 0' }}>
                还没有历史快照，点右上角「保存今日快照」开始积累
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
