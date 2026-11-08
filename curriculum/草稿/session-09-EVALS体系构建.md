# Session 9 · EVALS 体系构建

## 产出物

- `evals/conftest.py` — 共享基础设施：EvalReport(14维度) + 轨迹提取 + 22 种断言引擎 + 回归基线管理
- `evals/baseline/golden_scenarios.py` — 基线场景：35 个 Golden 场景（路由/工具/工作流/约束）
- `evals/boundary/edge_scenarios.py` — 边界场景：20 个边界+异常场景
- `evals/regression/known_defects.py` — 已知缺陷回归：5 个已修复 bug 的防复发测试
- `evals/cross_role/role_scenarios.py` — 跨角色场景：教师/学生/家长 3 角色路由
- `evals/sse/test_sse_streaming.py` — SSE 流式结构：事件顺序/字段完整性/心跳
- `evals/gateway/test_gateway_router.py` — Gateway 路由：24 个关键词路由用例
- `evals/consistency/test_passk.py` — Pass@k 一致性：关键场景 × 5 次重复，验证行为稳定性
- `evals/plan/test_plan_coherence.py` — 计划连贯性：循环检测/死路检测/过早终止
- `evals/checkpoint/test_checkpoint_replay.py` — Checkpoint Replay：确定性回归 + 轨迹哈希
- `evals/run_evals.py` — 全维度编排器 + CI 门禁模式 + 生产告警阈值
- `docs/evals-design.md` — EVALS 设计文档（14 个评测维度 + 22 种断言 + PRD 失败模式覆盖矩阵 + 业界对标）

## 前置条件

- Session 8 的 POC 全部通过（LLM 化学能力 + Agent 路由能力已验证可行）
- Session 6 的 PRD 就绪（含 13 种失败模式 + 10 条行为约束 + 三档性能阈值）
- 项目已有旧版评测文档作为输入参考：`评测文档/` 目录（v1.0 总览 + v2.0 Agent测评体系 + F1-F7 功能测试用例 + 化学审核专项 + LLM 专项评测 + 性能/安全方案）
- Claude Code 可用
- 理解：**EVALS 在开发前建立，不是开发后补测。** 本节课会整合旧评测文档中的功能测试用例和 LLM 质量指标，将其映射到 14 维度轨迹评测体系中——旧文档测"产出对不对"，新课测"行为对不对"，两者互补。

## 项目背景（给学生的概述）

传统软件测试是"写代码→写测试→修bug"。AI Agent 开发不能走这条路，因为 LLM 是非确定性的——改一行 prompt 可能彻底改变 Agent 的路由行为。

ChemAI EVALS 体系的核心理念来自业界共识：**测轨迹不测文本、按维度门禁不按总分、离线+在线双轨、生产失败回灌数据集。**

EVALS 覆盖 14 个维度（对标业界标准）：

```
维度 1:  路由准确性    → Gateway 关键词路由 24 用例 + Intent 分类器
维度 2:  工具调用      → 6 子专家工具链，参数/顺序/去重
维度 3:  工作流链路    → 多工具链、审批流、中断恢复、跨会话上下文
维度 4:  行为约束      → 10 条 PRD 约束（配平100%、不编造真题、学生引导式教学等）
维度 5:  边界处理      → 缺失信息、模糊意图、无效输入、不存在的资源
维度 6:  错误恢复      → 工具调用失败、LLM 超时、数据库异常
维度 7:  跨角色        → 教师/学生/家长 3 角色路由和权限
维度 8:  SSE 流式      → 事件结构、顺序、字段完整性、心跳
维度 9:  一致性        → Pass@k 重复稳定性、语义等价一致性、Checkpoint Replay 确定性
维度 10: 结果利用      → Agent 是否正确使用了工具返回的数据（而非忽略/篡改）
维度 11: 计划连贯性    → 无循环、无死路、无过早终止、工具调用深度合理
维度 12: 状态转换      → LangGraph 节点级状态转换正确性（state_before→node→state_after→edge）
维度 13: 性能与成本    → 延迟基准、API 调用次数、Token 消耗
维度 14: 回归+在线监控 → 基线快照对比、已知缺陷防复发、生产告警阈值、失败回灌
```

三层结构组织这 14 个维度：
- **基线层**：维度 1-4（正常条件下核心功能正确性）
- **边界层**：维度 5-6、10-12（异常条件 + 结果利用 + 计划 + 状态转换）
- **回归层**：维度 7-9、13-14（跨角色/SSE/一致性/性能/退化检测/在线监控）

### 旧评测文档 → 新 EVALS 体系整合

项目中已有 `评测文档/` 目录，含 21 份评测文档（v1.0 总览 + v2.0 Agent测评体系 + F1-F7 功能测试用例 + 化学审核专项 + LLM专项 + 性能/安全方案）。这些旧文档按**功能模块**组织，测的是"产出对不对"（输出质量）。新课 EVALS 按**行为维度**组织，测的是"行为对不对"（轨迹正确性）。两者互补：

| 旧评测文档 | 内容 | 映射到新课维度 | 整合方式 |
|-----------|------|--------------|---------|
| `评测清单_v1.0_总览.md` | 8 项 LLM 核心指标 + 7 功能模块评测清单 | 维度 1-4 (基线) | **作为场景定义的输入**：F1-F7 的测试用例直接转化为 baseline 场景的 input/expected |
| `ChemAI_Agent_v2.0_测评体系.md` | Hermes Skills + Agent 协同评测 | 维度 3 (工作流) + 维度 12 (状态转换) | **作为多工具链场景的参考**：Skills 协作流程映射到 workflow 场景 |
| `01_功能测试用例集/F1-F7/` | 每模块 20-30 条黑盒测试用例 | 维度 2 (工具调用) | **逐条转化为 tool_arg_contains 断言** |
| `02_化学方程式审核专项/` | 配平审核 + 反应条件 + 产物错误 测试集 | 维度 4 (行为约束) | **直接嵌入 constraint 场景**：配平100% → constraint_balance_audit_required |
| `03_LLM专项评测/` | 出题质量 + 安全审核 + 障碍诊断 + 真题关联 评测集 | 维度 2 (工具调用) + 维度 10 (结果利用) | **LLM 质量指标转化为 result_utilization 断言** |
| `04_性能测试/` | 性能基准测试方案 | 维度 13 (性能) | **S16 性能基线使用** |
| `05_安全测试/` | 安全与隐私测试方案 | 维度 7 (跨角色) | **直接嵌入 role_scenarios** |
| `00_测试报告/` | 3 份实际测试报告 | 维度 14 (回归) | **作为 known_defects 场景的 bug 来源** |

**整合原则**：旧文档不删不改——它们保留在 `评测文档/` 作为详细的**参考数据**。新课 EVALS 从旧文档中提取测试用例，转化为 14 维度的轨迹断言场景。学生在写每个维度场景时，先读对应的旧评测文档，再写场景定义。

---

## 操作步骤

### 步骤 1：搭建共享基础设施

**目标**：创建 EVALS 目录结构和共享模块

**提示词**（复制到 Claude Code）：

```
创建 ChemAI EVALS 体系的完整目录结构和共享基础设施。

## 目录结构

```
evals/
├── conftest.py                  # 共享基础设施
├── run_evals.py                 # 全维度编排器
├── baseline/
│   ├── __init__.py
│   └── golden_scenarios.py     # 35 个基线场景
├── boundary/
│   ├── __init__.py
│   └── edge_scenarios.py       # 20 个边界场景
├── regression/
│   ├── __init__.py
│   └── known_defects.py        # 已知缺陷回归
├── cross_role/
│   ├── __init__.py
│   └── role_scenarios.py       # 跨角色场景
├── sse/
│   ├── __init__.py
│   └── test_sse_streaming.py   # SSE 流式结构测试
└── gateway/
    ├── __init__.py
    └── test_gateway_router.py  # Gateway 路由测试
```

## evals/conftest.py

### EvalReport 类（支持 10 维度标记）

```python
import json, os, time
from dataclasses import dataclass, field
from typing import Optional, List

VALID_DIMENSIONS = [
    "routing",        # 维度1: 路由准确性
    "tool_call",      # 维度2: 工具调用
    "workflow",       # 维度3: 工作流链路
    "constraint",     # 维度4: 行为约束
    "edge_case",      # 维度5: 边界处理
    "error_recovery", # 维度6: 错误恢复
    "cross_role",     # 维度7: 跨角色
    "sse",            # 维度8: SSE流式
    "performance",    # 维度9: 性能与成本
    "regression",     # 维度10: 回归
]

@dataclass
class EvalResult:
    name: str
    layer: str          # "baseline" | "boundary" | "regression"
    dimension: str      # 10 维度之一
    passed: bool
    details: str = ""
    latency_ms: float = 0.0
    api_calls: int = 0
    tools_called: List[str] = field(default_factory=list)

class EvalReport:
    def __init__(self):
        self.results: List[EvalResult] = []

    def add(self, name, layer, dimension, passed, details="", latency_ms=0.0, api_calls=0, tools_called=None):
        self.results.append(EvalResult(
            name=name, layer=layer, dimension=dimension, passed=passed,
            details=details, latency_ms=latency_ms, api_calls=api_calls,
            tools_called=tools_called or []
        ))

    @property
    def passed_count(self): return sum(1 for r in self.results if r.passed)
    @property
    def failed_count(self): return sum(1 for r in self.results if not r.passed)
    @property
    def total(self): return len(self.results)

    def dimension_summary(self, dim):
        """按维度汇总"""
        results = [r for r in self.results if r.dimension == dim]
        if not results: return None
        passed = sum(1 for r in results if r.passed)
        return {"dimension": dim, "total": len(results), "passed": passed, "rate": passed/len(results)}

    def layer_summary(self, layer):
        results = [r for r in self.results if r.layer == layer]
        if not results: return None
        passed = sum(1 for r in results if r.passed)
        return {"layer": layer, "total": len(results), "passed": passed}

    def summary(self):
        """按维度和层双维度汇总"""
        print(f"\n{'='*70}")
        print(f"  ChemAI EVALS — 10 维度 × 3 层")
        print(f"{'='*70}")
        # 按维度
        for dim in ["routing","tool_call","workflow","constraint","edge_case",
                     "error_recovery","cross_role","sse","performance","regression"]:
            s = self.dimension_summary(dim)
            if s:
                bar = "█" * int(s["rate"] * 20) + "░" * (20 - int(s["rate"] * 20))
                print(f"  [{dim:15s}] {bar} {s['passed']:2d}/{s['total']:<2d} ({s['rate']:.0%})")
            else:
                print(f"  [{dim:15s}] (empty)")
        print(f"{'='*70}")
        print(f"  Total: {self.total} | Passed: {self.passed_count} | Failed: {self.failed_count}")
        print(f"{'='*70}")
        failed = [r for r in self.results if not r.passed]
        if failed:
            print(f"\n  Failed ({len(failed)}):")
            for r in failed:
                print(f"    [{r.dimension}] {r.name}: {r.details}")

    def to_dict(self):
        return {
            "total": self.total, "passed": self.passed_count, "failed": self.failed_count,
            "by_dimension": {dim: self.dimension_summary(dim) for dim in VALID_DIMENSIONS},
            "by_layer": {layer: self.layer_summary(layer) for layer in ["baseline","boundary","regression"]},
            "results": [{"name": r.name, "layer": r.layer, "dimension": r.dimension,
                         "passed": r.passed, "details": r.details} for r in self.results]
        }
```

### 轨迹提取 + 18 种断言引擎 + 回归基线引擎

（保持现有的 parse_tool_calls / extract_tool_names / extract_trajectory / check_assertion / capture_baseline / compare_to_baseline 实现，见上一版本）

创建完整的 evals/conftest.py。需要包含：EvalReport（10 维度版）、轨迹提取工具、18 种断言引擎、回归基线管理。
```

**验证**：
- [ ] `evals/` 目录结构完整（6 个子目录 + conftest.py + run_evals.py）
- [ ] EvalReport 支持 10 维度标记和双维度汇总
- [ ] 18 种断言类型全部可用
- [ ] 回归基线引擎可用

---

### 步骤 2：定义基线 Evals —— 35 个场景，覆盖 4 个维度

**目标**：定义完整的基线评测场景集。**输入参考：`评测文档/01_功能测试用例集/F1-F7/` + `评测文档/03_LLM专项评测/`**

**提示词**（复制到 Claude Code）：

```
在开始写场景之前，先读取以下旧评测文档作为参考：
- 评测文档/01_功能测试用例集/F2_AI出题审核测试用例.md → 提取典型出题场景
- 评测文档/01_功能测试用例集/F4_障碍诊断测试用例.md → 提取诊断场景
- 评测文档/01_功能测试用例集/F6_历年真题关联测试用例.md → 提取搜索场景
- 评测文档/03_LLM专项评测/AI出题质量评测集.md → 提取出题参数验证
- 评测文档/03_LLM专项评测/安全审核质量评测集.md → 提取配平/条件/产物审核

这些旧文档中的测试用例是场景定义的"原材料"——将黑盒测试用例转化为轨迹断言场景。

创建 evals/baseline/golden_scenarios.py —— 35 个基线场景，覆盖维度 1-4。

## 维度 1：路由准确性（8 个场景）

验证 Gateway 关键词预路由 + Coordinator 二次确认是否将用户输入路由到正确的子专家。

```python
BASELINE_SCENARIOS = {
    # ===== 维度1: 路由准确性 (routing) =====
    "route_tutor_redox": {
        "input": "氧化还原反应的本质是什么",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "chemistry_tutor"},
            {"type": "not_tool_called", "tool": "generate_questions"},
            {"type": "no_error"},
        ]
    },
    "route_exam_generate": {
        "input": "出3道氧化还原的选择题",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "not_tool_called", "tool": "chemistry_tutor"},
        ]
    },
    "route_search_exam": {
        "input": "找2020年全国卷的化学题",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "search_exam_bank"},
            {"type": "not_tool_called", "tool": "web_search"},
        ]
    },
    "route_web_search": {
        "input": "搜索2025年诺贝尔化学奖得主",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "web_search"},
        ]
    },
    "route_diagnosis": {
        "input": "诊断学生202610101的学习障碍",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "diagnose_barrier"},
        ]
    },
    "route_balance": {
        "input": "配平 KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "balance_equation"},
        ]
    },
    "route_experiment": {
        "input": "模拟钠和水的反应实验",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "simulate_experiment"},
        ]
    },
    "route_weekly_report": {
        "input": "生成本周学情周报",
        "layer": "baseline", "dimension": "routing",
        "assertions": [
            {"type": "tool_called", "tool": "weekly_report"},
        ]
    },
```

## 维度 2：工具调用正确性（8 个场景）

验证每个子专家的工具调用参数和输出。

```python
    # ===== 维度2: 工具调用 (tool_call) =====
    "tool_generate_with_params": {
        "input": "出3道氧化还原反应的选择题，中等难度",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "tool_arg_contains", "tool": "generate_questions", "value": "氧化还原"},
            {"type": "tool_arg_contains", "tool": "generate_questions", "value": "3"},
            {"type": "tool_count", "lte": 5},
        ]
    },
    "tool_save_question": {
        "input": "把刚才生成的题目保存到题库",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "save_question"},
        ]
    },
    "tool_create_variant": {
        "input": "以2020全国卷T3为蓝本，生成2个变种题",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "create_variant"},
        ]
    },
    "tool_diagnose_with_params": {
        "input": "诊断学生202610101的化学学习障碍，重点关注氧化还原",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "diagnose_barrier"},
            {"type": "tool_arg_contains", "tool": "diagnose_barrier", "value": "202610101"},
        ]
    },
    "tool_adaptive_practice": {
        "input": "根据学生202610101的诊断结果推荐自适应练习题",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "assign_adaptive_practice"},
            {"type": "tool_arg_contains", "tool": "assign_adaptive_practice", "value": "202610101"},
        ]
    },
    "tool_balance_complex": {
        "input": "配平 Cu + HNO3(稀) = Cu(NO3)2 + NO + H2O",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "balance_equation"},
            {"type": "has_text_response"},
            {"type": "no_error"},
        ]
    },
    "tool_search_with_filters": {
        "input": "找2020-2022年全国卷的有机化学选择题",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "search_exam_bank"},
            {"type": "tool_arg_contains", "tool": "search_exam_bank", "value": "有机"},
        ]
    },
    "tool_tutor_guided_teaching": {
        "input": "盐类水解怎么学",
        "layer": "baseline", "dimension": "tool_call",
        "assertions": [
            {"type": "tool_called", "tool": "chemistry_tutor"},
            {"type": "has_text_response"},
        ]
    },
```

## 维度 3：工作流链路（12 个场景）

验证多工具链、审批流、中断恢复、跨会话上下文等复杂工作流。

```python
    # ===== 维度3: 工作流链路 (workflow) =====
    # 多工具链
    "workflow_search_then_generate": {
        "input": "找一道氧化还原的高考题，然后出一道类似的题",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "search_exam_bank"},
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "tool_trajectory_order", "subsequence": ["search_exam_bank", "generate_questions"]},
        ]
    },
    "workflow_diagnose_then_practice": {
        "input": "诊断学生202610101的障碍，然后推荐对应的练习题",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "diagnose_barrier"},
            {"type": "tool_called", "tool": "assign_adaptive_practice"},
            {"type": "tool_trajectory_order", "subsequence": ["diagnose_barrier", "assign_adaptive_practice"]},
        ]
    },
    "workflow_generate_then_save": {
        "input": "出2道电化学选择题，保存到题库",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "tool_called", "tool": "save_question"},
            {"type": "tool_trajectory_order", "subsequence": ["generate_questions", "save_question"]},
        ]
    },
    "workflow_scan_then_diagnose": {
        "input": "上传了月考答题卡，帮我分析班级错题分布",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "exam_stats"},
            {"type": "has_text_response"},
        ]
    },

    # 审批流（出题→审核→确认保存）
    "workflow_exam_approval": {
        "input": "出一道氧化还原选择题",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "interrupt_triggered"},
        ],
        "comment": "出题必须触发教师审批中断"
    },
    "workflow_approval_resume": {
        "input": "这道题没问题，确认保存",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "save_question"},
        ],
        "comment": "审批通过后应执行保存"
    },
    "workflow_approval_reject": {
        "input": "这道题不行，重新出一道",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
        ],
        "comment": "审批驳回后应重新生成"
    },

    # 导航/面板
    "workflow_nav_to_exam": {
        "input": "打开出题工作台",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "route", "route": "exam_workbench"},
        ]
    },
    "workflow_nav_to_diagnosis": {
        "input": "查看学情诊断面板",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "route", "route": "diagnosis"},
        ]
    },
    "workflow_nav_to_students": {
        "input": "打开学生管理页面",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "route", "route": "students"},
        ]
    },

    # 多轮上下文
    "workflow_multiturn_context": {
        "input": "刚才那道题的知识点是什么",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "tool_called", "tool": "chemistry_tutor"},
            {"type": "has_text_response"},
        ],
        "comment": "验证跨轮次上下文保持（需要在对话历史中有'刚才的题'）"
    },
    "workflow_multiturn_followup": {
        "input": "那道题能不能改简单一点",
        "layer": "baseline", "dimension": "workflow",
        "assertions": [
            {"type": "has_text_response"},
        ],
        "comment": "验证对话历史中的题目信息仍可访问"
    },
```

## 维度 4：行为约束（7 个场景）

验证 PRD 中定义的 10 条行为约束在 Agent 行为中是否正确实现。

```python
    # ===== 维度4: 行为约束 (constraint) =====
    "constraint_no_fabricated_exam": {
        "input": "这道题是2023年全国甲卷的第5题",
        "layer": "baseline", "dimension": "constraint",
        "assertions": [
            {"type": "not_tool_called", "tool": "save_question"},
        ],
        "comment": "不能保存编造的真题引用——必须先通过 search_exam_bank 验证"
    },
    "constraint_student_guided_teaching": {
        "input": "氧化还原反应的本质是什么",
        "layer": "baseline", "dimension": "constraint",
        "role": "student",
        "assertions": [
            {"type": "tool_called", "tool": "chemistry_tutor"},
            {"type": "has_text_response"},
        ],
        "comment": "学生角色必须使用引导式教学（不直接给答案）"
    },
    "constraint_balance_audit_required": {
        "input": "生成一道含化学方程式的题目",
        "layer": "baseline", "dimension": "constraint",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "tool_called", "tool": "balance_equation"},
        ],
        "comment": "生成的题目包含方程式时，必须经过 chemical_balance 审核"
    },
    "constraint_teacher_not_student_mode": {
        "input": "直接告诉我氧化还原的答案",
        "layer": "baseline", "dimension": "constraint",
        "role": "teacher",
        "assertions": [
            {"type": "has_text_response"},
        ],
        "comment": "教师角色不应被引导式教学约束——教师需要直接答案"
    },
    "constraint_no_experiment_for_student": {
        "input": "帮我模拟钠和水反应的实验",
        "layer": "baseline", "dimension": "constraint",
        "role": "student",
        "assertions": [
            {"type": "not_tool_called", "tool": "simulate_experiment"},
        ],
        "comment": "虚拟实验仅供教师使用"
    },
    "constraint_report_contains_encouragement": {
        "input": "生成学生202610101的学习报告",
        "layer": "baseline", "dimension": "constraint",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "text_contains_one_of", "keywords": ["进步", "加油", "努力", "提升", "掌握"]},
        ],
        "comment": "学生报告中必须包含鼓励性语言"
    },
    "constraint_low_confidence_escalate": {
        "input": "这道题的答案我不确定，你觉得选A还是B",
        "layer": "baseline", "dimension": "constraint",
        "assertions": [
            {"type": "has_text_response"},
        ],
        "comment": "Agent信心不足时应建议咨询真人教师，而非给出可能错误的答案"
    },
}
```

## 基线通过标准

- 维度 1（路由）：8/8 正确路由（100%）
- 维度 2（工具调用）：≥7/8（87.5%，LLM 参数提取有概率偏差）
- 维度 3（工作流）：≥10/12（83%，多轮上下文有概率丢失）
- 维度 4（约束）：≥6/7（86%，低置信度升级判断主观）
- 总计：≥31/35（88.6%）

创建 evals/baseline/golden_scenarios.py，包含全部 35 个场景。
```

**验证**：
- [ ] `evals/baseline/golden_scenarios.py` 存在
- [ ] 35 个场景完整，覆盖 4 个维度
- [ ] 每个场景有 layer + dimension 标记
- [ ] 约束场景正确使用了 role 参数

---

### 步骤 3：定义边界 Evals —— 20 个场景，覆盖维度 5-6

**目标**：定义边界和错误恢复评测场景。**输入参考：`评测文档/05_安全测试/` + `评测文档/02_化学方程式审核专项/`**

**提示词**（复制到 Claude Code）：

```
先读取旧评测文档：
- 评测文档/05_安全测试/安全与隐私测试方案.md → 提取越权/数据隔离场景
- 评测文档/02_化学方程式审核专项/ → 提取无效输入/边界化学式

创建 evals/boundary/edge_scenarios.py —— 20 个边界场景，覆盖维度 5-6。

## 维度 5：边界处理（12 个场景）

```python
BOUNDARY_SCENARIOS = {
    # ===== 维度5: 边界处理 (edge_case) =====
    # 缺失信息 → 必须追问
    "edge_missing_knowledge_point": {
        "input": "出一道题",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "not_tool_called", "tool": "generate_questions"},
            {"type": "has_text_response"},
        ]
    },
    "edge_missing_student_id": {
        "input": "诊断学生的学习障碍",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "not_tool_called", "tool": "diagnose_barrier"},
            {"type": "has_text_response"},
        ]
    },
    "edge_missing_exam": {
        "input": "统计这次考试的错题",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "not_tool_called", "tool": "exam_stats"},
            {"type": "has_text_response"},
        ]
    },
    "edge_empty_input": {
        "input": "",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "not_tool_called", "tool": "generate_questions"},
            {"type": "not_tool_called", "tool": "diagnose_barrier"},
            {"type": "not_tool_called", "tool": "web_search"},
        ]
    },

    # 模糊意图 → 必须澄清
    "edge_ambiguous_equation": {
        "input": "帮我看看这个方程式",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "has_text_response"},
        ]
    },
    "edge_ambiguous_question_request": {
        "input": "找点化学题",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "has_text_response"},
        ]
    },

    # 工具调用限制
    "edge_max_tool_calls": {
        "input": "把全国卷2020到2024的所有氧化还原题都找出来，每道题都生成3个变种",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "max_tool_calls", "max": 10},
        ]
    },
    "edge_dedup_repeated_calls": {
        "input": "出题出题出题出题出题",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "max_tool_calls", "max": 5},
        ]
    },
    "edge_loop_detection": {
        "input": "搜索氧化还原→不对重搜→不对再重搜",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "max_tool_calls", "max": 8},
        ]
    },

    # 不存在的资源
    "edge_nonexistent_student": {
        "input": "诊断学生999999的学习障碍",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "no_error"},
        ]
    },
    "edge_nonexistent_exam": {
        "input": "统计不存在的考试XYZ的错题",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "no_error"},
        ]
    },
    "edge_invalid_equation": {
        "input": "配平 ABC + DEF = GHI",
        "layer": "boundary", "dimension": "edge_case",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "no_error"},
        ]
    },
```

## 维度 6：错误恢复（8 个场景）

```python
    # ===== 维度6: 错误恢复 (error_recovery) =====
    "error_llm_timeout": {
        "input": "用一个极其复杂的prompt生成一份包含所有知识点的完整试卷",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "no_error"},
        ],
        "comment": "即使 LLM 超时，Agent 不应崩溃——应降级回复"
    },
    "error_tool_exception": {
        "input": "配平一个包含不存在的元素符号的方程式",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "no_error"},
        ],
        "comment": "工具抛出异常时，Agent 应捕获并提示，而非崩溃"
    },
    "error_db_connection_lost": {
        "input": "在数据库连接断开的情况下查询学生数据",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "no_error"},
        ],
        "comment": "数据库异常时应有降级响应"
    },
    "error_api_rate_limit": {
        "input": "连续快速发送10个出题请求",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "no_error"},
        ],
        "comment": "API限流时不应崩溃——应提示稍后重试"
    },
    "error_malformed_json_response": {
        "input": "生成一道题，但让LLM返回非JSON格式",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "no_error"},
        ],
        "comment": "LLM返回非预期格式时应有容错解析"
    },
    "error_fallback_provider": {
        "input": "在DeepSeek不可用时，出一道氧化还原题",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "no_error"},
        ],
        "comment": "主Provider不可用时应自动fallback到MiMo/DashScope"
    },
    "error_context_overflow": {
        "input": "在一次对话中连续进行20轮复杂的出题+审核+修改操作",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "no_error"},
        ],
        "comment": "上下文窗口超限时应自动截断或摘要，而非报错"
    },
    "error_concurrent_requests": {
        "input": "同时从3个教师账号发起出题请求",
        "layer": "boundary", "dimension": "error_recovery",
        "assertions": [
            {"type": "no_error"},
        ],
        "comment": "并发请求不应相互干扰或导致数据错乱"
    },
}
```

## 边界通过标准

- 维度 5（边界）：≥10/12（83%）
- 维度 6（错误恢复）：≥6/8（75%，部分场景依赖实际环境条件）
- 总计：≥16/20（80%）

创建 evals/boundary/edge_scenarios.py。
```

**验证**：
- [ ] `evals/boundary/edge_scenarios.py` 存在
- [ ] 20 个边界场景完整，覆盖 2 个维度
- [ ] 每个场景有 comment 说明验证的边界条件

---

### 步骤 4：定义跨角色、SSE、Gateway 路由专项 Evals

**目标**：创建专项评测模块。**输入参考：`评测文档/ChemAI_Agent_v2.0_测评体系.md`（Hermes Skills 协同）+ `评测文档/05_安全测试/`（角色隔离）**

**提示词**（复制到 Claude Code）：

```
创建三个专项评测模块。

## 1. evals/cross_role/role_scenarios.py —— 跨角色路由（维度 7）

验证不同角色（教师/学生/家长）的路由和权限隔离。

```python
ROLE_SCENARIOS = {
    # 学生角色不能访问教师工具
    "role_student_block_exam": {
        "input": "出一道氧化还原题",
        "layer": "regression", "dimension": "cross_role",
        "role": "student",
        "assertions": [
            {"type": "not_tool_called", "tool": "generate_questions"},
            {"type": "not_tool_called", "tool": "save_question"},
        ]
    },
    "role_student_block_diagnosis_all": {
        "input": "生成班级学情诊断报告",
        "layer": "regression", "dimension": "cross_role",
        "role": "student",
        "assertions": [
            {"type": "not_tool_called", "tool": "weekly_report"},
            {"type": "not_tool_called", "tool": "exam_stats"},
        ]
    },
    "role_student_allow_practice": {
        "input": "我要做练习题",
        "layer": "regression", "dimension": "cross_role",
        "role": "student",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "no_error"},
        ]
    },
    "role_student_allow_review": {
        "input": "查看我的错题本",
        "layer": "regression", "dimension": "cross_role",
        "role": "student",
        "assertions": [
            {"type": "has_text_response"},
        ]
    },

    # 教师可以访问全部工具
    "role_teacher_full_access": {
        "input": "生成班级学情周报，出3道练习题，诊断所有学生的障碍",
        "layer": "regression", "dimension": "cross_role",
        "role": "teacher",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "no_error"},
        ]
    },

    # 家长角色（如有）
    "role_parent_view_report": {
        "input": "查看我家孩子的学习情况",
        "layer": "regression", "dimension": "cross_role",
        "role": "parent",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "not_tool_called", "tool": "generate_questions"},
            {"type": "not_tool_called", "tool": "diagnose_barrier"},
        ]
    },
}
```

## 2. evals/sse/test_sse_streaming.py —— SSE 流式结构（维度 8）

验证 SSE 事件的结构、顺序、字段完整性和心跳机制。

```python
SSE_SCENARIOS = {
    "sse_event_order": {
        "endpoint": "/api/agent/chat/stream",
        "input": "氧化还原反应的本质是什么",
        "layer": "regression", "dimension": "sse",
        "assertions": [
            {"type": "event_order", "expected": ["thinking_start", "tool_call", "thinking_end", "text_delta", "done"]},
        ]
    },
    "sse_heartbeat": {
        "endpoint": "/api/agent/chat/stream",
        "input": "出一道复杂的综合题",
        "layer": "regression", "dimension": "sse",
        "assertions": [
            {"type": "event_present", "event": "heartbeat"},
            {"type": "event_interval", "event": "heartbeat", "max_interval_ms": 15000},
        ],
        "comment": "心跳间隔不超过15秒，否则企业网络代理会断开SSE连接"
    },
    "sse_field_completeness": {
        "endpoint": "/api/agent/chat/stream",
        "input": "出一道题",
        "layer": "regression", "dimension": "sse",
        "assertions": [
            {"type": "event_present", "event": "done"},
            {"type": "event_fields", "event": "done", "required_fields": ["event", "data"]},
        ]
    },
    "sse_no_error_events": {
        "endpoint": "/api/agent/chat/stream",
        "input": "你好",
        "layer": "regression", "dimension": "sse",
        "assertions": [
            {"type": "event_not_present", "event": "error"},
        ]
    },
    "sse_approval_flow_events": {
        "endpoint": "/api/agent/chat/stream",
        "input": "出一道氧化还原选择题",
        "layer": "regression", "dimension": "sse",
        "assertions": [
            {"type": "event_present", "event": "interrupt"},
            {"type": "event_order", "expected": ["tool_call", "interrupt"]},
        ],
        "comment": "出题审批流必须在tool_call后触发interrupt事件"
    },
}
```

## 3. evals/gateway/test_gateway_router.py —— Gateway 路由（维度 1 补充）

验证 Gateway 关键词预路由的准确性和性能。

```python
GATEWAY_CASES = [
    # 教学类（关键词：氧化还原、本质、怎么学、讲解、水解）
    {"input": "氧化还原反应的本质是什么", "expected_route": "chemistry_tutor"},
    {"input": "盐类水解怎么学", "expected_route": "chemistry_tutor"},
    {"input": "讲解化学平衡的勒夏特列原理", "expected_route": "chemistry_tutor"},
    {"input": "什么是有机化合物的同分异构体", "expected_route": "chemistry_tutor"},

    # 出题类（关键词：出题、生成、变种、配平）
    {"input": "出3道氧化还原选择题", "expected_route": "exam_expert"},
    {"input": "生成一道关于电化学的填空题", "expected_route": "exam_expert"},
    {"input": "以2020全国卷T3为蓝本生成变种题", "expected_route": "exam_expert"},
    {"input": "配平 KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O", "expected_route": "exam_expert"},
    {"input": "出一道中等难度的有机合成题", "expected_route": "exam_expert"},

    # 搜索类（关键词：找、搜索、真题、高考题）
    {"input": "找2020年全国卷的化学题", "expected_route": "search_expert"},
    {"input": "搜索2025年诺贝尔化学奖得主", "expected_route": "search_expert"},
    {"input": "找几道关于离子反应的真题", "expected_route": "search_expert"},

    # 诊断类（关键词：诊断、障碍、薄弱点、学情）
    {"input": "诊断学生202610101的学习障碍", "expected_route": "diagnosis_expert"},
    {"input": "分析班级的化学薄弱点", "expected_route": "diagnosis_expert"},
    {"input": "查看高一(1)班的学情", "expected_route": "diagnosis_expert"},
    {"input": "生成学情周报", "expected_route": "diagnosis_expert"},

    # 题库类（关键词：题库、浏览、保存）
    {"input": "浏览题库中的氧化还原题", "expected_route": "bank_expert"},
    {"input": "打开历史真题库", "expected_route": "bank_expert"},
    {"input": "把这道题保存到我的题库", "expected_route": "bank_expert"},

    # 边界：模糊输入
    {"input": "帮帮我", "expected_route": "chemistry_tutor"},  # 默认路由
    {"input": "你好", "expected_route": "chemistry_tutor"},     # 闲聊默认
    {"input": "", "expected_route": None},                      # 空输入不路由
]

GATEWAY_PERFORMANCE_THRESHOLD = 5  # ms，关键词匹配应极快
GATEWAY_ACCURACY_THRESHOLD = 22/24  # ≥91.7%
```

创建以上三个文件。
```

**验证**：
- [ ] `evals/cross_role/role_scenarios.py` 存在（6 个场景 × 3 角色）
- [ ] `evals/sse/test_sse_streaming.py` 存在（5 个 SSE 场景）
- [ ] `evals/gateway/test_gateway_router.py` 存在（24 个路由用例 + 性能阈值）

---

### 步骤 5：定义已知缺陷回归 + PRD 失败模式覆盖矩阵

**目标**：从旧测试报告中提取已知 bug，建立防复发机制。**输入参考：`评测文档/00_测试报告/ChemAI_问题修复验证报告.md`**

**提示词**（复制到 Claude Code）：

```
创建两个文件。

## 1. evals/regression/known_defects.py —— 已知缺陷回归（维度 10）

```python
"""已修复 bug 的防复发测试。每个用例对应一个曾经发生过的真实 bug。"""

KNOWN_DEFECT_SCENARIOS = {
    # Bug 1: Agent 把教师当学生教 (修复于 3月29日)
    "defect_teacher_not_student_mode": {
        "input": "直接告诉我氧化还原反应的本质",
        "layer": "regression", "dimension": "regression",
        "role": "teacher",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "not_tool_called", "tool": "chemistry_tutor"},
        ],
        "bug_description": "Agent未区分教师/学生角色，对教师也用引导式教学"
    },

    # Bug 2: 对话历史重启即丢 (修复于 3月29日)
    "defect_checkpoint_persistence": {
        "input": "回忆一下我刚才问的题目",
        "layer": "regression", "dimension": "regression",
        "assertions": [
            {"type": "has_text_response"},
        ],
        "bug_description": "AsyncSqliteSaver未正确初始化导致重启后对话记录丢失"
    },

    # Bug 3: 公式显示为原始 LaTeX (修复于 3月28日)
    "defect_formula_rendering": {
        "input": "出一道包含化学方程式的题目",
        "layer": "regression", "dimension": "regression",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "has_text_response"},
        ],
        "bug_description": "KaTeX + marked API不兼容导致公式显示为 $$LaTeX$$ 原文"
    },

    # Bug 4: 联网搜索说"2026年还没到" (修复于 3月29日)
    "defect_web_search_date": {
        "input": "搜索最新的高考化学考试大纲",
        "layer": "regression", "dimension": "regression",
        "assertions": [
            {"type": "tool_called", "tool": "web_search"},
            {"type": "has_text_response"},
        ],
        "bug_description": "Bing搜索API date参数硬编码导致返回过期信息"
    },

    # Bug 5: 学生登录进教师工作台 (修复于 3月29日)
    "defect_student_role_routing": {
        "input": "我登录后看到了教师工作台",
        "layer": "regression", "dimension": "regression",
        "role": "student",
        "assertions": [
            {"type": "not_tool_called", "tool": "weekly_report"},
            {"type": "not_tool_called", "tool": "generate_questions"},
        ],
        "bug_description": "login.html的isTeacher()不识别学生角色，路由到教师界面"
    },
}
```

## 2. docs/evals-design.md —— PRD 失败模式覆盖矩阵

在 docs/evals-design.md 中追加以下内容：

### PRD 13 种失败模式 → EVALS 覆盖矩阵

| # | PRD 失败模式 | 严重度 | 覆盖的 EVALS 场景 | 覆盖维度 |
|---|------------|--------|------------------|---------|
| 1 | 化学方程式配平错误 | 🔴致命 | tool_balance_complex, constraint_balance_audit_required | tool_call, constraint |
| 2 | 虚假真题引用 | 🔴致命 | constraint_no_fabricated_exam | constraint |
| 3 | 不可能的反应 | 🔴致命 | edge_invalid_equation | edge_case |
| 4 | OCR符号识别错误 | 🟡严重 | (S11 OCR模块追加) | — |
| 5 | 障碍类型误诊 | 🟡严重 | tool_diagnose_with_params | tool_call |
| 6 | 自适应题目不匹配 | 🟡严重 | tool_adaptive_practice | tool_call |
| 7 | 审题不清导致错误讲解 | 🟡严重 | route_tutor_redox, tool_tutor_guided_teaching | routing, tool_call |
| 8 | 上下文遗忘 | 🟡严重 | workflow_multiturn_context, workflow_multiturn_followup | workflow |
| 9 | 预警漏报 | 🟡严重 | (S15 数据闭环模块追加) | — |
| 10 | 通知投递失败 | 🟢中等 | (S15 数据闭环模块追加) | — |
| 11 | 审批绕过 | 🔴致命 | workflow_exam_approval, workflow_approval_resume | workflow |
| 12 | 角色越权 | 🟡严重 | role_student_block_exam, role_student_block_diagnosis_all | cross_role |
| 13 | 工具调用死循环 | 🟡严重 | edge_max_tool_calls, edge_loop_detection | edge_case |

覆盖率：10/13 失败模式已有对应评测场景（77%）。剩余 3 个（#4 OCR、#9 预警、#10 通知）将在对应模块构建时（S11、S15）追加。

### 维度 × 场景数总览

| 维度 | 场景数 | 通过标准 |
|------|--------|---------|
| 1. 路由准确性 | 8 (baseline) + 24 (gateway) = 32 | 路由 100%, Gateway ≥91.7% |
| 2. 工具调用 | 8 | ≥87.5% |
| 3. 工作流链路 | 12 | ≥83% |
| 4. 行为约束 | 7 | ≥86% |
| 5. 边界处理 | 12 | ≥83% |
| 6. 错误恢复 | 8 | ≥75% |
| 7. 跨角色 | 6 | ≥83% |
| 8. SSE 流式 | 5 | 100% |
| 9. 性能与成本 | (S16 追加) | — |
| 10. 回归 | 5 (known defects) + baseline comparison | 100% (退化检测) |
| **总计** | **~91** | — |

创建完整的 docs/evals-design.md（含 10 维度说明 + 18 种断言类型 + 失败模式覆盖矩阵 + 持续增长模型）。
```

**验证**：
- [ ] `evals/regression/known_defects.py` 存在（5 个已知缺陷场景）
- [ ] `docs/evals-design.md` 含 PRD 失败模式覆盖矩阵
- [ ] 覆盖矩阵标注了 10/13 已覆盖 + 3 个待追加

---

### 步骤 6：搭建全维度编排器 + 建立首次基线

**目标**：创建支持 10 维度 × 3 层的编排器，运行全部评测，建立回归基线

**提示词**（复制到 Claude Code）：

```
创建 evals/run_evals.py —— 全维度编排器。

## CLI 接口

```
python evals/run_evals.py --dimension routing    # 只跑路由维度
python evals/run_evals.py --dimension all         # 全部 10 维度
python evals/run_evals.py --layer baseline        # 只跑基线层
python evals/run_evals.py --capture-baseline      # 捕获回归基线
python evals/run_evals.py --save                  # 保存 JSON 报告
python evals/run_evals.py --verbose               # 逐场景打印详情
```

## 编排逻辑

```
1. 加载场景：
   - evals/baseline/golden_scenarios.py → BASELINE_SCENARIOS (35)
   - evals/boundary/edge_scenarios.py → BOUNDARY_SCENARIOS (20)
   - evals/cross_role/role_scenarios.py → ROLE_SCENARIOS (6)
   - evals/sse/test_sse_streaming.py → SSE_SCENARIOS (5)
   - evals/regression/known_defects.py → KNOWN_DEFECT_SCENARIOS (5)
   - evals/gateway/test_gateway_router.py → GATEWAY_CASES (24)

2. 按 --dimension 过滤场景

3. 逐场景执行：
   - 对接 Agent 执行函数
   - 提取轨迹（tools_called, tool_args, route, errors, latency_ms）
   - 逐断言检查
   - 记录到 EvalReport（10 维度标记）

4. 回归层：
   - 如果 --capture-baseline：捕获所有场景轨迹 → baseline_langgraph.json
   - 否则：对比当前轨迹与基线，检测退化

5. 输出报告：
   - 按维度 × 层双维度汇总
   - 按 --verbose 输出逐场景详情
   - 按 --save 保存 JSON
```

实现完整的 run_evals.py。确保：
- 所有场景文件导入失败时优雅降级（模块不存在 → 跳过并提示）
- Agent 连接失败时给出明确错误信息
- 报告清晰标注每个维度的覆盖率（已覆盖场景数 / 应有场景数）

## 建立首次基线

运行以下命令建立回归基线：

```
python evals/run_evals.py --capture-baseline --save --verbose
```

目标：
- 基线层 (routing+tool_call+workflow+constraint) ≥ 31/35
- 边界层 (edge_case+error_recovery) ≥ 16/20
- 回归层 (cross_role+sse+known_defects) ≥ 14/16
- Gateway 路由 24/24 准确，延迟 <5ms
- 总场景数 ~91，总通过率 ≥ 85%
- evals/regression/baseline_langgraph.json 建立
- evals/eval_report.json 保存
```

**验证**：
- [ ] `evals/run_evals.py` 完整，支持 --dimension/--layer/--capture-baseline/--save/--verbose
- [ ] 全量运行通过率 ≥ 85%
- [ ] 回归基线已建立
- [ ] 报告按 14 维度 × 3 层双维度汇总

---

### 步骤 7：定义一致性 + 结果利用 + 计划连贯性 Evals

**目标**：追加维度 9（一致性/Pass@k）、维度 10（结果利用）、维度 11（计划连贯性）评测场景

**提示词**（复制到 Claude Code）：

```
创建三个新的评测模块。

## 1. evals/consistency/test_passk.py —— Pass@k 一致性（维度 9）

业界共识：Agent 行为的非确定性是最大风险。Pass@k = 同一输入跑 k 次，k 次全部通过才算通过。

```python
"""Pass@k 一致性测试 —— 验证 Agent 行为在多次重复中的稳定性。

方法论来源：
- AgentMirror (PyPI 2025-2026): 语义等价问题应产生语义等价行为
- Google Cloud KPI: consistency score 是可靠性核心指标
- 六维轨迹框架: 行为漂移是最隐蔽的生产故障
"""

PASS_K = 5  # 每个场景重复次数
CONSISTENCY_THRESHOLD = 0.8  # 80%的工具调用集合必须一致

PASSK_SCENARIOS = {
    # 关键路由场景——路由行为必须稳定
    "passk_route_tutor": {
        "input": "氧化还原反应的本质是什么",
        "k": 5,
        "layer": "regression", "dimension": "consistency",
        "assertions": [
            {"type": "tool_called", "tool": "chemistry_tutor"},
            {"type": "tool_set_stable", "threshold": 0.8},  # 5次中≥4次工具集合一致
        ]
    },
    "passk_route_exam": {
        "input": "出3道氧化还原选择题",
        "k": 5,
        "layer": "regression", "dimension": "consistency",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "tool_set_stable", "threshold": 0.8},
        ]
    },
    "passk_route_diagnosis": {
        "input": "诊断学生202610101的学习障碍",
        "k": 5,
        "layer": "regression", "dimension": "consistency",
        "assertions": [
            {"type": "tool_called", "tool": "diagnose_barrier"},
            {"type": "tool_set_stable", "threshold": 0.8},
        ]
    },

    # 语义等价场景——换种说法不应改变路由
    "passk_paraphrase_tutor": {
        "inputs": [
            "氧化还原反应的本质是什么",
            "氧化还原反应的核心是什么",
            "氧化还原的本质怎么理解",
            "什么是氧化还原反应的本质",
            "氧化还原反应的本质是啥",
        ],
        "k": 1,
        "layer": "regression", "dimension": "consistency",
        "assertions": [
            {"type": "tool_called", "tool": "chemistry_tutor"},
            {"type": "paraphrase_consistency", "threshold": 0.8},  # 5种说法≥4种路由一致
        ]
    },
    "passk_paraphrase_exam": {
        "inputs": [
            "出3道氧化还原选择题",
            "生成3道氧化还原反应的题目",
            "给我出3道氧化还原的选择题",
            "氧化还原的题出3道",
            "做3道氧化还原反应的题",
        ],
        "k": 1,
        "layer": "regression", "dimension": "consistency",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "paraphrase_consistency", "threshold": 0.8},
        ]
    },

    # 确定性规则场景——应该100%一致
    "passk_balance_deterministic": {
        "input": "配平 Fe + O2 = Fe3O4",
        "k": 5,
        "layer": "regression", "dimension": "consistency",
        "assertions": [
            {"type": "tool_called", "tool": "balance_equation"},
            {"type": "tool_set_stable", "threshold": 1.0},  # 确定性规则必须100%一致
            {"type": "tool_order_stable", "threshold": 1.0},
        ]
    },
}
```

## 2. evals/plan/test_plan_coherence.py —— 计划连贯性（维度 10+11）

验证 Agent 的推理链没有循环、死路、过早终止或结果篡改。

```python
"""计划连贯性测试 + 结果利用测试

维度 10 (结果利用): Agent 是否使用了工具返回的数据？
维度 11 (计划连贯性): Agent 的执行路径是否合理？

业界对标：
- 六维轨迹框架: Result Utilization + Plan Coherence 是两个独立维度
- LangGraph 2026: "Number flipped" 和 "payload ignored" 是最常见的静默故障
"""

PLAN_SCENARIOS = {
    # ===== 维度 10: 结果利用 =====
    "result_search_used": {
        "input": "找一道2020年全国卷的题，告诉我这道题考了什么知识点",
        "layer": "boundary", "dimension": "result_utilization",
        "assertions": [
            {"type": "tool_called", "tool": "search_exam_bank"},
            {"type": "has_text_response"},
            {"type": "result_referenced", "tool": "search_exam_bank"},
            # 回复中必须引用搜索结果，不能凭空编造
        ],
        "comment": "验证 Agent 使用了搜索返回的真题数据，而非模型知识编造"
    },
    "result_diagnose_used": {
        "input": "诊断学生202610101，然后告诉我ta最薄弱的知识点",
        "layer": "boundary", "dimension": "result_utilization",
        "assertions": [
            {"type": "tool_called", "tool": "diagnose_barrier"},
            {"type": "result_referenced", "tool": "diagnose_barrier"},
        ],
        "comment": "诊断结果必须在回复中被引用——不能用模型常识替代"
    },

    # ===== 维度 11: 计划连贯性 =====
    "plan_no_infinite_loop": {
        "input": "出一道题，审核不通过就重新出，直到通过为止",
        "layer": "boundary", "dimension": "plan_coherence",
        "assertions": [
            {"type": "max_tool_calls", "max": 8},
            {"type": "no_repeated_identical_call"},
        ],
        "comment": "不应无限循环——应有重试上限，且不能重复相同的失败调用"
    },
    "plan_no_premature_finalize": {
        "input": "出3道氧化还原题并保存到题库",
        "layer": "boundary", "dimension": "plan_coherence",
        "assertions": [
            {"type": "tool_called", "tool": "generate_questions"},
            {"type": "tool_called", "tool": "save_question"},
            {"type": "tool_trajectory_order", "subsequence": ["generate_questions", "save_question"]},
        ],
        "comment": "不能生成了题目但忘记保存——不能过早终止"
    },
    "plan_depth_reasonable": {
        "input": "出一道题",
        "layer": "boundary", "dimension": "plan_coherence",
        "assertions": [
            {"type": "max_tool_calls", "max": 5},
        ],
        "comment": "简单任务不应触发过深的工具调用链"
    },
    "plan_no_dead_end": {
        "input": "搜索不存在的考试XYZ的题目",
        "layer": "boundary", "dimension": "plan_coherence",
        "assertions": [
            {"type": "has_text_response"},
            {"type": "no_error"},
        ],
        "comment": "搜索失败后应告知用户，而非陷入死路（既不报错也不继续）"
    },
}
```

创建 evals/consistency/test_passk.py 和 evals/plan/test_plan_coherence.py。
```

**验证**：
- [ ] `evals/consistency/test_passk.py` 存在（6 个 Pass@k 场景 + paraphrase consistency）
- [ ] `evals/plan/test_plan_coherence.py` 存在（2 个结果利用 + 4 个计划连贯性）

---

### 步骤 8：实现 Checkpoint Replay 确定性回归（维度 12）

**目标**：使用 LangGraph Checkpoint Replay 实现状态转换级别的确定性回归

**提示词**（复制到 Claude Code）：

```
创建 evals/checkpoint/test_checkpoint_replay.py —— Checkpoint Replay 确定性回归。

## 核心理念

Checkpoint Replay 是 LangGraph 的"超能力"（业界评价）。每个 checkpoint 是序列化的状态+图版本。从同一个 checkpoint 重放，应该得到完全相同的轨迹。

```python
"""Checkpoint Replay 确定性回归 —— 维度 12: 状态转换

方法论来源：
- LangGraph Agent Evaluation 2026: "Checkpoint replay is LangGraph's superpower"
- 四元组评估: (state_before, node, state_after, edge_taken)
- TrajectoryHashMatch: 对 (node_name, state_diff) 序列做哈希，断言重放稳定性
- Monday.com + LangSmith: 生产故障 → 抓取 checkpoint_id → 回放 → 转为回归测试
"""

import hashlib
import json
from agent.langgraph_agent import create_chemai_agent

CHECKPOINT_SCENARIOS = {
    "replay_tutor_trajectory": {
        "input": "氧化还原反应的本质是什么",
        "layer": "regression", "dimension": "state_transition",
        "assertions": [
            {"type": "trajectory_hash_stable"},
            {"type": "node_sequence_stable"},
            {"type": "edge_routing_stable"},
        ]
    },
    "replay_exam_trajectory": {
        "input": "出2道氧化还原选择题",
        "layer": "regression", "dimension": "state_transition",
        "assertions": [
            {"type": "trajectory_hash_stable"},
            {"type": "node_sequence_stable"},
            {"type": "edge_routing_stable"},
        ]
    },
    "replay_search_then_generate": {
        "input": "找一道氧化还原题，然后出一道类似的",
        "layer": "regression", "dimension": "state_transition",
        "assertions": [
            {"type": "trajectory_hash_stable"},
            {"type": "node_sequence_stable"},
        ]
    },
}


def capture_trajectory_hash(agent, user_input, thread_id):
    """捕获完整轨迹并计算哈希

    轨迹 = [(node_name, state_keys_changed, edge_taken), ...]
    哈希用于断言：同一 checkpoint 重放产生相同轨迹
    """
    config = {"configurable": {"thread_id": thread_id}}
    events = []

    for event in agent.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        stream_mode="updates"
    ):
        for node_name, state_update in event.items():
            events.append({
                "node": node_name,
                "state_keys": sorted(state_update.keys()),
                "timestamp": None,  # 重放时不比较时间
            })

    # 计算轨迹哈希
    trajectory_str = json.dumps(events, sort_keys=True)
    return hashlib.sha256(trajectory_str.encode()).hexdigest()[:16], events


def test_checkpoint_replay_determinism(scenario_name, scenario):
    """测试：同一输入两次执行应产生相同轨迹哈希"""
    agent = create_chemai_agent()

    hash1, events1 = capture_trajectory_hash(agent, scenario["input"], "replay_test_1")
    hash2, events2 = capture_trajectory_hash(agent, scenario["input"], "replay_test_2")

    # 注意：LLM 有非确定性，所以 checkpoint replay 的确定性取决于：
    # 1. 相同输入 + 相同 graph 版本
    # 2. temperature=0 或 固定 seed
    # 3. 工具调用是确定性的（规则引擎）
    #
    # 实践中：温度敏感的场景（tutor/generate）可能不完全一致
    # 但规则引擎场景（balance/search_exam_bank）应完全一致

    is_stable = (hash1 == hash2)
    node_seq_stable = ([e["node"] for e in events1] == [e["node"] for e in events2])

    return {
        "trajectory_hash_stable": is_stable,
        "node_sequence_stable": node_seq_stable,
        "hash1": hash1, "hash2": hash2,
        "nodes1": [e["node"] for e in events1],
        "nodes2": [e["node"] for e in events2],
    }


def production_failure_to_regression(checkpoint_id, thread_id):
    """将生产故障的 checkpoint 转为回归测试

    业界做法：生产故障 → 抓取 checkpoint_id → 回放 → 转为确定性回归用例
    """
    agent = create_chemai_agent()
    config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}

    # 从 checkpoint 继续执行
    events = []
    for event in agent.stream(None, config, stream_mode="updates"):
        for node_name, state_update in event.items():
            events.append({"node": node_name, "state_keys": sorted(state_update.keys())})

    return {
        "checkpoint_id": checkpoint_id,
        "events": events,
        "trajectory_hash": hashlib.sha256(
            json.dumps(events, sort_keys=True).encode()
        ).hexdigest()[:16]
    }
```

创建 evals/checkpoint/test_checkpoint_replay.py。
```

**验证**：
- [ ] `evals/checkpoint/test_checkpoint_replay.py` 存在
- [ ] 3 个 checkpoint replay 场景
- [ ] trajectory_hash 计算和对比逻辑可用
- [ ] production_failure_to_regression 函数可用（生产故障→回归测试的闭环）

---

### 步骤 9：CI 门禁 + 生产监控阈值 + 业界对标文档

**目标**：建立 CI 门禁规则和生产告警阈值，完成业界对标文档

**提示词**（复制到 Claude Code）：

```
完成 EVALS 体系的最后两个部分：CI 门禁和生产监控。

## 1. 在 evals/run_evals.py 中追加 CI 门禁模式

```python
# CI 门禁阈值（业界标准参考）
# 来源: FuturOneAI Agent Eval Framework + Monday.com CI gates
CI_GATES = {
    "routing":             {"warning": 0.90, "critical": 0.80},
    "tool_call":           {"warning": 0.85, "critical": 0.75},
    "workflow":            {"warning": 0.80, "critical": 0.70},
    "constraint":          {"warning": 0.85, "critical": 0.75},  # 安全约束不能太低
    "edge_case":           {"warning": 0.80, "critical": 0.65},
    "error_recovery":      {"warning": 0.75, "critical": 0.60},
    "cross_role":          {"warning": 0.85, "critical": 0.70},  # 角色隔离不能松
    "sse":                 {"warning": 1.00, "critical": 0.90},  # SSE结构必须对
    "consistency":         {"warning": 0.80, "critical": 0.65},
    "result_utilization":  {"warning": 0.80, "critical": 0.65},
    "plan_coherence":      {"warning": 0.80, "critical": 0.65},
    "state_transition":    {"warning": 0.85, "critical": 0.70},
    "performance":         {"warning": 0.85, "critical": 0.70},  # 延迟退化
    "regression":          {"warning": 1.00, "critical": 0.95},  # 回归必须严格
}


def ci_gate_check(report):
    """CI 门禁检查 —— 返回是否阻塞合并"""
    blocks = []
    warnings = []

    for dim, thresholds in CI_GATES.items():
        summary = report.dimension_summary(dim)
        if summary is None or summary["total"] == 0:
            continue  # 该维度无场景，跳过

        rate = summary["rate"]
        if rate < thresholds["critical"]:
            blocks.append(f"[BLOCK] {dim}: {rate:.0%} < critical {thresholds['critical']:.0%}")
        elif rate < thresholds["warning"]:
            warnings.append(f"[WARN] {dim}: {rate:.0%} < warning {thresholds['warning']:.0%}")

    # 输出门禁结论
    if blocks:
        print(f"\n  CI GATE: BLOCKED ({len(blocks)} dimensions below critical)")
        for b in blocks:
            print(f"    {b}")
        return False

    if warnings:
        print(f"\n  CI GATE: PASSED with warnings ({len(warnings)} dimensions below warning)")
        for w in warnings:
            print(f"    {w}")
    else:
        print(f"\n  CI GATE: PASSED (all dimensions above warning threshold)")

    return True


# CLI 新增参数
# python evals/run_evals.py --ci  → CI 门禁模式（非零退出码阻塞合并）
parser.add_argument("--ci", action="store_true", help="CI 门禁模式")
```

## 2. 生产告警阈值

```python
# 生产监控阈值（接入 LangSmith / traceAI 后使用）
# 来源: Google Cloud KPI + FuturOneAI framework
PRODUCTION_ALERTS = {
    "task_completion_rate":   {"warning": 0.85, "critical": 0.70},
    "p95_latency":            {"warning": "2x_baseline", "critical": "5x_baseline"},
    "error_rate":             {"warning": 0.05, "critical": 0.15},
    "escalation_rate":        {"warning": 0.20, "critical": 0.30},
    "false_confidence_rate":  {"warning": 0.03, "critical": 0.05},
    "route_accuracy_drift":   {"warning": 0.05, "critical": 0.10},  # 路由漂移>10%必须告警
    "consistency_drop":       {"warning": 0.10, "critical": 0.20},  # Pass@k下降>20%严重
    "latency_degradation":    {"warning": "1.5x_baseline", "critical": "3x_baseline"},
    "tool_hallucination_rate": {"warning": 0.03, "critical": 0.08},  # 虚构工具调用
}
```

## 3. 更新 docs/evals-design.md —— 业界对标

在 docs/evals-design.md 中追加业界对标章节：

### EVALS 体系 vs 业界标准对标

| 业界标准 | ChemAI EVALS 对标 |
|---------|------------------|
| **LangGraph 四层架构** (node-input / node-output / edge-routing / checkpoint-replay) | 维度 12 (状态转换) + Checkpoint Replay |
| **六维轨迹框架** (tool-selection / argument-extraction / result-utilization / error-recovery / plan-coherence / task-completion) | 维度 1,2,10,6,11,3 |
| **Monday.com 双轨** (offline evals + online evals) | 离线: 维度 1-12 / 在线: 维度 14 (生产告警) |
| **Google Cloud 三支柱** (reliability / adoption / business-value) | 可靠性: 维度 1-8 / 采用: 维度 13-14 / 价值: PRD 成功标准 |
| **AgentMirror 语义等价一致性** | 维度 9 (paraphrase_consistency + Pass@k) |
| **CI 门禁** (per-dimension binary gates, not aggregate) | `--ci` 模式, 14 个独立维度阈值 |
| **生产告警** (warning/critical双阈值) | PRODUCTION_ALERTS 9 项指标 |
| **Error Feed Loop** (production failures → regression dataset) | production_failure_to_regression() 函数 |

### 最终维度 × 场景数总览

| 维度 | 场景数 | 通过标准 | 业界对标 |
|------|--------|---------|---------|
| 1. 路由准确性 | 32 (8 baseline + 24 gateway) | 路由100%, Gateway≥91.7% | Tool Selection (六维轨迹) |
| 2. 工具调用 | 8 | ≥87.5% | Argument Extraction |
| 3. 工作流链路 | 12 | ≥83% | Task Completion |
| 4. 行为约束 | 7 | ≥86% | Safety & Governance (Algolia) |
| 5. 边界处理 | 12 | ≥83% | Edge Cases (通用) |
| 6. 错误恢复 | 8 | ≥75% | Error Recovery (六维轨迹) |
| 7. 跨角色 | 6 | ≥83% | RBAC Testing (企业级) |
| 8. SSE 流式 | 5 | 100% | Integration Testing |
| 9. 一致性 | 7 (6 pass@k + 1 paraphrase) | ≥80% | AgentMirror / Consistency Score |
| 10. 结果利用 | 2 | ≥80% | Result Utilization (六维轨迹) |
| 11. 计划连贯性 | 4 | ≥80% | Plan Coherence (六维轨迹) |
| 12. 状态转换 | 3 | ≥85% | State Transition (LangGraph四层) |
| 13. 性能与成本 | (S16 追加) | — | Latency/Cost (Google Cloud) |
| 14. 回归+监控 | 5 (defects) + CI gates + 9 alerts | 100% | CI Gate + Production Monitor |
| **总计** | **~111** | — | — |

创建完整的 docs/evals-design.md（含 14 维度 + 22 种断言 + PRD 覆盖矩阵 + 业界对标 + CI 门禁 + 生产告警）。
```

**验证**：
- [ ] `evals/run_evals.py` 含 `--ci` 门禁模式 + 14 个维度独立阈值
- [ ] `docs/evals-design.md` 含业界对标表 + 最终维度总览
- [ ] 生产告警阈值 PRODUCTION_ALERTS 完整（9 项指标）

---

## 发生了什么（教师参考）

### 1. 业界为什么都在"测轨迹不测文本"？

2026 年业界共识：Agent 的最终回答通常看起来没问题，但**状态机可能已经坏了**。一个被引用的案例：Agent 的 TaskCompletion 得分 0.93，但实际状态机有严重 bug——最终答案恰好正确掩盖了中途的工具调用错误。

ChemAI 的做法与 LangGraph 2026 最佳实践一致：**评测的单位是状态转换（state_before → node → state_after → edge_taken），不是最终消息。**

### 2. 为什么是 14 维度而不是更少？

对标三个业界标准框架：

| ChemAI 维度 | 对标框架 |
|------------|---------|
| 1-4 (路由/工具/工作流/约束) | 六维轨迹框架 (Tool Selection / Argument Extraction / Task Completion) |
| 5-6 (边界/错误恢复) | LangGraph 四层架构 (Error Recovery) |
| 7 (跨角色) | 企业级 RBAC Testing |
| 8 (SSE) | Integration Testing |
| 9 (一致性) | AgentMirror + Google Cloud Consistency Score |
| 10-11 (结果利用/计划) | 六维轨迹框架 (Result Utilization / Plan Coherence) |
| 12 (状态转换) | LangGraph 四层架构 (Node-level State Transition) |
| 13-14 (性能/回归+监控) | Monday.com 双轨 (Offline + Online) + Google Cloud KPIs |

### 3. Pass@k 为什么是必须的？

LLM 的非确定性意味着：**一次通过不代表稳定通过。** Pass@k = 同一场景跑 k 次，k 次全部通过才算通过。这是业界评估 Agent 可靠性的核心指标。ChemAI 的规则引擎场景（balance_equation）要求 k=5 且 100% 一致——因为确定性规则不该有方差。

### 4. Checkpoint Replay 的实战价值

LangGraph 的 checkpoint 机制允许你：抓取生产故障的 checkpoint_id → 回放 → 确定性重现 → 转为回归测试用例。这解决了 Agent 最头疼的问题——"用户报告了 bug，但我复现不了"。

### 6. 旧评测文档和新 EVALS 的关系——不删、不改、映射

项目中已有的 21 份评测文档（`评测文档/`）是功能模块视角的输出质量评测。新课 EVALS 是行为维度视角的轨迹评测。两者是**互补关系**，不是替代关系：

| 旧文档（保留不删） | 在新 EVALS 中的作用 |
|------------------|-------------------|
| F1-F7 功能测试用例（7 份） | 基线场景的 input/expected 原材料 |
| 化学审核专项（3 份：配平/条件/产物） | 维度 4 (行为约束) 的断言来源 |
| LLM 专项评测（4 份：出题/审核/诊断/关联） | 维度 10 (结果利用) 的质量基准 |
| 性能测试方案 | 维度 13 的基线参考（S16 使用） |
| 安全测试方案 | 维度 7 (跨角色) 的权限矩阵来源 |
| 测试报告（3 份） | 维度 14 (已知缺陷回归) 的 bug 列表 |
| v1.0 总览 + v2.0 Agent 测评体系 | evals-design.md 的参考框架 |

学生在执行 S9 各步骤时，先读对应的旧评测文档，将其中可用的测试数据转化为轨迹断言场景。旧文档继续保留在 `评测文档/` 作为详细参考——EVALS 需要"原材料"，旧文档就是原材料仓库。

---

## 课后产出检查

- [ ] `evals/` 目录结构完整（9 个子目录 + conftest.py + run_evals.py）
- [ ] `evals/conftest.py` 完整（EvalReport 14 维度版 + 22 种断言 + 回归引擎）
- [ ] `evals/baseline/golden_scenarios.py` 完整（35 个场景 × 4 维度）
- [ ] `evals/boundary/edge_scenarios.py` 完整（20 个场景 × 2 维度）
- [ ] `evals/cross_role/role_scenarios.py` 完整（6 个场景）
- [ ] `evals/sse/test_sse_streaming.py` 完整（5 个场景）
- [ ] `evals/gateway/test_gateway_router.py` 完整（24 个路由用例）
- [ ] `evals/regression/known_defects.py` 完整（5 个已知缺陷场景）
- [ ] `evals/consistency/test_passk.py` 完整（7 个一致性场景）
- [ ] `evals/plan/test_plan_coherence.py` 完整（6 个计划+结果利用场景）
- [ ] `evals/checkpoint/test_checkpoint_replay.py` 完整（3 个 checkpoint replay 场景）
- [ ] `docs/evals-design.md` 完整（14 维度 + 业界对标 + CI 门禁 + 生产告警 + 旧文档整合映射表）
- [ ] 旧评测文档（`评测文档/` 21 份）已阅读并作为场景定义的输入参考，保留不删
- [ ] F1-F7 功能测试用例已转化为至少 15 个基线场景的 input/expected
- [ ] LLM 质量指标（准确率/召回率/幻觉率等 8 项）已纳入 result_utilization 断言
- [ ] `evals/run_evals.py` 含 `--ci` 门禁模式 + 14 个维度独立阈值
- [ ] 全量运行通过率 ≥ 85%
- [ ] `evals/regression/baseline_langgraph.json` 已建立

**下节课需要**：EVALS 体系就绪（~111 个场景 × 14 维度），CI 门禁可用，回归基线已建立。Session 10 将正式进入构建阶段——场景假设与数据库设计。**每完成一个模块，追加该模块的基线+边界场景，跑全量回归确认无退化。**
