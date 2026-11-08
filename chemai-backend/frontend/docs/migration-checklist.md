# ChemAI 教师端迁移检查清单

> 每页迁移完成后逐项核对，与旧版（`legacy/` 与 `pages/`）功能等价。

## 全局基建（Phase 0）✅

- [x] React 18/19 + TypeScript + Vite 脚手架（`frontend/` 根目录）
- [x] 设计 tokens（方向 A 现代学术蓝）：`src/styles/tokens.css`
- [x] UI 组件库：Button / Card / Tag / Badge / Modal / Toast / Table / Tabs / StatCard / Skeleton / EmptyState / Field / EChart
- [x] 依赖本地化：katex / echarts / lucide-react 走 npm；index.html 无 CDN script
- [x] 字体：系统字体栈，无 Google Fonts 依赖
- [x] 类型检查 `npm run typecheck` 通过；构建 `npm run build` 通过；94 项测试通过（87 旧 + 7 新）
- [x] 旧页面兼容：`legacy/index.html`（旧对话工作台备份）、`pages/`、`js/`、`m/` 原样保留可访问
- [x] 桌面 exe 核实：PyInstaller + pywebview 6.2.1，无打包源码；假设加载本地服务 URL，前端重建即可生效（若内嵌打包需另行重建 exe，待确认）

## 素材资产（Phase 0.2）✅ 已接入（2026 用户提供 6 张，映射待确认）

- [x] 素材提示词文档：`docs/前端素材生成提示词文档.md`
- [x] 6 张设计 agent 素材已归类到 `src/assets/`，按以下假设映射（**待用户核对截图确认**）：
  | 源文件 | 角色 | 用途 |
  |--------|------|------|
  | Iqp_*.png | logo-mark | 侧边栏 / 登录页 / favicon（64px 派生） |
  | fldWb5*.png | ai-tutor | 对话 AI 头像 |
  | sP7BFC*.png | teacher-default | 教师默认头像（待接入学生详情等） |
  | EqvpiC*.png | empty-chat | 对话欢迎区插画 |
  | 3XItpb*.png | empty-class | 班级学情/诊断空状态插画 |
  | Rjihuz*.png | empty-students | 学生列表空状态插画 |
- [ ] 用户确认映射正确 / 指出需要调换的文件
- [ ] login-hero（登录页配图，P1）未生成——登录页当前用品牌面板 + 元素符号装饰（设计如此，无需配图也可）

## 页面迁移

### 对话工作台 /chat（Phase 1）✅ 代码完成，待评审

- [x] 页面更名为 **Agent 工作台**（导航 + 页内文案）
- [x] 布局修复：Agent 工作台独占视口高度（main overflow-hidden），消息列表内部滚动，**输入框钉死在视口底部**（实测滚动到顶/到底输入框 bottom 恒定 899/900），切换对话不再整页跳底（实测切换前后输入框 top 恒定）
- [x] **历史真题库回归修复**（用户反馈：弹窗 + 题目格式/图片）：
  - 点击试卷（如 2020 全国卷）→ **弹窗展示题目**（旧版 openVariantPaper 行为），含题号/知识点/缩略图/答案/作蓝本；不再页内展开
  - 弹窗布局：**置顶展示**（top 32px，原居中）+ **撑满容器**（宽 1144/1440，原 max-w-3xl 居中留大阴影区）
  - 题目内容统一走 `renderChemMD`（KaTeX 公式 + markdown 图片）→ 新增 `components/ChemMd.tsx` 共享组件，AI 气泡/题库/预览/内联面板全部复用
  - `chem-markdown.ts` 增加 markdown 图片语法 `![..](url)` 支持 + 题目内嵌 HTML 表格透传（旧版 marked 行为）
  - **全卷 LaTeX 垃圾清洗 `cleanLatex`**（OCR→LLM 格式化脏数据）：`\mathrm { X }` 带空格归一（727 处）、带空格下标（354 处）、`{ = }` 花括号运算符（22 处）、`\textcircled{N}`→圈号（14 处）、`<sup>﹏</sup>`（32 处）、`$_` 多余下标（6 处）、`\Omega/\Gamma/\Nu` OCR 误识、`\bf` 装饰标记（80 处）、`\ { \bf \Gamma }` 垃圾组、`\\(反斜杠空格)→~`（75 处，修复 `\\mathrm` 变逐字母 m a t h r m）、`\mathrm-` 缺组、`\mathrm^{2}` 错位、`\stackrel` 单参、数学段内多余空白（"7 5"→"75"）、"\%Z" 垃圾；规则 10 加负向后顾避免拆 `\mathrm{-}` 花括号
  - **变种题功能恢复**（用户反馈：内联面板与主工作台缺"真题作蓝本"）：新增共享 `VariantBrowserModal`（地区→年份→试卷→题目→选为蓝本），主工作台「选真题作蓝本」按钮 + 内联面板「选蓝本」按钮；生成走 variant_source_id；Agent 预填知识点缺失时补为已选（旧版行为）→ evals: `inline-panel.test.tsx`
  - **AI 出题反斜杠丢失修复**（用户反馈：`\rightleftharpoons` 变成 `ightleftharpoons`）：根因 = LLM 输出未转义 `\r`，`json.loads` 把 `\r` 当回车符。后端 `parse_llm_json`（转义未转义 LaTeX 反斜杠）应用到 3 处解析点（question.py×2、agent/tools/generation.py）；前端 `cleanLatex` 存量修复（CR+字母 → `\r`）；实测 API 返回 `$N_2 + 3H_2 \rightleftharpoons 2NH_3$` 反斜杠保留、无 CR；单元测试 5 项（test_llm_json.py）
  - **内容重复问题最终根因**（用户多次反馈"双版本/三版本"）：**KaTeX CSS 未加载**（重构时丢了旧 index.html 的 katex.min.css）→ KaTeX 的 MathML/annotation 层全部可见 → 每个公式显示 3 遍（"7 5 % 75%75\%"、"(CH3COOOH)\mathrm{...}(CH3​COOOH)"）。修复：`src/main.tsx` 导入 `katex/dist/katex.min.css`（构建时打包）；浏览器实测 t1 可见层 "75%" 只出现 1 次、MathML 隐藏、无原始 LaTeX 源码
  - **ABCD 选项粘连**：cleanLatex 新增选项换行规则（中文/标点/数字后接 A-D + ．/、/空格+$ → 换行；不误伤公式内 "AB$"）→ evals: `render-t1.test.ts`
  - **\pH / \pOH 未知命令** → `\mathrm{pH}` / `\mathrm{pOH}`（KaTeX 报错修复）→ evals: `chem-markdown-ts.test.ts`
  - **出题功能完整审计与补齐**（用户反馈"题型选项被吃掉"）：对照旧版 Vue 主工作台 + 旧版内联面板逐项审计——
    - **题型 chips 恢复为 单选/多选/填空/计算/实验/推断**（新增"多选"题型；后端 llm_service TYPE_ALIAS + multi 题型规范（2-3 个正确选项，answer 逗号分隔）；实测多选生成 answer="A,C"）
    - **新建题库按钮**（主工作台 + 内联面板，POST /api/exam-bank/exam-sets，旧版"+ 新建"行为）
    - **打印预览**（主工作台，旧版 printPreview 行为：新窗口 KaTeX 渲染 + 打印按钮）
    - 保留项核对：题型/难度/知识点搜索多选/变种题(选蓝本)/保存题库/四维审核/AI 生成/手动录入/OCR 上传/题库管理/历史真题库/考试列表/作蓝本
    - **t4 渲染修复**：`<sub>/<sup>` HTML 透传（CH<sub>3</sub>I 下标）、`\\ = \\` 双反斜杠 OCR 垃圾 → `=`（⑥ 方程式单行）、page_image 缩略图与内容图去重（ed9966 只显示一次）、内容图居中显示 → evals: `chem-markdown-ts.test.ts`（+3）
  - 实测（2020 全国卷弹窗）：**katex-error 0 个**（原 4 个）、无 Γ/\bf 源码、无 m-a-t-h-r-m 字母残留（DOM 级验证）、58/58 图片、436 个 KaTeX 公式、T1 题干 75% 单版本、选项 A/B/C/D 分行
  - 后端图片兜底路由：`/static/figures` 兼容目录数字前缀（`01_全国卷` ↔ `全国卷`，与 exam_bank region 归一化一致）；page_image 缩略图补 `figures/` 路径段
  - evals：`chem-markdown-ts.test.ts`（cleanLatex 10 项 + 用户提供的 2020 真题样例）；实测弹窗置顶撑满 + 420 个 KaTeX 公式 + Ω 垃圾消失 + 无"C H 3"空格残留 + 58/58 图片 + 无控制台错误
  - ① 工具调用卡片：`tool_result.result` 为 JSON 字符串（v2 协议）→ 解析为数据；完成后卡片自动展开显示结果（旧版即时可见）；show_* 面板类工具补中文标签 → evals: `agent-stream-reducer.test.ts` + `tool-card.test.tsx`
  - ② component 事件：改为**内联面板**（出题工作台/诊断/学习计划/学生列表），不再跳页（navigate 事件仍跳转）→ evals: `agent-stream-reducer.test.ts`
  - ③ 思考分析状态：从右上角移回 **AI 气泡内**（脉冲点 + 阶段文案 + 耗时，文本输出后隐藏）→ evals: `chat-bubble.test.tsx`
- [x] SSE 事件处理重构为纯函数归约器 `src/lib/agent-stream-reducer.ts`（可测试、行为被 evals 锁定）
- [x] **真实 Agent 端到端验收**：新会话输入「请帮我出3道关于氧化还原反应的题目」→ 思考状态气泡内显示 ✅ / 工具卡片出现且展开显示「已打开出题工作台…」✅ / 内联出题面板渲染（预填知识点+3道选择题+难度）✅ / URL 不跳页 ✅ / 无控制台错误 ✅

- [x] SSE 流式：`src/lib/agent-sse.ts`（phase / text / tool_call / tool_result / tool_error / step / error / done 事件）
- [x] 工具卡片：内联折叠卡（图标 + 名称 + 状态徽章 + 可展开富结果），替换旧版左红边等宽卡
- [x] 工具结果富渲染：题目卡片 / 真题搜索 / 障碍分布 / 学习计划 / 配平审核 / 模拟实验 / 周报 / OCR 表格 / 导入结果 / 布置练习 / JSON 兜底
- [x] 快捷建议卡（6 个带图标）：配平 / 出题 / 实验 / 讲解 / 搜题 / 诊断
- [x] 对话管理：列表 / 新建 / 删除 / 历史加载（后端为数据源）
- [x] 审批流：awaiting_approval → 批准/取消 → resume
- [x] 文件上传（`/api/agent/upload` → 操作卡 → 触发指令）与批量答题卡（`/api/ocr/tasks/batch`）
- [x] 空状态欢迎区、流式打字、思考动画、耗时计时
- [x] 化学式实时预览条（输入 Fe3+ 等即时显示 ³⁺ 上标预览；`src/lib/chem-format.ts` + 8 项单测）
- [x] component 事件内联面板（exam-workbench / diagnosis / learning_plan / student-list）— 已实现内联渲染，不跳页（见下方用户反馈修复）
- [x] **用户反馈修复（Agent 工作台）**：
  - ① 工具调用卡片：`tool_result.result` JSON 字符串解析 + 完成后自动展开 + show_* 中文标签 → evals: `agent-stream-reducer.test.ts`、`tool-card.test.tsx`
  - ② component 事件内联面板（出题工作台/诊断/学习计划/学生列表），navigate 事件仍跳转 → evals: `agent-stream-reducer.test.ts`
  - ③ 思考分析状态回到 AI 气泡内（live-timer 0.1s 跳动计时器恢复，内联面板生成计时恢复）→ evals: `chat-bubble.test.tsx`、`use-live-timer.test.tsx`
  - ④ **发送新消息旧对话丢失**（reducer 重构引入）：`messagesRef` 同步 + `seedNewTurn` 纯函数种子状态（旧消息完整保留），实测两轮对话后两个用户气泡与全部内容都在 → evals: `agent-stream-reducer.test.ts`（问题④ 2 项）
  - ⑤ **内联面板显示不全**（输入框钉底后出现）：面板限高 `max-h-[72vh]` + 内部滚动 + 插入时滚动到面板顶部；实测面板全高 416px 完整可见 → 截图 `docs/ui-review/23-panel-geo.png`
  - SSE 事件处理重构为纯函数归约器 `src/lib/agent-stream-reducer.ts`，真实 Agent 端到端验收通过（出题流程：气泡状态/工具卡展开/内联面板/不跳页）

### 班级学情 /class（Phase 1）✅ 代码完成，待评审

- [x] 班级选择器 + 演示班级兜底
- [x] 4 统计卡（考试次数 / 需关注学生 / 班级人数 / 最近均分）
- [x] ECharts：知识点错误率柱状图 / 障碍类型环形图 / 成绩趋势折线图（替换 Chart.js CDN）
- [x] 需关注学生 Top5（按障碍占比，可点击跳学生管理）
- [x] 学生列表表格（障碍标签 + 弱知识点，行点击跳转）
- [x] 骨架屏加载态 / 空状态（素材就位前占位）

### 待迁移（Phase 2）→ ✅ 全部完成（2026）

- [x] 登录页 /login：表单 + 左侧品牌区（logo 已接入）
- [x] 学生管理 /students：统计卡 / 筛选 / 卡片网格 / 分页 / 详情抽屉（障碍条 / 迷你趋势 / 薄弱知识点 / 活动时间线）/ 添加学生（手动+邀请码）/ 转班 / 重置密码 / 学习计划生成（可编辑 + 保存 + 发给学生 + 历史）
- [x] 出题工作台 /exam：4 标签（出题工作台 AI 生成+手动录入+OCR 上传 / 题库管理 / 历史真题库 / 考试列表），AI 出题（题型+数量+难度+知识点+变式蓝本）、四维审核徽章、保存到题库、考试创建/预览/发布/删除
- [x] 诊断分析 /diagnosis：班级+考试选择、障碍分布条+环形图、掌握度统计、需关注学生列表（搜索+筛选+展开详情）、学习计划生成/发家长/应用/删除、计划面板
- [x] 答题卡识别 /ocr：拖拽上传、置信度标记、可编辑单元格、单条/批量入库
- [x] 答题卡批改 /ocr-sheets：批量上传预览、批次进度轮询、重试、标准答案批改、关联考试保存

### 已知偏差（Phase 2 补充）

- 出题工作台「考试管理」的选题组卷（从题库/真题库往试卷加题）深度集成未移植，先提供考试创建/预览/发布/删除 + 题库保存；组卷可后续深化
- 考试工作台原 Vue 版的弹窗管理（选卷蓝本浏览等）以「作蓝本」按钮内联替代

## 2026 追加修复（用户反馈三轮）

### 图片位置与 agent 真题附图（用户反馈：「图片放在题目的位置有问题」「agent 找真题图片位置也有问题、有些真题不显示图片」）

- [x] **根因**：存量 OCR 数据中配图被 LLM 格式化到【分析】/【解答】/【点评】之后（题目底部）或嵌在解析文字中间；前端忠实渲染数据位置 → 图跑到题目最下面。agent 找真题另有三个问题：① 后端 `exam_images` 事件（page_image 附图）在新前端 reducer 中被丢弃（旧版 DOM 注入有处理）；② 搜索卡片 `content.slice(0, 400)` 截断把尾部图片切掉；③ 内容无内联图引用、仅有 page_image 的真题完全无图
- [x] **修复**：
  - 纯函数 `reorganizeQuestionImages`（`src/lib/exam-utils.ts`）：题干（首个【分析】/【解答】/【点评】前）内图片原位保留；解析部分图片提取、去重后移到题干之后；解析部分图片引用移除；幂等 → evals: `exam-utils.test.ts`（16 项）
  - 新增 `components/QuestionMd.tsx` 共享题目渲染组件，接入全部题目展示位点：历史真题弹窗 / 题库管理 / 试卷预览 / 选蓝本弹窗 / 内联出题面板 / AI 气泡（`MessageList` AiBubble）/ 题目卡片 / 搜索结果
  - reducer 新增 `exam_images` 事件处理：附图挂到最近的 search_exam_bank 卡片 `data.images`（不跳页、无卡片安全忽略）→ evals: `agent-stream-reducer.test.ts`（问题⑤ 3 项）
  - `SearchResults`：去掉 400 字截断，渲染 `data.images` 附图画廊；`filterExamImages` 按文件 basename 与正文去重（正文已内联的图不重复显示）→ evals: `search-results.test.tsx`（4 项）
- [x] 实测（真实后端 + 新构建，2020 全国卷弹窗）：T1 乙醚题配图 1 张、位于【分析】之前（题干后）、不在答案之后；T6 电池题 1 张不重复；控制台 0 错误 → 截图 `docs/ui-review/32-img-position.png`，脚本 `scripts/ui-img-position-verify.py`

### 有机化学结构图（用户反馈：「AI出题出有机化学时画苯环等功能升级后是否保留」）

- [x] **结论：功能保留，管线完好**——RDKit 已装（2026.03.5）、`[SMILES:...]` 标记 → RDKit 渲染 PNG（`app/services/structure_render.py`）→ `/static/question_images` 挂载；agent 出题路径（`agent/tools/generation.py`）一直有替换
- [x] **发现并修复缺口**：工作台 `/api/question/generate` 与 `/api/question/smart-assign` 两个路径漏调 `replace_smiles_markers`（升级前端前即有），工作台 AI 出有机题时苯环显示为原始 `[SMILES:...]` 文本 → 两处补替换（非法 SMILES 仍退化为文本不阻断）→ evals: `tests/test_question_smiles.py`（2 项，monkeypatch LLM/检索/审核 + TestClient 断言 `[SMILES:` 消失且出现 `/static/question_images/` img）
- [x] 实测：`GET /static/question_images/b7192bb7….png`（苯，RDKit 渲染）→ 200 image/png；pytest 全绿

## 2026 追加修复（用户反馈第四轮）

### Agent 内联出题面板缺题型选择（「agent窗口内联的出题界面还是没有题目类型选择的功能」）

- [x] **根因**：内联面板的题型 chips 只渲染 Agent 预填的题型（通常只有单选 1 个），且 `generate_questions` 路径预填的 types 缺 `active` 字段 → 面板看起来"没有题型选择"
- [x] **修复**：`mergePanelTypes`（`InlinePanels.tsx`）——始终展示全部 6 种题型 chips（单选/多选/填空/计算/实验/推断），Agent 预填的保持选中与数量，预填缺失字段按默认值补齐，清单外题型（choice 等）保留 → evals: `inline-panel.test.tsx`（+3：全 6 题型、预填 5 题选中、无 active 不崩溃）
- [x] 实测（真实 Agent 对话「帮我出3道氧化还原反应的题目」）：内联面板 6 种题型 chips 全部渲染 → 截图 `docs/ui-review/38-inline-panel-types.png`

### 演示学生数据保护（「李世睿（202610201）直接没了……不要给我重置掉」）

- [x] **排查结论**：当前库中李世睿数据完整（学号 202610201 / 2419班 / barrier / 140 题 / 学习计划 / 家长李国华绑定 BIND770487）；真实根因有二——
  1. **种子名单不一致**：`init_db.py` 种子名单 202610201 = 陈伟（打印文档却写"李国华（李世睿的家长）"），库一旦被旧备份/重建覆盖，演示学生就变陈伟（备份 db_backup_20260810 即此状态）→ `STUDENT_NAMES[34]` 改为李世睿
  2. **重复绑定**：家长端孩子列表曾出现 2 条李国华→李世睿绑定（bind_demo_001 + bind_parent_demo_001_202610201）→ 清理为 1 条
- [x] **启动保护 `protect_demo_student`**（init_db.py，init_database 第 10.5 步）：202610201 姓名被覆盖为非李世睿 → 强制恢复；李国华→李世睿绑定缺失 → 补建；重复绑定 → 保留 1 条 → evals: `tests/test_demo_protection.py`（6 项：改名恢复/完整不动/补建绑定/不重复/缺学生不崩/重复绑定清理）
- [x] **快照备份**：`data/db_backup_20260814/chemai_consistent.db`（sqlite backup API 一致快照，校验含李世睿+两条父亲绑定+67 学生）
- [x] **学生管理首屏可见**（「李世睿直接没了」UI 根因：分页 12 人/页，她在第 3 页）：`sortStudentsForDisplay` 纯函数——演示学生 202610201 置顶 + 其余按练习数降序 → evals: `tests/student-utils.test.ts`（4 项）
- [x] 实测：学生管理首屏第一张卡 = 李世睿（2419班 概念 81%）；家长端 m/parent-login（lgh/123456）登录后孩子列表显示李世睿 1 次（无重复）；班级学情页含李世睿；截图 `docs/ui-review/36-lyx-students-sorted.png`、`37-lyx-parent.png`

## 2026 追加修复（用户反馈第五轮：有机化学题）

### 答案/选项 LaTeX 不渲染（「生成有机化学的题就这样？答案: A:$CH_3COOH$ B:...」）

- [x] **根因**：答案与选项全部走纯文本 Tag/`chem-mono` 文本显示，KaTeX 公式显示为原始 `$...$` 源码
- [x] **修复**：新增 `AnswerMd`（答案标签 + ChemMd 公式渲染）与 `OptionsRow`（选项逐项 KaTeX 渲染）组件，替换全部 9 处显示点（ExamPage 生成卡片/题库/历史弹窗/预览、InlinePanels、QuestionCards、SearchResults）→ evals: `tests/answer-options.test.tsx`（6 项：答案公式渲染/`\xrightarrow{浓硫酸}` 无 katex-error/选项逐项/字符串选项/空值）
- [x] 实测：历史真题弹窗 12 个答案标签 + 438 个 KaTeX 公式；工作台生成结果 13 个 KaTeX、无原始 `$` 源码

### 有机结构图生成（「有机化学分子式的结构呢？不是能生成吗？为什么实现不了」）

- [x] **根因**：LLM 生成有机题时几乎不输出 [SMILES:...] 标记（prompt 已要求但不遵守，实测 2 题均无标记）→ 结构图管线存在但永远触发不了
- [x] **修复（三层）**：
  1. `replace_smiles_markers` 应用范围从 content 扩到 **content/options/answer 三处**（question.py ×2、generation.py）
  2. **名称兜底 `enrich_organic_structures`**：常见有机结构名（苯/甲苯/苯酚/乙醇/乙酸/乙酸乙酯/乙烯/乙炔/环己烷/苯胺/苯乙烯，按长度降序匹配避免"苯"吃掉"苯酚"）出现即自动插入 RDKit 结构图，每名称只插一次，已有图不重复
  3. **分子式兜底**：`$CH_3CH_2OH$`/`$C_2H_5OH$`/`$CH_3COOH$`/`$CH_3CHO$`/`$CH_3COOC_2H_5$`/`$C_6H_5OH$`/`$C_6H_6$` 等 LaTeX 分子式 → 归一化匹配 → 追加结构图（保留原公式）
  4. prompt 强化（llm_service + smart-assign）：有机题强制要求 [SMILES:...] 标记 + 示例
- [x] evals: `tests/test_question_smiles.py`（8 项：content/options/answer 替换、苯环图、复合词优先级、幂等、分子式补图、未收录不误伤）
- [x] 实测（真实 LLM）：工作台生成有机题（有机化合物+酯化反应）→ 结果含 4 张结构图（苯/乙醇等）+ 13 个 KaTeX 公式 + 0 个原始 $ 源码 → 截图 `docs/ui-review/39-organic-question.png`；脚本 `scripts/ui-organic-verify.py`

## 2026 追加修复（用户反馈第六轮：Agent 找学生）

### 工具卡片与学生诊断图形化（「以前能看到工具调用卡片……以前能显示正常渲染的图和表格，现在最多就一个表格了」）

- [x] **排查**：SSE 事件流直测确认后端事件正常（找李世睿 → tool_call:diagnose_barrier → component:diagnosis，params 含 student_name/barrier_distribution/weak_knowledge_points/score_trend）；工具卡片在 UI 正常显示（完成徽章）。真正的问题是：**diagnose_barrier 学生场景结果落到 JsonFallback（原始 JSON）**，旧版是图形化渲染（renderDiagnosis）
- [x] **修复**：新增 `StudentBarrierResult` 渲染器——障碍百分比条（图）+ 成绩趋势柱状图（图）+ 薄弱知识点表格 + 统计卡 +「针对障碍出题练习」按钮（旧版 _diagToExam 行为，点击发消息给 Agent）；`diagnose_barrier` 按 student_name 分发学生/班级场景 → evals: `tests/student-barrier.test.tsx`（5 项）
- [x] **内联诊断面板补学生场景**：InlineDiagnosis 只认 `class_barrier_distribution/students`，学生场景（`student_name/barrier_distribution`）显示成引导版 → 支持两种数据形态 + 「针对障碍出题练习」按钮（带学生名）→ evals: `inline-panel.test.tsx`（+2）

### Agent 学习方案跳转（「说给她出一份个性化学习方案会跳转到学生界面自动出方案然后由我点确认发送」）

- [x] **根因**：后端仍发 `navigate:students params={focus:学号, action:'plan'}`，但新 reducer 的 navigate 只调 `onNavigate(path)` **丢弃 params** → 学生页不自动开抽屉/不出方案
- [x] **修复**：reducer navigate 透传 params（旧版 sessionStorage `chemai_navigate` 机制恢复）→ ChatPage 存 `chemai_navigate_params` → StudentsPage 挂载消费：focus → 自动打开抽屉 + loadDetail；action=plan → 自动调 genPlan（修复 genPlan 闭包捕获旧 drawerStudent 的问题，改为参数化）→ 方案预览 modal → 用户点「确认发送」（sendPlan）→ evals: `agent-stream-reducer.test.ts`（+1：navigate params 透传）
- [x] 实测（真实 Agent + UI）：说"给李世睿出一份个性化的学习方案" → URL 跳 #/students + 抽屉自动打开 + 方案生成 modal 出现（hasPlanModal=True）

## 2026 Ant Design v6 接入（用户选型：antd 渐进式提升视觉质量）

### 调研结论

- [x] antd 当前 v6（6.6.0），完整兼容 React 19；主题 design token 可定制品牌色；与 Tailwind v4 可共存（CSS-in-JS + 布局分工）；中文化 ConfigProvider 现成；Vite ESM 按需打包
- [x] 选型（用户确认）：**antd v6 渐进式接入** —— 保留 Tailwind 布局/自研小件/化学渲染，重交互区域换 antd 现成件；范围：登录页+全局消息、学生管理、班级学情、出题工作台、答题卡

### Phase 0 基础设施

- [x] `antd@6.6.0` 安装；`src/components/antd/AntdProvider.tsx`：ConfigProvider 主题映射（colorPrimary #002147 牛津蓝 / colorInfo #0d7377 / 语义色/圆角 8/字体栈/Table 表头底色）+ zhCN + antd App 上下文 → App.tsx 最外层挂载
- [x] **全局 Toast 桥接**：`useToast` API 不变，实现换成 antd `App.useApp().message`（全站消息视觉一次升级，216 项既有测试不受影响）

### Phase 1 登录页

- [x] 自研 Input/Button → antd `Form + Input + Input.Password + Checkbox + Button`（表单校验/图标前缀/加载态现成）；Playwright 选择器兼容（placeholder/type=submit 不变）

### Phase 2 学生管理

- [x] 卡片网格 → antd `Table`（学号/班级/主导障碍 Tag/练习/正确率/最后活跃列，分页现成，行点击开抽屉；**李世睿置顶排序保留**）
- [x] 详情抽屉 → antd `Drawer`；学习统计 → `Statistic`；障碍条 → `Progress`；薄弱知识点 → antd `Tag`
- [x] 工具栏搜索/班级/障碍筛选 → antd `Input`（allowClear）+ `Select`

### Phase 3 班级学情

- [x] 班级选择 → antd `Select`；4 统计卡 → `Statistic`（图标前缀/语义色）；学生列表 → antd `Table`；障碍标签 → antd `Tag`；ECharts 图表保留

### Phase 4 出题工作台

- [x] 保存题库/难度选择 → antd `Select`；知识点搜索 → antd `Input`；手动录入表单 → `Input/Input.TextArea/Select`；OCR 上传 → `Upload.Dragger`（拖拽+点击）；题型 chips/变种题/历史弹窗保留自研（定制交互）

### Phase 5 答题卡

- [x] OcrPage：上传区 → `Upload.Dragger`；结果表 → antd `Table`（题号动态列 + 可编辑单元格 + 置信度 + 入库操作，编辑状态逻辑不变）
- [x] 实测：5 页面全 antd 化（登录/学生/班级/出题/OCR），无控制台错误；截图 `docs/ui-review/50-antd-login.png` ~ `56-antd-students-drawer.png`

### 验证

- [x] typecheck / vitest 216 项 / build 全绿；后端 pytest 270 项不受影响（纯前端改动）

## 2026 第二轮优化（antd 深化）

- [x] **A. 全局确认弹窗**：4 处 `window.confirm` → antd `Modal.confirm`（删除题库/删除考试/删除学习计划/重置密码，危险按钮红色 + 品牌色）
- [x] **B. 题型 chips → antd CheckableTag + InputNumber**（主工作台 + agent 内联面板，保留点击选中/数量调节交互）→ evals 同步更新（`inline-panel.test.tsx` 锁定 antd DOM）
- [x] **C. antd vendor 独立分包**（vite manualChunks 函数）：主包 981KB → 413KB，antd 独立 chunk 缓存友好
- [x] **D. 诊断分析页统计卡 → antd Statistic**（3 个，与班级学情一致）
- [x] **E. 出题工作台 Tabs → antd Tabs + Segmented**（4 主 tab + 3 来源切换）
- [x] 实测：出题工作台（Tabs/Segmented/CheckableTag/InputNumber）、删除确认弹窗（危险按钮）、诊断 Statistic 全通过；截图 `docs/ui-review/60~62-round2-*.png`
- [x] 全量回归：typecheck / vitest 228 项 / build 全绿

## 2026 弹窗层级修复（用户反馈：历史计划弹窗在学生详情卡片下面）

- [x] **根因（两层）**：① antd Drawer/Modal 默认 z-index 1000；自研 Modal 原为 `z-50` → 被抽屉盖住；② 两个自研弹窗叠放时 DOM 顺序错误（计划详情先渲染）导致详情被列表盖住
- [x] **第一轮修复**：自研 Modal `z-50 → z-[1100]` + 调整 JSX 渲染顺序 → 计划详情盖历史计划 ✓，但**抽屉遮挡问题仍在**
- [x] **根因深挖（elementFromPoint 实测）**：弹窗中心命中 `ant-drawer-mask` —— 页面根 `animate-fade-in-up` 的动画 transform（matrix(1,0,0,1,0,0)）创建 **stacking context**，自研 Modal 被锁在页面子树内，z-1100 只在子树内生效，压不过 portal 到 body 的 antd Drawer（z-1000）——**与 z-index 数值无关**
- [x] **最终修复**：自研 Modal **createPortal 渲染到 document.body**（脱离页面根 stacking context，与 antd 弹层同级比较 z-index）→ 实测 elementFromPoint 命中弹窗内容（不再命中 drawer-mask）→ evals: `modal.test.tsx`（+portal 断言：parentElement === document.body）
- [x] 实测（localhost:3000 热更新地址）：抽屉(z-1000) → 历史计划弹窗(z-1100) 在抽屉之上 ✓ 可交互 ✓；关抽屉弹窗保留 ✓；查看计划详情盖在历史列表之上 ✓

## 2026 第三轮：用户 4 项功能/质量缺口（"把这个目标全部完成，再跑测试和 evals"）

### 1. 试卷打印入口收敛（「还没组成考试试卷就能打印，打印啥？」→「出题工作台还留个组卷打印干嘛？」）

- [x] 第一版：出题工作台加「组卷打印」弹窗（选考试→加题→打印）+ 考试列表预览加「打印试卷」
- [x] **终版（2026-08 用户确认）：打印属于试卷（考试）的事，出题工作台不再保留打印入口** —— 移除工作台「组卷打印」按钮与整组弹窗/状态逻辑；打印统一在「考试列表 → 预览 → 打印试卷」；无题目的考试不显示打印按钮
- [x] 实测：工作台操作区无任何打印按钮；考试有题目时预览弹窗显示「打印试卷」、无题目时不显示（`scripts/ui-print-entry-check.py` / `check2.py`，截图 `docs/ui-review/74-print-paper-btn.png`）

### 2. 有机结构正确性（「生成的图是错的，结构式不对」「碰到名字就自动出结构式，有时候不用」）—— 已调研业界方案

- [x] **调研结论**：RDKit sanitize 已内置价态/芳香性校验（官方 FAQ）；OPSIN 只认英文 IUPAC 名不认中文俗名；PubChem API 依赖外网。教育产品常规做法 = 权威白名单 + 解析器验证（无需引入外部依赖）
- [x] **白名单 canonical 归一**：高频高中结构（19 种，新增苯甲酸/硝基苯/乙二醇/甘油/氯苯/乙醛/丙酮/甲醛）人工验证 SMILES；LLM 输出的 [SMILES:...] 等价结构（canonical 相同，如苯简写 c1ccccc1）→ 归一化到教材白名单写法渲染，保证图标准正确
- [x] **化学合法性校验**：MolFromSmiles + 显式 SanitizeMol（价态/键数非法 → 不渲染退化为文本）
- [x] **名称兜底改语境触发**：「结构/简式/示性式/如图/键线式」等语境词 ±20 字符内才补图（"乙醇能与钠反应"不再乱插图）；分子式兜底保留（选项/题干分子式配图是题意所需）
- [x] evals: `tests/test_question_smiles.py`（+3：白名单归一同一图、价态非法拒绝、无语境不补图；语境/复合词/分子式用例同步更新）

### 3. 出题工作台 AI 生成计时器（「计时器不见了」）

- [x] 主工作台恢复旧版 live-timer：生成中按钮旁显示「⚡ AI 出题 xx.xs」（useLiveTimer，与内联面板一致）→ 实测 4.0s ticking ✓

### 4. 题库功能恢复（「只有整个题库删除，没有单题删除/选入考卷/批量加入」）

- [x] **单题删除**：题库题目行「删除」→ antd Modal.confirm → `DELETE /api/exam-bank/exam-sets/{set_id}/questions/{question_id}`（后端接口原有，前端补齐）
- [x] **加入考试**：题目行「加入考试」+ 批量栏（全选/勾选 N 题）→ 弹窗选考试 → `POST /api/exam/{exam_id}/questions`（后端原有，支持题库题+历史真题）
- [x] 实测：题库管理 checkbox 全选/批量栏/行内删除与加入考试按钮全部出现；批量加入考试弹窗正常（`scripts/ui-round3-verify.py`）

### 验证

- [x] 前端 typecheck / vitest **230 项** / build 全绿；后端 pytest **273 项** EXIT=0；UI 实测（localhost:3000）无 console 错误；截图 `docs/ui-review/70~72-round3-*.png`

## 2026 目标验收期补充（Round 5-6）

- [x] **DESIGN.md 补 §5.7 Ant Design v6 接入**：选型/主题映射/层级契约（自研 Modal z-[1100]+portal）/antd 化范围/分包策略
- [x] **验收清单 `docs/acceptance-checklist.md`**：素材映射核对表 + 设计方向评审检查点 + 8 项历史问题回归抽查 + 演示账号（用户一次验收）
- [x] **成功标准核查——新设计 token 零残留旧样式**：全 src 扫描无暖纸色（#faf8f5/#f5efe0）、无 Cormorant 衬线、无 4px 圆角、无 emoji 图标（唯一 JetBrains Mono 是 §5.1 明确保留的"等宽仅化学式"）
- [x] **antd v6 API 废弃清理**（8 页面巡检发现的 2 个 console warning）：`Statistic valueStyle` → `styles.content`（StudentsPage×4/ClassPage×1/DiagnosisPage×2）；`Drawer width={440}` → `size={440}` → console 完全零警告
- [x] **8 页面完整巡检**（`scripts/ui-full-sweep.py`）：chat/class/students/exam/diagnosis/ocr/ocr-sheets 全部正常、无破损图、无错误文案、console 零错误
- [x] **后端工程健康**：ruff 全绿（修复 2 处历史 E501 超长行）、`py_compile` 通过、pytest 全量 **273/273** EXIT=0
- [x] **静态托管冒烟**：根路由(React)/favicon/m/index/m/login/m/parent-login 全 200；**修复 `/legacy` 归档 404 缺口**（checklist 声称可访问但后端缺路由 → main.py 挂载 `StaticFiles(/legacy)`）→ legacy/index.html、legacy/teacher/app.js、旧出题页全部 200

### 验收结果（2026-08 用户确认「验收通过」）

- [x] **一键验收脚本 `scripts/ui-acceptance-run.py`：11/11 PASS**（登录表单/进入对话/李世睿置顶/抽屉 Statistic+Progress/历史计划弹窗层级/题型 6 种/题库批量栏/单题删除/单题加卷/诊断页加载）

## 2026 诊断图表丢失修复（用户反馈：「说展示图表了，图表在哪里？更新前端前都能正确展示」）

- [x] **根因**：LangGraph 新版 ToolMessage repr 带后缀（`content='{...}' name='show_diagnosis' tool_call_id='call_xxx'`），SSE 适配器旧 unwrap 用 `endswith(quote)` 判断失败 → 前端拿到 `{raw: repr}` → 诊断卡片无 student_name → 走空数据班级视图（0/0/0 空图表）；show_* 卡片显示原始 JSON 乱码
- [x] **修复**：v2 适配器 + v1 适配器（两处）改用正则解包 content 值（兼容 additional_kwargs/name/tool_call_id 后缀）；tool_result 解析成功时**重新序列化下发干净 JSON**（无 repr 残留、不触发 8000 截断）；前端 `show_*` 工具加友好渲染（显示 message 文本）
- [x] **防幻觉**：v2 agent prompt 加约束——只有实际调用诊断工具并收到结果才能说"已展示图表"，未调用时只能输出文字结论
- [x] evals: `tests/test_sse_adapter.py`（4 项：v2 解包+干净 JSON、v1 解包、纯 JSON 不误伤、普通 JSON 不受影响）
- [x] 实测：SSE 直测 diagnose_barrier 下发干净 JSON（student_name=李世睿、barrier 完整）；UI 复现工具路径 → 诊断卡片完整显示（140 题/88-123/72%/障碍条 81-15-4/趋势/薄弱点表格）+ show_diagnosis 显示 message；console 零错误

## 2026 布置练习反复批准修复（用户反馈：「反复需要批准，而且还报错」）

- [x] **根因链（六层）**：
  1. `assign_adaptive_practice` 只支持 class_id，"给李世睿布置"时 LLM 传参困难 → 反复失败（"班级 无学生"）
  2. 同一回合重复 awaiting_approval → 多张审批卡
  3. 批准后 handleApproval 只更新 messages，SSE onDone 用旧 state.items 覆盖 → 卡片恢复 pending（视觉上"批准了还要批准"）
  4. resume 时 `_get_or_create_agent` 不透传 guard_state → 新建 GuardState（approved=False）→ LLM 再 request_approval 又中断
  5. resume 时 LangGraph 重放 interrupt 前的 request_approval on_tool_start → adapter 重复发 awaiting_approval（即使 guard 已批准）
  6. LLM 重复请求确认 → 无 guard 拦截
- [x] **修复**：①工具支持 student_id/student_name（单学生反查）+ 友好参数错误；②reducer awaiting_approval 去重（pending 唯一）；③`updateApprovalStatus` 同步 state+消息；④`_get_or_create_agent` 透传 guard_state（resume 复用 approved）；⑤resume 端点过滤重放的 awaiting_approval（批准类 resume）；⑥guard：已批准后 request_approval 直接返回不再中断
- [x] evals: `test_assign_practice.py`（6 项：单学生姓名/学号/班级/无目标错误/未知学生/二次 request_approval 不中断）；`agent-stream-reducer.test.ts`（+2：pending 去重、updateApprovalStatus）
- [x] 实测：SSE 直测 首次 1 次 awaiting_approval → resume 后 0 次 → assign success；UI 端到端 1 张审批卡 → 批准 → "已批准执行"（无第二张 pending）→ "已为 1 名学生布置练习（李世睿 medium 5 题 concept）"；console 零错误（`scripts/sse_approval_flow.py` / `ui-assign-practice-e2e.py`）
- [x] 独立巡检 console 零错误；前端 230/230 + 后端 273/273 + ruff 全绿
- [x] 用户口头验收通过：素材映射核对 + 设计方向评审 ✅

### 收尾（Phase 3）✅

- [x] FastAPI 托管切换：`app/main.py` 增量改动——根路由优先 `dist/index.html`、`/assets` 静态挂载（构建产物）、`/favicon.png` 路由；`python -m py_compile` 通过；API/协议零改动
- [x] 旧教师端文件归档 `legacy/teacher/`：pages/（6 页）、app.js、common.css、design-system.css、diag.html、migrate-convs.html、js/{agent,agent-renderers,students,diagnosis,ocr}.js
  - ⚠️ 保留原位（m/ 学生端依赖）：`js/chem-markdown.js`、`login.html`（m/ 401 跳转目标）
  - 旧测试导入路径已更新指向 legacy，94 项测试全绿
- [x] `DESIGN.md` 更新：新增第五段「方向 A · 现代学术蓝」参数块（保留/移除/tokens/技术栈变更/规则覆盖/素材清单）
- [x] 全量回归：8 个教师端页面巡检（无破损图片、无控制台错误）、m/index.html 可加载、旧 /pages/teacher.html 自动落到新应用
- [x] **端到端验收（真实后端 + 生产构建 + 真实登录）**：启动 FastAPI:8001，`hai/hai123456` 登录成功 → 对话页正常；学情页真实数据（9 次考试 / 34 人 / 高一(1)(2)班选择器 / 2 个 echarts 图表 / 需关注学生 73%）；学生页 67 人 + 筛选 + 卡片；出题页 21 个知识点真实加载；无控制台错误
- [ ] 待用户确认：设计方向评审、素材映射核对（见上）

## 最终状态

| 项 | 状态 |
|----|------|
| 教师端 8 页面 React 迁移（/login /chat /class /students /exam /diagnosis /ocr /ocr-sheets） | ✅ |
| 设计系统方向 A（tokens.css 唯一事实来源） | ✅ |
| 素材接入（6 张 + favicon 派生） | ✅ 映射待用户核对 |
| typecheck / build / 94 测试 | ✅ |
| 学生端/家长端 m/ 目录 | ✅ 零改动 |
| 后端 | ✅ 仅 3 处增量静态托管改动，编译通过 |

## 已知偏差（评审时说明）

1. React 版本：安装为 React 19（npm 当前稳定版，原计划写 18，无破坏性差异）
2. 对话历史缓存：旧版 sessionStorage 缓存 + 服务端合并；新版以服务端为唯一数据源（更简单可靠）
3. component 事件（如打开出题工作台）由「气泡内嵌面板」改为「页面跳转」，后续可深化
4. 性能优化（2026 追加）：路由级懒加载（echarts 独立按需块）+ echarts 按需引入（1.1MB → 554kB），首屏包仅含 react+katex+对话
