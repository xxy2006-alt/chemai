## 1. gateway.py: 导航事件工厂（15 min）

- [ ] 1.1 新增 `build_navigate_events(intent: IntentResult, tool_results: list) -> dict`
  - 输入: 分类器输出 + Agent 执行后的 tool 结果列表
  - 输出: `{navigate: {...}, populate: [...], actions: [...]}`
- [ ] 1.2 实现 `page` → action 映射表：
  ```python
  _PAGE_ACTIONS = {
      "exam-v2": {
          "generate_questions": [{"action": "openTab", "payload": "generate"}],
          "search_exam_bank": [{"action": "openTab", "payload": "browse"}],
      },
      "diagnosis": {
          "diagnose_barrier": [{"action": "selectStudent", "payload": "{student_name}"}],
      },
  }
  ```
- [ ] 1.3 `populate` 事件：tool 返回的 JSON 数据按 tool 名映射到 populate target
- [ ] 1.4 验证: 单元测试输入各 intent 组合 → 输出正确的事件结构

## 2. fastapi_sse.py: SSE 流中插入导航事件（25 min）

- [ ] 2.1 `_classify_and_narrow()` 改为返回完整的 `IntentResult`（不只 `tools`）
- [ ] 2.2 `/chat` 端点：`intent` 非 chat 时，在 response JSON 中增加 `navigate` 字段
- [ ] 2.3 `/chat/stream` 端点：在 generator 中，tool 结果之后、done 之前，yield navigate/populate/action 事件
- [ ] 2.4 `page_action` 场景（无 tool 执行）：generator 开头 yield navigate + action
- [ ] 2.5 chat 场景：不发送任何导航事件（行为不变）
- [ ] 2.6 验证: curl stream 端点发送"打开考试工作台" → SSE 含 `navigate` 事件

## 3. exam-v2.html: __chemai_bridge 消费者（20 min）

- [ ] 3.1 Vue app `mounted()` 中检查 `window.__chemai_bridge`
- [ ] 3.2 `action: openTab` → 设置 `this.tab` + `this.sourceMode`
- [ ] 3.3 `action: openTab:bank` → `this.tab = 'bank'`
- [ ] 3.4 `populate data.questions` → 写入出题区 `this.generatedQuestions`
- [ ] 3.5 `populate data.searchResults` → 写入题库浏览区
- [ ] 3.6 `params.knowledge_points` → 预填知识点筛选器
- [ ] 3.7 消费后清除 `window.__chemai_bridge = null`

## 4. diagnosis.js: __chemai_bridge 消费者（15 min）

- [ ] 4.1 DOMContentLoaded 回调中检查 `window.__chemai_bridge`
- [ ] 4.2 `action: selectStudent` → 调用现有 `toggleStudentDetail(sid)`
- [ ] 4.3 `action: selectClass` → 设置 class 下拉框值，触发 change
- [ ] 4.4 `populate data.diagnosis` → 直接渲染诊断结果（跳过 API 调用）
- [ ] 4.5 消费后清除 `window.__chemai_bridge = null`

## 5. 端到端测试（15 min）

- [x] 5.1 "打开考试工作台" → page_action → navigate 到 exam-v2，无 tool 调用 ✓
- [x] 5.2 "给张三出5道盐类水解的题" → hybrid → 执行 generate → populate + navigate 到 exam-v2 + openTab:generate ✓
- [x] 5.3 "搜索有机化学真题" → hybrid → 执行 search → populate + navigate 到 exam-v2 + openTab:browse ✓
- [x] 5.4 "诊断张三的学习障碍" → hybrid → 执行 diagnose → populate + navigate 到 diagnosis + selectClass ✓
- [x] 5.5 "你好" → chat → 无导航事件，行为不变 ✓
