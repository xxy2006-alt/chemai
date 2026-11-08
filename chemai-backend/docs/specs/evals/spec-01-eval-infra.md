# Spec 01 — 评估基建：快/慢双层运行器 + 门禁 + 趋势

> 状态：ready-for-agent ｜ Phase：P0 ｜ 依赖：无 ｜ 接缝：runner CLI（主接缝）
> 依据：`docs/evals/eval-system-design.md` §4（快/慢双层）、§5（门禁策略）、`docs/adr/0007-agent-eval-system.md`（快跑 100% 绿、慢跑一票否决）。

## Problem Statement

ChemAI 现有评估是零散的「基线/边界/回归」三分法：`run_evals.py` 只汇总 unit + classifier 两类，CI 里是几行手写 pytest 单文件调用，各测试文件各自为政。这带来三个用户可见的问题：

1. **开发者不知道"更新后该跑什么、什么算过"** —— 没有分层的统一入口，门禁规则不存在。
2. **发布负责人无法判断"这次更新能不能发"** —— 没有"一票否决 vs 仅趋势"的区分，也没有质量趋势记录，回答不了「Agent 变好还是变差」。
3. **评估先行工作流无法落地** —— 设计文档要求先写红评估再开发，但没有机制让"预期失败的新评估"不挡门禁，门禁第一天就会全挂、失去公信力。

本 spec 只解决地基问题：把运行与门禁机制建起来，各层评估内容本身（L0-L6 的具体用例）在后续 spec 逐层补齐。

## Solution

从用户视角：**开发者**每次更新跑一条命令 `python evals/run_evals.py --fast`（秒级、零 LLM 成本）即可完成门禁自查，CI 用同一命令拦截坏 PR；**发布负责人**在发布前跑 `python evals/run_evals.py --slow`（分钟级、花 token），得到一份区分"严重错误（拦发布）"与"分数（仅趋势）"的报告；报告自动累积成历史序列，随时可查趋势。**评估先行的红评估**用 `expected_fail` 标记声明"我现在就该红"，不挡门禁，开发完成后去掉标记自动转常驻。

## User Stories

1. 作为一个开发者，我想要一条命令跑完整个快跑层，这样我可以在每次更新后几秒内、零成本地自查。
2. 作为一个开发者，我想要快跑层任一确定性断言失败时命令以非零退出，这样 CI 能直接用它拦截有问题的 PR。
3. 作为一个开发者，我想要在功能还没实现时先写评估（此时必然红），这样我能用评估定义"什么算好"（评估即 spec）。
4. 作为一个开发者，我想要红评估带 `expected_fail` 标记时不导致门禁失败，这样评估先行工作流不会让 CI 从第一天起全红。
5. 作为一个开发者，我想要当标记了 `expected_fail` 的评估意外变绿时收到明确提醒（"功能可能已完成，请移除标记转常驻"），这样不会出现"默默变绿但仍在豁免名单里"的死标记。
6. 作为一个开发者，我想要新增一个测试文件只需在层注册表里登记一行，这样分层结构清晰且新层接入零摩擦。
7. 作为一个发布负责人，我想要一条命令跑慢跑层，这样发布前能拿到判官/安全/端到端的完整质量画像。
8. 作为一个发布负责人，我想要慢跑层只有"严重错误"（化学错误、安全问题、端到端失败）才一票否决发布，而判官分数只记录不拦截，这样能避免分数噪声误拦发布。
9. 作为一个发布负责人，我想要每次运行的报告区分 pass / warn / fail / severe 四级，这样一眼就能做出发布决策。
10. 作为一个产品/教研负责人，我想要慢跑层分数自动累积成历史序列，这样我能回答「Agent 变好还是变差」并看到趋势。
11. 作为一个维护者，我想要每次慢跑记录判官调用次数与预估成本（¥），这样能确认月度预算（¥500 内）受控。
12. 作为一个维护者，我想要报告文件按运行时间归档、格式稳定，这样趋势统计与后续的看板消费不会因格式漂移而失效。
13. 作为一个开发者，我想要运行器在 Windows 开发机与 ubuntu CI 上行为一致，这样本地结论与 CI 结论不会打架。
14. 作为一个发布负责人，我想要单次运行结束打印一行总览（层通过情况 + 是否否决），这样不用翻全文就能决策。

## Implementation Decisions

1. **运行器是唯一入口**：`run_evals.py` 升级为快/慢双层统一入口，新增 `--fast` / `--slow` 两个互斥 flag；现有的 `--unit` / `--classifier` 语义并入层注册表，不再作为独立 flag 存在（保留兼容提示）。
2. **层注册表**：在 `evals/` 内维护一个层注册表（数据即代码，一张表），把七层映射到测试模块与运行层：快跑 = L0 + L1 + L4 + L5，慢跑 = L2 + L3 + L6。本 spec 中 L2/L4/L6 尚无内容，注册表允许"空层"占位并在报告中标注"未实现"。
3. **门禁规则（两级）**：快跑层 100% 必须绿——任一失败 → exit code 非零；慢跑层——severe 级结果 → 一票否决（exit 非零），warn/fail（非 severe）只入报告与趋势，不影响退出码。
4. **`expected_fail` 机制（评估先行）**：两层都支持；在测试用例级标记（L1 场景在 golden yaml 加 `expected_fail: true` 字段；pytest 系层用对应 marker 或注册表内登记用例 id）。行为：标记且红 → 计为 pending，不进失败统计；标记且绿 → 通过但打印醒目标志"请移除 expected_fail"。注册表驱动，运行器统一解释。
5. **报告结构**：沿用 `EvalReport` 汇总形态，扩展为按层分组、每条结果带 severity（pass/warn/fail/severe）与层标签；`--save` 时写入按时间戳归档的报告文件（`evals/reports/<timestamp>.json`），同时维护 `evals/reports/index.json` 作为历史序列（趋势数据源）。兼容读取现有 `eval_report.json` 的字段习惯，但新文件从本 spec 起用新结构。
6. **成本台账**：报告内嵌 cost 段（判官调用次数 + 预估 ¥）；本 spec 慢跑层尚无判官，cost 恒为 0，字段先占位，Spec 04 填充。
7. **CI 接线**：`ci.yml` 的 deterministic job 改为 `python evals/run_evals.py --fast` 单一调用；imports/docker job 不动。慢跑层本 spec 不进 CI（判官未建、成本未控），Spec 04 落地后以 nightly schedule + 发布前手动触发接入。
8. **跨平台**：运行器只用 pathlib 与标准库，不依赖 bash 特性；exit code 语义两平台一致。
9. **本 spec 不改任何现有测试文件的内容**（surgical）：只改运行器、注册表、报告写入与 CI 调用行；现有测试文件的行为断言保持原样。

## Testing Decisions

- **测试对象**：运行器自身的外部行为——exit code、报告文件生成与结构、门禁裁决（含 expected_fail 四种组合：红+标记 / 绿+标记 / 红+无标记 / 绿+无标记）、空层占位展示。
- **只测外部行为，不测实现细节**：断言 exit code、报告 JSON 结构、标准输出关键行；不断言内部函数名与中间对象。
- **假评估套件**：新建 `evals/test_runner.py`（快跑层内、零 LLM、纯标准库），内置"永远绿 / 永远红 / expected_fail 四组合"的假用例模块，驱动运行器断言门禁裁决。这是本仓库第一份"测评估系统本身"的元测试。
- **Prior art**：`conftest.py` 的 `EvalReport` 与 `run_evals.py` 现有汇总逻辑；CI `deterministic` job 的 pytest 调用方式。
- **验收命令**：
  1. `python evals/run_evals.py --fast` 在本地全绿退出 0；
  2. 人为注入一个红用例（临时改假套件）→ `--fast` 退出非零；
  3. `--save` 后 `evals/reports/` 下出现报告文件且 `index.json` 增加一条；
  4. 现有全部 pytest（`tests/` + `evals/`）仍全绿，`ci.yml` deterministic job 模拟运行通过。

## Out of Scope

- L0/L1/L4/L5 的评估内容扩充与 L4 埋点（Spec 02）
- read/write/edit/bash 四件套工具及沙箱（Spec 03）
- L2 判官 harness、rubric、校准集、人机兜底（Spec 04）
- 出题智能化 persona/prompt 开发（Spec 05）
- planner 接入与 L6 端到端场景（Spec 06）
- 慢跑层的 CI 自动化（nightly schedule，随 Spec 04 落地）
- 趋势可视化看板（先只落 JSON 历史，看板另行立项）
- 前端任何改动

## Further Notes

- 术语对齐设计文档：快跑层 / 慢跑层 / 判官 / 校准集 / 黄金场景 / 评估先行，见 `docs/evals/eval-system-design.md` §8。
- 门禁语义与 ADR-0007 一致：快跑 100% 绿是第一道闸；慢跑分数有噪声，只做趋势。
- 上一轮规划中遗留的两个执行决策在本 spec 已定：慢跑层载体 = nightly schedule + 发布前手动触发（本 spec 只留 CLI，CI 部分在 Spec 04 落地）；快/慢双层从 P0 先跑、零 LLM 成本。
- 本 spec 验收通过后，Spec 02（快跑层加固）与 Spec 04（判官）可并行。
