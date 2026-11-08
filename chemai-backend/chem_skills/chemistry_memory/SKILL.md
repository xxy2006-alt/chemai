---
name: chemistry-memory
description: ChemAI 学情历史记忆管理系统。跨会话记住学生学习状态、障碍类型、历史表现，实现真正的个性化教学。
version: 1.0.0
author: ChemAI
license: MIT
metadata:
  hermes:
    tags: [memory, student-profile, learning-history, personalization]
    related_skills: [chemistry-diagnosis, chemistry-notification]
---

# Chemistry Memory Skill

## Overview

ChemAI 的学情历史记忆管理系统，使 Agent 能够跨会话记住学生的学习状态，实现真正的个性化教学。

## Core Capabilities

- **学生画像管理** - 记录学生学习特点、障碍类型、薄弱知识点
- **障碍历史追踪** - 记录每次诊断的结果和变化趋势
- **薄弱知识点追踪** - 按错误频率排序，持续跟踪掌握情况
- **班级集体记忆** - 班级共性障碍、学情趋势
- **FTS5 全文搜索** - 跨会话搜索学情历史

## Memory Types

### Student Memory
- `profile.md` - 学生画像（LLM摘要）
- `barrier_history.md` - 障碍类型历史
- `weak_kps.md` - 薄弱知识点追踪
- `practice_history.md` - 练习/考试历史
- `preferences.md` - 学习偏好

### Class Memory
- `summary.md` - 班级学情摘要
- `common_barriers.md` - 班级共性障碍
- `trends.md` - 学情趋势

### Teacher Memory
- `config.md` - 个性化配置
- `teaching_style.md` - 教学风格偏好

## Event Triggers

记忆会在以下事件发生时自动更新：
- `exam_completed` - 考试完成 → 更新练习历史
- `diagnosis_completed` - 诊断完成 → 更新障碍历史、薄弱知识点、画像
- `practice_completed` - 练习完成 → 更新练习历史
- `learning_plan_applied` - 学习计划应用 → 更新画像

## Storage Structure

```
hermes-memory/
├── students/{student_id}/
│   ├── profile.md
│   ├── barrier_history.md
│   ├── weak_kps.md
│   ├── practice_history.md
│   └── preferences.md
├── classes/{class_id}/
│   ├── summary.md
│   ├── common_barriers.md
│   └── trends.md
├── teachers/{teacher_id}/
│   ├── config.md
│   └── teaching_style.md
└── sessions/
    └── search.db (FTS5)
```
