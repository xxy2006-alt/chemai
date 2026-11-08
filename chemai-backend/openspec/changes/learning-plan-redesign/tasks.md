## 1. Backend — 持久化

- [x] 1.1 补实现 `POST /api/diagnosis/learning-plan/apply/{student_id}` — 写入 SqliteStore namespace `("student", student_id, "learning_plan")` key `"current"`, 更新 `_plan_cache`
- [x] 1.2 验证: `curl POST /apply` → `GET /learning-plan/{student_id}` 返回刚写入的计划

## 2. Agent — 新建工具

- [x] 2.1 在 `agent/tools/diagnosis.py` 新建 `generate_learning_plan(student_id, student_name)` — 调 `POST /generate` API, 返回格式化计划文档 + `_component` 可渲染卡片
- [x] 2.2 在 `agent/tools/diagnosis.py` 新建 `send_learning_plan(student_id, plan_data)` — 调 `POST /apply` API, 返回确认消息
- [x] 2.3 在 `agent/tools/__init__.py` 注册两个新工具到 TOOLS + TOOL_META (personas: `["teacher"]`)

## 3. 前端 — 学生管理界面

- [x] 3.1 重写 `frontend/js/students.js` genPlan 函数 — 用 `currentStudent.barrier_type` 和 `currentStudent.weak_kps` 替代硬编码
- [x] 3.2 添加 spinner 进度反馈 — 点击后 Drawer 底部显示 "正在生成学习计划..." + 旋转动画
- [x] 3.3 渲染可编辑计划卡片 — API 返回后在 Drawer 内展示计划, 每个字段 `contenteditable`, 失焦保存到本地对象
- [x] 3.4 添加 [保存修改] [发给学生] [取消] 按钮 — 保存写 localStorage, 发送调 POST /apply
- [x] 3.5 错误处理 — API 失败时显示错误消息 + "重试" 按钮

## 4. 验证

- [x] 4.1 Agent Chat 全流程: "找到张小明" → "给他生成学习计划" → 查看计划 → "把第二周改成盐类水解" → "发给学生"
- [x] 4.2 学生管理界面: 点击学生 → 生成学习计划 → 看到 spinner → 看到计划卡片 → 编辑字段 → 保存 → 发送
- [x] 4.3 持久化验证: 发送后重启服务器, GET /learning-plan/{student_id} 仍可获取
- [x] 4.4 评测: `python -m pytest evals/test_unit_tools.py -q` 确认无回归
