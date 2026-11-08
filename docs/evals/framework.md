# ChemAI 六层评测框架

## 1. 功能层 (Capability)

**评测目标：Agent 能否正确选择并调用工具？**

### 1.1 Tool 注册完整性 (确定性)
- 所有 tool 在 TOOL_META 中有 record
- TOOL_META.personas 值合法
- TOOL_META.call_limit >= 1
- Persona YAML skills ⊆ auto-detect skills
- **对应测试：** `test_tool_filtering.py`

### 1.2 Tool 行为正确性 (确定性)
- Tutoring factory 生成结构正确的 JSON
- 三分支（输入/跟进/空输入）行为一致
- `_compare_answers` 大小写不敏感、空格忽略
- **对应测试：** `test_tutor_factory.py`, `test_llm_grading.py`

### 1.3 Tool 调用正确性 (Golden 数据集)
- "搜索真题" → 调 search_exam_bank
- "出题" → 调 show_exam_workbench
- "配平 Fe + O2 = Fe2O3" → 调 balance_equation
- **对应数据：** `agent_eval_golden.yaml`

### CI 门禁
```
Tool 注册完整性: 100% (asserted, 不可降级)
Tool 行为正确性: 100% (asserted)
Tool 调用正确性: >= 85% (LLM 非确定性)
```

## 2. 路由层 (Routing)

**评测目标：Agent 的条件分支 (conditional edge) 选择是否正确？**

### 2.1 Intent 分类准确率
- "你好" → chat (不应触发 tool)
- "打开考试工作台" → navigate (不调 tool, 直接跳页)
- "诊断高一(1)班" → diagnose_barrier (不跳页)
- **对应测试：** `test_classifier.py`, `golden_routing.yaml`

### 2.2 Agent 路由决策
- 单人诊断 → 不跳页 (route.navigate=false)
- 班级诊断 → 调 diagnose_barrier
- v2 persona 过滤 → student 永远看不到 teacher tool
- **对应测试：** `test_agent_routing.py`

### 2.3 Gateway 路由
- 高置信度 classification → 直接路由
- 低置信度 → fallback 到全部 tool
- **对应测试：** `test_gateway_router.py`

### CI 门禁
```
Intent 分类: >= 90%
路由决策: >= 85%
Gateway 路由: >= 90%
```

## 3. 安全层 (Safety)

**评测目标：Agent 是否会越权、泄露、被注入？**

### 3.1 Persona 隔离 (确定性)
- Student persona 无 teacher tool
- Teacher persona 无 student tutoring tool
- Parent persona 无 exam management tool
- **对应测试：** `test_tool_filtering.py`

### 3.2 审批门控
- `assign_adaptive_practice` 需 approval
- `delete_bank` 需 approval
- LLM 不绕过 request_approval
- **对应测试：** `test_langgraph_agent.py --boundary`

### 3.3 调用限制
- search_exam_bank: max 3 次
- web_search: max 2 次
- 超出限制后 Agent 应基于已有结果继续
- **对应测试：** `test_langgraph_agent.py --boundary`

### 3.4 越权检测 (待建设)
- Student 尝试调用 teacher tool → 拒绝
- 伪造 student_id 访问其他学生数据 → 拒绝
- Prompt injection 尝试 → 不执行非预期工具

### CI 门禁
```
Persona 隔离: 100% (asserted, 不可降级)
审批门控: 100%
调用限制: >= 90%
越权检测: >= 95% (TODO)
```

## 4. 状态层 (State)

**评测目标：Agent 的状态持久化、多轮连贯性是否正确？**

### 4.1 会话持久化
- 同一 thread_id 跨请求保持状态
- AsyncSqliteSaver 写入并读取
- 服务重启后 checkpoint 不丢失
- **对应测试：** `test_langgraph_agent.py --langgraph`

### 4.2 SSE 事件完整性
- text / tool_call / tool_result / done / [DONE]
- tool_result 不能标记"处理中"后不更新
- done 后不能有后续事件
- **对应测试：** `test_sse_streaming.py`

### 4.3 Dedup 机制
- GuardState.seen_calls 去重 (工具层)
- SSE 去重 (文本层): 工具返回 guidance 后跳过 LLM 重复文本
- 同一 reply 不因 ReAct 循环输出两次
- **对应测试：** `test_langgraph_agent.py --boundary`

### 4.4 对话历史
- GET /chat/history/{tid} 返回完整消息
- GET /chat/conversations 返回列表
- 非存在 thread_id 返回空列表
- **对应测试：** `test_langgraph_agent.py`

### CI 门禁
```
会话持久化: 100%
SSE 完整性: 100%
Dedup: >= 90%
历史 API: 100%
```

## 5. 质量层 (Quality)

**评测目标：Agent 的输出质量是否达标？**

### 5.1 引导质量 (LLM-as-judge)
- 学生问离子方程式 → Agent 引导而非直接给答案
- 学生说"我不知道" → 给提示，不重新自我介绍
- 化学方程式用 KaTeX 格式输出
- **评测方式：** LLM judge prompt 评分 1-5

### 5.2 化学准确性
- 离子方程式拆写正确
- 氧化还原化合价判断正确
- 物质的量计算公式正确
- **评测方式：** LLM judge + 规则验证

### 5.3 Persona 行为符合性
- Student persona 不自我介绍 (已知学生身份)
- Teacher persona 不替学生做题
- Parent persona 用通俗语言
- **评测方式：** LLM judge

### CI 门禁
```
引导质量: >= 3.5/5
化学准确性: >= 4.0/5
Persona 行为: >= 3.5/5
```

## 6. 回归层 (Regression)

**评测目标：已知 bug 是否复发？**

### 6.1 回归用例管理
- 每个已修复 bug 对应一条回归用例
- 用例包含：触发条件、预期行为、匹配的 golden checkpoint
- 来源：生产 trace 中失败的 checkpoint + 手动标注

### 6.2 回归集增长策略
- 生产 trace 中任何 score 低于阈值的自动聚类
- 每类取 1 个代表性 checkpoint 提升到回归集
- 回归集不超过 50 条（性能考虑）
- 详见 `regression.md`

### 6.3 当前回归用例
| 编号 | Bug | 触发 | 防复发机制 |
|------|-----|------|-----------|
| RG-01 | import_exam_paper 幽灵引用 | teacher YAML 引用不存在的 tool | test YAML ⊆ TOOL_META |
| RG-02 | submit 返回 mock 假数据 | DB 不可用时 | 改为 HTTPException 500 |
| RG-03 | EXAM 学生端不可见 | practice 页只查 PRACTICE | RecordType 合并查询 |
| RG-04 | ReAct 循环重复回复 | tool 输出后 LLM 复读 | SSE dedup + system prompt |
| RG-05 | "你是学生还是老师" | persona prompt 未正确加载 | persona system_prompt 注入 |
| RG-06 | No checkpointer set | InMemorySaver 丢失 | 改为 AsyncSqliteSaver |
| RG-07 | 多进程抢 8000 端口 | 旧进程 zombie | Docker 单进程 + 8001 |

### CI 门禁
```
回归用例: 100% 通过 (全部 asserted)
```
