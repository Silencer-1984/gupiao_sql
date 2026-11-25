import React from 'react'

function Card({ s }) {
  if (!s) return null
  const kind = s.kind || 'mid'
  return (
    <div className="mini-card style">
      <div className="sc-left">
        <div className="mc-name">{s.name}</div>
        <span className={`mc-pill ${kind}`}>{s.stance}</span>
      </div>
      <div className={`mc-big ${kind === 'up' ? 'up' : kind === 'down' ? 'down' : 'flat'}`}>
        {s.score == null ? '—' : s.score}
      </div>
      <div className="sc-reasons">{(s.reasons || []).join(' · ')}</div>
    </div>
  )
}

/** 风格建议：只有「今日」一个维度，因此不放进日/周/月/年切换的卡片网格。 */
export default function StyleRow({ sleeves }) {
  if (!sleeves) return null
  return (
    <div className="section">
      <div className="grid-head">
        <div>
          <h2>风格建议</h2>
          <span className="sub">
            成长（科创50+有色） / 价值（红利）· 仅今日读数
            {sleeves.tilt ? ` · 相对强弱：${sleeves.tilt}` : ''}
          </span>
        </div>
      </div>
      <div className="style-row">
        <Card s={sleeves.growth} />
        <Card s={sleeves.value} />
      </div>
    </div>
  )
}
