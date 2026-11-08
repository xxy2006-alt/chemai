# 六问题系统修复方案

> 日期: 2026-07-07 | 状态: 待实施

---

## 1. 陈思雨练习次数0

**根因:** `rebuild_all_students.py` 把 241901 放进 `PRESERVED` → 跳过数据生成。没有任何脚本给她造答题记录。

**修复:** 从 PRESERVED 里删掉 241901（只保留 242021 李世睿），重跑 rebuild_all_students.py。

**文件:** `tools/rebuild_all_students.py:15`

---

## 2. 所有学生最近活动一模一样

**根因:** 10 道共享题目内容简短 + activity 直接截取原始题目文本 `[0:40]` → 大家都显示同样的文字开头。不是 bug，是数据设计问题。

**修复:**
- 题库扩充到 20 道题（加 10 道真实高中化学题）
- Activity 描述改为可读格式：`"完成了一道关于盐类水解的选择题 ✓"` 而非 `"下列关于盐类水解的说法，正确的是"`
- `app/api/user.py:129` — `desc` 字段从原始 content 改为 `f"{'正确' if ok else '错误'}完成了{知识点}练习"`

**文件:** `app/api/user.py:122-129`, `tools/rebuild_all_students.py`

---

## 3. genPlan 没弹窗

**根因:** `students.html` 加载 `students.js?v=2`，浏览器缓存了旧版本。旧版 genPlan 没有 modal overlay。

**修复:** 版本号 `?v=2` → `?v=3`，强制浏览器重新下载。

**文件:** `frontend/pages/students.html:210`

---

## 4. 学习计划内容不像高中生

**根因:** `llm_service.py:214` 传给 DeepSeek 的 prompt 里没有任何"高中化学"上下文——连年级都没有。

**修复:**
```python
# 当前: "为学生{student_name}生成学习计划"
# 改为:
"你是资深高中化学教师，正在为高一学生{student_name}制定个性化学习计划。"
"学生水平：高中化学（高一），知识点范围为高考大纲。"
"请生成符合高中生认知水平和高考要求的学习计划。"
```
- 加上 `recent_performance` 数据（练习量、正确率）
- temperature 从 0.7 降到 0.3

**文件:** `app/services/llm_service.py:212-215`

---

## 5. 最近活动内容太low

**根因:** 同问题 2。activity desc = 原始题目内容截取 40 字符。而且题目标题格式是 `[盐类水解] 练习题 #3-1` —— 看起来很机械。

**修复:**
- 与问题 2 合并修复：activity desc 改为自然语言
- 题目内容扩充、改写，去掉 `[盐类水解]` 这种机械标记

**文件:** `app/api/user.py:129`, `tools/rebuild_all_students.py`

---

## 6. 学习计划没地方查看历史

**根因:** 两个孤立的存储系统
- `diagnosis.js` — localStorage key `chemai_plans`
- `students.js` — localStorage key `chemai_plan_{sid}`
- 没有一个统一的后端 API 列出所有计划

**修复:**
- 新增 `GET /api/diagnosis/learning-plans` — 返回所有学生的计划列表（从 SqliteStore + _plan_cache 聚合）
- `students.js` 发送计划后同步写入 `chemai_plans` localStorage key
- `diagnosis.js` 的"已生成计划"面板 → 调用后端 API 获取列表（服务端是数据源）
- 面板里显示：学生姓名、计划标题、生成时间、[查看] [重发] 按钮

**文件:** `app/api/diagnosis.py` (新端点), `frontend/js/diagnosis.js`, `frontend/js/students.js`

---

## 执行顺序

```
Step 1: 题库 + 题目内容 (问题 2+5, 底层数据)     — 20min
Step 2: LLM prompt 修复 (问题 4)                 — 5min
Step 3: 从 PRESERVED 删陈思雨 + 重跑 rebuild     — 5min
Step 4: students.js?v=3 强制刷新 (问题 3)        — 1min
Step 5: 计划历史 API + 前端面板 (问题 6)          — 20min
Step 6: 验证全部 6 项                              — 10min
```

**预估: ~1h**
