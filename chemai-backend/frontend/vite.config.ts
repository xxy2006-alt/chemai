import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// ChemAI 教师端 · React + TS 重构（方向 A 现代学术蓝）
export default defineConfig({
  root: '.',
  base: '/',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // 2026-08 第二轮：antd 独立分包（体积大且稳定，利于浏览器缓存 + 首屏并行加载）
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/antd') || id.includes('node_modules/@ant-design') || id.includes('node_modules/@rc-component') || id.includes('node_modules/rc-')) {
            return 'antd'
          }
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      // 127.0.0.1 而非 localhost：Windows 上 localhost 可能先解析到 ::1，
      // uvicorn 只绑 IPv4 时会导致代理 ECONNREFUSED（登录"请求失败"）
      '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/static': { target: 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
})
