import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'katex/dist/katex.min.css' // KaTeX 样式（隐藏 MathML 层，避免公式重复显示）
/* display 字体（R-T2 修订：display 层自托管子集 Web 字体；正文仍走系统栈）
   fontsource 按 unicode-range 切片，浏览器只下载用到的字符区间 */
import '@fontsource/inter/600.css'
import '@fontsource/inter/900.css'
import '@fontsource/noto-sans-sc/700.css'
import '@fontsource/noto-sans-sc/900.css'
import './styles/globals.css'
import { App } from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
