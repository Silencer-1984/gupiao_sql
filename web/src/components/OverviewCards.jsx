import EChart from './EChart.jsx'

const pctCls = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : 'flat')
const fmtPct = (v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}%`

function Gauge({ value, color }) {
  const option = {
    animationDuration: 900,
    series: [
      {
        type: 'gauge',
        startAngle: 208,
        endAngle: -28,
        min: 0,
        max: 100,
        radius: '104%',
        center: ['50%', '64%'],
        splitNumber: 10,
        axisLine: {
          lineStyle: {
            width: 15,
            color: [
              [0.15, '#0f9d58'],
              [0.3, '#4cb46b'],
              [0.45, '#a9d5a5'],
              [0.55, '#dfe4ea'],
              [0.7, '#f6c24a'],
              [0.85, '#ef8a3a'],
              [1, '#d63031'],
            ],
          },
        },
        pointer: { width: 4, length: '66%', offsetCenter: [0, '4%'], itemStyle: { color: '#2b3440' } },
        anchor: { show: true, size: 10, itemStyle: { color: '#2b3440' } },
        axisTick: { distance: -16, length: 4, lineStyle: { color: '#c3cbd8', width: 1 } },
        splitLine: { distance: -18, length: 9, lineStyle: { color: '#9aa5b5', width: 1.3 } },
        axisLabel: { distance: -2, color: '#98a3b3', fontSize: 10.5 },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '34%'],
          fontSize: 38,
          fontWeight: 700,
          color: '#1f2733',
          formatter: (v) => v.toFixed(1),
        },
        data: [{ value }],
      },
    ],
  }
  return <EChart option={option} height={210} />
}

export default function OverviewCards({ ov }) {
  if (!ov) return null
  const volPct = Math.min(100, Math.max(0, (ov.vol_ratio / 1.5) * 100))

  return (
    <div className="grid3">
      {/* 策略 */}
      <div className="card">
        <div className="card-head">
          <div className="ico">⚡</div>
          <div className="t">风格策略</div>
          <div className="d">{ov.date}</div>
        </div>
        <div className="card-body" style={{ justifyContent: 'space-between' }}>
          <div className="advice-box">
            <div className="lb">今日建议</div>
            <div className="val">{ov.advice}</div>
            {ov.sleeves?.tilt && (
              <div style={{ marginTop: 6, fontSize: 12, color: '#8a94a6' }}>
                相对强弱：<b style={{ color: ov.sleeves.tilt === '偏成长' ? '#e04b4b' : ov.sleeves.tilt === '偏价值' ? '#129d5b' : '#5b6678' }}>{ov.sleeves.tilt}</b>
              </div>
            )}
          </div>

          <div className="kv">
            <div className="k">📈 沪深300 近5日</div>
            <div className={`v ${pctCls(ov.mrzq)}`}>{fmtPct(ov.mrzq)}</div>
          </div>
          <div className="kv">
            <div className="k">🔍 极端信号扫描</div>
            <div className="v">
              <span className={`pill ${ov.anomaly >= 5 ? 'warn' : 'ok'}`}>异常 {ov.anomaly}</span>
            </div>
          </div>
          <div className="advice-reason">{ov.advice_reason}</div>
        </div>
      </div>

      {/* 温度 */}
      <div className="card">
        <div className="card-head">
          <div className="ico">🌡️</div>
          <div className="t">市场温度</div>
          <div className="d">{ov.date}</div>
        </div>
        <div className="card-body" style={{ paddingBottom: 8 }}>
          <Gauge value={ov.temperature} color={ov.temp_color} />
          <div style={{ textAlign: 'center', marginTop: -14, paddingBottom: 6 }}>
            <div style={{ fontSize: 17, fontWeight: 700, color: ov.temp_color }}>{ov.temp_label}</div>
            <div style={{ fontSize: 12, color: '#8a94a6', marginTop: 4 }}>
              全指恐慌度 {ov.fear}（100 − 恐慌 = 温度）
            </div>
          </div>
        </div>
      </div>

      {/* 行情 */}
      <div className="card">
        <div className="card-head">
          <div className="ico">📊</div>
          <div className="t">市场行情</div>
          <div className="d">{ov.date}</div>
        </div>
        <div className="card-body">
          <div className="stat2">
            <div className="stat-box">
              <div className="lb">上证指数 <span>▼</span></div>
              <div className={`v ${pctCls(ov.sh.pct)}`}>{fmtPct(ov.sh.pct)}</div>
            </div>
            <div className="stat-box">
              <div className="lb">深证成指 <span>▼</span></div>
              <div className={`v ${pctCls(ov.sz.pct)}`}>{fmtPct(ov.sz.pct)}</div>
            </div>
          </div>
          <div className="kv">
            <div className="k">💰 两市成交额</div>
            <div className="v">{(ov.amount / 10000).toFixed(2)} 万亿</div>
          </div>
          <div className="kv" style={{ display: 'block' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="k">📉 量能状态</span>
              <span className="v" style={{ fontSize: 13 }}>{ov.vol_ratio.toFixed(2)}</span>
            </div>
            <div className="volbar"><i style={{ width: `${volPct}%` }} /></div>
            <div style={{ fontSize: 11.5, color: '#8a94a6', marginTop: 5 }}>今日成交 / 20 日均值</div>
          </div>
          <div className="kv">
            <div className="k">🧭 小盘风格</div>
            <div className="v">
              <span className={`pill ${ov.smallcap > 0 ? 'up-pill' : 'down-pill'}`}>
                {ov.smallcap > 0 ? '占优' : '弱势'} {fmtPct(ov.smallcap)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
