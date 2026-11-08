#!/usr/bin/env node
/* token-lint.mjs — R-C7 的机器执行：源码中禁止出现设计 token 体系之外的色值。
 * 白名单（token 唯一事实源 + antd 映射文件 + 图表调色板）：
 *   src/styles/**            设计 token 定义
 *   src/components/antd/AntdProvider.tsx   antd 主题映射（tokens 的 JS 镜像）
 *   src/components/ui/EChart.tsx           图表数据-viz 调色板（后续收敛进 token）
 * 用法：node scripts/token-lint.mjs（或 npm run lint:tokens）
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'

const ROOT = join(process.cwd(), 'src')
const ALLOW_FILES = /[/\\](styles)([/\\]|$)|AntdProvider\.tsx$|EChart\.tsx$/
const COLOR_RE = /(#[0-9a-fA-F]{3,8}\b|\brgba?\(\s*[\d.]+\s*,)/
const EXTS = /\.(tsx?|jsx?)$/

const offenders = []

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) {
      if (name === 'node_modules') continue
      walk(p)
    } else if (EXTS.test(name)) {
      const rel = relative(process.cwd(), p)
      if (ALLOW_FILES.test(rel)) continue
      const lines = readFileSync(p, 'utf8').split('\n')
      let inBlock = false
      lines.forEach((line, i) => {
        // 区块豁免：/* token-lint:disable-frame */ ... /* token-lint:enable-frame */
        if (/token-lint:disable-frame/.test(line)) inBlock = true
        if (/token-lint:enable-frame/.test(line)) { inBlock = false; return }
        if (inBlock) return
        // 行级豁免：行内 @token-allow（注明理由）
        if (/@token-allow/.test(line)) return
        // 跳过纯注释行（说明性文字可能引用色值文档）
        const code = line.replace(/\/\/.*$/, '').replace(/\/\*.*?\*\//g, '')
        if (COLOR_RE.test(code)) offenders.push(`${rel}:${i + 1}: ${line.trim()}`)
      })
    }
  }
}

walk(ROOT)
if (offenders.length) {
  console.error(`✗ token-lint：发现 ${offenders.length} 处 token 体系之外的色值（R-C7 违例）：`)
  for (const o of offenders) console.error('  ' + o)
  console.error('\n处理：改用 tokens.css / 分册色板中的 CSS 变量；确需新增色值 → 先更新分册。')
  process.exit(1)
}
console.log('✓ token-lint：源码色值全部在 token 体系内（R-C7 合规）')
