# Proposal: adaptive-diagnosis-engine

## Summary

实现 F4 障碍诊断 LLM 增强、F5 自适应出题引擎真实算法、F2 全题型出题验证，构成 ChemAI 的核心"教学大脑"。

## Motivation

F4、F5 是 PRD 定义的 P0 功能，当前实现停留在 mock 数据阶段：
- `practice.py` 给所有学生推送相同题目，不区分障碍类型
- `diagnosis.py` 部分使用数据库但障碍判定逻辑简单
- `llm_service.py` 已有 `diagnose_barrier_type()` 和全题型 Prompt，但未在实际业务流中调用

## Scope

- `app/api/practice.py` — 自适应算法实现
- `app/api/diagnosis.py` — LLM 诊断集成
- `app/services/llm_service.py` — 全题型出题 Prompt 验证
- `app/models/database.py` — 可能需要加字段

## Dependencies

依赖 `infra-foundation` T2 (LLM httpx 改造完成)

## Acceptance

- [ ] `/api/practice/assign` 根据学生 barrier_type + 最近发展区生成不同题目
- [ ] 提交练习后 `student.barrier_type` 自动更新
- [ ] `/api/diagnosis/barrier/{class_id}/{exam_id}` 返回 LLM 分析结果（非 mock）
- [ ] 老师可推翻诊断结论，系统记录
- [ ] 选择题/填空/计算/实验/推断 5 种题型生成质量通过基本验证
