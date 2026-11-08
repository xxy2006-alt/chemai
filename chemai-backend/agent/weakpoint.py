"""
Class weak-point context (Spec 05) — 班级维度薄弱点聚合，注入 agent 上下文。

数据来自 students.barrier_type 聚合（与 show_students 同源）。格式化为一段
紧凑中文文本，供 create_chemai_agent(class_context=...) 注入系统提示。

分层：format_class_weakpoint_context 是纯函数（可单测）；DB 读取是薄壳。
"""


def format_class_weakpoint_context(rows):
    """rows: [(class_name, barrier_type, count), ...] -> 上下文文本或 ""。

    barrier_type 可能是 JSON 字符串/dict/None（沿用 show_students 的解析习惯）。
    """
    from agent.tools.diagnosis import _safe_barrier, _dominant

    if not rows:
        return ""
    barrier_labels = {"concept": "概念理解", "reading": "审题仔细度",
                      "expression": "答题表述", "unknown": "未诊断"}
    by_class = {}
    for class_name, barrier, count in rows:
        barrier = _safe_barrier(barrier)
        dominant, _ = _dominant(barrier)
        by_class.setdefault(class_name or "未分班", []).append(
            (barrier_labels.get(dominant, dominant), count or 0))

    parts = []
    for class_name, items in by_class.items():
        stats = "、".join(f"{label} {n} 人" for label, n in items[:5])
        parts.append(f"{class_name}：{stats}")
    return "班级薄弱点统计（最近诊断）：" + "；".join(parts)


def build_class_weakpoint_context(class_id="", student_id=""):
    """从 DB 聚合班级薄弱点上下文。返回文本（可能为 ""）。

    student_id 优先：查该生所在班级。失败/无数据时返回 ""（不阻断对话）。
    """
    if not class_id and not student_id:
        return ""
    try:
        from sqlalchemy import text
        from app.models.database import get_db

        session = next(get_db())
        try:
            if class_id:
                rows = session.execute(
                    text(
                        "SELECT c.name, s.barrier_type, COUNT(*) FROM students s "
                        "LEFT JOIN classes c ON s.class_id = c.class_id "
                        "WHERE s.class_id = :cid GROUP BY c.name, s.barrier_type"
                    ),
                    {"cid": class_id},
                ).fetchall()
            else:
                rows = session.execute(
                    text(
                        "SELECT c.name, s.barrier_type, COUNT(*) FROM students s "
                        "LEFT JOIN classes c ON s.class_id = c.class_id "
                        "WHERE s.class_id = (SELECT class_id FROM students WHERE student_id = :sid) "
                        "GROUP BY c.name, s.barrier_type"
                    ),
                    {"sid": student_id},
                ).fetchall()
        finally:
            session.close()
    except Exception:
        return ""
    return format_class_weakpoint_context(rows)
