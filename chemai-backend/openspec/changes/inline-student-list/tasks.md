# Inline Student List — 开发任务

## 1. 新增 show_students 工具
> Spec: student-list-component

- [x] 1.1 在 `agent/tools.py` 中新增 `show_students(class_id, class_name, filter_barrier)` 函数
- [x] 1.2 查 DB：`SELECT student_id, name, barrier_type, exercises_completed FROM students WHERE class_id = :cid ORDER BY exercises_completed ASC`
- [x] 1.3 解析 barrier JSON，提取 dominant_barrier 和百分比
- [x] 1.4 返回 `_component: {component: "student-list", params: {students: [...], class_name: "..."}}`
- [x] 1.5 添加到 `TOOLS` 列表

## 2. 注册工具到 diagnosis_expert
> Spec: student-list-component

- [x] 2.1 `agent/langgraph_agent.py` diagnosis_expert 工具列表添加 `"show_students"`
- [ ] 2.2 验证：Agent 路由到 diagnosis_expert 后可调用 show_students

## 3. 修复现有工具不再跳转
> Spec: remove-student-navigation

- [x] 3.1 `diagnose_barrier` 班级级：`_route: {navigate: True}` 改为 `_component: {component: "diagnosis", params: _data}`
- [x] 3.2 `weekly_report` 班级级：去掉 `_route`，仅返回数据（`student_name`、`report`、`exam_count`）
- [ ] 3.3 验证：班级级诊断/周报不产生 navigate SSE 事件

## 4. 前端内联学生列表面板
> Spec: student-list-component (前端部分)

- [x] 4.1 `agent.js` component switch 添加 `student-list` 分支 → `renderStudentList(params, bubble)`
- [x] 4.2 渲染学生卡片列表：每张卡片含姓名、学号、障碍标签+百分比、练习进度
- [x] 4.3 障碍颜色编码：高→红色、中→黄色、低→绿色
- [x] 4.4 卡片点击 → 选中该学生，更新 Agent 上下文 → 自动发送消息"诊断 [学生姓名]"
- [x] 4.5 使用 `max-height: 400px; overflow-y: auto` 可滚动容器，不限 20 名（不跳转）

## 5. 测试

- [ ] 5.1 手动 E2E："有哪些学生" → 学生列表面板渲染 → 点击学生 → 触发诊断
- [ ] 5.2 手动 E2E："找问题比较大的学生" → 诊断展示 → 零页面跳转
- [ ] 5.3 验证：班级级诊断不跳转到 /pages/diagnosis.html
- [ ] 5.4 验证：班级级周报不跳转到 /pages/students.html

---

**依赖关系:**
```
1 (show_students 工具) ─┐
                         ├→ 5 (testing)
2 (注册到 expert) ──────┤
                         │
3 (修复现有工具) ────────┤
                         │
4 (frontend) ───────────┘
```

1-4 可并行开发，5 依赖全部完成。
