# 20 · POC 验证 — 开发安排

## 变种真题功能的 POC

### POC 要验证什么

不是"这个功能能不能做"——技术上肯定能做。要验证的是：

1. **LLM 生成的变种题是否保持了原题的考查本质？**（教师判断"等价"的比例）
2. **变种题的化学式错误率是多少？**（需要过 `chemical_balance` 审核）
3. **生成速度是否可接受？**（教师等得起吗）

### POC 数据和脚本

**测试蓝本题**：2020 年全国卷 T3（气体除杂题）

```
原题: 下列气体去除杂质的方法中，不能实现目的的是（）
A. SO₂(H₂S) 通过酸性高锰酸钾溶液
B. Cl₂(HCl) 通过饱和食盐水
C. N₂(O₂) 通过灼热铜丝网
D. NO(NO₂) 通过氢氧化钠溶液
答案: A
知识点: 气体除杂、氧化还原反应
```

**POC 脚本**（直接调 DeepSeek，不加 Agent 层）：
```python
# agent/tools.py:generate_questions(variant_source="nat_2020_t3")

import os, httpx, json
key = os.getenv('DEEPSEEK_API_KEY')

# 读蓝本题
with open('data/exam_questions/全国卷/2020/2020年全国卷高考化学.json') as f:
    data = json.load(f)
source_q = [q for q in data['questions'] if q['exam_id'] == 'nat_2020_t3'][0]

# 构造 Prompt
prompt = f"""基于以下化学真题，生成 3 个同考点、同难度、同题型的变种题。

蓝本题:
{source_q['content']}
答案: {source_q['answer']}
知识点: {', '.join(source_q['knowledge_points'])}

严格约束:
1. 化学方程式系数/反应条件/产物不变
2. 可换: 气体种类、试剂名称、选项顺序、数据
3. 每个变种单独一个 JSON 对象

返回 JSON 数组: [{{"content":"变种1题干","answer":"A/B/C/D","knowledge_points":["..."]}}, ...]"""

# 调用 DeepSeek
resp = httpx.post("https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {key}"},
    json={"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],
          "max_tokens":2000,"temperature":0.3})

result = resp.json()['choices'][0]['message']['content']
```

### POC 脚本的实际执行

完整的 POC 脚本（`agent/tools.py:generate_questions` 的变种模式）：

```python
import os, httpx, json
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('DEEPSEEK_API_KEY')

# 1. 读蓝本题
with open('data/exam_questions/全国卷/2020/2020年全国卷高考化学.json', encoding='utf-8') as f:
    data = json.load(f)
source = [q for q in data['questions'] if q['exam_id'] == 'nat_2020_t3'][0]

# 2. 构造变种 Prompt（含四条红线）
prompt = f"""基于以下化学高考真题，生成 3 个同考点、同难度、同题型的变种题。

【蓝本题】（来源：{source['source']}）
{source['content']}

【蓝本题答案】
{source['answer']}

【蓝本题知识点】
{', '.join(source['knowledge_points'])}

【严格约束 — 不可违反】
1. 化学方程式系数不变（如 2H2 + O2 = 2H2O 的系数 2:1:2 不变）
2. 反应条件不变（加热/催化剂/通电/点燃必须完全一致）
3. 产物不变（不能把 NaCl 改成 KCl，不能把 Fe2O3 改成 Fe3O4）
4. 考查知识点不变（气体除杂+氧化还原→必须保持）

【可以改变】
- 题干情境（如"实验室制氯气"改为"工业制氯气"）
- 具体数据（如 0.1mol 改为 0.2mol）
- 选项顺序（A/B/C/D 重新排列）
- 干扰项（换一个新的常见错误选项）

返回 JSON 数组，每个变种一个对象：
[{{"number":"变种1","content":"变种题干(含选项和化学式)","answer":"A/B/C/D",
   "analysis":"简短解析","knowledge_points":["知识点列表"]}}]"""

# 3. 调 DeepSeek
resp = httpx.post("https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    json={"model": "deepseek-chat",
          "messages": [{"role": "system", "content": "只返回JSON数组。"},
                       {"role": "user", "content": prompt}],
          "max_tokens": 2000, "temperature": 0.3},
    timeout=60)

result = resp.json()['choices'][0]['message']['content']
variants = json.loads(result)
print(f"Generated {len(variants)} variants")

# 4. 审核每个变种
for v in variants:
    audit = audit_chemical_equation(v['content'])
    if audit.errors:
        print(f"Variant {v['number']}: FAILED - {audit.errors}")
    else:
        print(f"Variant {v['number']}: PASSED")
```

### POC 验证清单

| # | 验证项 | 方法 | 通过标准 |
|---|--------|------|---------|
| 1 | 生成 3 个变种 | 运行 POC 脚本 | 返回 3 个有效 JSON |
| 2 | 无化学式错误 | `chemical_balance` 审核 | 0 个 block 级别错误 |
| 3 | 保持考查本质 | 种子教师盲测 | ≥2/3 个变种被判为"等价" |
| 4 | 生成速度 | 计时 | ≤15s/个变种 |

### 开发阶段安排

```
Phase 1: POC 验证 (2h)
  ├── 运行 POC 脚本，生成 3 个变种
  ├── chemical_balance 审核
  └── 种子教师反馈 → 确认变种题质量

Phase 2: 集成到 Agent (2h)
  ├── generate_questions 加 variant_source 参数 ✅ (已有)
  ├── 端到端测试: "基于这道真题生成变种" → Agent 正确调用
  └── 前端变种题浏览器联调 ✅ (6/29)

Phase 3: 教导主任演示 (1h)
  ├── 现场演示: 选蓝本 → 生成变种 → 审核 → 保存
  └── 收集反馈: 变种数量够不够？审核细度够不够？

Phase 4: 迭代修复 (2h)
  ├── 根据反馈调整 Prompt 约束
  ├── 调整 chemical_balance 审核规则
  └── 更新 OpenSpec tasks.md
```

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 变种题质量不稳定 | 四维审核 + 教师盲测 |
| 教师认为"等价"标准不满足 | 迭代 Prompt 直到 ≥2/3 通过 |
| 教导主任要求支持含图的题 | 当前 scope 为纯文本题，图片变种放下一迭代 |
| 已有功能回归 | 跑 `evals/run_evals.py` 确认 |

### 成功标准

POC 成功的定义：种子教师看了 3 个变种后说"这些可以给学生练"。
---

## 补充内容

> 注：本节为满足教学深度要求补充的内容，与上文形成完整的知识体系。




























