## Why

学情面板 (teacher.html) 和学生管理 (students.html) 的职责边界模糊，功能错位——个体学生列表表格放在班级聚合分析页面里，而本该承担个体学生管理职责的 students.html 只是一个搜索框+纯文字列表。这与 Google Classroom、Canvas LMS 等行业成熟产品的「班级宏观 / 个体微观」双层信息架构差距明显。趁视觉统一重构的势头一并修复，避免后续因职责不清反复改动。

## What Changes

### students.html 重设计（学生管理）
- **BRAND NEW** 班级概览统计条：总人数 / 活跃学生 / 需关注 / 平均练习次数，页面顶部 4 KPI 卡片
- **BRAND NEW** 学生卡片网格布局：替代表格的卡片视图，每张卡片显示头像首字母、姓名、班级、障碍类型色标、练习次数、最后活跃日期
- **BRAND NEW** 右侧滑出 Drawer 详情面板：学习统计 KPI + 障碍诊断分布条 + 成绩趋势迷你折线图 + 薄弱知识点标签 + 最近活动时间线
- **BRAND NEW** 添加学生弹窗：手动输入姓名+班级 / 邀请码
- **CHANGED** 工具栏增强：搜索 + 班级筛选 + 障碍类型筛选 + 添加学生按钮（原来只有搜索+班级筛选）
- **KEPT** 转班弹窗保持不变
- **KEPT** 分页、Mock 数据降级逻辑保持

### teacher.html 瘦身（学情面板）
- **REMOVED** 删除底部学生列表表格（移到 students.html 作为卡片网格）
- **REMOVED** 删除学生详情弹窗（移到 students.html 作为 Drawer 详情面板）
- **BRAND NEW** 新增「重点关注学生」精选卡片横条（3-5 人，头像+姓名+障碍类型，点击跳转学生管理）

### 视觉一致性
- 所有新组件沿用实验室笔记本风格（#f7f4ed 暖羊皮纸背景、#b43c28 刚果红强调色、Cormorant Garamond + IBM Plex Sans + JetBrains Mono 字体）

## Capabilities

### New Capabilities
- `student-card-grid`: 学生卡片网格视图，含概览统计条、多维度筛选工具栏、卡片网格布局、分页
- `student-detail-drawer`: 右侧滑出详情面板，含学习统计 KPI、障碍诊断分布条、成绩趋势迷你图、薄弱知识点、活动时间线
- `student-add-modal`: 添加学生弹窗，支持手动输入和邀请码两种方式
- `attention-students-strip`: 学情面板的重点关注学生精选横条组件

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- **文件**: `frontend/pages/teacher.html`（瘦身，删学生列表和详情弹窗），`frontend/pages/students.html`（重写），`frontend/js/students.js`（重构）
- **API**: 不变，继续使用 `/api/classes`, `/api/panel`, `/api/diagnosis` 等已有端点
- **依赖**: Chart.js 仍用于成绩趋势迷你图；不引入新 CDN 依赖
- **断点**: 学生管理页面功能是纯新增/重设计，不破坏现有数据流
