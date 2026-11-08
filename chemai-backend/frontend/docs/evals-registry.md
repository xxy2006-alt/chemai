# ChemAI 回归 Evals 总表（问题 → 测试映射）

> 所有历史用户反馈与修复均已固化为可运行测试。**每次更新后跑：**
>
> ```bash
> # 前端（typecheck + 228 项 vitest + build）
> cd chemai-backend/frontend && npm run check
>
> # 后端（270 项 pytest）
> cd chemai-backend && python -m pytest tests -q --ignore=tests/test_smart_parse.py
> ```
>
> 新问题修复后必须补对应 eval（先复现 → 修复 → 固化），并在此表登记。

## 前端 Evals（228 项，26 个文件）

| # | 用户问题 / 修复点 | 测试文件 | 关键断言 |
|---|---|---|---|
| 1 | 发送消息后旧对话丢失 | `agent-stream-reducer.test.ts` 问题④ | seedNewTurn 保留旧消息，SSE 首事件不覆盖 |
| 2 | 工具结果不显示（v2 SSE result 为 JSON 字符串） | `agent-stream-reducer.test.ts` 问题① | tool_result 解析出 questions 数据；非法 JSON 兜底 {raw} |
| 3 | component 事件跳页（应内联面板） | `agent-stream-reducer.test.ts` 问题② | component → panel 消息项，onNavigate 不被调用 |
| 4 | 思考状态位置/实时计时器 | `chat-bubble.test.tsx` + `use-live-timer.test.tsx` | 状态在气泡内、100ms 跳动 |
| 5 | 工具卡片自动展开 | `tool-card.test.tsx` | done + data 到达 → 展开显示结果 |
| 6 | 历史真题弹窗置顶撑满 | `modal.test.tsx` | wide 弹窗 items-start + max-w-[1120px] + 视口内 |
| 7 | KaTeX CSS 缺失公式重复显示 | `chem-markdown-ts.test.ts` + `render-t1.test.ts` | 公式只渲染 1 次、无 MathML 层 |
| 8 | cleanLatex 全套（\pH、\\ = \\、\r、sub/sup、选项换行、\mathrm 系列） | `chem-markdown-ts.test.ts` + `render-t1.test.ts` | 各规则单项断言 + 2020 真题样例全卷 |
| 9 | 题型清单被吃（单选/多选等 6 种） | `exam-types.test.ts` | 6 chips、别名映射、labels |
| 10 | 变种题蓝本入口 | `inline-panel.test.tsx` | 选蓝本按钮存在 |
| 11 | 题目配图位置（移题干后/去重/幂等） | `exam-utils.test.ts` | reorganizeQuestionImages 全规则 |
| 12 | agent 找真题不显示图片（exam_images 事件） | `agent-stream-reducer.test.ts` 问题⑤ | 附图挂到搜索卡片；无卡片安全忽略；不跳页 |
| 13 | 搜索附图去重（正文已含不重复显示） | `search-results.test.tsx` + `exam-utils.test.ts` | filterExamImages basename 去重 |
| 14 | 答案/选项 LaTeX 显示源码 | `answer-options.test.tsx` | AnswerMd/OptionsRow KaTeX 渲染、\xrightarrow 无 error |
| 15 | 内联面板无题型选择 | `inline-panel.test.tsx` | 6 题型 chips 全渲染、预填合并、无 active 不崩 |
| 16 | 学生诊断显示原始 JSON（应有图+表格） | `student-barrier.test.tsx` | 障碍条/趋势图/表格/出题按钮；班级场景不误伤 |
| 17 | 诊断面板缺"针对障碍出题练习"按钮 | `inline-panel.test.tsx` | 按钮显示 + chemai:send 事件 |
| 18 | 学习方案跳转丢参数（focus/action） | `agent-stream-reducer.test.ts` | navigate params 透传回调 |
| 19 | 学生管理分页找不到李世睿 | `student-utils.test.ts` + `students-page.test.tsx` | 演示学生置顶排序；antd Table 第一行=李世睿 |
| 20 | antd 主题接入（品牌色/中文上下文） | `antd-provider.test.tsx` | antd 组件正常渲染 |
| 21 | 全局 Toast 桥接（antd message，API 不变） | `antd-provider.test.tsx` | 五种 API 可调；message 弹出 |
| 22 | 登录页 antd 表单（placeholder 兼容 Playwright） | `antd-provider.test.tsx` | Input/Password/Checkbox/submit 存在 |
| 23 | 学生管理 antd 化（Table/Select/抽屉） | `students-page.test.tsx` | Table 渲染、筛选 Select、点击行开 Drawer（Statistic/Progress） |
| 24 | 答题卡 antd 化（Dragger + 可编辑表格） | `ocr-page.test.tsx` | Dragger 存在；题号动态列/可编辑/置信度/入库/编辑回调 |
| 25 | 化学式实时预览（Fe3+ → Fe³⁺） | `chem-format.test.ts` | 上标转换 |
| 26 | 基础 UI 组件（方向 A tokens） | `ui-components.test.tsx` | Button/Tag/Badge/StatCard/Tabs 类名 |
| 27 | 题型 chips antd 化（CheckableTag + InputNumber，第二轮） | `inline-panel.test.tsx` | 选中态/数量在 antd 组件下仍正确（防回归） |
| 28 | 自研 Modal 层级被 antd 抽屉盖住（z-50 < z-1000） | `modal.test.tsx` | z-[1100] + **createPortal 到 body**（脱离页面根 stacking context） |
| 29 | SSE 工具结果丢失（ToolMessage repr 未解包 → 诊断卡片空图表/JSON 乱码） | `test_sse_adapter.py`（4 项） | v2/v1 适配器解包带 name/tool_call_id 后缀的 repr；tool_result 下发可解析干净 JSON（含 student_name）；纯 JSON 不误伤 |
| 30 | 布置练习反复需要批准/报错（assign_adaptive_practice） | `test_assign_practice.py`（6 项） | 支持单学生（姓名/学号）布置；无目标友好参数错误；未知学生错误；**已批准后 request_approval 不再中断**（防重复审批） |
| 31 | 批准后审批卡恢复 pending（视觉上反复要批准） | `agent-stream-reducer.test.ts` | updateApprovalStatus 同步批准/取消状态；重复 awaiting_approval 去重（同一 pending 只一张卡） |

## 后端 Evals（270 项）

| # | 用户问题 / 修复点 | 测试文件 | 关键断言 |
|---|---|---|---|
| 1 | LLM JSON 未转义 LaTeX 反斜杠（\rightleftharpoons 变 CR） | `test_llm_json.py`（6 项） | parse_llm_json 修复后 json.loads 成功 |
| 2 | 有机结构图（SMILES → 结构图 img） | `test_question_smiles.py`（11 项） | content/options/answer 三处替换；名称/分子式兜底；幂等；复合词优先级；**白名单 canonical 归一（等价结构同一教材图）**；**价态非法拒绝渲染**；**无语境不补图** |
| 3 | 演示学生保护（李世睿不可重置） | `test_demo_protection.py`（6 项） | 改名恢复/绑定补建/重复绑定清理/缺学生不崩 |
| 4 | 结构渲染服务（RDKit） | `test_structure_render.py` | 合法 SMILES 出 PNG、缓存、非法返回 None |
| 5 | SMILES 标记替换（ADR-0005） | `test_question_marker.py` | 标记 → img、括号原子、非法退化、静态图 200 |

## Playwright UI 巡检脚本（真实后端 :8001，人工/CI 可选）

```bash
cd chemai-backend/frontend
python scripts/ui-img-position-verify.py   # 真题配图位置（T1/T6）
python scripts/ui-organic-verify.py        # 有机题结构图 + 答案公式
python scripts/ui-antd-final.py            # antd 全页面巡检 + 截图
python scripts/ui-lyx-verify3.py           # 李世睿可见性 + 家长绑定
```

## 数据快照（演示数据保护）

- 李世睿 (202610201) 一致快照：`chemai-backend/data/db_backup_20260814/chemai_consistent.db`
- 启动自愈：`protect_demo_student`（init_db.py 第 10.5 步）强制姓名/绑定不变量
