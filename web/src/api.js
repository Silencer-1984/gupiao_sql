const base = '/api'

async function j(url, opt) {
  const r = await fetch(base + url, opt)
  if (!r.ok) throw new Error(`${url} ${r.status}`)
  return r.json()
}

export const api = {
  overview: () => j('/overview'),
  watch: () => j('/watch'),
  grid: (freq = 'D') => j(`/grid?freq=${freq}`),
  series: (code, freq) => j(`/series?code=${encodeURIComponent(code)}&freq=${freq}&limit=400`),
  sentiment: () => j('/sentiment'),
  summary: (period = 'day') => j(`/summary?period=${period}`),
  dailyJob: () => j('/daily_job', { method: 'POST' }),
  tempHistory: (freq = 'D') => j(`/temperature/history?freq=${freq}`),
  trendMeta: () => j('/trend/meta'),
  trend: ({ code, range, gran, mode, ind, pctWin, bench }) =>
    j(`/trend?code=${encodeURIComponent(code)}&range=${range}&gran=${gran}&mode=${mode}`
      + `&ind=${encodeURIComponent(ind || '')}&pct_win=${pctWin}&bench=${encodeURIComponent(bench || '')}`),
}
