import { useEffect, useMemo, useState } from 'react'
import { Empty, Segmented, Select, Spin, Tooltip, Typography } from 'antd'
import EChart from './EChart.jsx'
import { api } from '../api.js'

const { Text } = Typography

const RED = '#e04b4b'
const GREEN = '#129d5b'
const IDX_COLOR = '#2563EB'
const BENCH_COLOR = '#EA580C'
const IND_COLORS = ['#9333EA', '#0891B2']
const QCOLORS = { 20: '#16A34A', 50: '#EAB308', 80: '#DC2626' }

const fmt = (v, d = 2) => (v == null ? '—' : v.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d }))
const pct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`)
const swatch = (color, dash) => (
  <i style={{
    display: 'inline-block', width: 12, height: 3, borderRadius: 2, marginRight: 5, verticalAlign: 'middle',
    background: dash ? `repeating-linear-gradient(90deg,${color} 0 4px,transparent 4px 7px)` : color,
  }} />
)

const readParams = () => {
  const q = window.location.hash.split('?')[1] || ''
  const p = new URLSearchParams(q)
  return {
    code: p.get('code') || '',
    range: p.get('range') || '',
    gran: p.get('gran') || '',
    mode: (p.get('mode') === 'pct' ? 'point' : p.get('mode')) || '',
    ind: p.get('ind'),
    pct_win: p.get('pct_win') || '',
    bench: p.get('bench'),
  }
}

export default function Trend() {
  const init = readParams()
  const [meta, setMeta] = useState(null)
  const [code, setCode] = useState(init.code || '000300')
  const [range, setRange] = useState(init.range || '1Y')
  const [gran, setGran] = useState(init.gran || 'W')
  const [mode, setMode] = useState(init.mode || 'point')
  const [inds, setInds] = useState(init.ind != null ? init.ind.split(',').filter(Boolean) : ['pe_ttm'])
  const [pctWin, setPctWin] = useState(init.pct_win || '3Y')
  const [bench, setBench] = useState(init.bench || '')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => { api.trendMeta().then(setMeta).catch((e) => setErr(String(e))) }, [])

  useEffect(() => {
    const q = new URLSearchParams({ code, range, gran, mode, ind: inds.join(','), pct_win: pctWin, bench })
    window.history.replaceState(null, '', `#/trend?${q.toString()}`)
  }, [code, range, gran, mode, inds, pctWin, bench])

  const pickIndex = (c) => {
    setCode(c)
    const info = meta?.by_code?.[c]
    if (!info) return
    const valid = info.indicators.map((i) => i.key)
    const keep = inds.filter((k) => valid.includes(k))
    setInds(keep.length ? keep : valid.slice(0, 1))
  }

  useEffect(() => {
    if (!code) return
    setLoading(true)
    api.trend({ code, range, gran, mode, ind: inds.join(','), pctWin, bench })
      .then((r) => { setData(r); setErr('') })
      .catch((e) => { setErr(String(e)); setData(null) })
      .finally(() => setLoading(false))
  }, [code, range, gran, mode, inds, pctWin, bench])

  const info = meta?.by_code?.[code]
  const list = meta?.indexes || []
  const indOptions = info?.indicators || []
  const pts = data?.points || []
  const stats = data?.stats || {}
  const refLines = data?.ref_lines || []

  const toggleInd = (k) => setInds((cur) => {
    if (cur.includes(k)) return cur.filter((x) => x !== k)
    if (cur.length >= 2) return [cur[1], k]
    return [...cur, k]
  })

  // ---------- 主图 ----------
  const option = useMemo(() => {
    if (!pts.length) return null
    const dates = pts.map((p) => p.date)
    const axes = [{
      type: 'value',
      name: mode === 'cum' ? '累积收益 %' : (data?.cls === 'stock' ? '股价（元）' : '指数点位'),
      nameTextStyle: { color: IDX_COLOR, fontSize: 11, padding: [0, 0, 4, 0] },
      axisLine: { show: true, lineStyle: { color: IDX_COLOR } },
      axisTick: { show: false },
      axisLabel: { color: IDX_COLOR, fontSize: 11, formatter: mode === 'cum' ? '{value}%' : undefined },
      splitLine: { lineStyle: { color: '#eef2f7' } },
      scale: true,
    }]
    const indList = data?.indicators || []
    indList.forEach((o, i) => {
      const vals = o.points.map((p) => p.value).filter((v) => v != null)
      const mine = refLines.filter((r) => r.ind === o.key)
      let lo = vals.length ? Math.min(...vals) : null
      let hi = vals.length ? Math.max(...vals) : null
      mine.forEach((r) => { lo = lo == null ? r.value : Math.min(lo, r.value); hi = hi == null ? r.value : Math.max(hi, r.value) })
      let min, max
      if (lo != null && hi != null) {
        const pad = Math.max((hi - lo) * 0.08, Math.abs(hi) * 0.01)
        min = Math.round((lo - pad) * 100) / 100
        max = Math.round((hi + pad) * 100) / 100
      }
      axes.push({
        type: 'value', name: o.label,
        nameTextStyle: { color: IND_COLORS[i], fontSize: 11, align: 'left', padding: [0, 0, 2, 0] },
        nameGap: 26,
        position: 'right', offset: i * 56,
        axisLine: { show: true, lineStyle: { color: IND_COLORS[i] } },
        axisTick: { show: false },
        axisLabel: { color: IND_COLORS[i], fontSize: 11 },
        splitLine: { show: false }, scale: true, min, max,
      })
    })

    const series = []
    if (mode === 'point') {
      series.push({
        name: '指数点位', type: 'line', data: pts.map((p) => p.close),
        showSymbol: false, smooth: 0.1, lineStyle: { width: 2.4, color: IDX_COLOR },
        areaStyle: {
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [{ offset: 0, color: 'rgba(37,99,235,0.10)' }, { offset: 1, color: 'rgba(37,99,235,0)' }] },
        }, z: 2,
      })
    } else {
      series.push({
        name: '累积收益', type: 'line', data: pts.map((p) => p.cum),
        showSymbol: false, smooth: 0.12, lineStyle: { width: 2.4, color: IDX_COLOR },
        markLine: { silent: true, symbol: 'none', label: { show: false },
          lineStyle: { color: '#cbd5e1', type: 'dashed' }, data: [{ yAxis: 0 }] }, z: 2,
      })
    }
    indList.forEach((o, i) => {
      const mine = refLines.filter((r) => r.ind === o.key)
      series.push({
        name: o.label, type: 'line', yAxisIndex: i + 1,
        data: o.points.map((p) => p.value), showSymbol: false, connectNulls: true, smooth: 0.1,
        lineStyle: { width: 2, color: IND_COLORS[i] }, itemStyle: { color: IND_COLORS[i] }, z: 4,
        markLine: mine.length ? {
          silent: true, symbol: 'none',
          data: mine.map((r) => ({
            yAxis: r.value,
            lineStyle: { color: QCOLORS[r.q] || IND_COLORS[i], type: 'dashed', width: 1.6 },
            label: {
              formatter: `${r.q}% ${fmt(r.value, 2)}${o.unit || ''}`,
              position: i === 0 ? 'insideEndTop' : 'insideStartTop', fontSize: 10.5,
              color: QCOLORS[r.q] || IND_COLORS[i],
              backgroundColor: 'rgba(255,255,255,.88)', padding: [1, 3],
            },
          })),
        } : undefined,
      })
    })

    return {
      animationDuration: 420,
      grid: { left: 6, right: 10 + 62 * indList.length, top: 58, bottom: 34, containLabel: true },
      tooltip: {
        trigger: 'axis', backgroundColor: 'rgba(255,255,255,.97)', borderColor: '#e6ebf2', borderWidth: 1,
        padding: [8, 12], textStyle: { color: '#1f2733', fontSize: 12 },
        formatter: (ps) => {
          const p = pts[ps[0].dataIndex]
          if (!p) return ''
          const rows = [`<div style="font-weight:600;margin-bottom:4px">${p.date}</div>`, `<div>收盘 <b>${fmt(p.close)}</b></div>`]
          if (p.pct != null) rows.push(`<div>涨跌 <b style="color:${p.pct >= 0 ? RED : GREEN}">${pct(p.pct)}</b></div>`)
          if (p.cum != null) rows.push(`<div>区间累积 <b>${pct(p.cum)}</b></div>`)
          indList.forEach((o) => {
            const v = o.points[ps[0].dataIndex]?.value
            if (v != null) {
              const q = refLines.filter((r) => r.ind === o.key)
              const tag = q.length ? ` <span style="color:#94a3b8">(${q.map((r) => `${r.q}%:${fmt(r.value, 2)}`).join(' / ')})</span>` : ''
              rows.push(`<div>${o.label} <b>${fmt(v)}${o.unit || ''}</b>${tag}</div>`)
            }
          })
          return rows.join('')
        },
      },
      axisPointer: { type: 'line', lineStyle: { color: '#cbd5e1', type: 'dashed' } },
      xAxis: {
        type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: '#e6ebf2' } }, axisTick: { show: false },
        axisLabel: { color: '#98a3b3', fontSize: 11, hideOverlap: true },
      },
      yAxis: axes, series,
    }
  }, [pts, data, mode, refLines])

  // ---------- 对比图 ----------
  const benchOption = useMemo(() => {
    if (!data?.bench || !pts.length) return null
    const dates = pts.map((p) => p.date)
    const bm = new Map(data.bench.points.map((p) => [p.date, p.value]))
    const bNames = data.bench.name
    return {
      animationDuration: 420,
      grid: { left: 6, right: 6, top: 42, bottom: 30, containLabel: true },
      tooltip: {
        trigger: 'axis', backgroundColor: 'rgba(255,255,255,.97)', borderColor: '#e6ebf2', borderWidth: 1,
        padding: [6, 10], textStyle: { color: '#1f2733', fontSize: 12 },
        formatter: (ps) => {
          const i = ps[0].dataIndex
          const d = dates[i]
          const p = pts[i]
          const bv = bm.get(d)
          const bAll = data.bench.points
          const bi = bAll.findIndex((x) => x.date === d)
          const bp = bi > 0 ? (bAll[bi].value / bAll[bi - 1].value - 1) * 100 : null
          return `<div style="font-weight:600;margin-bottom:3px">${d}</div>` +
            `<div style="color:${IDX_COLOR}">${data.name} <b>${fmt(p.close)}</b></div>` +
            (bv != null ? `<div style="color:${BENCH_COLOR}">${bNames} <b>${fmt(bv)}</b>` +
              (bp != null ? ` <span style="color:${bp >= 0 ? RED : GREEN}">${pct(bp)}</span>` : '') + '</div>' : '')
        },
      },
      axisPointer: { type: 'line', lineStyle: { color: '#cbd5e1', type: 'dashed' } },
      xAxis: {
        type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: '#e6ebf2' } }, axisTick: { show: false },
        axisLabel: { color: '#98a3b3', fontSize: 11, hideOverlap: true },
      },
      yAxis: [
        { type: 'value', name: data.name, scale: true,
          nameTextStyle: { color: IDX_COLOR, fontSize: 11, align: 'right', padding: [0, 0, 3, 0] },
          axisLine: { show: true, lineStyle: { color: IDX_COLOR } }, axisTick: { show: false },
          axisLabel: { color: IDX_COLOR, fontSize: 11 }, splitLine: { lineStyle: { color: '#f1f4f8' } } },
        { type: 'value', name: bNames, scale: true, position: 'right',
          nameTextStyle: { color: BENCH_COLOR, fontSize: 11, align: 'left', padding: [0, 0, 3, 0] },
          axisLine: { show: true, lineStyle: { color: BENCH_COLOR } }, axisTick: { show: false },
          axisLabel: { color: BENCH_COLOR, fontSize: 11 }, splitLine: { show: false } },
      ],
      series: [
        { name: data.name, type: 'line', data: pts.map((p) => p.close), showSymbol: false, smooth: 0.1,
          lineStyle: { width: 2.2, color: IDX_COLOR }, z: 2 },
        { name: bNames, type: 'line', yAxisIndex: 1,
          data: dates.map((d) => (bm.has(d) ? bm.get(d) : null)), showSymbol: false, connectNulls: true,
          smooth: 0.1, lineStyle: { width: 2, color: BENCH_COLOR }, z: 3 },
      ],
    }
  }, [pts, data])

  if (err) return <div className="tv-card"><Empty description={`接口连接失败：${err}`} /></div>
  if (!meta) return <div style={{ padding: 60, textAlign: 'center' }}><Spin size="large" tip="正在加载…" /></div>

  const up = (stats.last_pct ?? 0) >= 0

  return (
    <Spin spinning={loading}>
      <div className="tv">
        <div className="tv-hero">
          <div className="tv-hero-l">
            <h1>指数估值走势</h1>
            <p>PE · 股息率 · 溢价 · 分位，一眼看清贵贱</p>
          </div>
          <div className="tv-hero-r">
            <div className="tv-hero-price" style={{ color: up ? RED : GREEN }}>
              {data ? fmt(stats.last) : '—'}
              <span>{data ? pct(stats.last_pct) : ''}</span>
            </div>
            <div className="tv-hero-meta">
              {data ? `${data.name} · ${stats.start} ~ ${stats.end} · ${stats.n} 点` : '加载中'}
            </div>
          </div>
        </div>

        <div className="tv-panel">
          <div className="tv-row">
            <span className="tv-label">标的</span>
            <div className="chips">
              {list.map((x) => (
                <button key={x.code} className={`chip ${x.code === code ? 'on' : ''}`} onClick={() => pickIndex(x.code)}>
                  {x.name}<em>{x.tag}</em>
                </button>
              ))}
            </div>
          </div>

          <div className="tv-row">
            <span className="tv-label">区间</span>
            <Segmented size="small" options={meta.ranges.map((r) => ({ label: r.label, value: r.key }))} value={range} onChange={setRange} />
            <span className="tv-label">粒度</span>
            <Segmented size="small" options={meta.grans.map((g) => ({ label: g.label, value: g.key }))} value={gran} onChange={setGran} />
            <span className="tv-label">视图</span>
            <Segmented size="small"
              options={[{ label: '点位', value: 'point' }, { label: '累积收益', value: 'cum' }]}
              value={mode} onChange={setMode} />
          </div>

          <div className="tv-row">
            <span className="tv-label">第二 Y 轴</span>
            <div className="chips">
              {indOptions.map((o) => (
                <Tooltip key={o.key} title={o.why}>
                  <button className={`chip ${inds.includes(o.key) ? 'on' : ''}`} onClick={() => toggleInd(o.key)}>
                    {o.label}{o.pct_line ? <em>分位</em> : null}
                  </button>
                </Tooltip>
              ))}
            </div>
            <span className="phint">最多 2 条</span>
          </div>

          {indOptions.some((o) => inds.includes(o.key) && o.pct_line) && (
            <div className="tv-row">
              <span className="tv-label">分位参考线</span>
              <Segmented size="small" options={meta.pct_windows.map((w) => ({ label: w.label, value: w.key }))} value={pctWin} onChange={setPctWin} />
              <span className="phint">图上 20% / 50% / 80% 三条横线，看当前处在历史什么位置</span>
            </div>
          )}

          <div className="tv-row">
            <span className="tv-label">对比</span>
            <Select size="small" style={{ width: 200 }} allowClear placeholder="不对比" value={bench || undefined}
              onChange={(v) => setBench(v || '')}
              options={list.filter((x) => x.code !== code).map((x) => ({ label: x.name, value: x.code }))} />
            <span className="phint">在主图下方单独成图</span>
          </div>
        </div>

        <div className="tv-card">
          <div className="statrow">
            <div className="sbox"><span>区间涨跌</span><b style={{ color: stats.ret >= 0 ? RED : GREEN }}>{pct(stats.ret)}</b></div>
            <div className="sbox"><span>最大回撤</span><b style={{ color: GREEN }}>{pct(stats.mdd)}</b></div>
            <div className="sbox"><span>年化波动</span><b>{stats.vol == null ? '—' : `${stats.vol}%`}</b></div>
            <div className="sbox"><span>上涨 / 下跌</span><b>{stats.up_days ?? '—'} / {stats.down_days ?? '—'}</b></div>
            {(data?.indicators || []).map((o) => {
              const v = stats.ind_last?.[o.key]
              const q = stats.ind_last?.[o.key + '_pct']
              return (
                <div className="sbox" key={o.key}>
                  <span>{o.label}{q != null ? ` · ${pctWinLabel(meta, pctWin)}分位 ${q}%` : ''}</span>
                  <b style={{ color: IND_COLORS[data.indicators.indexOf(o)] }}>{v == null ? '—' : `${fmt(v)}${o.unit || ''}`}</b>
                </div>
              )
            })}
          </div>
          {option ? <EChart option={option} height={440} /> : <Empty description="暂无数据" />}
          <div className="legend">
            <span>{swatch(IDX_COLOR)}{mode === 'point' ? (data?.cls === 'stock' ? '股价（元）' : '指数点位') : '区间累积收益'}</span>
            {(data?.indicators || []).map((o, i) => (
              <span key={o.key}>{swatch(IND_COLORS[i])}{o.label}{o.unit ? `（${o.unit}）` : ''}</span>
            ))}
            {refLines.length > 0 && [20, 50, 80].map((q) => (
              <span key={q}>{swatch(QCOLORS[q], true)}{q}% 分位</span>
            ))}
          </div>
        </div>

        {data?.bench && benchOption && (
          <div className="tv-card">
            <div className="tv-card-head">
              <h2>指数对比</h2>
              <Text type="secondary" style={{ fontSize: 12 }}>{data.name} vs {data.bench.name} · 各自独立 Y 轴</Text>
            </div>
            <div className="statrow">
              <div className="sbox"><span>{data.name} 区间涨跌</span><b style={{ color: stats.ret >= 0 ? RED : GREEN }}>{pct(stats.ret)}</b></div>
              <div className="sbox"><span>{data.bench.name} 区间涨跌</span><b style={{ color: data.bench.ret >= 0 ? RED : GREEN }}>{pct(data.bench.ret)}</b></div>
              <div className="sbox"><span>强弱差</span><b style={{ color: stats.ret - data.bench.ret >= 0 ? RED : GREEN }}>{pct(stats.ret - data.bench.ret)}</b></div>
            </div>
            <EChart option={benchOption} height={250} />
            <div className="legend">
              <span>{swatch(IDX_COLOR)}{data.name}</span>
              <span>{swatch(BENCH_COLOR)}{data.bench.name}</span>
            </div>
          </div>
        )}

        <div className="tv-foot">数据仅供研究，不构成投资建议</div>
      </div>
    </Spin>
  )
}

function pctWinLabel(meta, key) {
  return meta.pct_windows.find((w) => w.key === key)?.label || ''
}
