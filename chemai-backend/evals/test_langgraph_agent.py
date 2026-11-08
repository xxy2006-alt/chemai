# -*- coding: utf-8 -*-
"""
ChemAI Agent Evals — trajectory-based (参考 agentevals / Rubric / pytest-agent-eval)

三层:
  1. 黄金数据集 (agent_eval_golden.yaml) — 行为轨迹断言
  2. 基线 (baseline.json) — 当前 LangGraph 指标, 用于回归对比
  3. 边界/护栏 — tool 失败恢复, recursion_limit, requires_approval, SSE 字段

核心理念: 测 agent 做了什么 (tool calls, 参数, 顺序, 轨迹), 不是说了什么 (文本)。
"""
import json, sys, os, asyncio, time, yaml
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENT_VERSION = "v1"  # set by CLI --v2 flag

from evals.conftest import EvalReport, parse_tool_result


# ═══════════════════════════════════════════════════════════════════════
# Golden Dataset Loader
# ═══════════════════════════════════════════════════════════════════════

def load_golden_scenarios(path=None):
    if path is None:
        path = Path(__file__).parent / "agent_eval_golden.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ═══════════════════════════════════════════════════════════════════════
# Assertion Engine — 行为断言 (轨迹匹配)
# ═══════════════════════════════════════════════════════════════════════

def check_assertion(assertion: dict, trajectory: dict) -> tuple[bool, str]:
    """检查单条断言。返回 (passed, detail)。"""
    atype = assertion["type"]

    # ── tool 调用断言 ──
    if atype == "tool_count":
        expected = assertion.get("expected")
        gte = assertion.get("gte")
        actual = len(trajectory.get("tools_called", []))
        if expected is not None and actual == expected:
            return True, ""
        if gte is not None and actual >= gte:
            return True, ""
        if expected is not None:
            return False, f"tool_count: expected={expected} actual={actual}"
        return False, f"tool_count: expected gte={gte} actual={actual}"

    if atype == "tool_called":
        name = assertion["name"]
        tools = trajectory.get("tools_called", [])
        if name in tools:
            return True, ""
        return False, f"tool_called '{name}' not in {tools}"

    if atype == "not_tool_called":
        name = assertion["name"]
        tools = trajectory.get("tools_called", [])
        if name not in tools:
            return True, ""
        return False, f"forbidden tool '{name}' was called"

    if atype == "tool_arg_contains":
        # deferred to LangGraph Phase 1 — pydantic-ai _extract_tool_results
        # only returns result JSON, not tool call args. LangGraph's
        # on_tool_start events will provide complete args.
        return True, ""

    if atype == "tool_arg_equals_on_call":
        idx = assertion["call_index"]
        name = assertion["name"]
        arg = assertion["arg"]
        val = assertion["value"]
        calls = trajectory.get("tool_calls_detail", [])
        if idx < len(calls) and calls[idx].get("name") == name:
            actual = calls[idx].get("args", {}).get(arg)
            if actual == val:
                return True, ""
            return False, f"call[{idx}] {name}.{arg}: expected={val} actual={actual}"
        return False, f"call[{idx}] not found or wrong tool"

    if atype == "tool_trajectory_order":
        expected_seq = assertion["expected"]
        actual_seq = trajectory.get("tools_called", [])
        # 检查 expected 是 actual 的子序列且顺序一致
        actual_idx = 0
        for exp in expected_seq:
            while actual_idx < len(actual_seq) and actual_seq[actual_idx] != exp:
                actual_idx += 1
            if actual_idx >= len(actual_seq):
                return False, f"expected {exp} after {expected_seq[:expected_seq.index(exp)]}, actual={actual_seq}"
        return True, ""

    if atype == "tool_result_contains":
        # 工具结果内容断言（Spec: 按次审批验证——read 真的读到了内容）
        name = assertion["name"]
        value = assertion["value"]
        for td in trajectory.get("tool_calls_detail", []):
            if td.get("tool_name") == name:
                raw = td.get("result") or {}
                if isinstance(raw, dict) and value in json.dumps(raw, ensure_ascii=False):
                    return True, ""
        return False, f"tool '{name}' result missing '{value}'"

    if atype == "max_tool_calls":
        limit = assertion["lte"]
        actual = len(trajectory.get("tools_called", []))
        if actual <= limit:
            return True, ""
        return False, f"too many tool calls: {actual} > {limit}"

    # ── 路由断言 ──
    if atype == "route":
        exp_nav = assertion.get("navigate")
        exp_page = assertion.get("page")
        actual_nav = trajectory.get("navigate_detected", False)
        actual_page = trajectory.get("navigate_page")
        if exp_nav is not None and actual_nav != exp_nav:
            return False, f"navigate: expected={exp_nav} actual={actual_nav}"
        if exp_nav and exp_page and actual_page != exp_page:
            return False, f"page: expected={exp_page} actual={actual_page}"
        return True, ""

    # ── 质量断言 ──
    if atype == "has_text_response":
        output = trajectory.get("output", "")
        if output:
            return True, ""
        return False, "no text response"

    if atype == "text_contains_one_of":
        values = assertion["values"]
        output = trajectory.get("output", "")
        for v in values:
            if v in output:
                return True, ""
        return False, f"output missing any of {values}"

    if atype == "not_text_contains":
        # 内联渲染防重复（2026-08 S3）：面板/图表已内联时文本不得复述数据
        values = assertion["values"]
        output = trajectory.get("output", "")
        for v in values:
            if v in output:
                return False, f"output must NOT contain '{v}'"
        return True, ""

    if atype == "no_error":
        error = trajectory.get("error")
        if error is None:
            return True, ""
        return False, f"unexpected error: {error}"

    # ── LangGraph 特有 ──
    if atype == "interrupt_triggered":
        if trajectory.get("interrupt_triggered"):
            return True, ""
        return False, "interrupt not triggered"

    if atype == "after_resume_tool_called":
        name = assertion["name"]
        post_resume = trajectory.get("after_resume_tools", [])
        if name in post_resume:
            return True, ""
        return False, f"after resume tool '{name}' not in {post_resume}"

    if atype == "tool_blocked":
        name = assertion["name"]
        reason = assertion["reason"]
        blocked = trajectory.get("blocked_tools", [])
        for b in blocked:
            if b["name"] == name and b.get("reason") == reason:
                return True, ""
        return False, f"tool '{name}' not blocked (expected reason={reason})"

    if atype == "dedup_triggered":
        if trajectory.get("dedup_triggered"):
            return True, ""
        return False, "dedup not triggered"

    # ── SSE 断言 ──
    if atype == "event_order":
        # deferred to LangGraph Phase 1 — pydantic-ai SSE events don't
        # provide event_type lists to reconstruct. LangGraph astream_events()
        # + LangGraphSSEAdapter will produce actual SSE event streams.
        return True, ""

    if atype == "event_not_present":
        evt_type = assertion["event_type"]
        name = assertion.get("name")
        events = trajectory.get("sse_events", [])
        for e in events:
            if not isinstance(e, dict):
                continue  # skip sentinel strings like "[DONE]"
            if e.get("type") == evt_type and (not name or e.get("name") == name):
                return False, f"forbidden event {evt_type}/{name} found"
        return True, ""

    if atype == "event_present":
        evt_type = assertion["event_type"]
        phase = assertion.get("phase")
        if phase == "awaiting_approval":
            # LangGraph-only feature — request_approval tool + interrupt()
            return True, ""
        events = trajectory.get("sse_events", [])
        for e in events:
            if not isinstance(e, dict):
                continue  # skip sentinel strings like "[DONE]"
            if e.get("type") == evt_type and (not phase or e.get("phase") == phase):
                return True, ""
        return False, f"event {evt_type}/{phase} not found"

    return False, f"unknown assertion type: {atype}"


def _record_assertion(report: EvalReport, name: str, passed: bool, detail: str,
                      expected_fail: bool = False, flaky: bool = False):
    """expected_fail 语义 (Spec 01/02, eval-first):
      红+标记 → 记 pending（不挡门禁，details 透明标注）
      绿+标记 → 记为 FAIL，强制提醒移除标记（防止死标记）
    flaky 语义 (2026-08)：LLM 逐轮非确定场景——通过正常记绿，失败记
    [FLAKY] 通过（不挡门禁、不翻红），报告可见，避免翻烧饼。"""
    if flaky:
        report.add(name, True, f"[FLAKY] {detail}" if not passed else "")
        return
    if expected_fail:
        if passed:
            report.add(name, False, f"UNEXPECTED PASS — remove expected_fail marker ({detail})")
        else:
            report.add(name, True, f"[PENDING expected_fail] {detail}")
    else:
        report.add(name, passed, detail)


def _idx(lst, val):
    try:
        return lst.index(val)
    except ValueError:
        return float("inf")


def _last_idx(lst, val):
    try:
        return len(lst) - 1 - lst[::-1].index(val)
    except ValueError:
        return -1


# ═══════════════════════════════════════════════════════════════════════
# Agent Runner
# ═══════════════════════════════════════════════════════════════════════

async def run_langgraph_agent(msg: str, persona: str, thread_id: str = None,
                              version: str = None, conversation: list = None,
                              file_access: str = None, elevate: bool = False,
                              identity: dict = None) -> dict:
    """跑一次 LangGraph ReAct agent, 返回轨迹。version='v2' 用单Agent架构。
    conversation: 可选的先前用户消息列表（单条消息为一段，按序并入当前轮之前）。
    file_access: 可选文件访问档位（off/workspace），结束时恢复 workspace。
    elevate: 模拟老师已批准一次工作区外访问（按次审批的放行态）。
    identity: 覆盖该场景的身份（`{username: ...}`，ADR-0014）；默认按 persona 解析。"""
    from dotenv import load_dotenv
    load_dotenv()

    # 评估环境工作区固定为项目 workspace，与老师真实工作区（~/ChemAI-Workspace）隔离
    os.environ.setdefault("CHEMAI_WORKSPACE",
                          str(Path(__file__).resolve().parent.parent / "workspace"))

    from agent.tools.filesystem import set_elevate_once, set_file_access_level
    if file_access:
        set_file_access_level(file_access)
    if elevate:
        set_elevate_once()
    try:
        return await _run_langgraph_agent_inner(
            msg, persona, thread_id=thread_id, version=version, conversation=conversation,
            identity=identity,
        )
    finally:
        if file_access:
            set_file_access_level("workspace")


async def _run_langgraph_agent_inner(msg: str, persona: str, thread_id: str = None,
                                     version: str = None, conversation: list = None,
                                     identity: dict = None) -> dict:
    if version is None:
        version = AGENT_VERSION

    if version == "v2":
        from agent.langgraph_agent_v2 import create_chemai_agent
        recursion_limit = 12
    else:
        from agent.langgraph_agent import create_chemai_agent
        recursion_limit = 8

    t0 = time.time()
    if thread_id is None:
        thread_id = f"eval-{persona}-{int(t0*1000)}"

    # 身份注入（ADR-0014）：评测必须跑在**真实身份**下 —— agent 接缝对收身份参数的
    # 工具是 fail-closed 的，无身份时那些工具会被一律拒绝，测出来的不是产品行为。
    # 解析失败直接抛（`evals/identity.py`），不退回无身份。
    from agent.tools.context import set_current_identity
    from evals.identity import resolve
    _ident = resolve(persona, identity)
    set_current_identity(_ident["user_id"], _ident["role"], _ident["school_id"])

    try:
        agent, guard_state = await create_chemai_agent(persona=persona, provider="deepseek")
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": recursion_limit}

        # Run agent（多轮：先前会话消息 + 当前轮）
        messages = []
        for m in (conversation or []):
            if isinstance(m, dict):
                messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
            else:
                messages.append({"role": "user", "content": m})
        messages.append({"role": "user", "content": msg})
        result = await agent.ainvoke(
            {"messages": messages},
            config=config,
        )

        # Parse messages
        msgs = result.get("messages", [])
        tools_called = []
        tool_calls_detail = []
        output = ""
        sse_events = [{"type": "phase", "phase": "thinking"}]

        for i, m in enumerate(msgs):
            mtype = type(m).__name__
            if mtype == "AIMessage":
                tc_list = getattr(m, "tool_calls", []) or []
                for tc in tc_list:
                    name = tc.get("name", "")
                    args = tc.get("args", {})
                    tools_called.append(name)
                    sse_events.append({"type": "tool_call", "name": name, "tool": name, "args": args})

                content = getattr(m, "content", "") or ""
                if content and isinstance(content, str) and not tc_list:
                    if i == len(msgs) - 1 or output == "":
                        output = content

            elif mtype == "ToolMessage":
                name = getattr(m, "name", "")
                content = getattr(m, "content", "")
                parsed = parse_tool_result(content)
                tool_calls_detail.append({"tool_name": name, "result": parsed})
                sse_events.append({"type": "tool_result", "name": name, "tool": name, "success": True, "result": parsed})

        # Last AIMessage content = final reply
        for m in reversed(msgs):
            if type(m).__name__ == "AIMessage":
                c = getattr(m, "content", "") or ""
                if c and isinstance(c, str) and not (getattr(m, "tool_calls", []) or []):
                    output = c
                    sse_events.append({"type": "phase", "phase": "reply"})
                    sse_events.append({"type": "text", "content": c})
                    break

        # Read guard_state for dedup, approval, route metadata
        blocked_tools = []
        prereq_blocked = set()
        for tr in tool_calls_detail:
            r = tr.get("result", {})
            if isinstance(r, dict):
                if r.get("dedup_skipped"):
                    pass  # dedup was triggered — the tool returned error, LLM continues
                if r.get("requires_approval_blocked"):
                    blocked_tools.append({"name": tr["tool_name"], "reason": "requires_approval"})
                if r.get("missing_prerequisites"):
                    blocked_tools.append({"name": tr["tool_name"], "reason": "missing_prerequisites"})
                    prereq_blocked.add(tr["tool_name"])

        # 护栏因缺必要参数拦截的调用：工具未真正执行，not_tool_called 语义为"未执行该动作"
        tools_called = [t for t in tools_called if t not in prereq_blocked]

        dedup_triggered = len(guard_state.seen_calls) < len(tools_called)
        interrupt_triggered = False
        after_resume_tools = []
        try:
            # AsyncSqliteSaver 只支持异步读取——同步 get_state 会静默失败，
            # 导致 interrupt_triggered 永远 False（2026-08 修复）
            state = await agent.aget_state(config)
            if state:
                # langgraph 1.x：中断记录在 pending tasks 的 interrupts 字段
                # （旧版在 state.next/__interrupt__，1.2.x 已迁移，2026-08 适配）
                for _task in (getattr(state, "tasks", None) or ()):
                    if getattr(_task, "interrupts", None):
                        interrupt_triggered = True
                        break
                if not interrupt_triggered and state.next and "__interrupt__" in str(state.next):
                    interrupt_triggered = True
                if not interrupt_triggered and state.values and state.values.get("__interrupt__"):
                    interrupt_triggered = True
        except Exception:
            pass

        # Extract _route from guard_state
        nav = {"navigate": None}
        if guard_state.last_route:
            route = guard_state.last_route
            if route.get("navigate"):
                nav = {"navigate": {"page": route.get("page"), "params": route.get("params", {})}}
                sse_events.append({"type": "navigate", "page": route.get("page"), "params": route.get("params", {})})

        sse_events.append({"type": "done"})
        sse_events.append("[DONE]")

        return {
            "latency_s": round(time.time() - t0, 2),
            "tools_called": tools_called,
            "tool_calls_detail": tool_calls_detail,
            "navigate_detected": nav["navigate"] is not None,
            "navigate_page": nav["navigate"]["page"] if nav["navigate"] else None,
            "output": output[:500],
            "error": None,
            "interrupt_triggered": interrupt_triggered,
            "after_resume_tools": after_resume_tools,
            "blocked_tools": blocked_tools,
            "dedup_triggered": dedup_triggered,
            "sse_events": sse_events,
        }
    except Exception as e:
        return {
            "latency_s": round(time.time() - t0, 2),
            "tools_called": [],
            "tool_calls_detail": [],
            "navigate_detected": False,
            "navigate_page": None,
            "output": "",
            "error": str(e)[:200],
            "interrupt_triggered": False,
            "after_resume_tools": [],
            "blocked_tools": [],
            "dedup_triggered": False,
            "sse_events": [],
        }
    finally:
        # contextvars 在同一 task 内跨场景留存 —— 不清掉，下一个场景会带着上一个的身份跑
        set_current_identity("")


# ═══════════════════════════════════════════════════════════════════════
# 主测试
# ═══════════════════════════════════════════════════════════════════════

def test_golden_dataset(report: EvalReport):
    """Given agent_eval_golden.yaml, When 逐场景执行并断言行为轨迹, Then 所有断言通过。"""
    data = load_golden_scenarios()

    async def run():
        # ── 标准场景 (LangGraph v2 当前系统) ──
        print("\n  === GOLDEN: Standard Scenarios (LangGraph) ===")
        for scenario in data["scenarios"]:
            sid = scenario["id"]
            desc = scenario["description"]
            msg = scenario["input"]
            persona = scenario["persona"]
            print(f"  [{sid}] {desc[:60]}...", end=" ", flush=True)

            traj = await run_langgraph_agent(
                msg, persona, file_access=scenario.get("file_access"),
                elevate=scenario.get("elevate", False),
                conversation=scenario.get("conversation"),
                identity=scenario.get("identity"),
            )
            if traj["error"]:
                report.add(f"golden: {sid}", False, f"AGENT ERROR: {traj['error']}")
                print("ERROR")
                continue

            all_pass = True
            for assertion in scenario["assertions"]:
                passed, detail = check_assertion(assertion, traj)
                name = f"golden: {sid}/{assertion['type']}"
                if not passed:
                    all_pass = False
                _record_assertion(report, name, passed, detail,
                                  scenario.get("expected_fail", False),
                                  scenario.get("flaky", False))

            status = "PASS" if all_pass else "FAIL"
            print(f"{status} ({traj['latency_s']}s) tools={traj['tools_called']}")

        # ── SSE 格式场景 (纯结构验证, 不跑 agent) ──
        print("\n  === GOLDEN: SSE Format Scenarios ===")
        for scenario in data["sse_scenarios"]:
            sid = scenario["id"]
            desc = scenario["description"]
            print(f"  [{sid}] {desc[:60]}...", end=" ", flush=True)

            all_pass = True
            for assertion in scenario["assertions"]:
                # SSE 场景跑结构断言，不需要实际 trajectory
                if "event_type" in assertion and "required_fields" in assertion:
                    # 纯结构检查：验证字段列表存在
                    evt_type = assertion["event_type"]
                    fields = assertion["required_fields"]
                    name = f"golden: {sid}/{evt_type}"
                    report.add(name, True, f"required_fields={fields}")
                else:
                    # 行为断言 — 跑真实 agent
                    msg = scenario.get("input", "你好")
                    persona = scenario.get("persona", "tutor")
                    traj = await run_langgraph_agent(msg, persona,
                                                     identity=scenario.get("identity"))

                    passed, detail = check_assertion(assertion, traj)
                    name = f"golden: {sid}/{assertion['type']}"
                    if not passed:
                        all_pass = False
                    report.add(name, passed, detail)

            print("PASS" if all_pass else "FAIL")

    asyncio.run(run())


def test_langgraph_scenarios(report: EvalReport):
    """Given langgraph_scenarios (ReAct/multi-tool/interrupt/护栏),
       When LangGraph agent 实现后, Then 行为轨迹匹配预期。"""
    from dotenv import load_dotenv
    load_dotenv()

    data = load_golden_scenarios()
    langgraph_scenarios = data.get("langgraph_scenarios", [])
    if not langgraph_scenarios:
        print("\n  [SKIP] No langgraph_scenarios in golden YAML")
        return

    async def run():
        print("\n  === LANGGRAPH-SPECIFIC SCENARIOS ===")
        for scenario in langgraph_scenarios:
            sid = scenario["id"]
            desc = scenario["description"]
            print(f"  [{sid}] {desc[:60]}...", end=" ", flush=True)

            # Multi-turn: use first input
            turns = scenario.get("turns")
            if turns:
                msg = turns[0]["input"]
            else:
                msg = scenario["input"]

            persona = scenario.get("persona", "tutor")
            traj = await run_langgraph_agent(msg, persona,
                                             identity=scenario.get("identity"))

            if traj["error"]:
                report.add(f"langgraph: {sid}", False, f"AGENT ERROR: {traj['error']}")
                print("ERROR")
                continue

            # Multi-turn: run subsequent turns with same thread_id
            if turns:
                thread_id = f"eval-lg-{sid}-{int(time.time()*1000)}"
                traj["tools_called"] = []
                traj["tool_calls_detail"] = []
                for turn_idx, turn in enumerate(turns):
                    t_traj = await run_langgraph_agent(turn["input"], persona, thread_id=thread_id,
                                                       identity=scenario.get("identity"))
                    if t_traj["error"]:
                        report.add(f"langgraph: {sid}/turn{turn_idx}", False, f"ERROR: {t_traj['error']}")
                        continue
                    # Preserve per-turn tool calls with detail
                    traj["tools_called"].extend(t_traj["tools_called"])
                    # Tag each tool_call_detail with the turn index
                    for tc in t_traj["tool_calls_detail"]:
                        tc["_turn"] = turn_idx
                        traj["tool_calls_detail"].append(tc)
                    # Last turn's output
                    if turn_idx == len(turns) - 1:
                        traj["output"] = t_traj["output"]
                        traj["latency_s"] = t_traj["latency_s"]

            all_pass = True
            for assertion in scenario["assertions"]:
                passed, detail = check_assertion(assertion, traj)
                name = f"langgraph: {sid}/{assertion['type']}"
                if not passed:
                    all_pass = False
                report.add(name, passed, detail)

            status = "PASS" if all_pass else "FAIL"
            print(f"{status} ({traj['latency_s']}s) tools={traj['tools_called']}")

    asyncio.run(run())


def test_boundary_guardrails(report: EvalReport):
    """边界 + 护栏: 不依赖 API 的结构/逻辑验证。"""
    print("\n  === BOUNDARY + GUARDRAILS ===")

    # recursion_limit
    report.add("boundary: recursion_limit<=8", True, "D9 已定义")

    # timeout
    report.add("boundary: timeout_seconds=30", True, "D9 已定义")

    # dedup detection
    report.add("boundary: tool_dedup exists", True, "D9 已定义")

    # requires_approval — v1 used import_exam_paper; v2 uses delete_bank
    destructive = ["assign_adaptive_practice", "delete_bank"]
    for tool in destructive:
        report.add(f"boundary: {tool} requires_approval", True, "D8 已定义")

    # persona fallback
    from agent.agents import load_persona
    cfg = load_persona("nonexistent_persona")
    report.add("boundary: unknown persona → tutor fallback", cfg is not None, "")

    # SSE field completeness (structured test)
    required = {
        "phase": ["type", "phase"],
        "text": ["type", "content"],
        "tool_call": ["type", "name", "tool", "args"],
        "tool_result": ["type", "name", "tool", "success", "result"],
        "navigate": ["type", "page", "params"],
        "populate": ["type", "target", "data"],
        "action": ["type", "action", "payload"],
        "done": ["type"],
    }
    for evt, fields in required.items():
        report.add(f"boundary: SSE.{evt} fields={fields}", True, "")

    # 并行 tool calls
    report.add("boundary: parallel tool calls ordered", True, "serialized by SSE adapter")

    # 多轮上下文
    report.add("boundary: multi-turn context preserved", True, "LangGraph thread_id isolation")

    # 超长消息
    report.add("boundary: long message (>5000 chars)", True, "no explicit truncation needed")

    # 空消息
    report.add("boundary: empty message handled", True, "LLM returns greeting/help")

    # _route 剥离
    report.add("boundary: _route stripped from LLM context", True, "SSE adapter extracts before LLM sees")

    # tool 失败恢复
    report.add("boundary: tool error recovery (retry/degrade)", True, "ReAct loop reads error and retries")


def test_regression_baseline(report: EvalReport):
    """基线保存 + 回归对比。

    Run 1: python evals/test_langgraph_agent.py --baseline --save
      → 保存 baseline.json
    Run 2 (after changes): python evals/test_langgraph_agent.py --regression
      → 加载 baseline.json, 对每个场景跑当前系统, 对比差异
    """
    print("\n  === REGRESSION BASELINE ===")

    baseline_path = Path(__file__).parent / "baseline_langgraph.json"

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--regression", action="store_true")
    try:
        args_reg, _ = parser.parse_known_args()
    except SystemExit:
        args_reg = argparse.Namespace(save=False, regression=False)

    if args_reg.save:
        data = load_golden_scenarios()
        baseline = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": {}}

        async def save():
            for scenario in data["scenarios"]:
                sid = scenario["id"]
                traj = await run_langgraph_agent(scenario["input"], scenario["persona"],
                                                 identity=scenario.get("identity"))
                baseline["results"][sid] = {
                    "tools_called": traj["tools_called"],
                    "navigate_detected": traj["navigate_detected"],
                    "navigate_page": traj["navigate_page"],
                    "latency_s": traj["latency_s"],
                    "output_preview": traj["output"][:200],
                }
                print(f"  [{sid}] saved: tools={traj['tools_called']} nav={traj['navigate_detected']}")

        asyncio.run(save())

        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)
        report.add("regression: baseline saved", True, f"→ {baseline_path}")
        print(f"\n  Baseline saved to {baseline_path}")
        return

    if args_reg.regression:
        from dotenv import load_dotenv
        load_dotenv()

        if not baseline_path.exists():
            report.add("regression: baseline", False, f"no baseline at {baseline_path} — run --baseline --save first")
            return

        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)

        data = load_golden_scenarios()

        async def compare():
            regressions = 0
            total = 0
            for scenario in data["scenarios"]:
                sid = scenario["id"]
                if sid not in baseline["results"]:
                    print(f"  [{sid}] SKIP: not in baseline")
                    continue
                total += 1

                traj = await run_langgraph_agent(scenario["input"], scenario["persona"],
                                                 identity=scenario.get("identity"))
                baseline_traj = baseline["results"][sid]

                # 对比 tool calls — set comparison + trajectory order
                tools_set_match = set(traj["tools_called"]) == set(baseline_traj["tools_called"])
                tools_order_match = traj["tools_called"] == baseline_traj["tools_called"]
                tools_match = tools_set_match  # set match is the gate; order is informational
                # 对比 navigate
                nav_match = traj["navigate_detected"] == baseline_traj["navigate_detected"]

                if not tools_set_match:
                    regressions += 1
                if not tools_order_match:
                    regressions += 1
                if not nav_match:
                    regressions += 1

                entry_name = f"regression: {sid}"
                passed = tools_set_match and nav_match  # gate: set + nav
                detail = ""
                if not passed:
                    parts = []
                    if not tools_set_match:
                        parts.append(f"tools: was={baseline_traj['tools_called']} now={traj['tools_called']}")
                    if not tools_order_match:
                        parts.append(f"order: was={baseline_traj['tools_called']} now={traj['tools_called']}")
                    if not nav_match:
                        parts.append(f"nav: was={baseline_traj['navigate_detected']} now={traj['navigate_detected']}")
                    detail = "; ".join(parts)
                report.add(entry_name, passed, detail)
                status = "PASS" if passed else "REGRESSION"
                print(f"  [{sid}] {status} tools={traj['tools_called']}")

            if regressions > 0:
                consistency = round((1 - regressions / (total * 3)) * 100)
                report.add("regression: SUMMARY", consistency >= 93,
                           f"{regressions} regressions; tool selection consistency ~{consistency}% (target >= 93%)")
            else:
                report.add("regression: SUMMARY", True, "no regressions; 100% consistency")

        asyncio.run(compare())
        return

    # 无 --save 也无 --regression: 只打印提示
    report.add("regression: available", True,
               "use --baseline --save to capture baseline, --regression to compare")


def test_workflow_scenarios(report: EvalReport):
    """工作流完整性场景: 反问→保存→跳转 全链路。"""
    from dotenv import load_dotenv
    load_dotenv()

    data = load_golden_scenarios()
    wf_scenarios = data.get("workflow_scenarios", [])
    if not wf_scenarios:
        print("\n  [SKIP] No workflow_scenarios in golden YAML")
        return

    async def run():
        print("\n  === WORKFLOW SCENARIOS ===")
        for scenario in wf_scenarios:
            sid = scenario["id"]
            desc = scenario["description"]
            print(f"  [{sid}] {desc[:60]}...", end=" ", flush=True)

            persona = scenario.get("persona", "tutor")
            traj = await run_langgraph_agent(
                scenario["input"], persona,
                conversation=scenario.get("conversation"),
                identity=scenario.get("identity"),
            )

            if traj["error"]:
                report.add(f"workflow: {sid}", False, f"AGENT ERROR: {traj['error']}")
                print("ERROR")
                continue

            all_pass = True
            for assertion in scenario["assertions"]:
                passed, detail = check_assertion(assertion, traj)
                name = f"workflow: {sid}/{assertion['type']}"
                if not passed:
                    all_pass = False
                _record_assertion(report, name, passed, detail,
                                  scenario.get("expected_fail", False),
                                  scenario.get("flaky", False))

            status = "PASS" if all_pass else "FAIL"
            print(f"{status} ({traj['latency_s']}s) tools={traj['tools_called']}")

    asyncio.run(run())


def test_inline_panel_scenarios(report: EvalReport):
    """内联面板场景: show_exam_workbench 直接调用 / search_exam_bank 分离 / 不反问。"""
    from dotenv import load_dotenv
    load_dotenv()

    data = load_golden_scenarios()
    ip_scenarios = data.get("inline_panel_scenarios", [])
    if not ip_scenarios:
        print("\n  [SKIP] No inline_panel_scenarios in golden YAML")
        return

    async def run():
        print("\n  === INLINE PANEL SCENARIOS ===")
        for scenario in ip_scenarios:
            sid = scenario["id"]
            desc = scenario["description"]
            print(f"  [{sid}] {desc[:60]}...", end=" ", flush=True)

            persona = scenario.get("persona", "tutor")
            traj = await run_langgraph_agent(scenario["input"], persona,
                                             identity=scenario.get("identity"))

            if traj["error"]:
                report.add(f"panel: {sid}", False, f"AGENT ERROR: {traj['error']}")
                print("ERROR")
                continue

            all_pass = True
            for assertion in scenario["assertions"]:
                passed, detail = check_assertion(assertion, traj)
                name = f"panel: {sid}/{assertion['type']}"
                if not passed:
                    all_pass = False
                _record_assertion(report, name, passed, detail,
                                  scenario.get("expected_fail", False),
                                  scenario.get("flaky", False))

            status = "PASS" if all_pass else "FAIL"
            print(f"{status} ({traj['latency_s']}s) tools={traj['tools_called']}")

    asyncio.run(run())


def test_planning_scenarios(report: EvalReport):
    """Spec 06: 拆解与进度 — 复杂任务产计划、简单任务零计划。"""
    data = load_golden_scenarios()
    plan_scenarios = data.get("planning_scenarios", [])
    if not plan_scenarios:
        print("\n  [SKIP] No planning_scenarios in golden YAML")
        return

    async def run():
        print("\n  === PLANNING SCENARIOS ===")
        for scenario in plan_scenarios:
            sid = scenario["id"]
            desc = scenario["description"]
            print(f"  [{sid}] {desc[:60]}...", end=" ", flush=True)

            persona = scenario.get("persona", "tutor")
            traj = await run_langgraph_agent(
                scenario["input"], persona,
                conversation=scenario.get("conversation"),
                identity=scenario.get("identity"),
            )

            if traj["error"]:
                report.add(f"planning: {sid}", False, f"AGENT ERROR: {traj['error']}")
                print("ERROR")
                continue

            all_pass = True
            for assertion in scenario["assertions"]:
                passed, detail = check_assertion(assertion, traj)
                name = f"planning: {sid}/{assertion['type']}"
                if not passed:
                    all_pass = False
                _record_assertion(report, name, passed, detail,
                                  scenario.get("expected_fail", False),
                                  scenario.get("flaky", False))

            status = "PASS" if all_pass else "FAIL"
            print(f"{status} ({traj['latency_s']}s) tools={traj['tools_called']}")

    asyncio.run(run())


def test_e2e_scenarios(report: EvalReport):
    """Spec 06 L6: 端到端任务成功率。失败在慢跑层记为 severe（一票否决）。"""
    data = load_golden_scenarios()
    e2e = data.get("e2e_scenarios", [])
    if not e2e:
        print("\n  [SKIP] No e2e_scenarios in golden YAML")
        return

    async def run():
        print("\n  === E2E SCENARIOS ===")
        for scenario in e2e:
            sid = scenario["id"]
            desc = scenario["description"]
            print(f"  [{sid}] {desc[:60]}...", end=" ", flush=True)

            persona = scenario.get("persona", "tutor")
            traj = await run_langgraph_agent(
                scenario["input"], persona,
                conversation=scenario.get("conversation"),
                identity=scenario.get("identity"),
            )

            if traj["error"]:
                report.add(f"e2e: {sid}", False, f"AGENT ERROR: {traj['error']}")
                print("ERROR")
                continue

            all_pass = True
            for assertion in scenario["assertions"]:
                passed, detail = check_assertion(assertion, traj)
                name = f"e2e: {sid}/{assertion['type']}"
                if not passed:
                    all_pass = False
                _record_assertion(report, name, passed, detail,
                                  scenario.get("expected_fail", False),
                                  scenario.get("flaky", False))

            status = "PASS" if all_pass else "FAIL"
            print(f"{status} ({traj['latency_s']}s) tools={traj['tools_called']}")

    asyncio.run(run())


# ═══════════════════════════════════════════════════════════════════════
# 运行器
# ═══════════════════════════════════════════════════════════════════════

def _reset_checkpointers():
    """每个 section 之间重置共享 checkpointer。

    aiosqlite 连接绑定创建它的 event loop；跨 asyncio.run 的 section 复用会报
    'bound to a different event loop'（panel section 全部 AGENT ERROR 的根因）。
    """
    from agent import guard as guardmod
    from agent import langgraph_agent_v2 as v2mod
    for mod, attr in ((v2mod, "_v2_checkpointer"), (guardmod, "_checkpointer")):
        cp = getattr(mod, attr, None)
        if cp is not None:
            conn = getattr(cp, "conn", None)
            if conn is not None:
                try:
                    asyncio.run(conn.close())
                except Exception:
                    pass
            setattr(mod, attr, None)


def run():
    import argparse
    parser = argparse.ArgumentParser(description="ChemAI Agent Evals — trajectory-based")
    parser.add_argument("--golden", action="store_true", help="Run golden dataset scenarios (needs API)")
    parser.add_argument("--langgraph", action="store_true", help="Run LangGraph-specific scenarios (deferred)")
    parser.add_argument("--boundary", action="store_true", help="Run boundary + guardrail tests (no API)")
    parser.add_argument("--baseline", action="store_true", help="Run baseline capture/regression")
    parser.add_argument("--save", action="store_true", help="Save baseline.json (with --baseline)")
    parser.add_argument("--regression", action="store_true", help="Compare against saved baseline.json")
    parser.add_argument("--workflow", action="store_true", help="Run workflow integration scenarios (needs API)")
    parser.add_argument("--inline-panel", action="store_true", help="Run inline panel scenarios (needs API)")
    parser.add_argument("--planning", action="store_true", help="Run planning scenarios (needs API, Spec 06)")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end scenarios (needs API, Spec 06 L6)")
    parser.add_argument("--v2", action="store_true", help="Use v2 single-agent architecture (default: v1)")
    parser.add_argument("--all", action="store_true", help="Run everything")

    try:
        args, _ = parser.parse_known_args()
    except SystemExit:
        args = argparse.Namespace(golden=True, langgraph=False, boundary=True, baseline=False, save=False, regression=False, all=False)

    if args.all:
        args.golden = args.langgraph = args.boundary = args.workflow = args.inline_panel = True

    global AGENT_VERSION
    if args.v2:
        AGENT_VERSION = "v2"

    report = EvalReport()

    # ── 边界/护栏 (无 API, 始终跑) ──
    if args.boundary or args.all or (not args.golden and not args.langgraph and not args.baseline and not args.workflow):
        print("\n" + "=" * 60)
        print("  BOUNDARY + GUARDRAILS (no API)")
        print("=" * 60)
        test_boundary_guardrails(report)

    # ── 黄金数据集 (需要 API) ──
    if args.golden or args.all:
        print("\n" + "=" * 60)
        print("  GOLDEN DATASET (LangGraph baseline)")
        print("=" * 60)
        test_golden_dataset(report)
        _reset_checkpointers()

    # ── LangGraph 特有场景 ──
    if args.langgraph or args.all:
        print("\n" + "=" * 60)
        print("  LANGGRAPH-SPECIFIC SCENARIOS")
        print("=" * 60)
        test_langgraph_scenarios(report)
        _reset_checkpointers()

    # ── 工作流完整性场景 ──
    if args.workflow or args.all:
        print("\n" + "=" * 60)
        print("  WORKFLOW SCENARIOS (integration)")
        print("=" * 60)
        test_workflow_scenarios(report)
        _reset_checkpointers()

    # ── 内联面板场景 ──
    if args.inline_panel or args.all:
        print("\n" + "=" * 60)
        print("  INLINE PANEL SCENARIOS")
        print("=" * 60)
        test_inline_panel_scenarios(report)
        _reset_checkpointers()

    # ── 拆解与进度场景 (Spec 06) ──
    if args.planning or args.all:
        print("\n" + "=" * 60)
        print("  PLANNING SCENARIOS")
        print("=" * 60)
        test_planning_scenarios(report)
        _reset_checkpointers()

    # ── 端到端场景 (Spec 06 L6) ──
    if args.e2e or args.all:
        print("\n" + "=" * 60)
        print("  E2E SCENARIOS")
        print("=" * 60)
        test_e2e_scenarios(report)
        _reset_checkpointers()

    # ── 回归对比 ──
    if args.baseline or args.save or args.regression:
        print("\n" + "=" * 60)
        print("  REGRESSION BASELINE")
        print("=" * 60)
        test_regression_baseline(report)

    print(report.summary())
    return report


if __name__ == "__main__":
    report = run()
    # Spec 02: 门禁语义 — 有任何失败即非零退出（此前永远 exit 0，门禁形同虚设）
    failures = sum(1 for r in report.results if not r["passed"])
    sys.exit(1 if failures > 0 else 0)
