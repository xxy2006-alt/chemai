## Why

Agent 页面驱动协议已实现 exam-v2 和 diagnosis。teacher 面板 bridge 消费者未实现。

## What Changes

| 文件 | 改动 |
|------|------|
| `agent/gateway.py` | PAGE_ACTIONS 加 teacher 映射：`showClass`、`openWarnings` |
| `frontend/pages/teacher.html` | bridge 消费者：消费 navigate/action/populate，驱动班级定位、预警面板 |

### Teacher bridge 协议

```
navigate  {page:"teacher", params:{class_name:"高三1班"}}
populate  {target:"classStats", data:{...}}
populate  {target:"warnings", data:{...}}
action    {action:"showClass", payload:"高三1班"}
action    {action:"openWarnings", payload:""}
```

## Tasks

- [x] 1. gateway.py: PAGE_ACTIONS 加 teacher 条目
- [x] 2. teacher.html: bridge 消费者（showClass/openWarnings）
- [x] 3. E2E: "查看高三1班学情" → navigate 到 teacher + 定位班级

## Impact

- **Files changed**: 2 files, ~20 lines
- **Breaking**: 无
