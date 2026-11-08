## Spec: Student Barrier Guard

### 需求
- barrier_type 可能是对象或字符串，代码必须兼容两种类型
- 字符串类型时降级为空对象，不导致排序崩溃

### 验收
- `studentCard({barrier_type: {concept: 0.5, reading: 0.3, expression: 0.2}})` → 正常显示
- `studentCard({barrier_type: "concept"})` → 降级为 "未诊断"，不崩溃
- `openDetail()` 同样对 barrier_type 做类型防护
