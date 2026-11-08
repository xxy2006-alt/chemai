# Session 12 · 基础前端页面

## 产出物

- `frontend/` 目录，含教师端 6 个页面 + 学生端 4 个页面
- `frontend/index.html` — 教师 AI 教研助手主页（约 250 行），SSE 流式对话
- `frontend/pages/exam-v2.html` — 考试工作台（917 行），4 Tab 架构
- `frontend/pages/students.html` — 学生管理页
- `frontend/pages/teacher.html` — 班级学情面板
- `frontend/pages/diagnosis.html` — 障碍诊断页
- `frontend/pages/ocr.html` — 答题卡识别页
- `frontend/m/index.html` — 学生 AI 助教对话页
- `frontend/m/practice.html` — 学生练习页（约 300 行）
- `frontend/m/wrong.html` — 学生错题本（约 180 行，UI 上叫"待复习"）
- `frontend/m/report.html` — 学生个人中心（约 180 行）
- `frontend/m/app.js` — 学生端共享模块（约 130 行，4 个导出函数）
- `frontend/login.html` — 教师登录页
- `frontend/m/login.html` — 学生专用登录页（移动端优化）
- 完整的后端路由（`app/main.py`）支持以上所有页面

## 前置条件

- Session 11 完成的 `chemai-backend/` 目录完整可用
- `app/main.py` 已有基础路由
- `app/services/llm_service.py` 已封装 DeepSeek API
- `app/models/database.py` 已有 users/students/questions 等表
- `requirements.txt` 已安装所有依赖

## 项目背景（给学生的概述）

ChemAI 的用户是两类人：教师用 PC，学生用手机。这意味着你需要写两套前端——一套宽屏桌面端（教师），一套移动端（学生）。

但如果你打开任何一个现代前端项目，你会发现它们用 React / Vue CLI / Webpack / Tailwind——构建链加起来比业务代码还长。ChemAI 不做这个。原因很简单：这是一个给 5 个教师 + 200 个学生用的项目，不是给百万用户用的产品。

所以我们选了一条很少人走的路：**原生 HTML + Vue 3 CDN**。所有代码在一个 HTML 文件里，无需构建，无需打包，右键用浏览器打开就能看。全前端代码加起来只有约 1300 行。如果用 React，同样的功能至少 3000 行起步——光是 `create-react-app` 初始脚手架就 2000 行。

这节课你将在 Claude Code 的帮助下，一行行写出教师端 6 页面 + 学生端 4 页面 + 登录系统 + 共享模块。每个页面都有完整的提示词，你复制粘贴就能生成。

---

## 操作步骤

### 步骤 1：搭建教师端主页 index.html（AI 教研助手）

**目标**：创建教师登录后的主页面，包含侧边栏导航 + SSE 流式对话区

**提示词**（复制到 Claude Code）：

```
请根据以下设计规范创建 frontend/index.html：

【配色系统】
- 主背景: #f7f4ed (暖羊皮纸)
- 主色: #b43c28 (刚果红，来自实验室试剂瓶标签的颜色联想)
- 文字: #1a1a1a (墨色)
- 辅色: #2c6e49 (甲基绿)
- 字体: Cormorant Garamond (衬线标题) + PingFang SC (中文正文)

【为什么是这个配色】
不用纯白背景（#ffffff）——教师反馈"太白像考试卷，看久了累"。
不用蓝色作为主色——教师原话："化学实验室里没有蓝色的试剂瓶"。
红色来自实验室试剂瓶标签的颜色联想，更符合化学主题。

【页面结构】
1. 左侧边栏（240px宽）：
   - 顶部：ChemAI Logo 和产品名
   - 中间：5 个导航项（AI助手 / 考试工作台 / 学生管理 / 学情面板 / 诊断中心），每个34x34px图标，hover 显示 Tooltip
   - 底部：用户信息（头像 + 姓名 + 角色）+ 退出登录按钮
   - 背景色略深于主背景（#efe8d5）

2. 右侧主内容区：
   - 顶部标题栏：当前页面名称
   - 中间对话区：消息列表，AI 消息用左侧气泡（背景 #e8e0d0），用户消息用右侧气泡（背景 #b43c28 白色文字）
   - 底部输入区：多行文本输入框 + 发送按钮

【SSE 流式对话】
对话通过 EventSource 连接到 /api/agent/chat/stream，使用 SSE（Server-Sent Events）。
需要处理以下事件类型：
- token：追加到当前 AI 消息
- tool_call：显示工具调用指示器
- tool_result：显示工具调用结果
- component：渲染内联面板（如出题工作台）
- route：页面跳转
- [DONE]：流结束，关闭连接

【侧边栏权限过滤】
根据当前用户的 role 过滤导航项：
- 教师：显示全部 5 项
- 学生：只显示 AI助手
- admin：显示全部 + 学校管理（隐藏项，debug 时显示）

请完整实现这个文件，所有 CSS 内联在 <style> 标签中，所有 JS 内联在 <script> 标签中。
不要使用任何外部 CSS 框架（Bootstrap/Tailwind 等）。
```

**验证**：
- [ ] `frontend/index.html` 文件存在，约 250 行
- [ ] 配色为暖羊皮纸 #f7f4ed + 刚果红 #b43c28
- [ ] 侧边栏 240px 宽，5 个导航项带图标
- [ ] 对话区支持气泡样式，带输入框和发送按钮
- [ ] 浏览器打开 `http://127.0.0.1:8001/` 能看到完整页面

---

### 步骤 2：创建后端静态文件路由

**目标**：让 FastAPI 能 serve 所有前端 HTML 文件

**提示词**（复制到 Claude Code）：

```
修改 app/main.py，添加以下路由来 serve 前端文件：

1. @app.get("/") → 返回 frontend/index.html（教师主页）
2. @app.get("/login.html") → 返回 frontend/login.html
3. @app.get("/pages/{name}") → 返回 frontend/pages/{name}.html
4. @app.get("/m/{name}") → 返回 frontend/m/{name}.html（学生端）
5. @app.get("/m") → RedirectResponse("/m/index.html")

实现方式：
- 用 from pathlib import Path
- frontend_dir = Path(__file__).parent.parent / "frontend"
- 用 FileResponse 返回文件
- 如果文件不存在，返回 404

同时确保：
- 之前的 API 路由（/api/agent/chat/stream 等）不受影响
- 静态文件路由放在 API 路由之后定义（避免路径冲突）

测试：启动服务器后，浏览器访问 http://127.0.0.1:8001/ 应该看到 index.html 页面。
```

**验证**：
- [ ] `python chemai.py` 启动后，浏览器访问首页能看到 index.html
- [ ] 访问 `http://127.0.0.1:8001/pages/exam-v2.html` 返回 404（还没创建）
- [ ] API 路由 `/api/` 不受影响

---

### 步骤 3：创建教师登录页

**目标**：创建教师和学生公用的登录页面

**提示词**（复制到 Claude Code）：

```
创建 frontend/login.html，教师登录页面：

【设计规格】
- 居中卡片布局（max-width: 400px）
- 背景色 #f7f4ed
- 卡片白色背景，阴影，圆角 12px
- ChemAI Logo + 标题在顶部

【表单字段】
- 用户名（学号/工号）输入框
- 密码输入框
- 角色选择器：教师 / 学生（两个大按钮，不选默认教师）

【登录逻辑】
- 提交调用 POST /api/auth/login
- 请求体：{username, password, role}
- 成功后：sessionStorage 存储用户信息，根据 role 跳转
  - 教师 → /index.html（或 /）
  - 学生 → /m/index.html
- 失败：显示红色错误提示（不显示具体 HTTP 状态码，只显示"用户名或密码错误"）

【学生专用登录入口】
同时创建 frontend/m/login.html（学生端专用，移动端优化）：
- 不显示角色选择器（默认角色为学生）
- 学号 + 密码即可
- 底部有"教师登录"链接跳回 /login.html
- 移动端适配：最大宽度 480px 居中，输入框纵向排列

两个文件都用纯 HTML + 内联 CSS + 内联 JS 实现。
```

**验证**：
- [ ] `frontend/login.html` 存在，角色选择器可用
- [ ] `frontend/m/login.html` 存在，无角色选择器
- [ ] 浏览器访问 `http://127.0.0.1:8001/login.html` 可看到教师登录页
- [ ] 浏览器访问 `http://127.0.0.1:8001/m/login.html` 可看到学生登录页

---

### 步骤 4：创建学生端共享模块 app.js

**目标**：创建学生端 4 页共享的 JS 模块

**提示词**（复制到 Claude Code）：

```
创建 frontend/m/app.js（约 130 行），导出四个全局函数供学生端 4 个页面使用：

【函数 1】getUser()
function getUser() {
  // 从 sessionStorage 读取用户对象
  // 如果不存在，返回 null（不自动跳转，让调用方决定）
}

【函数 2】requireAuth()
function requireAuth() {
  // 检查登录态
  // 如果 getUser() 返回 null，跳转到 /m/login.html
  // 在页面 <head> 最早的位置调用
}

【函数 3】api(url, opts)
function api(url, opts) {
  // fetch 封装，自动注入认证头
  // opts = { method, body, headers }
  // 自动注入：Authorization: Bearer <token>（从 sessionStorage 读取）
  // 自动注入：Content-Type: application/json（如果 method 不是 GET）
  // 如果响应 401 → 跳转登录页
  // 返回 response（不自动 parse JSON，让调用方决定）
}

【函数 4】renderTabBar()
function renderTabBar() {
  // 纯 JS 生成底部 4 Tab 导航栏
  // Tab 列表：AI助教 / 练习 / 错题 / 我的（名称用"待复习"而非"错题"）
  // 每个 Tab 用 Material Icons + 文字
  // 当前页面高亮（根据 window.location.pathname 判断）
  // 点击切换到对应页面
  // Tab 栏高度 50px，固定在底部
  // 安全区适配：padding-bottom: env(safe-area-inset-bottom)
  // 不使用 Emoji——教师端设计评审认为 Emoji"太像大众消费 App，不像教育工具"
  // 注入到 body 末尾（document.body.appendChild）
}

【函数 5】renderHeader()
function renderHeader() {
  // 纯 JS 生成顶部标题栏
  // 标题根据当前页面路径动态设置：
  //   /m/index.html → "AI助教"
  //   /m/practice.html → "练习"
  //   /m/wrong.html → "待复习"
  //   /m/report.html → "我的"
  // 注入到 body 最前面（document.body.prepend）
  // 高度 44px，白色背景，底部细线分隔
}

【设计理由】
不做 SPA：app.js 130 行 + 每个页面平均 200 行 = 总前端代码约 1300 行。
如果用 React + Redux + React Router，同样的功能至少 3000 行起步——create-react-app 空项目就 2000 行。
4 个页面之间没有共享状态——不需要 Redux，原生 JS 完全够用。
```

**验证**：
- [ ] `frontend/m/app.js` 存在，约 130 行
- [ ] 包含 getUser、requireAuth、api、renderTabBar、renderHeader 五个函数
- [ ] 错题 Tab 在 UI 上显示为"待复习"

---

### 步骤 5：创建学生端 4 个页面

**目标**：创建学生移动端全部 4 个页面

**提示词**（复制到 Claude Code）：

```
请根据以下规范创建学生端 4 个页面。所有页面都使用 frontend/m/app.js 中的共享函数。

【通用规范】
- 最大宽度 480px，居中（适配 iPhone 15 Pro 的 393px 逻辑宽度 + 边距）
- 底部 padding-bottom 留出 Tab 栏空间（50px + 安全区）
- 页面顶部调用 renderHeader()，底部调用 renderTabBar()
- 所有 CSS 内联，不使用外部框架

---

【页面 1】frontend/m/index.html（AI 助教对话，约 200 行）
- 跟教师端 index.html 共享同一个 SSE 端点 /api/agent/chat/stream
- 区别仅在于请求体：body: JSON.stringify({ persona: 'student', message: t, provider: 'deepseek', conversation_id: cid })
- 对话区：AI 消息左侧气泡（灰底），用户消息右侧气泡（#b43c28 红底白字）
- 输入框固定在底部，上面留白用于消息滚动
- 初始化时加载历史对话（GET /api/conversation/list）
- 支持 SSE 事件：token / tool_call / tool_result / component / [DONE]
- 不显示排名、不显示班级信息——只显示 AI 对话内容

---

【页面 2】frontend/m/practice.html（练习，约 300 行）
- 三个视图：「任务列表」「做题中」「结果」
- 状态管理：var state = {view:'list', tasks:[], quiz:[], qIdx:0, answers:{}, practiceId:''}
- 三个 API 串联流程：
  1. GET /api/practice/tasks → 显示任务列表（标题 + 题目数 + 难度 + 创建时间）
  2. 点击任务 → GET /api/practice/{id}?student_id=xxx → 进入做题视图
  3. 提交答案 → POST /api/practice/submit → 进入结果视图（正确率 + 每题分析）
- 做题视图：选择题（4 个选项按钮）+ 判断题（对/错按钮）+ 填空题（输入框）
- 结果视图：显示正确率百分比（不显示排名），每题显示正确答案和解析
- 变式题按钮在 UI 上叫"做一组相似的"——不叫"重做"（种子教师建议："别让学生觉得自己很差"）

---

【页面 3】frontend/m/wrong.html（错题本，约 180 行）
- 标题在 UI 上不叫"错题本"，叫"待复习"（种子教师建议）
- 数据来源：GET /api/wrong-book?student_id=xxx
- 列表展示：每题显示题干（renderChem 渲染）+ 做错次数 + 上次做错时间
- 展开/折叠：点击题目展开，显示正确答案 + 解析 + "做一组相似的"按钮
- 展开状态用 expanded 变量（布尔值，每个题目一个）控制
- 空状态：当没有错题时，显示"暂无待复习题目" + 鼓励文案

---

【页面 4】frontend/m/report.html（我的，约 180 行）
- 个人信息卡片：学生姓名 + 学号 + 班级（从 sessionStorage 读取）
- 统计卡片：累计练习次数 / 正确率 / 待复习题数（3 个卡片横向排列）
- 菜单列表：练习历史 / 我的成绩 / 关于 ChemAI
- 底部：退出登录按钮（红色文字），点击清除 sessionStorage 并跳转 /m/login.html
- 退出登录按钮放在页面底部——不在顶部栏、不在侧边栏——学生不容易误触

每个页面独立的 HTML 文件，完整可独立运行。
```

**验证**：
- [ ] 4 个文件 `frontend/m/index.html`、`practice.html`、`wrong.html`、`report.html` 都存在
- [ ] 每个页面都调用了 `renderHeader()` 和 `renderTabBar()`
- [ ] practice.html 的状态管理使用 `var state = {view, tasks, quiz, qIdx, answers, practiceId}`
- [ ] wrong.html 的 UI 标题显示为"待复习"，变式题按钮显示为"做一组相似的"
- [ ] report.html 的退出登录按钮在底部，统计卡片 3 列排列
- [ ] 没有页面展示排名或满分数据

---

### 步骤 6：创建教师端 students.html 和 teacher.html

**目标**：创建学生管理页和学情面板

**提示词**（复制到 Claude Code）：

```
创建两个教师端页面：

【页面 1】frontend/pages/students.html（学生管理）
- 教师端查看和管理学生列表
- 搜索框：按姓名/学号搜索
- 表格列：姓名 / 学号 / 班级 / 练习进度 / 最近练习时间 / 障碍类型
- 数据来源：GET /api/students?class_id=xxx
- 点击学生行：展开显示障碍详情（barrier_type JSON 字段解析显示）
- 添加学生按钮：弹窗输入姓名、学号、班级 → POST /api/students
- 批量导入：上传 CSV/Excel → POST /api/students/import

【页面 2】frontend/pages/teacher.html（班级学情面板）
- 教师端查看班级学情
- 顶部：班级选择器（下拉框）
- 中间：成绩分布图表（用 Canvas 画柱状图，不用图表库）
- 下方：知识点掌握情况热力图（用 Canvas 画矩形格，颜色从红到绿）
- 最下方：最近 5 次考试的班级平均分趋势线
- 数据来源：GET /api/analytics/class/{class_id}
- Canvas 图表纯手写，不导入 Chart.js 等库——保持前端体积 <50KB

两个文件都用纯 HTML + 内联 CSS + 内联 JS 实现，风格与 index.html 一致。
使用相同的配色系统（#f7f4ed 背景 + #b43c28 主色）。
```

**验证**：
- [ ] `frontend/pages/students.html` 存在，含搜索框 + 表格 + 添加按钮
- [ ] `frontend/pages/teacher.html` 存在，含 Canvas 柱状图 + 热力图 + 趋势线
- [ ] 配色与 index.html 一致

---

### 步骤 7：创建教师端 diagnosis.html 和 ocr.html

**目标**：创建障碍诊断页和答题卡识别页

**提示词**（复制到 Claude Code）：

```
创建两个教师端页面：

【页面 1】frontend/pages/diagnosis.html（障碍诊断）
- 教师端查看学生的知识障碍诊断结果
- 两步骤流程：
  第一步：选择班级 → 选择考试 → 显示学生列表（带障碍标签）
  第二步：点击某个学生 → 展开详细诊断（知识点薄弱项 + 建议练习方向）
- 障碍标签用彩色徽章显示：
  - "配平障碍"：红色
  - "概念混淆"：橙色
  - "计算错误"：黄色
  - "记忆薄弱"：蓝色
  - "无显著障碍"：绿色
- 数据来源：
  - 班级/考试列表：GET /api/classes + GET /api/exams
  - 诊断数据：GET /api/diagnosis/{exam_id}?student_id=xxx
- 每个学生的诊断结果包含 barrier_type（JSON 字段）和推荐练习题目

【页面 2】frontend/pages/ocr.html（答题卡识别）
- 教师端上传试卷 PDF 或图片 → OCR 识别 → 展示结果
- 上传区：拖拽或点击上传，支持 PDF/JPG/PNG
- 上传后：POST /api/ocr/upload → 返回 job_id
- 轮询结果：GET /api/ocr/status/{job_id}（每 2s 一次，最多 10 次）
- 结果显示：识别出的题目列表，每题显示题目图片 + 识别文本
- 底部操作：全部保存到题库 / 逐题编辑后保存
- 上传中显示进度条（CSS 动画），超时显示"识别时间较长，请稍候..."
- 错误处理：网络错误显示"上传失败，请检查网络"——不显示 HTTP 状态码

两个文件都用纯 HTML + 内联 CSS + 内联 JS 实现，风格与 index.html 一致。
```

**验证**：
- [ ] `frontend/pages/diagnosis.html` 存在，含两步骤流程 + 障碍彩色徽章
- [ ] `frontend/pages/ocr.html` 存在，含上传区 + 轮询逻辑 + 结果展示
- [ ] ocr.html 的错误提示不显示具体 HTTP 状态码

---

### 步骤 8：创建考试工作台 exam-v2.html（核心页面）

**目标**：创建项目中最复杂的单页面（917 行），包含 4 个 Tab

**提示词**（复制到 Claude Code）：

```
创建 frontend/pages/exam-v2.html——ChemAI 项目最复杂的单页面。

【技术选型】
使用 Vue 3 CDN（<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>）
不使用 Vue CLI / Vite / 构建工具。所有逻辑在一个 HTML 文件内完成。
为什么不用 React：917 行用 Vue 3 CDN 就能写完，React 需要 JSX 编译、Babel、Webpack，构建链比业务代码长。

【数据模型】（行 481）
在 Vue app 的 data() 中定义：
```
modal: {
  show: false,
  fading: false,
  title: '',
  message: '',
  type: 'confirm',
  _manageTab: 'paper',       // 考试管理的子 Tab：'paper' | 'questions'
  _vbStep: 'dir',             // 变种题浏览器的步骤：'dir' | 'browse' | 'select'
  _vbPapers: [],              // 变种题浏览器的试卷列表
  _vbQuestions: [],           // 变种题浏览器的题目列表
  previewLoading: false,
  previewQuestions: null,     // 考试预览题目
}
sourceMode: 'ai',  // 当前 Tab：'ai' | 'bank' | 'history' | 'exam'
```

【四个 Tab 的实现】
用 v-show 切换，不是 Vue Router——四个 Tab 的数据一次性加载，不需要懒加载。

Tab 1 — 出题工作台（sourceMode = 'ai'）：
- 输入区：知识点输入框 + 题型选择（选择题/填空题/判断题/简答题）+ 难度选择（1-5）
- AI 出题按钮 → 调 aiGenerate() → POST /api/question/generate
- 生成结果展示：renderChem() 渲染化学式
- 逐题保存按钮 → saveOne(i) → POST /api/question/save
- 手动录入按钮 → 打开表单（题干 + 答案 + 解析 + 知识点 + 难度）
- 变种题入口 → 打开变种题浏览器

Tab 2 — 题库管理（sourceMode = 'bank'）：
- 题库列表：GET /api/question/bank?page=1&size=20
- 每个题目显示：题干（renderChem 渲染）+ 答案 + 知识点 + 难度
- 操作：编辑（打开编辑表单）/ 删除（确认弹窗）/ 查看详情（展开）
- 搜索：按知识点/题型/难度筛选
- 如果题库超过 1000 题需要分页加载

Tab 3 — 历史真题库（sourceMode = 'history'）：
- 真题列表：按年份（2020-2025）+ 区域筛选
- 图渲染：<img :src="'/static/figures/' + encodeURIComponent(q.region||'') + '/' + q.year + '/' + q.page_image">
- 点击查看题目详情（展开 renderChem 渲染的内容）
- 多选复选框 → "加入考试"按钮 → addHistToExam() → POST /api/exam/{eid}/questions
- 数据来源：GET /api/questions/history?year=2024&region=hunan

Tab 4 — 考试列表（sourceMode = 'exam'）：
- 已创建的考试列表：GET /api/exam/list
- 创建考试按钮 → 模态框（输入考试名称 + 选择班级）→ POST /api/exam/create
- 每个考试可操作：
  - "管理"→ manageExam() → 展开子面板（题目列表 + 添加 + 删除 + 预览）
  - "预览"→ 显示完整试卷（移动端样式，max-width 480px）
  - "发布"→ POST /api/exam/{id}/publish → 锁定题目不可修改
- 关键约束：发布后不可修改（question_stats.published = true 时锁定按钮）
  种子教师原话："万一学生已经看到了，我改了题目就乱套了"
- 发布时显示确认弹窗："发布后题目不可修改，确定发布？"

【化学式渲染函数 renderChem】在 methods 中实现：
```javascript
renderChem: function(t) {
  // 1. 保护 LaTeX 块（替换成占位符）
  //    $$...$$ → 占位符 1
  //    $...$   → 占位符 2
  // 2. Markdown → HTML（用 marked.parse）
  // 3. 恢复 LaTeX 块 → KaTeX 渲染（katex.renderToString）
}
```
需要引入 CDN：
- KaTeX CSS: https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css
- KaTeX JS: https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js
- Marked: https://cdn.jsdelivr.net/npm/marked/marked.min.js

【完整文件】
所有 CSS 内联在 <style> 中，所有 JS 在 <script> 中（Vue app）。
不要拆分成多个文件——这是一个完整的单文件组件。
加上上面要求的 4 个 Tab 的所有功能。
```

**验证**：
- [ ] `frontend/pages/exam-v2.html` 存在，约 900+ 行
- [ ] 4 个 Tab（ai/bank/history/exam）全部可通过按钮切换
- [ ] Vue 3 data 中包含 modal 和 sourceMode 定义
- [ ] renderChem 函数存在，用 KaTeX + marked 渲染
- [ ] CDN 引入正确：Vue 3、KaTeX、marked

---

### 步骤 9：统一前端导航和页面间跳转

**目标**：让教师端 6 页面之间的导航正常工作

**提示词**（复制到 Claude Code）：

```
修改 frontend/index.html，完善教师端侧边栏导航逻辑：

1. 点击侧边栏导航项时：
   - "AI助手" → 已经在 index.html，不需要跳转，高亮当前项
   - "考试工作台" → 跳转到 /pages/exam-v2.html
   - "学生管理" → 跳转到 /pages/students.html
   - "学情面板" → 跳转到 /pages/teacher.html
   - "诊断中心" → 跳转到 /pages/diagnosis.html

2. 在其他 5 个页面（exam-v2/students/teacher/diagnosis/ocr）中：
   - 每个页面顶部有一个 44px 的导航条
   - 导航条左侧：返回主页按钮（← 回到 AI 助手）
   - 导航条中间：当前页面标题
   - 导航条背景：#f7f4ed，底部细线分隔
   - 点击"回到 AI 助手"→ window.location.href = '/'

3. 学生端 4 页面：
   - 底部 Tab 栏（已在 app.js 的 renderTabBar() 中实现）负责页面间切换
   - 学生端不暴露教师端页面的导航入口

4. 内联面板 vs 页面跳转的决策原则：
   - 出题工作台：内联面板（高频操作，在聊天中直接完成，不需要切换页面）
   - 诊断结果：内联面板（紧跟出题流程，不需要切换上下文）
   - 学生管理：页面跳转（低频操作，需要完整表格）
   - 学情面板：页面跳转（需要大屏图表）
   - 答题卡识别：页面跳转（需要文件上传 UI）

确保所有页面间的跳转链接正确，不会出现 404。
```

**验证**：
- [ ] index.html 侧边栏点击可跳转到 exam-v2/students/teacher/diagnosis
- [ ] 每个子页面顶部有"← 回到 AI 助手"导航条
- [ ] 学生端底部 Tab 栏 4 个 Tab 可正常切换

---

### 步骤 10：添加错误处理和优化用户体验

**目标**：为所有前端的错误处理添加恰当的用户提示

**提示词**（复制到 Claude Code）：

```
为所有前端页面添加以下错误处理逻辑：

1. 化学式渲染失败：
   - 不要显示红色错误信息
   - 显示原始 LaTeX 文本（用户自己能看懂，$H_2SO_4$ 虽然不美观但能识别）
   - 实现：renderChem 函数用 try-catch 包裹，catch 中返回原始文本

2. 网络错误：
   - 不显示具体 HTTP 状态码（用户不需要知道 500 vs 503）
   - 统一显示"发送失败，请检查网络"
   - 实现：在 fetch/EventSource 的 error 回调中显示统一消息

3. AI 超时：
   - SSE 流如果 30 秒内没有任何事件，显示"AI 思考时间较长，请稍候..."
   - 不关闭连接（可能还在处理），但给用户反馈
   - 实现：setTimeout 30s，如果被 token 事件重置计时器则取消

4. 对话持久化失败：
   - 静默处理
   - 对话记录丢失是 bug，但不应打断用户当前的使用
   - 实现：在保存对话的 API 调用中 catch 但不 alert

5. 登录态过期：
   - API 返回 401 时自动跳转登录页
   - 跳转前保留当前 URL 到 sessionStorage（登录后跳回）
   - 实现：在 app.js 的 api() 函数中统一处理

6. 删除确认：
   - 题库删除 / 考试删除 / 学生删除 → 都需要二次确认弹窗
   - 弹窗文字："确定删除 [名称] 吗？此操作不可撤销。"
   - 确认按钮红色，取消按钮灰色

请修改所有受影响的文件（index.html、exam-v2.html、students.html、app.js、m/login.html 等）。
```

**验证**：
- [ ] renderChem 有 try-catch 保护
- [ ] 网络错误显示统一消息，不显示状态码
- [ ] AI 超时有 30s 提示
- [ ] 删除操作有二次确认弹窗
- [ ] 401 响应自动跳转登录页

---

## 发生了什么（教师参考）

### 1. 设计系统的三次迭代：这不是设计师做的决定

ChemAI 的视觉系统不是一次做对的。经历了三次完整迭代，每次都有用户反馈支撑：

**v1（2026 年 1 月）**：
Academic Catalyst 设计系统——Oxford Blue `#002045` + 羊皮纸色 + glassmorphism AI 气泡。参考了学术界期刊的配色风格，视觉上很"学术"。

**v2（2 月，commit 824c2c6）**：
前端完全重做，"完美还原" Academic Catalyst，删除了 177+ 旧文件。这个版本已经接近最终形态，但配色还是蓝色的。

**v3（3 月，commit 8bba4e9）**：
5 页面精简架构 + 配色切换到暖羊皮纸 `#f7f4ed` + 刚果红 `#b43c28`。

**切换原因——来自种子教师的原话**：
"蓝色太冷、像银行系统，不像教育工具。"

开发者追问："那你觉得什么颜色像化学？"

教师想了想："实验室试剂瓶的标签……很多是红色的。"

于是主色从牛津蓝变成了刚果红——一个来自化学实验室的颜色联想。这不是设计师拍板的，是用户一句话引发的。

**补充设计细节**：
- 不用纯白背景（#ffffff）——教师反馈"太白像考试卷，看久了累"
- 不用蓝色作为主色——"化学实验室里没有蓝色的试剂瓶"（虽然实际上有硫酸铜，但用户的感觉胜过事实）
- 侧边栏 240px——刚好放下 5 个导航项 + 用户信息，多 1px 浪费空间，少 1px 文字被截断

每个版本都有文档记录：
- 1 月：`REDESIGN.md`（竞品分析 + Academic Catalyst 设计系统）
- 2 月：commit `824c2c6`
- 3 月：commit `8bba4e9`

### 2. 教师端导航的三次演进

**v1（8 项导航）**：
AI助手 / 答题卡 / 考试工作台 / 题库 / 诊断 / 学生管理 / 学情面板 / 设置

种子用户反馈："太多了，常用的就前三个。"

**v2（5 项 + 图标）**：
用心理学风格的图标替代文字，导航项精简为 5 个：心理学 / 扫描 / 作业 / 健康 / 人群。

种子用户反馈："图标不错，但考试工作台为什么不叫考试工作台？"

**v3（当前：紧凑图标 + Tooltip）**：
在 `app.js:56-62` 实现了 34x34px 的紧凑图标导航，hover 显示 Tooltip。移动端测试发现：教师用 iPad 访问时图标太小 → 加了 `min-width: 34px`。

关键教训：**用户不关心你的设计理念，他们关心按钮上写了什么字**。导航的目的不是好看，是快速找到功能。

### 3. 为什么不用 React：1300 行 vs 3000+ 行

这不是技术选型的偏见，是实际数字：

| 方案 | 代码量 | 构建链 | 维护成本 |
|------|--------|--------|---------|
| 原生 HTML + Vue 3 CDN | ~1300 行 | 零构建 | 小学生能改 |
| React + CRA | ~3000+ 行 | webpack/babel | 需要 Node.js 环境 |
| React + Vite | ~2500+ 行 | vite | 需要 Node.js 环境 |
| Vue CLI 项目 | ~2800+ 行 | webpack | 需要 Node.js 环境 |

**关键因素**：
- `create-react-app` 空项目的脚手架代码就有 2000 行
- 4 个学生页面之间没有共享状态——不需要 Redux
- 教师端只有一个复杂页面（exam-v2.html，917 行），其余都在 300 行以内
- 用户量 <5 教师 + <200 学生，没有并发问题，不需要做 SPA 的懒加载和路由
- 6 个教师页面之间独立，不需要前端路由

### 4. 化学式渲染的坑：marked v12 API 废弃

这是 ChemAI 开发中最典型的一次"第三方库隐式依赖"踩坑。

**v1（不做渲染）**：
MinerU 导入的 Markdown 包含 `$\mathrm{H_2SO_4}$` 这样的 LaTeX，前端直接显示为原始字符串。学生和教师都能看懂，但确实不好看。

**v2（marked + KaTeX）**：
用 CDN 加载 KaTeX + marked，写了一个 `renderChem()` 函数。逻辑是先过 marked 把 Markdown 转 HTML，再过 KaTeX 把 LaTeX 渲染成数学公式。

但是——marked 库在 v12 版本废弃了 `marked.setOptions()` API。没有 lockfile 的 CDN 引用自动升级到了 v12，整段渲染逻辑崩溃，回退到纯文本显示。

**v3（KaTeX 保护方案——最终方案）**：
不再信任 marked 的 API 稳定性。改用一个更保守的策略：

```javascript
renderChem: function(t) {
  // 1. 先手动保护 LaTeX 块（用正则提取 $$...$$ 和 $...$，替换成占位符）
  // 2. 用 marked 处理纯 Markdown 部分 → HTML
  // 3. 恢复 LaTeX 占位符 → 逐个调用 katex.renderToString() 渲染
}
```

这样做的好处：即使 marked 未来又改 API，LaTeX 部分不受影响——它是由独立的 KaTeX 处理的。KaTeX 是一个纯数学渲染库，API 比 marked 稳定得多。

**核心教训**：CDN 引用的第三方库没有版本锁定（没有 package-lock.json），API 变更会导致静默崩溃。对前端隐式依赖要加保护层。

### 5. 内联面板 vs 页面跳转的决策

这不是随便拍的——每个交互方式都有具体的决策理由：

| 操作 | 方式 | 理由 |
|------|------|------|
| 出题 | 内联面板 | 高频操作，教师每天出 5-10 道题，每次跳转页面太慢 |
| 诊断 | 内联面板 | 紧跟出题流程，出完题直接看学生会不会做 |
| 学生管理 | 页面跳转 | 低频操作（每月 1-2 次），需要完整表格 |
| 学情面板 | 页面跳转 | 需要大屏图表，内联面板放不下热力图 |
| 答题卡识别 | 页面跳转 | 需要文件上传 UI + 进度条，独立页面更合适 |

内联面板的技术实现：工具返回 `_component` 指令 → SSE adapter 发出 `component` 事件 → 前端 switch 分支渲染对应组件。这是整个 Agent→前端 数据流的关键环节，我们将在下节课深入讲解。

### 6. 前端性能的实际数字

这些数字不是估算的，是在真实环境（Windows 笔记本 + Chrome）下测的：

| 指标 | 数值 | 说明 |
|------|------|------|
| 首页加载（首次） | ~500ms | 含 CDN 脚本下载（Vue 3/KaTeX/marked），这些 CDN 文件会被浏览器缓存 |
| 首页加载（缓存后） | ~50ms | CDN 脚本命中浏览器缓存，只加载 HTML 本体 |
| 对话延迟（首 token） | ~2s | DeepSeek API 网络延迟 + 推理延迟 |
| 对话延迟（后续 token） | ~50ms/token | SSE 流式，tokens 逐个返回 |
| 考试工作台加载 | ~300ms | Vue 3 内联编译 + 数据拉取 |
| 学生练习页加载 | ~200ms | 纯原生 JS，无框架开销 |
| 前端 JS 总体积 | <50KB | 不含 CDN 依赖（Vue/KaTeX/marked） |

**为什么不需要做更多优化**：用户量 <5 个教师 + <200 个学生。没有并发问题。没有 CDN 崩溃问题（unpkg 和 jsdelivr 的可用性比我们的服务器高得多）。没有 SEO 问题（所有页面都是登录后可见）。

### 7. 学生端的"温柔设计"

学生端的设计有大量"反常规"的细节——不是开发者想出来的，是种子教师多次反馈的结果：

**不显示排名**：
学生端只显示正确率和知识点分析，不显示班级排名。教师原话："学生直接看到排名会崩溃，要先过我这一关。"

**错题本叫"待复习"**：
UI 上的标题是"待复习"而非"错题本"。这不是好听而已——教师说："别让学生觉得自己很差。有些题目不是做错了，是对知识点的理解需要加深。"

**变式题按钮叫"做一组相似的"**：
不叫"重做"，不叫"再练"。要给学生一种"我在拓展"的感觉，而不是"我没做对所以要重新来"。

**退出登录在"我的"页底部**：
不在侧边栏、不在顶部栏。学生不容易误触——移动端这么小的屏幕，按钮放哪里都可能被指头点到。

**移动端适配的具体数据**：
- 最大宽度 480px（iPhone 15 Pro 的 393px 逻辑宽度 + 边距）
- Tab 栏高度 50px（拇指舒适区，太矮点不中，太高占屏幕）
- 输入框在键盘弹出时自动上移（`scrollIntoView`）
- 底部安全区适配（`env(safe-area-inset-bottom)`，iPhone X 及以后的机型）
- 不使用 Emoji（教师端设计评审意见："太像大众消费 App，不像教育工具"）

### 8. exam-v2.html 为什么是 917 行

这是整个项目最复杂的单文件。虽然 CLUAUE.md 说"不喜欢 200 行以上"，但 917 行是经过评估后的最优解：

1. **4 个 Tab 共享 Vue 实例**：如果拆成 4 个 HTML 文件，每个文件都要独立的 Vue 实例、独立的 renderChem 函数、独立的样式——代码总量会翻倍而非减少。

2. **没有构建工具**：用 Vue SFC（单文件组件）需要编译——跟"零构建"的哲学矛盾。既然不构建，那就只有一个 HTML 文件。

3. **已知问题**（教师需要了解，学生不需要主动提）：
   - `renderChem` 和 `agent.js` 中的 `renderChemistry` 是两份独立实现，逻辑重复（如果时间充裕应该合并）
   - 变种题浏览器的逻辑（约 200 行）可以考虑拆到独立文件
   - 4 个 Tab 的数据一次性加载——如果题库超过 1000 题，需要加懒加载

### 9. 登录系统的权限设计

4 个角色（admin / 学科组长 / 教师 / 学生）的权限矩阵：

| 功能 | admin | 学科组长 | 教师 | 学生 |
|------|-------|---------|------|------|
| 出题/题库 | Yes | Yes | Yes | No |
| 考试管理 | Yes | Yes | Yes | No |
| 学生管理 | Yes | Yes | No | No |
| 障碍诊断 | Yes | Yes | Yes | No |
| AI 对话 | Yes | Yes | Yes | Yes |
| 练习/错题 | No | No | No | Yes |
| 学校管理 | Yes | No | No | No |

权限在前端侧边栏渲染时过滤（`app.js:45-62`），后端中间件验证（`app/main.py:57-78`）。前端过滤是 UI 层面的优化——避免显示用户无权访问的菜单项。后端中间件是真正的安全层——即使前端显示了不该显示的菜单，API 调用也会被拒绝。

### 10. 经常出现的问题

**Q：KaTeX 渲染中文时报错？**
A：KaTeX 不处理中文。确保 LaTeX 公式里的化学式用 `\mathrm{}` 包裹中文（如 `\mathrm{浓硫酸}`），或者中文不要放在 `$...$` 里面。

**Q：marked CDN 引用哪个版本？**
A：必须锁定版本号。不要用 `marked@latest`，用 `marked@12.0.0` 或更早的稳定版本。如果已经用了 latest 且崩溃了，降级到 `marked@4.3.0`（v12 之前最后一个稳定版）。

**Q：Vue 3 CDN 加载失败？**
A：如果 unpkg 被墙，改用 `https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js`。jsdelivr 在中国大陆有节点，访问速度更快。

**Q：学生端页面在手机上排版错乱？**
A：检查是否在 `<head>` 中添加了 `<meta name="viewport" content="width=device-width, initial-scale=1.0">`。这是移动端适配的第一行代码。

**Q：SSE 连接频繁断开？**
A：检查后端是否发送了心跳帧（每 15s 一个 `[PING]`）。如果用了 nginx 反向代理，确保配置了 `X-Accel-Buffering: no` 头——否则 nginx 会缓冲 SSE 导致前端收不到事件。

---

## 课后产出检查

学生应该同时具备：

- [ ] `frontend/` 目录完整，包含教师端 6 页面 + 学生端 4 页面
- [ ] 教师端主页 `http://127.0.0.1:8001/` 能正常加载（配色暖羊皮纸 + 刚果红）
- [ ] 登录页 `http://127.0.0.1:8001/login.html` 有角色选择器，学生登录页有底部"教师登录"链接
- [ ] `frontend/pages/exam-v2.html` 约 900+ 行，4 个 Tab 可切换，renderChem 函数可用
- [ ] 学生端 4 页面都能加载，底部 Tab 栏正常工作
- [ ] `frontend/m/app.js` 约 130 行，包含 getUser / requireAuth / api / renderTabBar / renderHeader
- [ ] 错题 UI 标题为"待复习"，变式题按钮为"做一组相似的"，不显示排名
- [ ] 删除操作有二次确认弹窗
- [ ] 网络错误不显示 HTTP 状态码

**下节课需要**：前端页面全部可用。Session 13 将实现 Agent 多智能体架构（LangGraph StateGraph），让 AI 能智能调度 6 个子专家。

---

## 补充内容 — 教师深度参考

### A. 设计迭代的时间线和关键 commit

| 日期 | 版本 | Commit | 变更 |
|------|------|--------|------|
| 2026-01 | v1 | （初始） | Academic Catalyst 蓝色系统 |
| 2026-02 | v2 | 824c2c6 | "完美还原" Academic Catalyst，删 177+ 旧文件 |
| 2026-03 | v3 | 8bba4e9 | 暖羊皮纸 + 刚果红，"前端重设计 — 5页面精简架构" |

### B. renderChem 三次迭代的技术细节

| 版本 | 方案 | 问题 | 根因 | 修复 |
|------|------|------|------|------|
| v1 | 纯文本 | LaTeX 源码直接显示 | 没有渲染步骤 | 不加修复，等待 KaTeX 方案 |
| v2 | marked + KaTeX 串联 | marked.setOptions() 崩溃 | marked v12 废弃 API | CDN 自动升级到 v12 |
| v3 | LaTeX 保护 + marked + KaTeX 恢复 | 无 | — | KaTeX 独立于 marked，不受 API 变更影响 |

### C. 教师端 6 页面代码行数明细

| 文件 | 行数 | 复杂度 |
|------|------|--------|
| `index.html` | ~250 | 中等：SSE + 侧边栏 + 对话 |
| `pages/exam-v2.html` | 917 | 极高：Vue 3 + 4 Tab + renderChem |
| `pages/students.html` | ~200 | 中低：表格 + 搜索 + CRUD |
| `pages/teacher.html` | ~250 | 中等：Canvas 图表绘制 |
| `pages/diagnosis.html` | ~200 | 中等：两步骤流程 + 徽章系统 |
| `pages/ocr.html` | ~250 | 中等：上传 + 轮询 + 结果展示 |

### D. 学生端 4 页面 + app.js 明细

| 文件 | 行数 | 技术要点 |
|------|------|---------|
| `m/index.html` | ~200 | SSE 流式对话，persona:'student' |
| `m/practice.html` | ~300 | 三视图状态管理，三 API 串联 |
| `m/wrong.html` | ~180 | 展开/折叠，UI 名称"待复习" |
| `m/report.html` | ~180 | 统计卡片 + 菜单 + 退出登录 |
| `m/app.js` | ~130 | 4 导出函数 + 认证 + Tab 栏 |
| **总计** | **~990** | **不含 CDN 依赖** |

### E. 教师端配色完整定义

```css
/* 从 frontend/index.html <style> 块提取的核心变量 */
主背景:  #f7f4ed  /* 暖羊皮纸，不放纯白 */
主色:    #b43c28  /* 刚果红，试剂瓶标签联想 */
文字:    #1a1a1a  /* 墨色 */
辅色:    #2c6e49  /* 甲基绿 */
侧边栏:  #efe8d5  /* 羊皮纸暗色 */
气泡AI:  #e8e0d0  /* 浅羊皮纸 */
卡片白:  #ffffff  /* 仅用于弹出卡片 */
边框:    #d4c9b5  /* 暖灰 */
错误:    #b43c28  /* 与主色相同 */
成功:    #2c6e49  /* 与辅色相同 */
```
