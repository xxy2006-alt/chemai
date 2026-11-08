# Agent-Exam Workbench Integration — 开发任务

## 1. Agent 侧：废弃 generate_questions，新增 navigate_to_exam_workbench
> Spec: exam-workbench-navigation

- [x] 1.1 在 `agent/tools.py` 中新增 `navigate_to_exam_workbench` 函数
- [x] 1.2 在 `agent/tools.py` 中给 `generate_questions` docstring 加 `[DEPRECATED for agent use]` 标记
- [x] 1.3 从 `TOOLS` 列表中移除 `generate_questions`，添加 `navigate_to_exam_workbench`
- [x] 1.4 从 `agent/langgraph_agent.py` 的 `TOOL_PREREQUISITES` 中移除 `generate_questions`，添加 `navigate_to_exam_workbench`
- [x] 1.5 更新 `navigate_to_exam_workbench` 的 docstring 为 When/What/Next 三段式格式
- [x] 1.6 更新所有 persona YAML 的 `available_skills`：将 `generate_questions` 替换为 `navigate_to_exam_workbench`

## 2. 前端 Bridge：exam-v2 接收 exam-config
> Spec: exam-config-bridge

- [x] 2.1 在 `exam-v2.html` 的 `mounted()` bridge handler 中新增 `populate.target === "exam-config"` 分支
- [x] 2.2 预填完成后在 `$nextTick` 中自动调用 `this.aiGenerate()`
- [x] 2.3 添加 `setTypes` action handler

## 3. 跨页面记忆
> Spec: cross-page-memory

- [x] 3.1 在 `agent.js` 的 navigate 处理逻辑中：跳转前持久化 conversation_id
- [x] 3.2 在聊天页初始化时恢复 conversation_id + 请求中携带 conversation_id
- [ ] 3.3 验证：发送消息 → 跳转考试工作台 → 返回聊天 → 发送关联消息 → Agent 正确理解上下文

## 4. 测试
> 验证改动不破坏现有功能

- [ ] 4.1 跑 `--boundary` 验证护栏不受影响
- [ ] 4.2 跑 `--workflow` 验证工作流场景（更新期望：不再期望 generate_questions 被调用）
- [ ] 4.3 跑 `--golden` 验证 golden 场景不回归（更新期望：涉及 generate_questions 的场景改为期望 navigate_to_exam_workbench）
- [ ] 4.4 手动 E2E：完整流程测试——聊天出题需求 → Agent 反问收集参数 → 跳转考试工作台 → 自动生成 → 确认保存 → 返回聊天

---

**依赖关系:**
```
1 (agent tools) ─┐
                  ├→ 4 (testing)
2 (frontend bridge)┤
                  │
3 (memory) ───────┘
```

1、2、3 可并行开发。4 依赖全部。
