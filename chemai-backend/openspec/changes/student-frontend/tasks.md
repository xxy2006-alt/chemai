# Student Mobile Frontend — Tasks

## 1. 共享模块 app.js
> 所有页面依赖

- [x] 1.1 `getUser()` — 从 sessionStorage 读取 `chemai_user`，无登录态跳 `/login.html`
- [x] 1.2 `api(url, opts)` — fetch 封装，自动注入 `Authorization: Bearer <token>`
- [x] 1.3 `TabBar(activeId)` — 4 Tab 底部导航，纯 JS 生成 DOM + 点击切换
- [x] 1.4 `Header(title, subtitle)` — 顶部标题栏组件

## 2. AI 助教对话 index.html
> P0 — 核心入口

- [x] 2.1 页面骨架：Header + 消息区 + 快捷提问芯片 + 输入框 + TabBar
- [x] 2.2 SSE 流式：连接 `/api/agent/chat/langgraph/stream`，persona=student
- [x] 2.3 消息渲染：用户气泡(右/红底白字) + AI 气泡(左/白底黑字)
- [x] 2.4 处理 SSE 事件：text/subagent_text/tool_call/route/error
- [x] 2.5 快捷芯片点击 → 填充输入框并发送

## 3. 我的练习 practice.html
> P1 — 教学核心

- [x] 3.1 任务列表：`GET /api/practice/student/{id}/tasks` → 待完成 + 已完成
- [x] 3.2 开始练习 → 逐题作答界面（选项卡片 + 上一题/下一题）
- [x] 3.3 提交答案：`POST /api/practice/submit`
- [x] 3.4 结果展示：正确率 + 每题对错

## 4. 错题本 wrong.html
> P1 — 教学闭环

- [x] 4.1 错题列表：从练习历史提取错误题目
- [x] 4.2 展开详解：正确答案 + 你的答案 + 错误原因
- [x] 4.3 变式题按钮（placeholder，后续对接 AI 生成）

## 5. 我的页 report.html
> P2

- [x] 5.1 个人信息卡片：姓名/班级/学号
- [x] 5.2 统计数据：练习完成数/正确率
- [x] 5.3 菜单入口：学习报告/复习中心/学习计划/个人设置
- [x] 5.4 退出登录

## 6. 复习中心 review.html
> P2

- [ ] 6.1 今日待复习列表（localStorage 存储复习计划）
- [ ] 6.2 复习统计：累计/掌握/今日完成

## 7. 学习计划 plan.html
> P2

- [ ] 7.1 教师布置的计划列表
- [ ] 7.2 进度追踪

## 8. 报告详情 report_detail.html
> P2

- [ ] 8.1 成绩趋势展示
- [ ] 8.2 知识点分析

---

**依赖关系:**
```
1 (app.js) ──→ 2 (index.html) ──→ 3-8 (其余页面)
                    │
                    └── TabBar 导航到其余页面
```

2 和 3 可并行开发（都只依赖 1）。
