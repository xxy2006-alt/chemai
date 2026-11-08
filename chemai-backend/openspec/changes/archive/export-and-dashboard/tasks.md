# Tasks: export-and-dashboard

## T1: 试卷导出 Word

**估时**: 1.5h
**涉及文件**: 新建 `app/services/export_service.py`，API 加端点
**验证**: 下载的 .docx 文件在 Word 中打开格式正确

- [x] 1.1 安装依赖 → python-docx 已随 MinerU 安装
- [x] 1.2 实现试卷模板 → A4纸，标题，题型分组，密封线标题区
- [x] 1.3 支持两种模式 → with_answers=True/False，答案红字标注，解析绿字
- [x] 1.4 API 端点 → `GET /api/question/export/{record_id}?format=docx&with_answers=false`
- [x] 1.5 验证 → export_service 直接测试 37KB docx 生成成功

---

## T2: 报告导出 PDF

**估时**: 1.5h
**涉及文件**: `app/api/report.py`, 后端 HTML 生成
**方案**: 后端 generate_report_html() → HTML 页面 → 浏览器 window.print()

- [x] 2.1 报告 HTML 生成 → `export_service.generate_report_html()`
- [x] 2.2 @media print CSS → A4, 边距, 分页，按钮隐藏
- [x] 2.3 老师版报告 → TOP5 错题表格 + 知识点错误分布 + 教学建议
- [x] 2.4 学生版报告 → 个人错题 + 鼓励语 （report_type="student"）
- [x] 2.5 "打印/导出 PDF"按钮 → window.print() 调用
- [x] 2.6 后端端点 → `GET /api/report/print/{exam_id}?type=teacher`

---

## T3: 学情面板前端可视化

**估时**: 2.5h
**涉及文件**: `frontend/pages/teacher.html`
**验证**: 浏览器 `http://localhost:8000/teacher` 看到可视化面板

- [x] 3.1 Chart.js CDN 引入 → v4 from cdn.jsdelivr.net
- [x] 3.2 班级总览卡片 → 平均分/考试次数/预警学生/班级人数
- [x] 3.3 知识点错误率柱状图 → Bar chart, X=知识点, Y=错误率%
- [x] 3.4 障碍分布饼图 → Doughnut chart, concept/reading/expression
- [x] 3.5 成绩趋势折线图 → Line chart, 考试次数 vs 平均分
- [x] 3.6 学生列表表格 → 姓名/障碍badge/薄弱知识点/练习完成/最近练习
- [x] 3.7 加载/空数据状态 → loading spinner + empty state 已处理

---

## T4: 出题工作台页面

**估时**: 2h
**涉及文件**: `frontend/pages/question-generator.html`
**验证**: 从工作台可完成一次完整出题流程

- [x] 4.1 条件区域 → 知识点chip多选 + 难度select + 题型chip + 数量input
- [x] 4.2 生成区域 → spinner加载 + 逐题渲染到卡片
- [x] 4.3 审核视图 → 每题 passed/warning/blocked 彩色左边框
- [x] 4.4 题目详情 → 内容 + 选项 + 答案 + 知识点 + 难度meta
- [x] 4.5 操作栏 → 题数统计 + 重新生成按钮 + 导出Word按钮
- [x] 4.6 API对接 → generate/export 已对接，audit/historical 可级联
