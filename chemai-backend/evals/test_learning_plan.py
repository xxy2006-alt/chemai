"""学习计划 Agent 工具评测 — 验证工具注册 / 路由 / 数据解析"""

import pytest, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── 工具注册验证 ──

def test_tools_registered():
    """generate_learning_plan + send_learning_plan 已在 TOOLS 中注册"""
    from agent.tools import TOOLS, TOOL_META
    names = {t.__name__ for t in TOOLS}
    assert "generate_learning_plan" in names, "generate_learning_plan not in TOOLS"
    assert "send_learning_plan" in names, "send_learning_plan not in TOOLS"
    assert len(TOOLS) == len(TOOL_META), "TOOLS/TOOL_META mismatch"

def test_tool_meta_teacher_only():
    """学习计划工具仅限 teacher persona"""
    from agent.tools import TOOL_META
    for name in ["generate_learning_plan", "send_learning_plan"]:
        import agent.tools
        fn = getattr(agent.tools, name)
        meta = TOOL_META[fn]
        assert "teacher" in meta["personas"], f"{name} missing teacher persona"
        assert "student" not in meta["personas"], f"{name} leaked to student"
        assert "parent" not in meta["personas"], f"{name} leaked to parent"

# ── 网关关键字路由 ──

@pytest.mark.asyncio
async def test_gateway_keyword_no_longer_triggers_plan():
    """关键词匹配已移除 — 学习计划交给 LLM docstring 选择, 关键词不应触发"""
    from agent.gateway import IntentClassifier
    gw = IntentClassifier("deepseek")
    result = await gw.classify("给李世睿制定学习方案")
    # 关键词已删除, tools 中不应有 generate_learning_plan (交给 LLM 处理)
    if result.tools:
        assert "generate_learning_plan" not in result.tools, \
            "generate_learning_plan should NOT be triggered by keyword — LLM handles it"

@pytest.mark.asyncio
async def test_gateway_routes_adaptive_practice():
    """网关关键字匹配 '布置针对性练习' → assign_adaptive_practice"""
    from agent.gateway import IntentClassifier
    gw = IntentClassifier("deepseek")
    result = await gw.classify("给李世睿布置一些针对性练习")
    assert result.type == "chat"
    if result.tools:
        assert "assign_adaptive_practice" in result.tools, \
            f"Expected assign_adaptive_practice in tools, got {result.tools}"

# ── 工具文档 ──

def test_plan_tool_has_docstring():
    """generate_learning_plan 有完整的何时用/会发生什么/NOT for"""
    from agent.tools import generate_learning_plan
    doc = generate_learning_plan.__doc__ or ""
    assert "何时用" in doc, "missing 何时用"
    assert "会发生什么" in doc, "missing 会发生什么"
    assert "NOT for" in doc, "missing NOT for"

def test_plan_vs_practice_disambiguation():
    """两个工具互相引用 NOT for，防止误选"""
    from agent.tools import generate_learning_plan, assign_adaptive_practice
    plan_doc = generate_learning_plan.__doc__ or ""
    practice_doc = assign_adaptive_practice.__doc__ or ""
    # generate_learning_plan should NOT for 练习
    assert "assign_adaptive_practice" in plan_doc, \
        "generate_learning_plan NOT for should mention assign_adaptive_practice"
    # assign_adaptive_practice should NOT for 学习计划
    assert "generate_learning_plan" in practice_doc, \
        "assign_adaptive_practice NOT for should mention generate_learning_plan"

# ── 安全函数 ──

def test_safe_barrier_handles_all_types():
    """_safe_barrier 处理 str/dict/None/非法值"""
    from agent.tools.diagnosis import _safe_barrier, _dominant
    assert _safe_barrier(None) == {}
    assert _safe_barrier({"concept": 0.5}) == {"concept": 0.5}
    assert _safe_barrier('{"concept":0.3}') == {"concept": 0.3}
    assert _safe_barrier("invalid") == {}
    assert _safe_barrier(42) == {}

def test_dominant_never_crashes():
    """_dominant 不会递归崩溃"""
    from agent.tools.diagnosis import _dominant
    assert _dominant({}) == ("unknown", 0)
    assert _dominant({"concept": 0.5, "reading": 0.3, "expression": 0.2}) == ("concept", 0.5)
    # 非法输入
    assert _dominant("bad string")[0] == "unknown"

# ── 计划持久化链路 ──

def test_apply_endpoint_structure():
    """POST /apply 端点存在且接受正确参数"""
    from app.api.diagnosis import apply_student_learning_plan
    import inspect
    sig = inspect.signature(apply_student_learning_plan)
    params = list(sig.parameters.keys())
    assert "student_id" in params
    assert "plan_data" in params
    assert "db" in params

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
