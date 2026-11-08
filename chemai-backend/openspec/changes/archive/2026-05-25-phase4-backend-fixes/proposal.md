## Why

后端 6 个关键问题：`parent.py` 运算符优先级 bug 导致注册永远失败；`practice.py` 静默返回假数据；`vector_search.py` 伪造向量嵌入；`database.py` 重复 relationship；考试 finalize 未实现；`question.py` 命令注入风险。

## What Changes

| # | 文件 | 严重度 | 修复 |
|---|------|--------|------|
| 4.1 | `api/parent.py:106` | P0 | `== data.phone or data.email` → `|` SQL 操作符 |
| 4.2 | `api/practice.py` | P0 | 删除 mock 回退，返回明确错误 |
| 4.3 | `services/vector_search.py:241` | P1 | 标注 TODO，暂用关键词匹配 |
| 4.4 | `models/database.py:357-358` | P2 | 删重复 `class_obj` relationship |
| 4.5 | `api/exam.py:finalize_exam` | P2 | 实现 avg_score 计算 |
| 4.6 | `api/question.py:839` | P2 | `os.popen` → `subprocess.run(..., shell=False)` |

## Capabilities

### Modified Capabilities
- `parent-register`: 修复注册 bug
- `practice-api`: 删除 mock 数据回退
- `vector-search`: 修复伪嵌入
- `database-models`: 修复重复 relationship
