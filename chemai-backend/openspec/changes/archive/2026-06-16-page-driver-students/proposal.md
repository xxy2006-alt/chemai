## Why

Agent 页面驱动协议已实现 exam-v2 和 diagnosis。students 页面 bridge 消费者未实现——Agent 无法通过对话导航到学生管理页。

## What Changes

| 文件 | 改动 |
|------|------|
| `agent/gateway.py` | PAGE_ACTIONS 加 students 映射：`searchStudent`、`openDetail`、`openWeeklyReport`；TOOL_POPULATE_TARGET 加 weekly_report → `weeklyReport` 映射 |
| `frontend/pages/students.html` | bridge 消费者：消费 navigate/action/populate，驱动搜索、详情弹窗、周报 |

### Students bridge 协议

```
navigate  {page:"students", params:{student_name:"张三"}}
populate  {target:"studentDetail", data:{...学生详情...}}
populate  {target:"weeklyReport", data:{...周报...}}
action    {action:"searchStudent", payload:"张三"}
action    {action:"openDetail", payload:""}
action    {action:"openWeeklyReport", payload:""}
```

## Tasks

- [x] 1. gateway.py: PAGE_ACTIONS 加 students 条目 + populate 映射
- [x] 2. students.html: bridge 消费者（searchStudent/openDetail/openWeeklyReport）
- [x] 3. E2E: "搜索学生张三" → navigate 到 students + 搜索高亮

## Impact

- **Files changed**: 2 files, ~25 lines
- **Breaking**: 无
