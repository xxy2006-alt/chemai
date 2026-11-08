# Spec 02 — 快跑层加固：L0 摸底 + L4 埋点 + L1 扩充

> 状态：ready-for-agent ｜ Phase：P1 ｜ 依赖：Spec 01 ｜ 接缝：runner CLI（1）、golden schema（2）、埋点包装器（4）
> 依据：`docs/evals/eval-system-design.md` §2（L0/L1/L4）、§4（快跑层 = L0+L1+L4+L5）。

## Problem Statement

Spec 01 建起了快/慢双层的运行骨架，但快跑层的内容还撑不起"第一道闸"：L0 只覆盖少数工具的 happy path（`test_unit_tools.py` 是雏形），agent 注册的 26 个工具大部分没有任何确定性断言；L4 性能预算完全空白——延迟、token、循环数无人测量，runaway loop 只能靠 `recursion_limit=12` 硬切；L1 golden 场景缺管理类动作（删除题库、批量导入等），破坏性操作的轨迹无人校验。快跑层因此无法兑现"每次更新必跑、挂了就是真挂了"的门禁承诺。

## Solution

从用户视角：**开发者**每次更新跑 `--fast` 时，得到的不再是"抽查几个工具"，而是全工具覆盖的确定性断言 + 每次 agent 运行的性能指标（延迟/token/循环数）+ 管理动作轨迹校验。任何工具干错、任何轨迹偏离、任何性能指标越界（以软警告起步），都在报告中可见；确定性失败依旧 100% 拦门禁。

## User Stories

1. 作为一个开发者，我想要每个已注册工具都有至少一条确定性断言，这样工具被改坏时快跑层必然拦截。
2. 作为一个开发者，我想要 L0 测试保持零 LLM 依赖，这样它们在 CI 上几秒内跑完、不花一分钱。
3. 作为一个开发者，我想要 L0 不只覆盖 happy path，还覆盖坏参数与缺资源等错误路径，这样工具的错误处理本身也被测。
4. 作为一个开发者，我想要一份"工具 → 是否有 L0 测试"的覆盖率清单，且运行器对未覆盖工具打警告，这样覆盖缺口可见而不是沉默。
5. 作为一个开发者，我想要一个薄包装器对任意 agent 运行产出 `{latency, tokens, iterations}` 指标，这样 L4 预算断言有统一数据源。
6. 作为一个开发者，我想要 L4 的 SLO 阈值断言以软警告（warn）起步，这样阈值可以先用真实数据校准，不阻碍开发。
7. 作为一个开发者，我想要循环数 SLO 与 `recursion_limit=12` 对齐，这样 runaway loop 在切断前就能被指标发现。
8. 作为一个发布负责人，我想要快跑层报告里带每次运行的性能数字，这样性能漂移可见、可追。
9. 作为一个开发者，我想要 golden yaml 新增管理类动作场景（删除题库需 approval、批量导入等），这样破坏性动作的轨迹被校验。
10. 作为一个测试者，我想要新场景继续沿用现有断言 schema（tool_called/tool_arg/route 等），这样旧场景零迁移成本。
11. 作为一个维护者，我想要 L0 测试的组织按工具模块镜像排布，这样新工具一进来就知道测试写哪。
12. 作为一个开发者，我想要快跑层整体在本地保持秒级完成（目标 <60s），这样它配得上"每次提交都跑"。
13. 作为一个开发者，我想要 golden 场景中已知未实现的行为（known_gaps 对齐）用 `expected_fail` 标记，这样评估先行与门禁互不冲突。
14. 作为一个维护者，我想要 L5 回归层在本 spec 保持原样不动，这样稳定性验证不因本次加固而引入新变量。

## Implementation Decisions

1. **L0 全覆盖摸底**：逐个审计 `agent.tools.TOOLS` 的 26 个工具，为缺失者补确定性断言（纯逻辑、零 LLM）；现有 `test_unit_tools.py` 的断言保留，测试文件按工具模块镜像拆分/新增。
2. **覆盖率清单（数据即代码）**：在层注册表（Spec 01）内维护"工具 → L0 测试存在性"清单；运行器在快跑报告中对无测试工具打印 warning 行。清单不进门禁（门禁只认测试实际结果），但让覆盖缺口永不被沉默掩盖。
3. **L4 埋点包装器（接缝 4）**：`evals/metrics.py` 提供 `invoke_with_metrics(agent, input) -> {latency, tokens, iterations}` 薄包装——latency 为墙钟耗时；tokens 优先读 LangGraph 响应消息的 `usage_metadata`，读不到时记 null 并降级该 SLO 为"未测量"；iterations 数 agent 消息轮次/工具调用轮数。agent 本体代码不动。
4. **SLO 阈值（软警告起步）**：首批阈值——单轮延迟 p95 ≤ 60s、单次运行 tokens ≤ 40k、循环数 ≤ 12（与 recursion_limit 对齐）。**全部 warn 级**：越界打印警告并计入报告，不进失败统计、不拦门禁；阈值本身写在注册表，便于日后收紧。校准数据积累一轮后（Spec 04 慢跑层落地时）再讨论转 fail 级。
5. **L1 golden 扩充（接缝 2）**：`agent_eval_golden.yaml` 新增管理类场景：删除题库（必须先调 `request_approval`、未批准不得执行）、批量导入、分配自适应练习等；与 `known_gaps` 对齐的未实现行为用 `expected_fail: true` 标记（机制由 Spec 01 提供）。断言只复用既有类型，不新增 schema。
6. **L5 不动**：回归层（`test_regression_*.py`、快照对比）本 spec 零改动。
7. **门禁语义不变**：确定性失败仍 100% 拦；warn（SLO、覆盖率）只报不拦。

## Testing Decisions

- **L0 测试本身**：纯函数级确定性断言，零 LLM、零 API——外部行为（输入输出、副作用、报错消息），不测内部实现。Prior art：`evals/test_unit_tools.py` 现有风格。
- **L4 包装器测试**：用假 agent（确定性 stub，返回带/不带 `usage_metadata` 的 canned 消息序列）测指标提取正确性，零真实 API 调用；SLO 断言逻辑用假指标验证 warn/不拦语义。
- **覆盖率清单测试**：`test_runner.py`（Spec 01 元测试）增补——未覆盖工具出现在警告行、覆盖工具不出现。
- **golden 新场景验证**：`--golden`（需 API，CI 不跑）；管理类场景的 `expected_fail` 语义由 `test_runner.py` 的四组合用例覆盖。
- **验收命令**：
  1. `python evals/run_evals.py --fast` 全绿、秒级退出 0，报告中出现 SLO 段与覆盖率警告行；
  2. 26 个工具在覆盖率清单中全覆盖（或未覆盖者以 warning 显式列出）；
  3. `pytest evals/test_runner.py -q` 全绿（含 expected_fail 四组合）；
  4. 现有全部 pytest 与 CI deterministic job 仍绿。

## Out of Scope

- read/write/edit/bash 四件套及沙箱（Spec 03）
- L2 判官（Spec 04）——L4 阈值转 fail 级的讨论也随 Spec 04 慢跑层数据再做
- 出题智能化（Spec 05）
- planner 接线与 L6（Spec 06）
- SLO 的告警外发（企微/钉钉）与性能看板
- 快跑层"覆盖率不足即拦截"（本 spec 只警告；何时升级拦截另行决策）

## Further Notes

- L4 是软警告起步，符合设计文档"软警告起步"的明确要求；本 spec 的关键产出是**埋点接缝**（接缝 4），阈值收紧是后续免费动作。
- tokens 读取依赖 LangGraph 消息的 `usage_metadata` 实际可用性，实现时若发现该版本不携带，以 iterations + latency 先行，tokens 记为"未测量"，并在报告中如实标注（诚实优先于假装）。
- 26 个工具的数字以 `ci.yml` imports job 的断言为准，工具增减时覆盖率清单与 CI 断言需同步更新（Spec 03 会改这个数字，注意不要打架）。
