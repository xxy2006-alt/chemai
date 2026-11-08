# Tasks: vue-migration

## T1: 共享 CSS 抽离

- [x] 1.1 新建 `frontend/common.css` → btn/card/tag/chip/empty/toast/dialog/modal 全部抽离
- [x] 1.2 exam.html 引入 `<link rel="stylesheet" href="/common.css">`
- [x] 1.3 teacher.html 同样引入

## T2: Vue 3 CDN + 出题面板改造

- [x] 2.1 Vue 3 CDN 引入: `unpkg.com/vue@3/dist/vue.global.prod.js`
- [x] 2.2 AI 出题面板 → Vue 组件: 知识点 chips (v-for+toggle) + 题型 chips + difficulty select + totalQty
- [x] 2.3 题目结果列表 → v-for + reactive: questions array, _removed flag for card removal
- [x] 2.4 保留所有功能: saveOne/saveAll/removeOne/deleteAll with confirm/regenAll

## T3: 历史真题搜索

- [x] 3.1-3.3 历史真题和考试面板保持原有 vanilla JS，未变更（功能完整）

## T4: 学情面板上线

- [x] 4.1 侧边栏 app.js 加入口: `{ id: 'teacher', sym: 'Td', label: '学情面板' }`
- [x] 4.2 teacher.html 引入 common.css + Chart.js (unpkg CDN)
- [x] 4.3 图表/卡片/学生列表数据加载正常

## T5: 清理

- [x] 5.1 删除 `pages/question-generator.html`
- [x] 5.2 删除 `main.py` 中 `/question-generator` 显式路由
- [x] 5.3 HTMLResponse import 移除

## T6: 验证

- [x] 6.1 Vue 应用挂载成功，知识点 chips 21 个全加载
- [x] 6.2 题型 chips 5 种 + 难度 + 题量正确
- [x] 6.3 Vue → `typeof Vue` = "object", 0 JS errors
- [x] 6.4 Chart.js 从 unpkg CDN 加载正常
