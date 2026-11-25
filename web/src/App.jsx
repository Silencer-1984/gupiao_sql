import { useEffect, useState } from 'react'
import { Segmented, Space, Typography } from 'antd'
import Home from './components/Home.jsx'
import Trend from './components/Trend.jsx'

const NAV = [
  { label: '总览', value: 'home' },
  { label: '指数走势', value: 'trend' },
]
const readPage = () => (window.location.hash.replace(/^#\/?/, '').split('?')[0] || 'home')

export default function App() {
  const [page, setPage] = useState(readPage() === 'trend' ? 'trend' : 'home')

  useEffect(() => {
    const onHash = () => setPage(readPage() === 'trend' ? 'trend' : 'home')
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (p) => {
    window.location.hash = p === 'trend' ? '#/trend' : '#/'
    setPage(p)
  }

  return (
    <div className="wrap">
      <Space direction="vertical" size={14} style={{ width: '100%' }}>
        <Space align="center" size={16} wrap>
          <Typography.Title level={3} style={{ margin: 0 }}>A股风格轮动看板</Typography.Title>
          <Segmented options={NAV} value={page} onChange={go} />
        </Space>
        {page === 'trend' ? <Trend /> : <Home />}
      </Space>
    </div>
  )
}
