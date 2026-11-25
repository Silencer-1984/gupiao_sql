import { useEffect, useState } from 'react'
import { api } from '../api.js'

const pct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`)
const cls = (v) => (v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : '')


function SubScore({ label, hint, value, weight }) {
  const v = value == null ? null : Math.max(0, Math.min(100, value))
  const color = v == null ? '#cfd6e0' : v > 60 ? '#e04b4b' : v < 40 ? '#129d5b' : '#f2b134'
  return (
    <div style={{ padding: '7px 0', borderTop: '1px dashed #eef1f6' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
        <span style={{ color: '#5b6678' }}>
          {label}
          <span style={{ color: '#b3bcc9', marginLeft: 6, fontSize: 11 }}>{weight}</span>
        </span>
        <span style={{ fontWeight: 600, color: v == null ? '#b3bcc9' : '#1f2733' }}>
          {v == null ? '—' : v.toFixed(1)}
        </span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: '#eef1f6', marginTop: 5 }}>
        <i style={{ display: 'block', height: '100%', borderRadius: 2, width: `${v || 0}%`, background: color }} />
      </div>
      <div style={{ fontSize: 11, color: '#a9b3c2', marginTop: 4 }}>{hint}</div>
    </div>
  )
}

export default function Sentiment({ tick }) {
  const [tab, setTab] = useState('hot')
  const [d, setD] = useState(null)

  useEffect(() => {
    api.sentiment().then(setD).catch(() => setD(null))
  }, [tick])

  if (!d) return <div className="chart-card"><div className="empty">舆情缓存读取中…</div></div>

  if (d.pending) {
    return (
      <div className="chart-card">
        <div className="empty">
          还没有舆情缓存。<br />运行一次每日任务后即可查看：uv run python scripts/daily_job.py
        </div>
      </div>
    )
  }

  const scoreColor = d.score > 65 ? '#e04b4b' : d.score < 35 ? '#129d5b' : '#f2b134'
  const rows = tab === 'hot' ? d.hot : d.search
  const fetched = d.fetched_at ? d.fetched_at.slice(11, 16) : '—'

  return (
    <div className="two">
      <div className="card">
        <div className="card-head">
          <div className="ico">💬</div>
          <div className="t">舆情情绪</div>
          <div className="d" style={{ marginLeft: 'auto', fontSize: 11.5 }}>
            {d.stale ? `缓存 ${d.date}` : `今日 ${fetched} 采集`}
          </div>
        </div>
        <div className="card-body">
          <div className="score-num" style={{ color: scoreColor }}>{d.score}</div>
          <div className="score-lb">舆情情绪分（0 极度悲观 · 100 极度亢奋）</div>
          <div className="meter"><i style={{ width: `${d.score}%` }} /></div>

          <div style={{ marginTop: 6 }}>
            <SubScore
              label="① 人气股评价"
              hint={d.comment_n ? `千股千评 · ${d.comment_n} 只` : '未取到'}
              value={d.score_text}
              weight="40%"
            />
            <SubScore
              label="② 快讯多空"
              hint={d.news_n ? `财联社近 ${d.news_n} 条：${d.news_pos} 正 / ${d.news_neg} 负` : '未取到'}
              value={d.score_news}
              weight="35%"
            />
            <SubScore
              label="③ 热股涨跌表现"
              hint={`平均 ${pct(d.mean_pct)}，上涨 ${d.up_ratio == null ? '—' : d.up_ratio + '%'}`}
              value={d.score_price}
              weight="25%"
            />
          </div>

          <div className="kv">
            <span className="k">数据来源</span>
            <span className="v" style={{ fontSize: 12, color: '#8a94a6', fontWeight: 400 }}>
              {d.source_name || '热度榜'} + 百度热搜（只读缓存）
            </span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <div className="ico">🔥</div>
          <div className="t">个股热度榜</div>
          <div className="d" style={{ marginLeft: 'auto' }}>
            <div className="tabs">
              <button className={tab === 'hot' ? 'on' : ''} onClick={() => setTab('hot')}>热度榜</button>
              <button className={tab === 'search' ? 'on' : ''} onClick={() => setTab('search')}>百度热搜</button>
            </div>
          </div>
        </div>
        <div className="card-body" style={{ padding: '6px 10px 12px', maxHeight: 330, overflow: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 44 }}>#</th>
                <th>名称</th>
                <th className="num">涨跌幅</th>
                <th className="num">热度</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.rank}-${r.name}`}>
                  <td className="rk">{r.rank}</td>
                  <td>
                    {r.name}
                    {r.code ? <span style={{ color: '#a9b3c2', fontSize: 11.5 }}> · {r.code}</span> : null}
                  </td>
                  <td className={`num ${cls(r.pct)}`}>{pct(r.pct)}</td>
                  <td className="num" style={{ color: '#8a94a6' }}>
                    {r.heat ? (r.heat >= 10000 ? (r.heat / 10000).toFixed(1) + '万' : r.heat.toFixed(0)) : '—'}
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan={4} className="empty">暂无数据</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
