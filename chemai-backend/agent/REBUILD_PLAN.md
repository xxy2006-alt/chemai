# ChemAI 教师端前端重做计划

## 技术栈

| 层 | 选型 | 原因 |
|---|------|------|
| 构建 | Vite | 已有配置，零成本复用 |
| CSS | Tailwind CSS v3 (CDN) | 原型用 Tailwind，完美还原 |
| 字体 | Manrope + IBM Plex Sans + JetBrains Mono | 原型指定的三字体系 |
| 图标 | Material Symbols (Google Fonts) | 原型使用，免费 |
| JS | vanilla JS (ES module) | 保持简单，不引入框架 |
| 状态 | sessionStorage + URL params | 轻量 |

## 原型对应 → 实现文件

| # | 原型页面 | 实现文件 | 功能 |
|---|---------|---------|------|
| 0 | — | `login.html` | 登录（已有，保留） |
| 1 | `ai/code.html` | `index.html` (首页) | AI 教研助手对话 |
| 2 | `_5/code.html` | `pages/ocr.html` | 答题卡识别 |
| 3 | `_7/code.html` | `pages/exam.html` | 考试管理 |
| 4 | `_2/code.html` | `pages/questions.html` | 题目管理 |
| 5 | `_1/code.html` | `pages/diagnosis.html` | 障碍诊断 |
| 6 | `_6/code.html` | `pages/report.html` | 学情报告 |
| 7 | `_3/code.html` | `pages/panel.html` | 学情面板 |
| 8 | `_4/code.html` | `pages/students.html` | 学生管理 |

## 目录结构

```
chemai-backend/frontend/
├── index.html              # 首页 = AI 教研助手
├── login.html              # 登录（保留原有）
├── app.js                  # 全局 JS：登录检查 + 导航 + fetch 拦截
├── design-system.css       # 设计系统 CSS 变量 + 自定义组件样式
├── pages/
│   ├── ocr.html            # 答题卡识别
│   ├── exam.html           # 考试管理
│   ├── questions.html      # 题目管理
│   ├── diagnosis.html      # 障碍诊断
│   ├── report.html         # 学情报告
│   ├── panel.html          # 学情面板
│   └── students.html       # 学生管理
└── js/
    ├── agent.js            # AI 对话逻辑 (SSE)
    ├── ocr.js              # OCR 识别逻辑
    ├── exam.js             # 考试管理逻辑
    ├── questions.js        # 题目管理逻辑
    ├── diagnosis.js        # 障碍诊断逻辑
    ├── report.js           # 报告逻辑
    ├── panel.js            # 学情面板逻辑
    └── students.js         # 学生管理逻辑
```

## 清理列表（删除旧文件）

```
删除整个 src/ 目录（50个旧JS文件）
删除 styles.css（旧样式）
删除 index_new.html（旧入口）
删除 parent_portal.html
删除 components/ 目录
删除 app.js（重写）
保留 login.html（修改样式匹配新设计系统）
保留 .env / .gitignore / package.json / vite.config.js
```

## 实施步骤

### Step 1: 清理 + 基础设施 (~10min)
- 删除 `frontend/src/`、`frontend/styles.css`、`frontend/components/`、`frontend/index_new.html`
- 创建新目录结构 `frontend/pages/`、`frontend/js/`
- 写 `design-system.css` (设计 token CSS 变量)
- 写 `app.js` (全局登录检查 + 导航 + fetch token 注入)

### Step 2: 首页 — AI 教研助手 (~30min)
- 按 `ai/code.html` 的布局精确还原
- 左：240px 侧边栏（Oxford Blue 背景）
- 右：聊天区（AI 消息气泡 + 快速提问标签 + 输入框）
- 连接 `POST /api/agent/chat/stream` (SSE)
- 底部状态栏

### Step 3: 功能页面 × 7 (~60min)
- 每个页面按原型 HTML 还原布局
- 接入对应的后端 API
- 共享侧边栏和顶部导航

### Step 4: 端到端验证 (~20min)
- 登录 → AI 对话 → 各功能页面切换
- 每个 API 返回正确数据

## 原型页面关键布局总结

**侧边栏 (240px, Oxford Blue #002045)**
- Logo + 产品名
- 导航项: AI对话, 答题卡识别, 考试管理, 题目管理, 障碍诊断, 学情报告, 学情面板, 学生管理
- 底部: 用户头像 + 退出

**AI 对话页 (首页)**
- 消息流 (flex-1, overflow-y-auto)
- 用户气泡: Oxford Blue bg, 白色文字, 右对齐
- AI 气泡: ai-glow bg, 1px teal border, 左对齐
- 工具卡片: 左侧 wood-accent 边框, 可折叠
- 快速提问栏: 6个 pill 按钮
- 输入框 + 发送按钮
- 底部状态栏 (agent-status)

**通用功能页面**
- 页面标题 (Manrope headline)
- 筛选区 (下拉框 + 搜索框 + 按钮)
- 数据区 (卡片列表 / 表格 / 图表)
- 模态框 (创建/导入/预览)
