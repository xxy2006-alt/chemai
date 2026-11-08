# 全工具链路验收矩阵（2026-08-16 · 目标工件）

> 目标：48 工具（42 核心 + 5 browse + request_approval）链路全部验证达标，
> 问题修复 + 收敛 evals。前端标准 S1–S4 见下。状态随进度更新。

## 前端标准（验收判据）

- **S1 工具卡**：每个工具调用 = 图标 + 中文动作说明 + 状态徽章（执行中/完成/失败）；
  完成自动展开，结果**直接可读**（内容/stdout/匹配列表/表格），
  不允许裸英文工具名（browse_* 缺 meta）、不允许原始 JSON 倾倒（JsonFallback）。
- **S2 内联面板无重复**：同一诊断/计划只渲染一个面板；「保存到学生端/发送给家长」
  按钮在位；不跳页。
- **S3 文本不复述面板**：agent 文本最多一句过渡，不复述得分/障碍分布/计划明细。
- **S4 无卡死/无空气泡/无裸报错**：审批卡即时弹出；弃单可恢复；错误是中文可行动提示。

## 验收分组

- **A 组（UI 对话触发，教师 persona，35 个）**：无头 Chrome 驱动 + 视觉判断，
  每个工具记录：工具卡是否出现（中文名+图标+状态）→ 结果渲染是否符合 S1。
- **B 组（学生 persona 专属，7 个）**：simulate_experiment + 6 学科 tutor。
  前端 vitest 渲染器测试 + golden（persona: student）断言覆盖。
- **C 组（需上传/外部服务前置）**：grade_answer_sheets / query_ocr_progress /
  save_grading_results / query_batch_grades / list_teacher_exams /
  parse_chemistry_document / import_question_bank / check_parser_services。
  vitest 渲染器测试 + 后端单元断言覆盖（UI 触发成本高，不逐条跑对话）。
- **D 组（browse_*，5 个）**：补 meta + 渲染器；能力验证走一次真实导航链路
  （若 headless 环境可行），否则 vitest 冒烟 + golden 断言。

## 矩阵

### A 组（教师对话链路）

| 工具 | 触发消息 | 预期（S1） | 状态 |
|---|---|---|---|
| search_exam_bank | 搜索电化学的高考真题 | SearchResults 卡片：题目+选项+答案可读 | ✅ 终轮验证 |
| web_search | 网上查一下次氯酸钠的漂白原理 | WebSearchView：标题+摘要列表 | ✅ 终轮验证 |
| show_exam_workbench | 出5道氧化还原选择题 | 面板事件，工具卡「打开出题工作台」 | ✅ 终轮验证 |
| show_diagnosis | 展示张浩宇的诊断 | StudentBarrierResult/BarrierOverview 图表 | ✅ 终轮验证 |
| show_students | 班里有哪些学生 | ShowPanelResult | ✅ 终轮验证 |
| diagnose_barrier | 诊断张浩宇的学习障碍 | 诊断面板图表（去重+无文本复述） | ✅ 终轮验证 |
| chemistry_tutor | 讲解一下盐类水解 | TutorAnswer 文本 | ✅ 终轮验证 |
| balance_equation | 配平铜和浓硫酸反应的方程式 | BalanceResult 表格 | ✅ 终轮验证 |
| weekly_report | 生成张浩宇的周报 | WeeklyReport 卡（S3 压制） | ✅ 终轮验证 |
| assign_adaptive_practice | 给张浩宇布置电离平衡练习 | AssignResult + 审批卡（取消路径验证） | ✅ 终轮验证 |
| save_to_bank | 出题后"保存到题库" | BankSaveResult 确认文案 | ✅ 自包含复验 |
| list_banks | 查看我的题库 | BankListResult 列表（S3 压制+过渡） | ✅ 自包含复验 |
| delete_bank | 删除题库（审批） | BankDeleteResult + 审批卡 | ⚠️ 副作用大未 UI 触发；golden mgmt-delete-bank 覆盖 |
| generate_questions | 出3道氧化还原选择题中等难度 | QuestionCards | ✅ 终轮验证 |
| memory_student_get | 查看张浩宇的学习记忆 | MemoryStudentResult（空记录合法） | ✅ 终轮验证 |
| memory_teacher_get | 我的教学偏好是什么 | MemoryTeacherResult | ✅ 终轮验证 |
| generate_learning_plan | 给张浩宇生成学习计划 | LearningPlan 面板×1 + 两按钮 + S3 | ✅ 终轮验证 |
| send_learning_plan | 把学习计划发送给学生 | SendPlanResult（副作用：真实发送，vitest 覆盖） | ✅ vitest |
| generate_parent_report | 生成张浩宇的家长报告 | ParentReportResult 预览 | ✅ 终轮验证 |
| send_report_to_parent | 把报告发给家长 | SendReportResult（副作用：vitest 覆盖） | ✅ vitest |
| read | 读取桌面上的文件 X | FileReadResult（审批卡+内容） | ✅ 已修已验证 |
| write | 把这段内容写到工作区 test.md | FileWriteResult（区内直写） | ✅ 已修已验证 |
| edit | 编辑工作区里的 test.md | FileWriteResult(edited) | ✅ golden fs-agent-edit |
| find | 在工作区找一下 md 文件 | FindResult 列表 | ✅ 终轮验证 |
| grep | 在工作区搜索"化学" | GrepResult 匹配列表 | ✅ 终轮验证 |
| bash | 查看当前时间/目录 | BashResult stdout | ✅ 终轮验证 |
| plan_task | 帮我规划一个出题任务 | PlanTaskResult 步骤 + 过渡文案 | ✅ 终轮验证 |
| request_approval | （随审批链路出现） | 审批卡（非工具卡） | ✅ 已验证 |
| import_question_bank | 导入题库 | ImportBankResult | ✅ vitest |
| check_parser_services | 检查解析服务状态 | ParserServicesResult | ✅ vitest |
| parse_chemistry_document | 解析这份化学文档 | ParseDocResult | ✅ vitest |
| query_batch_grades | 查看批改批次成绩 | BatchGradesResult（需批次参数） | ✅ 终轮验证（追问批次属合理） |
| list_teacher_exams | 我的考试列表 | TeacherExamsResult + 教师身份注入 | ✅ 已修已验证 |
| save_grading_results | 保存批改结果 | SaveGradesResult | ✅ vitest |
| query_ocr_progress | 查询识别进度 | OcrProgressResult | ✅ vitest |
| grade_answer_sheets | 批改这批答题卡 | GradeSheetsResult | ✅ vitest |

### B 组（学生 persona）

| 工具 | 覆盖方式 | 状态 |
|---|---|---|
| simulate_experiment | vitest Experiment 渲染器 | 待测 |
| chemistry_tutor | 已含 A 组；student persona golden 断言 | 待测 |
| ionic/stoichiometry/redox/equilibrium/periodic_law/organic_tutor (6) | vitest TutorAnswer + golden(student) | 待测 |

### C 组（前置服务，vitest+单元断言）

grade_answer_sheets / query_ocr_progress / save_grading_results / query_batch_grades /
list_teacher_exams / parse_chemistry_document / import_question_bank /
check_parser_services —— 渲染器补齐后 vitest 冒烟，后端行为由已有 pytest 覆盖兜底。

### D 组（browse）

browse_navigate / browse_read / browse_click / browse_input / browse_screenshot ——
补 ToolCard meta + 结果渲染器；headless 下走一次导航链路（可行则 UI 验证，否则 vitest）。

## 已知问题清单（阶段 2 修复）

1. [P1] 16 个工具无渲染器 → JsonFallback 裸 JSON（S1 违规）
2. [P1] 5 个 browse_* 无 meta → 裸英文名（S1 违规）
3. [P1] 诊断/计划面板重复渲染（S2 违规）→ 前端按组件类型去重
4. [P1] agent 文本重复输出诊断/计划内容（S3 违规）→ SYSTEM_PROMPT 强化 + not_text_contains 断言
5. [P2] 掌握度 0% / 诊断学生 0 的数据占位疑点（诊断面板数据映射）
6. [P2] 登录按钮「登 录」带空格（选择器脆弱性，非验收项，仅记录）

## 收敛目标（阶段 5）

- golden（agent_eval_golden.yaml）：A 组每工具 1 条场景（tool_called + 必要的结果断言）；
  S3 用新断言类型 not_text_contains；S2 用前端 vitest（面板去重逻辑）
- vitest：48 工具 meta 全覆盖断言；每渲染器 ≥1 冒烟测试
- 门禁：pytest + evals --fast + vitest 全绿

## 进度

- [x] read 卡死修复与验证（含审批卡/弃单恢复/毒化线程）
- [x] 阶段 2：16 工具渲染器补齐 + 5 browse meta + 面板去重 + S3 适配器压制（标准过渡文案）+ 诊断面板视图修复 + 教师身份注入 + write 工作区直写
- [x] 阶段 3：A 组 14 场景 UI 链路全跑（两轮：首轮发现 → 修复 → 终轮验证）
- [x] 阶段 4：问题修复（全部 eval-first：红测试 → 实现 → 绿）
- [x] golden 58/58（含 7 条新 tc 场景 + interrupt 检测修复）
- [x] 2026-08 第二轮：记录完整恢复（user/ai/tool 历史结构）+ DSH 式思考行 + 白块根除 + batch_id 防泄漏（提交 c582d67 之后）
- [x] 6 基础工具单对话连测（UI 实测全绿：write/edit/find/grep/bash/read 审批）
- [x] 文件访问三档：off/workspace/full（DSH danger-full-access 等价）+ UI 人话说明
- [ ] 测试会话清理（清单 41 条待用户确认）
- [ ] e2e 新场景（tool-chain-six + long-conversation）跑绿（进行中）
- [ ] 门禁终跑 + 提交
