## Context

当前学生相关的 Agent 交互有两种路径：
1. **单学生诊断**：`diagnose_barrier(student_id)` → 返回 JSON 数据 → Agent 回复文本 → 无跳转 ✓
2. **班级级诊断**：`diagnose_barrier(class_id)` → 返回 `_route: {navigate: True, page: "diagnosis"}` → 页面跳转 ✗
3. **班级级周报**：`weekly_report(class_name)` → 返回 `_route: {navigate: True, page: "students"}` → 页面跳转 ✗
4. **"有哪些学生"**：没有专门的工具 → Agent 尝试其他方式 → 可能跳转 ✗

考试工作台已通过 `show_exam_workbench` + `_component` 模式实现内联渲染。本方案把学生相关交互也统一到同一模式。

## Goals / Non-Goals

**Goals:**
- 新增 `show_students` 工具，聊天中渲染学生列表内联面板
- `diagnose_barrier` 班级级改为返回 `_component` 而非 `_route`
- `weekly_report` 班级级去掉 `_route.navigate`，只返回数据
- 前端渲染学生卡片列表，支持障碍标签和选中交互

**Non-Goals:**
- 不修改 students.html 页面（保留为独立入口）
- 不修改 LangGraph 图结构
- 不修改 SSE adapter（已有 `component` 事件支持）

## Decisions

### D1: 新增专用工具，不修改现有工具的数据返回

**选择**: 新增 `show_students` 工具，和 `show_exam_workbench`/`show_diagnosis` 保持一致模式。

**理由**: 数据查询工具（`diagnose_barrier`、`weekly_report`）返回数据；展示工具（`show_*`）返回 `_component`。职责分离清晰。

### D2: `diagnose_barrier` 班级级改为 `_component`

**选择**: 当传入 `class_id` 时，`diagnose_barrier` 返回 `_component: {component: "diagnosis", params: {...}}` 而非 `_route: {navigate: True}`。

**理由**: 已有 `renderDiagnosis` 前端函数，直接复用。消除页面跳转。

### D3: `weekly_report` 班级级去掉导航

**选择**: `_is_class` 为 True 时不再返回 `_route`，仅返回数据。

**理由**: 报告数据已在 Agent 上下文中，不需要跳转页面。

### D4: 学生列表面板复用已有数据 API

**选择**: `show_students` 直接查 SQLite 获取学生列表 + 障碍数据，不走独立 HTTP API。

**理由**: Agent 工具已有 DB session 访问能力（`diagnose_barrier` 已证明），不需要额外 API 端点。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 班级学生过多（50+）面板过长 | 限制展示前 20 名，加"查看全部"跳转 fallback |
| `show_students` 工具被其他 expert 滥用 | 只注册到 diagnosis_expert 的工具列表 |
| 前端 `renderStudentList` 需要新 CSS | 使用已有设计系统 token + inline style |
