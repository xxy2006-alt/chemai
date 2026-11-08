// ui-review.mjs — 新教师端 UI 截图（Phase 1 评审用）
// 用法: node scripts/ui-review.mjs [url] [out.png] [width height]
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const url = process.argv[2] || 'http://localhost:3000/#/login'
const out = resolve(process.argv[3] || `docs/ui-review/${new URL(url).hash.replace(/[^a-z]/g, '') || 'page'}.png`)
const width = Number(process.argv[4] || 1440)
const height = Number(process.argv[5] || 900)

mkdirSync(dirname(out), { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width, height } })
// 注入假 token 以便进入需要登录的页面
await page.addInitScript(() => {
  localStorage.setItem('token', 'review-token')
})
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(600)
await page.screenshot({ path: out, fullPage: false })
await browser.close()
console.log('saved:', out)
