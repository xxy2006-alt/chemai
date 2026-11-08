"""
L0 deterministic tool tests (Spec 02) — pure-logic paths, zero LLM, zero DB.

Covers the deterministic slices of tools that test_unit_tools.py doesn't:
  - show_exam_workbench: arg parsing + panel JSON structure
  - save_to_bank:      validation error paths (invalid JSON / empty questions)
  - delete_bank:       empty set_id validation
  - memory_*:          graceful degradation without store context
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from evals.conftest import EvalReport, parse_tool_result


def _run(coro):
    return asyncio.run(coro)


def test_show_exam_workbench_parses_args():
    """Arg parsing + panel JSON — no LLM, no DB."""
    from agent.tools import show_exam_workbench

    async def run():
        results = []

        async def case(name, kwargs, check):
            raw = await show_exam_workbench(**kwargs)
            data = parse_tool_result(raw)
            passed, detail = check(data)
            results.append({"name": name, "passed": passed, "details": detail})

        await case("kp parse", {"knowledge_points": "盐类水解, 电化学"}, lambda d: (
            d["_component"]["params"]["knowledge_points"] == ["盐类水解", "电化学"],
            f"kps={d['_component']['params']['knowledge_points']}"))

        await case("type parse", {"question_types": "single_choice:5,fill_blank:2"}, lambda d: (
            [t["qty"] for t in d["_component"]["params"]["types"]] == [5, 2],
            f"types={d['_component']['params']['types']}"))

        await case("default type", {}, lambda d: (
            d["_component"]["params"]["types"] == [{"val": "single_choice", "active": True, "qty": 3}],
            f"types={d['_component']['params']['types']}"))

        await case("component name", {}, lambda d: (
            d["_component"]["component"] == "exam-workbench",
            f"component={d['_component']['component']}"))

        await case("variant/set passthrough", {"variant_source": "高考", "set_name": "周测一"}, lambda d: (
            d["_component"]["params"]["variant_source"] == "高考"
            and d["_component"]["params"]["set_name"] == "周测一",
            f"params={d['_component']['params']}"))

        return results

    return _run(run())


def test_save_to_bank_validation_errors():
    """Invalid input must error out BEFORE any DB write, with navigate=False."""
    from agent.tools import save_to_bank

    async def run():
        results = []

        raw = await save_to_bank(questions="not-json")
        data = parse_tool_result(raw)
        results.append({
            "name": "invalid json",
            "passed": "error" in data and "格式无效" in data["error"]
                      and data["_route"]["navigate"] is False,
            "details": json.dumps(data, ensure_ascii=False)[:120],
        })

        raw = await save_to_bank(questions='{"questions": []}')
        data = parse_tool_result(raw)
        results.append({
            "name": "empty questions",
            "passed": "error" in data and "没有可保存" in data["error"],
            "details": json.dumps(data, ensure_ascii=False)[:120],
        })

        return results

    return _run(run())


def test_delete_bank_empty_id():
    """Empty set_id must fail fast with a clear message (no DB hit)."""
    from agent.tools import delete_bank

    async def run():
        raw = await delete_bank(set_id="")
        data = parse_tool_result(raw)
        return [{
            "name": "empty set_id",
            "passed": "error" in data and "请指定" in data["error"],
            "details": json.dumps(data, ensure_ascii=False)[:120],
        }]

    return _run(run())


def test_memory_tools_degrade_without_store():
    """Outside agent context the store is unavailable — tools must degrade
    gracefully instead of crashing."""
    from agent.tools import memory_student_get, memory_teacher_get

    async def run():
        results = []
        for name, tool in [("memory_student_get", memory_student_get),
                           ("memory_teacher_get", memory_teacher_get)]:
            raw = await tool()
            data = parse_tool_result(raw)
            passed = ("error" in data and "不可用" in data["error"]) or isinstance(data, dict)
            results.append({
                "name": name,
                "passed": passed,
                "details": json.dumps(data, ensure_ascii=False)[:120],
            })
        return results

    return _run(run())


IDENTITY_PARAMS = ("student_id", "class_id", "teacher_id", "student_name", "class_name")


def test_identity_params_are_declared_in_scope():
    """收了身份类参数的工具，必须在 TOOL_META 里声明 `scope` 维度（ADR-0014）。

    这是 ADR-0014 能被长期遵守的**关键** —— 新增工具忘了声明会被这条拦住，
    而不是让接缝静默放行。这正是本次权限改造的根因「**没写检查不会报错**」的解药：
    接缝只能执行它被告知的规则，声明缺失必须是一个**会报错的**状态。

    两个方向都查：身份参数漏声明（会让该参数不受校验）、
    声明里有工具并不存在的参数（参数改名后会留下失效声明）。
    """
    import inspect

    from agent.tools import TOOL_META, TOOLS

    results = []
    for tool in TOOLS:
        params = set(inspect.signature(tool).parameters)
        id_params = params & set(IDENTITY_PARAMS)
        if not id_params:
            continue

        declared = set((TOOL_META.get(tool) or {}).get("scope") or {})
        missing = sorted(id_params - declared)
        extra = sorted(declared - params)

        if missing:
            detail = f"这些身份参数没有 scope 声明: {missing}"
        elif extra:
            detail = f"scope 声明了工具并不存在的参数（改名了？）: {extra}"
        else:
            detail = f"scope={sorted(declared)}"

        results.append({
            "name": f"{tool.__name__}",
            "passed": not missing and not extra,
            "details": detail,
        })
    return results


def run():
    report = EvalReport()

    print("=== L0: show_exam_workbench (纯参数解析) ===")
    for r in test_show_exam_workbench_parses_args():
        report.add(f"workbench: {r['name']}", r["passed"], r.get("details", ""))

    print("=== L0: save_to_bank 校验路径 ===")
    for r in test_save_to_bank_validation_errors():
        report.add(f"save_to_bank: {r['name']}", r["passed"], r.get("details", ""))

    print("=== L0: delete_bank 校验 ===")
    for r in test_delete_bank_empty_id():
        report.add(f"delete_bank: {r['name']}", r["passed"], r.get("details", ""))

    print("=== L0: memory 降级 ===")
    for r in test_memory_tools_degrade_without_store():
        report.add(f"memory: {r['name']}", r["passed"], r.get("details", ""))

    print("=== L0: 身份类参数必须有 scope 声明（ADR-0014）===")
    for r in test_identity_params_are_declared_in_scope():
        report.add(f"scope-decl: {r['name']}", r["passed"], r.get("details", ""))

    print(report.summary())
    return report


if __name__ == "__main__":
    run()
