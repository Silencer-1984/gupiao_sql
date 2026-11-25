import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'

const FREQ = [
  { k: 'D', label: '日' },
  { k: 'W', label: '周' },
  { k: 'M', label: '月' },
  { k: 'Y', label: '年' },
]

const fmtPct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`)
const cls = (v) => (v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : 'flat')
const num = (v) => (v == null ? '—' : v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))

export default function GridCards() {
  const [freq, setFreq] = useState('D')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.grid(freq).then(setData).catch(() => setData(null)).finally(() => setLoading(false))
  }, [freq])

  const items = data?.items || []
  const updated = useMemo(() => items.find((x) => x.date)?.date || '', [items])

  return (
    <div className="grid-card-wrap">
      <div className="grid-head">
        <div>
          <h2>重点关注</h2>
          <span className="sub">12 个标的 · 支持日 / 周 / 月 / 年</span>
        </div>
        <div className="tabs">
          {FREQ.map((f) => (
            <button key={f.k} className={f.k === freq ? 'on' : ''} onClick={() => setFreq(f.k)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mini-grid">
        {items.map((it) => (
          <div className="mini-card" key={it.code}>
            <div className="mc-name">
              {it.name}
              {it.tag ? <span className="mc-tag">{it.tag}</span> : null}
            </div>
            <div className={`mc-big ${cls(it.pct)}`}>{fmtPct(it.pct)}</div>
            <div className="mc-sub">
              <span className="mc-close">{num(it.close)}</span>
              {it.premium != null && (
                <span className={`mc-prem ${it.premium > 5 ? 'warn' : ''}`} title="场内价/前一日净值 - 1">
                  溢价 {it.premium > 0 ? '+' : ''}{it.premium.toFixed(1)}%
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="grid-foot">
        {loading ? '加载中…' : `数据截至 ${updated || '—'}　·　涨跌按${FREQ.find((f) => f.k === freq)?.label}度计算`}
        　·　纳指溢价率为 159941 场内价/前一日净值（时点匹配口径）　·　仅供研究，不构成投资建议
      </div>
    </div>
  )
}
