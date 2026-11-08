---
name: chemistry-diagnosis
description: 高中化学学生障碍类型诊断专家。诊断概念理解型/审题障碍型/表述障碍型，生成个性化干预建议和学习计划。
version: 1.0.0
author: ChemAI
license: MIT
metadata:
  hermes:
    tags: [chemistry, education, diagnosis, learning-barrier, teaching]
    related_skills: [chemistry-exam, chemistry-report]
---

# Chemistry Diagnosis Skill

> 高中化学学生障碍类型诊断专家

## Overview

本 Skill 提供三类学习障碍的精准诊断能力：
- **概念理解型 (concept)** - 基础概念薄弱，需加强概念辨析
- **审题障碍型 (reading)** - 题意理解偏差，需练习审题技巧
- **表述障碍型 (expression)** - 表述不规范，需强化专业用语

## Tools

本 Skill 通过调用 ChemAI FastAPI 后端实现功能：

### diagnosis_barrier_class

对班级所有学生进行障碍类型诊断。

```
diagnosis_barrier_class(class_id="xxx", exam_record_id="xxx")
```

Returns: 每个学生的障碍类型占比 + 班级分布

### diagnosis_barrier_student

获取单个学生的障碍类型详情。

```
diagnosis_barrier_student(student_id="xxx")
```

### diagnosis_plan_generate

为学生生成个性化学习计划（调用 LLM）。

```
diagnosis_plan_generate(student_id="xxx", barrier_type="concept", weak_kps=["盐类水解", "电离"])
```

### diagnosis_config_get

获取老师的障碍诊断配置。

```
diagnosis_config_get(teacher_id="xxx")
```

### diagnosis_config_update

更新老师的障碍诊断配置（阈值）。

```
diagnosis_config_update(teacher_id="xxx", concept_threshold=3, reading_threshold=2, expression_threshold=3)
```

## Diagnosis Rules

### 障碍类型判定

| 类型 | 特征 | 判定规则 |
|------|------|---------|
| concept | 错题集中在基础概念题 | 相关知识点连续错误 ≥3 次 |
| reading | 错题集中在长题干题目 | 题意理解偏差，关键信息抓取错误 |
| expression | 错题集中在填空/计算题 | 知道答案但表述不规范 |

### 干预建议

| 障碍类型 | 推荐干预策略 |
|---------|------------|
| concept | 加强基础概念复习，使用思维导图梳理知识体系，重点理解"为什么" |
| reading | 练习审题技巧，使用划线法提取题目关键信息 |
| expression | 加强规范化表述训练，参考标准答案的表述方式 |

## Output Format

```json
{
  "student_id": "学生ID",
  "student_name": "学生姓名",
  "barrier_type": {"concept": 0.3, "reading": 0.5, "expression": 0.2},
  "dominant_barrier": "reading",
  "weak_knowledge_points": ["盐类水解", "电离"],
  "recommended_intervention": "建议练习审题技巧...",
  "last_updated": "2026-04-14"
}
```

## Workflow

```
1. 接收诊断请求 (class_id + exam_record_id 或 student_id)
2. 获取学生答题数据 (StudentAnswer 表)
3. 统计各类型错误分布
4. 确定主要障碍类型
5. 识别薄弱知识点
6. 生成干预建议
7. （可选）生成个性化学习计划
```

## Limitations

- 不处理非化学科目题目
- 不提供主观题评分
- 学习计划需教师审核后执行
