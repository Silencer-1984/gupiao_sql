import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import ChartApp from './ChartApp.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#2563EB',
          colorText: '#1f2733',
          colorTextSecondary: '#8a94a6',
          colorBgLayout: '#f4f6f9',
          borderRadius: 10,
          fontSize: 13,
        },
      }}
    >
      <ChartApp />
    </ConfigProvider>
  </React.StrictMode>,
)
