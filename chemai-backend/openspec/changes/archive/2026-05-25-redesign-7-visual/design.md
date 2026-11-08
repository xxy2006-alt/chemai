## Design: 视觉打磨

### 当前状态
design-system.css 已实现完整的 Academic Catalyst 设计系统，覆盖全部 12 个组件。

### 审查清单
- 侧边栏: Oxford Blue bg / 选中态 / 字体 ✅
- AI气泡: glassmorphism / teal border ✅
- 用户气泡: Oxford Blue / 白字 / 右下直角 ✅
- ToolCard: 左侧色带 / 可折叠 / JetBrains Mono ✅
- 卡片: 白色 / wood border / hover shadow ✅
- 表格: JetBrains Mono header / 大写 ✅
- 进度条: 渐变 / 脉冲动画 ✅
- 按钮: 三变体 / hover / disabled ✅
- 输入框: inset / focus glow ✅
- Modal: 圆角 / 大阴影 / backdrop blur ✅
- 滚动条: 自定义细滚动条 ✅
- 字体: Manrope+IBM Plex Sans+JetBrains Mono ✅

### 待改进
- 主页(index.html)内联样式较多，可适当迁移到 CSS class
- OCR 页面视觉一致性审查
