---
name: chemistry-exam
description: 高中化学出题与安全审核专家。AI生成题目，四维安全审核（配平/条件/产物/结构），历年真题关联，人工二审机制。
version: 1.0.0
author: ChemAI
license: MIT
metadata:
  hermes:
    tags: [chemistry, exam, question-generation, audit, education]
    related_skills: [chemistry-diagnosis, chemistry-report]
---

# Chemistry Exam Skill

> 高中化学出题与安全审核专家

## Overview

本 Skill 是高中化学出题的核心引擎，具备：
- **AI 出题** - 基于知识点和难度生成题目
- **四维安全审核** - 配平/条件/产物/结构
- **历年真题关联** - RAG 增强生成
- **人工二审机制** - 所有题目必须老师确认

## The Iron Law

```
系数未配平的方程式 → 直接 BLOCKED
所有题目必须老师确认后才能发布
```

## Tools

### exam_generate

使用 AI 生成化学练习题目。

```
exam_generate(knowledge_points=["盐类水解", "电离"], difficulty="medium", quantity=10)
```

Returns: 题目列表 + 四维审核报告

### exam_audit

对单道题目进行四维安全审核。

```
exam_audit(question_content="题目内容...", options=["A. xxx", "B. xxx"])
```

### exam_search_historical

检索历年真题库。

```
exam_search_historical(source="全国卷2024", year=2024, knowledge_point="盐类水解")
```

### exam_find_similar

查找与指定知识点相似的历年真题。

```
exam_find_similar(knowledge_points=["盐类水解"], difficulty="medium", limit=5)
```

### exam_manual_select

手动选题（教师从历年真题库选择）+ AI 安全审核。

```
exam_manual_select(exam_ids=["national_2024_t15", "national_2024_t16"])
```

### exam_import

老师自助导入题目到真题库。

```
exam_import(source_name="2024年长沙市一模", year=2024, questions=[...])
```

### exam_balance_check

化学方程式配平检查（独立工具）。

```
exam_balance_check(equation="2H2 + O2 → 2H2O")
```

## Four-Dimensional Audit

| 维度 | 检查内容 | 判定规则 |
|------|---------|---------|
| **F1: 系数配平** | 方程式两边原子数相等 | 配平错误 → **blocked** |
| **F2: 反应条件** | 加热/点燃/催化剂等标注 | 缺条件 → warning |
| **F3: 产物稳定性** | 产物是否符合化学规律 | 不稳定产物 → warning |
| **F4: 分子结构** | 有机物结构简式正确性 | 结构错误 → warning |

## Audit Report Format

```json
{
  "question_id": "ai_1713000000_0",
  "content": "题目内容",
  "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],
  "answer": "A",
  "knowledge_points": ["盐类水解", "电离"],
  "difficulty": "medium",
  "coefficient_audit": {
    "dimension": "coefficient",
    "status": "passed",
    "message": "方程式已配平"
  },
  "condition_audit": {
    "dimension": "condition",
    "status": "passed",
    "message": "反应条件正确"
  },
  "product_audit": {
    "dimension": "product",
    "status": "passed",
    "message": "产物判断通过"
  },
  "structure_audit": {
    "dimension": "structure",
    "status": "passed",
    "message": "结构检查通过"
  },
  "overall_status": "passed",
  "trap_hints": ["注意区分\"水解\"与\"电离\"的概念"],
  "historical_matches": [
    {
      "source": "全国卷2024",
      "year": 2024,
      "question_number": "T15",
      "similarity": 0.85
    }
  ]
}
```

## Audit Conclusion

| 状态 | 含义 | 后续操作 |
|------|------|---------|
| **passed** | 审核通过 | 等待老师确认 |
| **warning** | 有警告但可接受 | 老师需确认 |
| **blocked** | 审核拒绝 | 必须修改后重新审核 |

## Chemical Equation Rules

### 配平规则

- 方程两边每种元素的原子数必须相等
- 使用 → 或 = 表示反应方向
- 可逆反应使用 ⇌ 或 \ Equilibrium

### 反应条件标注

| 反应类型 | 必要条件 |
|---------|---------|
| 燃烧反应 | 必须标注"点燃" |
| 催化反应 | 建议标注催化剂 |
| 加热反应 | 标注"△"或"加热" |
| 电解 | 标注"电解" |

### 化学式格式

- 元素符号首字母大写：Fe, Cu, Na
- 上下标使用 LaTeX：H_2O, Ca^{2+}
- 有机物使用简写：CH_4, C_2H_5OH

## Manual Review Workflow

```
AI 生成题目 → 四维安全审核 → 老师二审 → 发布/修改
```

所有 AI 生成题目必须经过人工审核，不可自动发布。

## RAG Enhancement

当历年真题库中有 >=3 道相似题目时，AI 会基于这些真题生成变种题，并标注：
- `is_from_rag: true`
- `source_question_id`: 源真题 ID
- `similarity`: 相似度

## Limitations

- 不处理大学化学内容
- 不生成涉及政治/宗教/色情的题目
- 计算题步骤分需明确标注
