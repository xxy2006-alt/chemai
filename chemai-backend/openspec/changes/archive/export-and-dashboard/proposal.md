# Proposal: export-and-dashboard

## Summary

实现试卷 Word 导出、报告 PDF 导出、学情面板前端可视化，补上"输出端"的最后拼图。

## Motivation

ChemAI 的 API 层已经能生成所有数据，但老师和学生无法以物理形式获得结果：
- 老师需要打印试卷 → Word 导出
- 学生需要错题报告 → PDF 导出
- 班级学情 → 需要图表可视化而非裸 JSON

## Scope

- 导出功能：python-docx (试卷), 前端/后端 PDF (报告), openpyxl (面板数据)
- 前端可视化：F7 学情面板 Teacher Dashboard，Chart.js 图表
- 关键页面：出题工作台、OCR 工作台、诊断面板前端

## Dependencies

依赖 `infra-foundation` T2 (LLM 可用) 和 `adaptive-diagnosis-engine` (面板需要真实诊断数据)

## Acceptance

- [ ] 老师可下载 Word 格式试卷（含答案版/不含答案版）
- [ ] 老师可导出 PDF 错题报告和学生报告
- [ ] 学情面板 `/teacher` 显示柱状图 + 饼图 + 趋势折线图
- [ ] 出题工作台页面可完成"选知识点 → 生成 → 预览 → 审核 → 导出"全流程
