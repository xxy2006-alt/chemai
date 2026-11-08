# Proposal: vue-migration

## Summary

考试工作台 Vue 3 迁移 + 知识点 Chips 移植 + 共享 CSS 抽离 + 学情面板上线。

## Motivation

当前 exam.html 800 行 vanilla JS DOM 操作，维护成本高。手工拼接 HTML 字符串容易出错且难以调试。同时：
- question-generator.html 中的知识点 chips 组件比 exam.html 的输入框体验好，应移植
- 全站 inline style 散落各处，无复用
- teacher.html 学情面板已开发但未接入侧边栏

## Scope

1. **Vue 3 CDN 迁移** — exam.html 改用 Vue 3 全局构建版 (CDN, 无构建)
2. **知识点 Chips 移植** — AI 出题区域: chips 多选替代逗号分隔输入
3. **共享 CSS** — 抽 common.css，统一 tag/card/btn/chip 样式
4. **学情面板上线** — teacher.html 挂进侧边栏
5. **清理** — 删除 pages/question-generator.html (已集成)

## Dependencies

依赖 infra-foundation, adaptive-diagnosis-engine, export-and-dashboard 的前期产出

## Acceptance

- [ ] exam.html 出题/题库/历史真题三个 Tab 正常运行，无功能退化
- [ ] 知识点 chips 可点选，题型 chips 可切换
- [ ] 共享 CSS 加载，全局样式一致
- [ ] 学情面板从侧边栏可进入
- [ ] 无旧版 question-generator.html 残留
