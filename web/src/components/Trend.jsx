import { useEffect, useMemo, useState } from 'react'
import { Empty, Segmented, Select, Spin, Tooltip, Typography } from 'antd'
import EChart from './EChart.jsx'
import { api } from '../api.js'

const { Text } = Typography

const RED = '#C0392B'
const GREEN = '#12805C'
const IDX_COLOR = '#2B5CE6'
const BENCH_COLOR = '#B26B3A'
const IND_COLORS = ['#7C5CE6', '#0E9F9F']
const QCOLORS = { 20: '#2E9E6B', 50: '#C99A2E', 80: '#C05252' }

const fmt = (v, d = 2) => (v == null ? '—' : v.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d }))
const pct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`)
const swatch = (color, dash) => (
  <i style={{
    display: 'inline-block', width: 14, height: 3, borderRadius: 2, marginRight: 6, verticalAlign: 'middle',
    background: dash ? `repeating-linear-gradient(90deg,${color} 0 5px,transparent 5px 8px)` : color,
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
    pct: p.get('pct'),
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
  const [pcts, setPcts] = useState(init.pct != null ? init.pct.split(',').filter(Boolean) : ['pe_ttm'])
  const [pctWin, setPctWin] = useState(init.pct_win || '3Y')
  const [bench, setBench] = useState(init.bench || '')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => { api.trendMeta().then(setMeta).catch((e) => setErr(String(e))) }, [])

  useEffect(() => {
    const q = new URLSearchParams({ code, range, gran, mode, ind: inds.join(','),
      pct: pcts.join(','), pct_win: pctWin, bench })
    window.history.replaceState(null, '', `#/trend?${q.toString()}`)
  }, [code, range, gran, mode, inds, pcts, pctWin, bench])

  const pickIndex = (c) => {
    setCode(c)
    const info = meta?.by_code?.[c]
    if (!info) return
    const valid = info.indicators.map((i) => i.key)
    const pValid = info.indicators.filter((i) => i.pct_line).map((i) => i.key)
    const keep = inds.filter((k) => valid.includes(k))
    setInds(keep.length ? keep : valid.slice(0, 1))
    const keepPct = pcts.filter((k) => pValid.includes(k))
    setPcts(keepPct.length ? keepPct : pValid.slice(0, 1))
  }

  useEffect(() => {
    if (!code) return
    setLoading(true)
    api.trend({ code, range, gran, mode, ind: inds.join(','), pct: pcts.join(','), pctWin, bench })
      .then((r) => { setData(r); setErr('') })
      .catch((e) => { setErr(String(e)); setData(null) })
      .finally(() => setLoading(false))
  }, [code, range, gran, mode, inds, pcts, pctWin, bench])

  const info = meta?.by_code?.[code]
  const list = meta?.indexes || []
  const indOptions = info?.indicators || []
  const pctOptions = indOptions.filter((o) => o.pct_line)
  const pts = data?.points || []
  const stats = data?.stats || {}
  const refLines = data?.ref_lines || []
  const labelOf = (key) => indOptions.find((o) => o.key === key)

  const toggleInd = (k) => setInds((cur) => {
    if (cur.includes(k)) return cur.filter((x) => x !== k)
    if (cur.length >= 2) return [cur[1], k]
    return [...cur, k]
  })
  const togglePct = (k) => setPcts((cur) => cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k])

  // 轴顺序：曲线指标在前，只有分位线的指标在后；颜色按轴序统一
  const axisKeys = useMemo(() => {
    const keys = (data?.indicators || []).map((o) => o.key)
    refLines.forEach((r) => { if (!keys.includes(r.ind)) keys.push(r.ind) })
    return keys
  }, [data, refLines])
  const colorOf = (k) => IND_COLORS[axisKeys.indexOf(k) % IND_COLORS.length] || IND_COLORS[0]

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
      splitLine: { lineStyle: { color: '#EEF1F6' } },
      scale: true,
    }]
    axisKeys.forEach((k, i) => {
      const o = labelOf(k)
      if (!o) return
      const spec = data?.indicators?.find((x) => x.key === k)
      const vals = (spec?.points || []).map((p) => p.value).filter((v) => v != null)
      const mine = refLines.filter((r) => r.ind === k)
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
        nameTextStyle: { color: colorOf(k), fontSize: 11, align: 'left', padding: [0, 0, 2, 0] },
        nameGap: 26,
        position: 'right', offset: i * 62,
        axisLine: { show: true, lineStyle: { color: colorOf(k) } },
        axisTick: { show: false },
        axisLabel: { color: colorOf(k), fontSize: 11 },
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
            colorStops: [{ offset: 0, color: 'rgba(43,92,230,0.10)' }, { offset: 1, color: 'rgba(43,92,230,0)' }] },
        }, z: 2,
      })
    } else {
      series.push({
        name: '累积收益', type: 'line', data: pts.map((p) => p.cum),
        showSymbol: false, smooth: 0.12, lineStyle: { width: 2.4, color: IDX_COLOR },
        markLine: { silent: true, symbol: 'none', label: { show: false },
          lineStyle: { color: '#C9D1DD', type: 'dashed' }, data: [{ yAxis: 0 }] }, z: 2,
      })
    }

    axisKeys.forEach((k, i) => {
      const spec = data?.indicators?.find((x) => x.key === k)
      const o = labelOf(k)
      const mine = refLines.filter((r) => r.ind === k)
      const markLine = mine.length ? {
        silent: true, symbol: 'none',
        data: mine.map((r) => ({
          yAxis: r.value,
          lineStyle: { color: QCOLORS[r.q], type: 'dashed', width: 1.5 },
          label: {
            formatter: `${r.q}% ${fmt(r.value, 2)}${o?.unit || ''}`,
            position: i === 0 ? 'insideEndTop' : 'insideStartTop', fontSize: 10.5,
            color: QCOLORS[r.q], backgroundColor: 'rgba(255,255,255,.9)', padding: [1, 3],
          },
        })),
      } : undefined
      // 曲线指标：画线 + 分位线；仅分位指标：空序列只承载分位线
      series.push({
        name: o?.label || k, type: 'line', yAxisIndex: i + 1,
        data: spec ? spec.points.map((p) => p.value) : [],
        showSymbol: false, connectNulls: true, smooth: 0.1,
        lineStyle: { width: 2, color: colorOf(k), opacity: spec ? 1 : 0 },
        itemStyle: { color: colorOf(k) }, z: 4, markLine,
      })
    })

    return {
      animationDuration: 420,
      grid: { left: 6, right: 12 + 64 * axisKeys.length, top: 58, bottom: 34, containLabel: true },
      tooltip: {
        trigger: 'axis', backgroundColor: 'rgba(255,255,255,.97)', borderColor: '#E6EAF0', borderWidth: 1,
        padding: [8, 12], textStyle: { color: '#1F2733', fontSize: 12 },
        formatter: (ps) => {
          const p = pts[ps[0].dataIndex]
          if (!p) return ''
          const rows = [`<div style="font-weight:600;margin-bottom:4px">${p.date}</div>`, `<div>收盘 <b>${fmt(p.close)}</b></div>`]
          if (p.pct != null) rows.push(`<div>涨跌 <b style="color:${p.pct >= 0 ? RED : GREEN}">${pct(p.pct)}</b></div>`)
          if (p.cum != null) rows.push(`<div>区间累积 <b>${pct(p.cum)}</b></div>`)
          data.indicators.forEach((o) => {
            const v = o.points[ps[0].dataIndex]?.value
            if (v != null) rows.push(`<div>${o.label} <b>${fmt(v)}${o.unit || ''}</b></div>`)
          })
          return rows.join('')
        },
      },
      axisPointer: { type: 'line', lineStyle: { color: '#C9D1DD', type: 'dashed' } },
      xAxis: {
        type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: '#E6EAF0' } }, axisTick: { show: false },
        axisLabel: { color: '#98A3B3', fontSize: 11, hideOverlap: true },
      },
      yAxis: axes, series,
    }
  }, [pts, data, mode, refLines, axisKeys, labelOf, colorOf])

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
        trigger: 'axis', backgroundColor: 'rgba(255,255,255,.97)', borderColor: '#E6EAF0', borderWidth: 1,
        padding: [6, 10], textStyle: { color: '#1F2733', fontSize: 12 },
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
      axisPointer: { type: 'line', lineStyle: { color: '#C9D1DD', type: 'dashed' } },
      xAxis: {
        type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: '#E6EAF0' } }, axisTick: { show: false },
        axisLabel: { color: '#98A3B3', fontSize: 11, hideOverlap: true },
      },
      yAxis: [
        { type: 'value', name: data.name, scale: true,
          nameTextStyle: { color: IDX_COLOR, fontSize: 11, align: 'right', padding: [0, 0, 3, 0] },
          axisLine: { show: true, lineStyle: { color: IDX_COLOR } }, axisTick: { show: false },
          axisLabel: { color: IDX_COLOR, fontSize: 11 }, splitLine: { lineStyle: { color: '#F1F4F8' } } },
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

  if (err) return <div className="ds-card ds-empty"><Empty description={`加载失败：${err}`} /></div>
  if (!meta) return <div className="ds-loading"><Spin size="large" tip="正在准备数据…" /></div>

  const up = (stats.last_pct ?? 0) >= 0

  return (
      <div className="ds-page">
        <header className="ds-hero">
          <div className="ds-hero-main">
            <div className="ds-eyebrow">VALUATION WATCH · 估值观察</div>
            <h1>指数估值走势</h1>
            <p>估值水位、股息回报与 QDII 溢价，一屏看全</p>
          </div>
          <div className="ds-hero-quote">
            <div className="ds-quote-value" style={{ color: up ? RED : GREEN }}>
              {data ? fmt(stats.last) : '—'}
              <span>{data ? pct(stats.last_pct) : ''}</span>
            </div>
            <div className="ds-quote-sub">
              {data ? `${data.name} · ${stats.start} 至 ${stats.end} · ${stats.n} 个数据点${loading ? ' · 更新中' : ''}` : '正在读取行情'}
            </div>
          </div>
        </header>

        <section className="ds-panel">
          <div className="ds-row">
            <span className="ds-label">选择指数</span>
            <div className="ds-chips">
              {list.map((x) => (
                <button key={x.code} className={`ds-chip ${x.code === code ? 'is-on' : ''}`} onClick={() => pickIndex(x.code)}>
                  {x.name}<em>{x.tag}</em>
                </button>
              ))}
            </div>
          </div>

          <div className="ds-divider" />

          <div className="ds-row">
            <span className="ds-label">时间区间</span>
            <Segmented size="small" options={meta.ranges.map((r) => ({ label: r.label, value: r.key }))} value={range} onChange={setRange} />
            <span className="ds-label ds-label-gap">K 线粒度</span>
            <Segmented size="small" options={meta.grans.map((g) => ({ label: g.label, value: g.key }))} value={gran} onChange={setGran} />
            <span className="ds-label ds-label-gap">显示方式</span>
            <Segmented size="small"
              options={[{ label: '点位', value: 'point' }, { label: '累积收益', value: 'cum' }]}
              value={mode} onChange={setMode} />
          </div>

          <div className="ds-divider" />

          <div className="ds-row">
            <span className="ds-label">指标曲线</span>
            <div className="ds-chips">
              {indOptions.map((o) => (
                <Tooltip key={o.key} title={o.why}>
                  <button className={`ds-chip ${inds.includes(o.key) ? 'is-on' : ''}`} onClick={() => toggleInd(o.key)}>
                    {o.label}{o.unit ? <em>{o.unit}</em> : null}
                  </button>
                </Tooltip>
              ))}
            </div>
            <span className="ds-hint">最多同时显示 2 条</span>
          </div>

          <div className="ds-row">
            <span className="ds-label">分位线</span>
            <div className="ds-chips">
              {pctOptions.map((o) => (
                <Tooltip key={o.key} title={`在 ${o.label} 轴上叠加 20% / 50% / 80% 三条参考线`}>
                  <button className={`ds-chip ds-chip-ghost ${pcts.includes(o.key) ? 'is-on' : ''}`} onClick={() => togglePct(o.key)}>
                    {o.label}
                  </button>
                </Tooltip>
              ))}
            </div>
            {pcts.length > 0 ? (
              <>
                <span className="ds-label ds-label-gap">参考窗口</span>
                <Segmented size="small" options={meta.pct_windows.map((w) => ({ label: w.label, value: w.key }))} value={pctWin} onChange={setPctWin} />
              </>
            ) : <span className="ds-hint">逐项开启，可独立于指标曲线</span>}
          </div>

          <div className="ds-divider" />

          <div className="ds-row">
            <span className="ds-label">指数对比</span>
            <Select size="small" style={{ width: 200 }} allowClear placeholder="不对比" value={bench || undefined}
              onChange={(v) => setBench(v || '')}
              options={list.filter((x) => x.code !== code).map((x) => ({ label: x.name, value: x.code }))} />
            <span className="ds-hint">在下方单独成图，不影响上方指标</span>
          </div>
        </section>

        <section className="ds-card">
          <div className="ds-stats">
            <div className="ds-stat"><span>区间涨跌</span><b style={{ color: stats.ret >= 0 ? RED : GREEN }}>{pct(stats.ret)}</b></div>
            <div className="ds-stat"><span>最大回撤</span><b style={{ color: GREEN }}>{pct(stats.mdd)}</b></div>
            <div className="ds-stat"><span>年化波动</span><b>{stats.vol == null ? '—' : `${stats.vol}%`}</b></div>
            <div className="ds-stat"><span>上涨 / 下跌</span><b>{stats.up_days ?? '—'} / {stats.down_days ?? '—'}</b></div>
            {(data?.indicators || []).map((o) => {
              const v = stats.ind_last?.[o.key]
              const q = stats.ind_last?.[o.key + '_pct']
              return (
                <div className="ds-stat" key={o.key}>
                  <span>{o.label}{q != null ? ` · 近${pctWin === 'ALL' ? '全部' : pctWin}分位 ${q}%` : ''}</span>
                  <b style={{ color: colorOf(o.key) }}>{v == null ? '—' : `${fmt(v)}${o.unit || ''}`}</b>
                </div>
              )
            })}
          </div>
          {option ? <EChart option={option} height={440} /> : <Empty description="暂无数据" />}
          <div className="ds-legend">
            <span>{swatch(IDX_COLOR)}{mode === 'point' ? (data?.cls === 'stock' ? '股价' : '指数点位') : '累积收益'}</span>
            {(data?.indicators || []).map((o) => (
              <span key={o.key}>{swatch(colorOf(o.key))}{o.label}</span>
            ))}
            {axisKeys.filter((k) => !(data?.indicators || []).some((o) => o.key === k)).map((k) => (
              <span key={k}>{swatch(colorOf(k), true)}{labelOf(k)?.label}（仅分位）</span>
            ))}
            {refLines.length > 0 && [20, 50, 80].map((q) => (
              <span key={q}>{swatch(QCOLORS[q], true)}{q}% 分位</span>
            ))}
          </div>
        </section>

        {data?.bench && benchOption && (
          <section className="ds-card">
            <div className="ds-card-head">
              <h2>指数对比</h2>
              <Text type="secondary" style={{ fontSize: 12 }}>{data.name} vs {data.bench.name} · 各自独立纵轴</Text>
            </div>
            <div className="ds-stats">
              <div className="ds-stat"><span>{data.name} 区间涨跌</span><b style={{ color: stats.ret >= 0 ? RED : GREEN }}>{pct(stats.ret)}</b></div>
              <div className="ds-stat"><span>{data.bench.name} 区间涨跌</span><b style={{ color: data.bench.ret >= 0 ? RED : GREEN }}>{pct(data.bench.ret)}</b></div>
              <div className="ds-stat"><span>强弱差</span><b style={{ color: stats.ret - data.bench.ret >= 0 ? RED : GREEN }}>{pct(stats.ret - data.bench.ret)}</b></div>
            </div>
            <EChart option={benchOption} height={250} />
            <div className="ds-legend">
              <span>{swatch(IDX_COLOR)}{data.name}</span>
              <span>{swatch(BENCH_COLOR)}{data.bench.name}</span>
            </div>
          </section>
        )}

        <div className="ds-foot">仅供研究，不构成投资建议</div>
      </div>
  )
}
