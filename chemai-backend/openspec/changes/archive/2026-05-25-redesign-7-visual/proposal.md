## Why

当前前端离 Academic Catalyst 原型的视觉质量差距巨大。需要逐组件还原：glassmorphism AI 气泡、牛津蓝侧边栏、羊皮纸质感、JetBrains Mono 公式区、进度条渐变。

## What Changes

- 更新 `frontend/design-system.css` — 完整实现所有组件样式
- 所有页面逐一检查视觉还原度

## Tasks

- [ ] 7.1 侧边栏：Oxford Blue (#002045) bg, 选中态白色加粗+右边框
- [ ] 7.2 AI 气泡：ai-glow bg + glassmorphism (backdrop-filter blur 12px) + teal 1px border
- [ ] 7.3 用户气泡：Oxford Blue bg, 白色文字, 右下角直角
- [ ] 7.4 ToolCard：左侧 surface-tint 3px 色带, 可折叠, JetBrains Mono
- [ ] 7.5 卡片组件：白色 bg, 1px wood-accent 30% opacity border, hover 微阴影
- [ ] 7.6 表格：JetBrains Mono table header (11px uppercase), IBM Plex Sans body
- [ ] 7.7 进度条：primary→secondary 渐变填充 + 脉冲动画
- [ ] 7.8 按钮：primary/teal/secondary 三变体, hover 态, disabled 态
- [ ] 7.9 输入框：inset 样式, focus 2px Oxford Blue 边框+外发光
- [ ] 7.10 Modal：16px 圆角, 柔和大阴影, backdrop blur
- [ ] 7.11 滚动条：自定义细滚动条
- [ ] 7.12 全站字体：Manrope (标题) + IBM Plex Sans (正文) + JetBrains Mono (代码/数据)
