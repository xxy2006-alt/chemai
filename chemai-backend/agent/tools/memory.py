"""Memory tools — student diagnosis history and teacher preferences."""

import json

from dotenv import load_dotenv
load_dotenv()


def _get_store_context():
    """Get SqliteStore from agent context."""
    try:
        from agent.langgraph_agent_v2 import get_store_context
        return get_store_context()
    except Exception:
        return None


async def memory_student_get(
    student_id: str = "",
    memory_type: str = "all",
) -> str:
    """学情记忆 — 获取学生历史诊断和学习计划记忆

    何时用: 教师询问某学生的学习历史、之前的诊断结果、薄弱环节变化趋势
    会发生什么: 返回学生诊断历史(最多5条)和当前学习计划"""
    store = _get_store_context()
    if not store:
        return json.dumps({"error": "记忆系统不可用"}, ensure_ascii=False)

    results = {"student_id": student_id, "diagnoses": [], "learning_plan": None}

    if student_id:
        ns = ("student", student_id, "diagnosis")
        try:
            items = await store.asearch(ns, limit=5)
            results["diagnoses"] = [
                {"key": getattr(i, "key", ""), "data": getattr(i, "value", i)}
                for i in (items or [])
            ]
        except Exception:
            pass

        ns2 = ("student", student_id, "learning_plan")
        try:
            plan = await store.aget(ns2, "current")
            if plan and hasattr(plan, "value"):
                results["learning_plan"] = plan.value
        except Exception:
            pass

    return json.dumps(results, ensure_ascii=False)


async def memory_teacher_get(
    teacher_id: str = "",
) -> str:
    """教师偏好 — 获取教师教学偏好和历史设置

    何时用: 需要了解教师的教学风格、难度偏好、班级配置
    会发生什么: 返回教师存储的偏好设置"""
    store = _get_store_context()
    if not store:
        return json.dumps({"error": "记忆系统不可用"}, ensure_ascii=False)

    prefs = {}
    if teacher_id:
        try:
            item = await store.aget(("teacher", teacher_id, "preferences"), "current")
            if item and hasattr(item, "value"):
                prefs = item.value
        except Exception:
            pass

    return json.dumps(prefs, ensure_ascii=False)
