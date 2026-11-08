# 教师端改造 · 用户验收清单（2026）

> 目标（goal-17d42af3）等待的两项用户验收。其余工作已全部完成并通过全量测试。
> 验收地址：**http://localhost:3000**（热更新）或 http://127.0.0.1:8001（生产构建）
> 演示账号：`hai / hai123456`；家长端 `lgh / 123456`；李世睿 `202610201 / 123456`

## ① 素材映射核对（6 张设计 agent 素材，已按假设接入）

| 素材 | 当前用途 | 验收方式 |
|------|---------|---------|
| logo-mark（Iqp_*.png） | 侧边栏 / 登录页 / favicon | 看左上角 Logo 与浏览器标签图标 |
| ai-tutor（fldWb5*.png） | 对话 AI 头像 | Agent 工作台发一条消息看 AI 头像 |
| teacher-default（sP7BFC*.png） | 教师默认头像 | 暂未接入页面（待用户指出位置） |
| empty-chat（EqvpiC*.png） | 对话欢迎区插画 | 新对话空状态 |
| empty-class（3XItpb*.png） | 班级学情 / 诊断空状态 | 班级学情无数据时 |
| empty-students（Rjihuz*.png） | 学生列表空状态 | 学生管理筛选无结果时 |

截图索引：`frontend/docs/ui-review/50-antd-login.png`（登录页 Logo）、`52-antd-lyx-drawer.png`

## ② 设计方向评审（方向 A 现代学术蓝 + antd 视觉）

| 页面 | 检查点 | 截图 |
|------|-------|------|
| 登录页 | antd 表单（图标前缀/校验/加载态） | 50-antd-login.png |
| 学生管理 | antd 表格（李世睿置顶）/ 抽屉 / 统计数字 / 障碍进度条 | 51/52/56 |
| 班级学情 | Statistic 统计卡 + ECharts | 53-antd-class.png |
| 出题工作台 | antd Tabs/Segmented/题型 CheckableTag/拖拽上传 | 54/60/71 |
| 答题卡 | 拖拽上传区 + 可编辑表格 | 55 |
| 全局 | 消息提示（antd message）、确认弹窗（红色危险按钮） | 61 |
| 对话 | 工具卡片、诊断图形化（障碍条/趋势图/出题按钮） | 44/46 |

## ③ 历史问题回归抽查（每项已固化为 evals，230 前端 + 273 后端）

- [ ] 真题弹窗：配图在题干后、公式 KaTeX 渲染、无重复图（`scripts/ui-img-position-verify.py`）
- [ ] Agent 找真题：图片位置正确、不丢图
- [ ] AI 出有机题：苯环结构图（白名单教材式）、答案公式渲染、无语境不乱插图（`scripts/ui-organic-verify.py`）
- [ ] 学习方案：对话说"给李世睿出一份个性化学习方案"→ 自动跳学生页 → 自动出方案 → 确认发送
- [ ] 弹窗层级：学生抽屉 → 历史计划（贴顶、在抽屉之上）→ 查看计划（盖在列表上）
- [ ] 组卷打印：生成题目 → 保存到题库 → 组卷打印（选考试）→ 打印试卷
- [ ] 题库管理：单题删除、勾选批量加入考试
- [ ] 李世睿数据保护：学生管理首屏第一位；家长端 lgh 登录绑定正常

## ④ 运行回归（更新后执行）

```bash
cd chemai-backend/frontend && npm run check   # typecheck + 230 vitest + build
cd chemai-backend && python -m pytest tests -q --ignore=tests/test_smart_parse.py  # 273 项
```
详细问题→测试映射见 `frontend/docs/evals-registry.md`；全部改动记录见 `frontend/docs/migration-checklist.md`。
