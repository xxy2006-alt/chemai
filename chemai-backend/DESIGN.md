# DESIGN.md — ChemAI 智辅化学 · AI 可执行设计规格（v2 · 三端分册制）

> **v2 合成来源**：v1（35号+38号，见 `design-upgrade/归档/`）× 三端融合提案（Academic Catalyst × Linear/Spotify/Wise，2026-09-14 产品定案）。
> **使用方式**：AI 生成或修改任何 ChemAI 界面代码前，**必读总册（本文件）+ 按目标端读对应分册**。分册参数优先于本册通用描述；两册都未覆盖的，查第四段缺口表，**禁止自行发明设计参数**。

## ① 三端索引（改哪端代码 → 读哪册）

| 端 | 分册 | 温度 | 模式 | 主操作色 | AI 声音 |
|----|------|------|------|---------|---------|
| 教师 Web（7 页，React） | [design/教师端.md](design/教师端.md) | 冷峻精密（Linear） | 浅色 + 深色 AI 嵌板 | Oxford Blue `#002147` | Teal（深底用 `#2dd4bf`） |
| 学生移动（6 页，SPA /m/） | [design/学生端.md](design/学生端.md) | 活力深色（Spotify） | 深色 | 亮青 `#2dd4bf` | 同主色（单彩槽） |
| 家长移动（2 页，SPA /m/） | [design/家长端.md](design/家长端.md) | 温暖可信（Wise） | 浅色（鼠尾草底） | 亮绿 `#9fe870` | Teal（浅底变体） |

工程事实：教师端换肤走 `frontend/src/styles/tokens.css` + `AntdProvider.tsx`；学生/家长页已并入主 SPA（[ADR-0017](docs/adr/0017-mobile-into-react-spa.md)）。

## ② 全局规则（跨端 MUST/NEVER，端内细则见分册）

### 化学渲染
- **R-H1** 化学方程式 MUST 用 KaTeX + mhchem（`\ce{}`）。
- **R-H2** 纯文本化学式 MUST 转上下标（H2O → H₂O、Fe^3+ → Fe³⁺）。

### 字体
- **R-T1** 化学式/代码/数字数据 MUST JetBrains Mono 等宽；KPI 数字加 `tabular-nums`。
- **R-T2**（修订）正文 MUST 系统栈（PingFang SC / Microsoft YaHei / Noto Sans SC），零 Web 字体；**display 层允许自托管子集化 Web 字体**（Noto Sans SC 900/700、Inter 600/900）；NEVER 使用 CDN Google Fonts。Cormorant Garamond 已退役。

### 色彩
- **R-C2** Teal `#0d7377` 专属 AI 声音（AI 气泡/AI 按钮/AI 生成标记），三端一致；深底上用其亮变体 `#2dd4bf`（教师端深嵌板/学生端主彩）。NEVER 用于系统命令控件。
- **R-C7** NEVER 使用分册色板之外的颜色；新增先改分册。
- 语义状态一律「浅/深底 + 深/亮字」标签式（R-C6），NEVER 大面积纯色填充传状态。

### 几何
- **R-R1** 圆角梯子 8 / 12 / 16 / 24 / 9999（24 档为家长端卡片/按钮专用；学生端按钮与输入直接 9999 胶囊，见分册）。
- **R-R2** 阴影哲学按端：教师端以 1px 边框代阴影；学生端深底必须重阴影；家长端表面对比代阴影——细节值以分册为准。

### 状态与交互
- **R-S1** 每页 MUST 覆盖三态：加载（骨架屏）/空态/错误（描述+重试）。
- **R-S2** 空态 MUST 给出下一步行动，NEVER 只写"暂无数据"。
- **R-I1** 发消息后输入框清空并禁用；**R-I2** 审批类操作出确认卡片；**R-I3** Toast 3 秒自动消失。
- **R-I4** 跨页面跳转 MUST 走 Agent 桥接协议（SSE navigate/populate/action → 前端桥接存储 → 目标页自动配置）。

### 布局
- **R-L2** 移动端按 430×900 视口设计；**R-L4** 底部 Tab 56px。教师端三栏/侧边栏规则见教师端分册（R-T-L2）。

## ③ 跨端组件模式（P-01~P-20）

> 每端变体细节在对应分册"组件变体要点"。新页面遇到同类需求 MUST 复用，禁止另起炉灶。

| 编号 | 模式 | 端 | 分册变体差异 |
|------|------|----|------------|
| P-01 | 对话气泡 chat-bubble | 三端 | 教师浅区 Teal 浅底/深嵌板 teal-bubble-bg；学生 accent 胶囊；家长 Teal 浅底 24px 圆角 |
| P-02 | 状态徽章 status-badge | 三端 | 教师保持浅底深字（定案）；家长 positive-pale 胶囊 |
| P-03 | 顶部标题栏 top-bar | 移动端 | 学生取消实底顶栏融入 canvas；家长保留 |
| P-04 | 底部 Tab 导航 bottom-tabbar | 移动端 | 激活色：学生 accent / 家长亮绿 |
| P-05 | 侧边栏 sidebar | 教师 | Oxford Blue 实底 232px（定案） |
| P-06 | KPI 卡 kpi-card | 三端 | 教师 mono 数字；学生 surface 卡 900；家长 48px/900 + 涨跌徽章 |
| P-07 | 学生卡+详情抽屉 student-card/drawer | 教师 | 480px 右滑 + 遮罩 |
| P-08 | 弹窗 modal | 三端 | 圆角：教师/学生 16、家长 24 |
| P-09 | 通知 toast | 三端 | 右上浮出 3 秒（R-I3） |
| P-10 | 骨架屏 skeleton | 三端 | 深端用 surface-interactive 闪烁 |
| P-11 | 空状态 empty-state | 三端 | 烧杯图标 + 行动引导（R-S2） |
| P-12 | 上传区域 upload-zone | 教师 | 拖拽虚线框，悬停高亮 |
| P-13 | 进度条 progress-bar | 三端 | OCR/上传/掌握度 |
| P-14 | 题目卡片 question-card | 教师+学生 | 审核徽章/陷阱提示/操作按钮 |
| P-15 | 审核标记 audit-mark | 教师 | 四维安全审核（绿✓/黄⚠/红✗） |
| P-16 | 考试卡片 exam-card | 教师 | 状态标签 + 操作菜单 |
| P-17 | 数据表格 data-table | 教师 | OCR 结果表，失败行重试 |
| P-18 | 搜索筛选栏 search-filter-bar | 教师 | 输入框 + 筛选 chip |
| P-19 | 分页控件 pagination | 教师+学生 | 页码高亮 |
| P-20 | 手风琴折叠列表 accordion-list | 教师+学生 | 错题本/障碍诊断分组 |

## ④ 整体约束与缺口表

### 整体约束
1. 改界面代码前必读：总册 + 目标端分册；冲突时分册优先。
2. 设计系统变更 MUST 同步修订对应文档（总册或分册），并更新 `design-upgrade/README.md` 决议日志。
3. 页面口径：教师 7（6 外显 + 1 内联出题工作台）· 学生 6 · 家长 2 = 14 条目。
4. 跨页面数据传递一律走桥接协议（R-I4）。

### 缺口表（原 v1 GAP 处置）

| 编号 | 缺口 | 处置（v2） |
|------|------|-----------|
| GAP-01 | 间距尺度 | **已填**：教师/家长 4px 基数八档；学生 8px 基数（分册） |
| GAP-02 | 渐变按钮色值 | **已关闭**：渐变废弃，纯色主按钮（Linear no-gradients） |
| GAP-03 | 字号/字重/行高 | **已填**：三端 scale 见分册 |
| GAP-04 | 深色模式 | 教师端不设深色（AI 嵌板与登录页 moment 除外）；学生端即深色 |
| GAP-05 | 平板学生/家长端 | 沿用 v1：复用移动布局加宽内边距 |
| GAP-06 | 外部通知渠道样式 | 沿用 v1：仅站内 Toast + 家长消息 Tab |
| GAP-07 | 多主题切换 | 不支持；换肤即改分册参数 |

---

*v2 由三端融合提案（design-upgrade/提案-*.md，2026-09-14 定案）升格而来；v1 单册版归档于 design-upgrade/归档/。源设计分析文件（教师端-Linear 等）仅为灵感出处，NEVER 直接引用其色值——一切以本册与分册为准。*
