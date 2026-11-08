"""
Spec 05 unit tests — weak-point context formatting + system prompt building.

Pure logic, zero API: format_class_weakpoint_context (aggregation formatting)
and build_system_prompt (persona contract + class context injection).
"""
from agent.weakpoint import format_class_weakpoint_context
from agent.langgraph_agent_v2 import build_system_prompt
from agent.agents import load_persona


def test_format_empty_rows():
    assert format_class_weakpoint_context([]) == ""


def test_format_groups_and_labels():
    rows = [
        ("高一(3)班", '{"concept": 12, "reading": 5}', 17),
        ("高一(3)班", None, 3),
        ("高二(1)班", {"expression": 4}, 4),
        ("高二(1)班", {"reading": 9, "concept": 2}, 11),
    ]
    text = format_class_weakpoint_context(rows)
    assert "高一(3)班" in text and "高二(1)班" in text
    assert "概念理解" in text and "审题仔细度" in text and "答题表述" in text
    assert "未诊断 3 人" in text


def test_format_handles_malformed_barrier():
    rows = [("A班", "not-json{{{", 2)]
    text = format_class_weakpoint_context(rows)
    assert "未诊断" in text  # malformed -> unknown, never crash


def test_build_system_prompt_teacher_has_contract():
    prompt = build_system_prompt(load_persona("teacher"))
    assert "出题交互契约" in prompt
    assert "diagnose_barrier" in prompt or "薄弱点" in prompt


def test_build_system_prompt_injects_class_context():
    prompt = build_system_prompt(load_persona("teacher"), class_context="高一(3)班：概念理解 12 人")
    assert "## 班级学情上下文" in prompt
    assert "高一(3)班" in prompt
    # without class_context, no empty section
    prompt2 = build_system_prompt(load_persona("teacher"))
    assert "## 班级学情上下文" not in prompt2


def test_build_system_prompt_injects_student_profile():
    profile = {"name": "张三", "student_id": "S001",
               "barrier": {"concept": 0.7, "reading": 0.2}, "exercises_completed": 30}
    prompt = build_system_prompt(load_persona("parent"), student_profile=profile)
    assert "当前孩子: 张三（学号 S001）" in prompt
    assert "概念理解" in prompt and "30 次" in prompt


def test_build_system_prompt_injects_local_env():
    """本机环境注入：桌面路径不用猜（2026-08 修复「agent 反问路径不调工具」）。"""
    import pathlib
    prompt = build_system_prompt(load_persona("teacher"))
    assert "## 本机环境" in prompt
    assert str(pathlib.Path.home()) in prompt
    assert "Desktop" in prompt
