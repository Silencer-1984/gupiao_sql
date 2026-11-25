import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// 图表专用构建：只打包 Trend 页，产物写到部署目录的 public/（避开发布工具对 dist 的排除）
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(import.meta.dirname, '../deploy/chart/static'),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(import.meta.dirname, 'chart.html'),
    },
  },
})
