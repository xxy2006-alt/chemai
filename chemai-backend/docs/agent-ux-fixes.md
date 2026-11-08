# Agent 体验四问题 — 修复方案

> 日期: 2026-07-07 | 状态: 待实施

---

## 问题 1: 历史对话 AI 输出丢失 (HIGH)

**根因:** `agent.js:145` 检查 `m.role === 'ai'`，但 `conversation.py:121` 返回 `role: 'assistant'`。角色名不匹配，AI 消息被静默过滤。

**修复:**
- `agent.js` `loadHistoryFromServer` — `m.role === 'ai'` → `m.role === 'assistant'`
- 同时兼容两种角色名 (加 `|| m.role === 'assistant'`)

**文件:** `frontend/js/agent.js` (1 行)

---

## 问题 2: 两个李世睿 (MEDIUM)

**根因:** `init_db.py` 的 STUDENT_NAMES[0] = "李世睿" → 202610101。`create_liyuxuan_data.py` 创建 202610201 = "李世睿"。同名同班。

**修复:**
- `init_db.py` — 把 STUDENT_NAMES[0] 从 "李世睿" 改成其他名字（如 "陈思雨"），避免跟演示数据冲突
- 或者 `create_liyuxuan_data.py` 把 202610101 重命名

**建议:** 改 init_db.py 的数据源。演示用的李世睿保留 202610201。

**文件:** `app/utils/init_db.py` (1 行)

---

## 问题 3: 诊断输出无渲染 (CRITICAL)

**根因:** `_dominant()` 函数体内无限递归。`replace_all` 操作把 `max(barrier.items(), ...)` 替换成了 `_dominant(barrier)`，但 `_dominant` 函数体内自己的调用也被替换了。

```python
# 改成:
def _dominant(barrier: dict) -> tuple:
    if not barrier:
        return ("unknown", 0)
    try:
        return max(barrier.items(), key=lambda x: x[1])  # ← 修: 还原原始逻辑
    except (ValueError, AttributeError):
        return ("unknown", 0)
```

**连锁影响:** 所有诊断工具 (diagnose_barrier, show_diagnosis, show_students, generate_learning_plan, generate_parent_report) 都会崩溃。修复这个一个函数即可。

**修复后验证:**
```python
assert _dominant({}) == ("unknown", 0)
assert _dominant({"concept": 0.5}) == ("concept", 0.5)
assert _dominant("invalid string") == ("unknown", 0)
```

**文件:** `agent/tools/diagnosis.py` (1 行, 第 32 行)

---

## 问题 4: "学习方案" 变成 "练习" (LOW)

**根因:** `generate_learning_plan` 的 "NOT for" 没有排除布置练习场景。`assign_adaptive_practice` 需要 `request_approval` 确认，LLM 在确认前被审批拦截导致流程卡住。

**修复:**
- `generate_learning_plan` docstring — NOT for 加: "NOT for 布置练习题/针对性习题 — 用 assign_adaptive_practice"
- `assign_adaptive_practice` docstring — NOT for 加: "NOT for 学习计划/学习方案 — 用 generate_learning_plan"
- `langgraph_agent_v2.py` SYSTEM_PROMPT — 加一句话: "学习计划(规划)和练习(做题)是不同的工具，按用户用词选择。"

**文件:** `agent/tools/diagnosis.py` (2 处 docstring), `agent/langgraph_agent_v2.py` (1 行)

---

## 执行顺序

```
Step 1: 修 _dominant 递归 (P0, 1行, 修完所有诊断工具恢复)
Step 2: 修 AI 消息角色 (HIGH, 1行)
Step 3: 修李世睿同名 (MEDIUM, 1行)
Step 4: 修工具 docstring 互斥 (LOW, 3行)
Step 5: 评测验证
```

**总改动: ~7 行, 3 个文件。**
