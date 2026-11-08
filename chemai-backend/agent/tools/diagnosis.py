"""Diagnosis tools — barrier diagnosis, student listing, weekly reports, adaptive practice."""

import json
import re

from dotenv import load_dotenv
load_dotenv()


def _safe_barrier(raw) -> dict:
    """Parse barrier_type from DB into a dict, handling all edge cases."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            if isinstance(val, dict):
                return val
            return {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _dominant(barrier: dict) -> tuple:
    """Get dominant barrier type and score. Returns ('unknown', 0) on empty."""
    if not barrier:
        return ("unknown", 0)
    try:
        return max(barrier.items(), key=lambda x: x[1])
    except (ValueError, AttributeError):
        return ("unknown", 0)


def _caller_scope(db):
    """调用者数据范围：身份只认服务端注入的 token 身份（current_teacher()），
    模型自报的 student_id/class_id 一律按这个范围收窄（fail-closed：无身份=空集）。"""
    from agent.tools.context import current_teacher
    from app.middleware.scope import RequestScope, resolve_identity
    return RequestScope.from_user(resolve_identity(db, current_teacher()), db)


def _in_scope(db, rows):
    """把按姓名查到的 (student_id, name) 结果收窄到调用者数据范围内。"""
    scope = _caller_scope(db)
    return [r for r in rows if scope.allows_student(r[0])]


def _student_ref_to_id(session, ref: str):
    """纯数字引用先按学号精确解析，命中返回 student_id，否则 None。

    背景：LLM 会把学号（如 241914）填进 student_name 参数，姓名 LIKE/精确
    匹配必失败，导致"查无此人"假错误（2026-09-20 实测：241914 陈湘旻）。"""
    v = str(ref or "").strip()
    if not v.isdigit():
        return None
    from sqlalchemy import text
    row = session.execute(
        text("SELECT student_id FROM students WHERE student_id = :s"), {"s": v}
    ).fetchone()
    return row[0] if row else None


def _scope_denied(what: str = "该学生") -> str:
    """越界统一返回错误（不区分「不存在」与「不在范围内」，避免探测他人学号）。"""
    return json.dumps({"error": f"无权访问{what}：不在你的数据范围内",
                       "_route": {"navigate": False}}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# diagnose_barrier
# ═══════════════════════════════════════════════════════════════════════

async def diagnose_barrier(
    student_id: str = "",
    student_name: str = "",
    class_id: str = "",
) -> str:
    """学情诊断 — 诊断学生的化学学习障碍类型（概念理解/审题障碍/表述障碍）

    何时用：用户询问某个学生或班级的学习情况、错题原因、薄弱环节
    会发生什么：个体诊断返回学生障碍分布和主导障碍类型；班级诊断返回全班障碍分布统计
    下一步：个体诊断 → 根据障碍类型推荐针对性练习（assign_adaptive_practice）；班级诊断 → 跳转诊断页面展示图表
    NOT for 在聊天中展示诊断图表 — 用 show_diagnosis
    NOT for 生成周报/学习报告 — 用 weekly_report"""
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    if student_id and not student_id.isdigit():
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_id}%"},
        ).fetchall()
        rows = _in_scope(session, rows)   # 姓名搜索按调用者范围收窄，不列别班同名
        if not rows:
            session.close()
            return json.dumps({
                "error": f"未找到名为 '{student_id}' 的学生",
                "hint": "请确认姓名是否正确，或提供学号查询",
                "_route": {"navigate": False},
            })
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({
                "multiple_matches": candidates,
                "hint": "找到多个匹配学生，请提供完整学号",
                "_route": {"navigate": False},
            })
        student_id = rows[0][0]

    if student_name and not student_id:
        _by_id = _student_ref_to_id(session, student_name)
        if _by_id:
            student_id = _by_id
    if student_name and not student_id:
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        rows = _in_scope(session, rows)   # 姓名搜索按调用者范围收窄，不列别班同名
        if not rows:
            session.close()
            return json.dumps({
                "error": f"未找到名为 '{student_name}' 的学生",
                "hint": "请确认姓名是否正确，或提供学号/班级ID查询",
                "_route": {"navigate": False},
            })
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({
                "multiple_matches": candidates,
                "hint": "找到多个匹配学生，请指定学号",
                "_route": {"navigate": False},
            })
        student_id = rows[0][0]

    if student_id:
        if not _caller_scope(session).allows_student(student_id):
            session.close()
            return _scope_denied()

        row = session.execute(
            text("SELECT name, barrier_type, exercises_completed FROM students WHERE student_id = :sid"),
            {"sid": student_id},
        ).fetchone()

        if not row:
            session.close()
            return json.dumps({"error": f"学生 {student_id} 不存在", "_route": {"navigate": False}})

        barrier = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        dominant = _dominant(barrier) if barrier else ("unknown", 0)

        # 答题统计
        stats = session.execute(
            text(
                "SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) "
                "FROM student_answers WHERE student_id = :sid"
            ),
            {"sid": student_id},
        ).fetchone()
        total_answers = stats[0] or 0
        correct_answers = stats[1] or 0
        accuracy = round(correct_answers / total_answers, 2) if total_answers > 0 else 0

        # 薄弱知识点 (从错题中提取)
        weak_kps = []
        wrong_rows = session.execute(
            text(
                "SELECT q.knowledge_points FROM student_answers sa JOIN questions q "
                "ON sa.question_id = q.question_id WHERE sa.student_id = :sid "
                "AND sa.is_correct = 0 ORDER BY sa.answered_at DESC LIMIT 30"
            ),
            {"sid": student_id},
        ).fetchall()
        kp_counter = {}
        for (kps_json,) in wrong_rows:
            if kps_json:
                kps = json.loads(kps_json) if isinstance(kps_json, str) else kps_json
                for kp in kps:
                    kp_counter[kp] = kp_counter.get(kp, 0) + 1
        weak_kps = sorted(kp_counter.items(), key=lambda x: -x[1])[:5]

        # 成绩趋势 — 和學生详情页一致：按时间排序的滚动累计正确率
        score_trend = []
        act_rows = session.execute(
            text(
                "SELECT sa.is_correct, sa.answered_at FROM student_answers sa "
                "WHERE sa.student_id = :sid ORDER BY sa.answered_at ASC"
            ),
            {"sid": student_id},
        ).fetchall()
        correct = 0
        total = 0
        for is_correct, answered_at in act_rows:
            total += 1
            if is_correct:
                correct += 1
            date_str = (
                answered_at[:10] if isinstance(answered_at, str) and len(answered_at) > 10
                else (answered_at.strftime("%m-%d") if hasattr(answered_at, 'strftime') else str(answered_at)[:10])
            )
            score_trend.append({
                "date": date_str,
                "cumulative_rate": round(correct / total, 2) if total > 0 else 0,
                "correct": correct,
                "total": total,
            })

        # Downsample to max 20 points for rendering
        if len(score_trend) > 20:
            step = len(score_trend) / 20
            score_trend = [score_trend[int(i * step)] for i in range(20)]

        session.close()

        result_data = {
            "student_id": student_id,
            "student_name": row[0],
            "barrier_distribution": barrier,
            "dominant_barrier": dominant[0],
            "exercises_completed": row[2] or 0,
            "total_answers": total_answers,
            "correct_answers": correct_answers,
            "accuracy": accuracy,
            "weak_knowledge_points": [{"name": k, "errors": c} for k, c in weak_kps],
            "score_trend": score_trend,
            "_route": {"navigate": False},
            "_component": {"component": "diagnosis", "params": {
                "student_id": student_id,
                "student_name": row[0],
                "barrier_distribution": barrier,
                "dominant_barrier": dominant[0],
                "exercises_completed": row[2] or 0,
                "total_answers": total_answers,
                "correct_answers": correct_answers,
                "accuracy": accuracy,
                "weak_knowledge_points": [{"name": k, "errors": c} for k, c in weak_kps],
                "score_trend": score_trend,
            }},
        }

        _writeback_diagnosis(student_id, result_data)
        return json.dumps(result_data, ensure_ascii=False)

    elif class_id:
        if not _caller_scope(session).allows_class(class_id):
            session.close()
            return _scope_denied("该班级")

        rows = session.execute(
            text("SELECT student_id, name, barrier_type FROM students WHERE class_id = :cid"),
            {"cid": class_id},
        ).fetchall()
        session.close()

        students = []
        concept_count = reading_count = expression_count = 0
        for row in rows:
            barrier = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            if barrier:
                dominant = _dominant(barrier)[0]
                students.append({
                    "student_id": row[0], "student_name": row[1],
                    "dominant": dominant,
                })
                # 按每人的主导障碍计数（三个人桶之和 == 班级人数）
                if dominant == "concept":
                    concept_count += 1
                elif dominant == "reading":
                    reading_count += 1
                elif dominant == "expression":
                    expression_count += 1

        _data = {
            "class_id": class_id,
            "total_students": len(students),
            "barrier_distribution": {
                "concept": concept_count, "reading": reading_count, "expression": expression_count,
            },
            "students": students[:10],
        }
        return json.dumps({
            **_data,
            "_component": {"component": "diagnosis", "params": _data},
        }, ensure_ascii=False)

    session.close()
    return json.dumps({"error": "请提供 student_id 或 class_id", "_route": {"navigate": False}})


# ═══════════════════════════════════════════════════════════════════════
# show_diagnosis
# ═══════════════════════════════════════════════════════════════════════

async def show_diagnosis(student_id: str = "", student_name: str = "", class_id: str = "") -> str:
    """学情诊断 — 在聊天中展示诊断结果和图表

    何时用：用户要求查看学生或班级的诊断结果
    会发生什么：在聊天中渲染诊断面板，包含障碍分布图和关键指标
    下一步：用户可点击"针对出题"快捷按钮，跳转到出题面板
    NOT for 只需要原始障碍数据不需要图表 — 用 diagnose_barrier"""
    from agent.tools import diagnose_barrier as _diag
    diag_result = await _diag(student_id=student_id, student_name=student_name, class_id=class_id)

    try:
        data = json.loads(diag_result) if isinstance(diag_result, str) else diag_result
    except (json.JSONDecodeError, TypeError):
        data = {"error": "诊断数据解析失败"}

    if "error" in data:
        return json.dumps({"message": data.get("error", "诊断失败"), "_component": None}, ensure_ascii=False)

    # data 副本留在返回体：guard 弹出 _component 后，工具卡也能渲染图表；
    # 组件 params 用 {data: ...} 嵌套（前端 InlineDiagnosis 读 params.data）
    return json.dumps({
        "message": "诊断结果已生成，请查看下方图表。",
        "data": data,
        "_component": {"component": "diagnosis", "params": {"data": data}},
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# show_students
# ═══════════════════════════════════════════════════════════════════════

async def show_students(
    class_id: str = "",
    class_name: str = "",
    student_name: str = "",
    filter_barrier: str = "",
) -> str:
    """学生/班级列表 — 展示班级学生或全部班级

    何时用：用户问"有几个班""有哪些学生""找问题大的学生""班里谁最薄弱""找下李世睿"
    会发生什么：指定学生姓名时按姓名模糊搜索学生；指定班级时列出班级学生；都不指定时列出所有班级
    下一步：用户点击学生卡片 → 触发该学生的诊断
    NOT for 不需要搜索学生只需要诊断数据 — 用 diagnose_barrier
    NOT for 查某个学生或班级的障碍数据 — 用 diagnose_barrier"""
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    # ── student_name search: fuzzy match on student name ──
    if student_name:
        scope = _caller_scope(session)
        # 纯数字先按学号精确查（LLM 常把学号填进 student_name）
        _by_id = _student_ref_to_id(session, student_name)
        if _by_id:
            rows = session.execute(
                text("SELECT s.student_id, s.name, s.barrier_type, s.exercises_completed, c.name as class_name "
                     "FROM students s LEFT JOIN classes c ON s.class_id = c.class_id "
                     "WHERE s.student_id = :s"),
                {"s": _by_id},
            ).fetchall()
        else:
            rows = session.execute(
                text("SELECT s.student_id, s.name, s.barrier_type, s.exercises_completed, c.name as class_name "
                     "FROM students s LEFT JOIN classes c ON s.class_id = c.class_id "
                     "WHERE s.name LIKE :n ORDER BY s.exercises_completed ASC"),
                {"n": f"%{student_name}%"},
            ).fetchall()
        # 只列调用者范围内的学生：模型自报姓名不能当查询范围用（跨班/跨校全库搜人）
        rows = [r for r in rows if scope.allows_student(r[0])]
        session.close()

        if not rows:
            return json.dumps({
                "message": f"未找到名为 '{student_name}' 的学生",
                "_component": None,
            }, ensure_ascii=False)

        barrier_labels = {"concept": "概念理解", "reading": "审题仔细度", "expression": "答题表述", "unknown": "未诊断"}
        students = []
        for r in rows:
            barrier = r[2] or {}
            if isinstance(barrier, str):
                try:
                    barrier = json.loads(barrier)
                except Exception:
                    barrier = {}
            if not isinstance(barrier, dict) or not barrier:
                dominant = ("unknown", 0)
            else:
                try:
                    dominant = _dominant(barrier)
                except Exception:
                    dominant = ("unknown", 0)
            students.append({
                "student_id": r[0], "name": r[1],
                "dominant_barrier": dominant[0],
                "barrier_score": round(dominant[1], 2),
                "exercises_completed": r[3] or 0,
                "class_name": r[4] or "",
            })

        summary = f"找到 {len(students)} 名匹配 '{student_name}' 的学生：" + "、".join(
            f"{s['name']}({barrier_labels.get(s['dominant_barrier'], s['dominant_barrier'])})" for s in students[:10]
        )
        return json.dumps({
            "result": summary,
            "student_count": len(students),
            "students": students,
            "_component": {
                "component": "student-list",
                "params": {"students": students, "search_term": student_name},
            },
        }, ensure_ascii=False)

    if class_name and not class_id:
        cn = str.maketrans("一二三四五六七八九十", "1234567890")

        row = session.execute(
            text("SELECT class_id, name FROM classes WHERE name = :n"),
            {"n": class_name},
        ).fetchone()

        if not row:
            row = session.execute(
                text("SELECT class_id, name FROM classes WHERE name LIKE :n"),
                {"n": f"%{class_name}%"},
            ).fetchone()

        if not row:
            clean = class_name.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
            m = re.match(r"(.+)([一二三四五六七八九十\d]+)\s*班", clean)
            if m:
                prefix = m.group(1)
                num = m.group(2).translate(cn)
                pattern = f"%{prefix}%{num}%班%"
                row = session.execute(
                    text("SELECT class_id, name FROM classes WHERE REPLACE(REPLACE(name, '(', ''), ')', '') LIKE :p"),
                    {"p": pattern},
                ).fetchone()

        if not row:
            hint_rows = session.execute(
                text("SELECT name FROM classes ORDER BY name")
            ).fetchall()
            session.close()
            names = "、".join(r[0] for r in hint_rows[:9]) if hint_rows else "暂无"
            return json.dumps({
                "message": f"未找到班级 '{class_name}'，可用班级：{names}",
                "_component": None,
            }, ensure_ascii=False)
        class_id = row[0]

    if not class_id:
        scope = _caller_scope(session)
        rows = session.execute(
            text("SELECT class_id, name, grade, student_count FROM classes ORDER BY name")
        ).fetchall()
        session.close()
        rows = [r for r in rows if scope.allows_class(r[0])]   # 无班级范围 = 空集，不列全校
        if not rows:
            return json.dumps({"result": "暂无班级数据"}, ensure_ascii=False)
        classes = [{"class_id": r[0], "name": r[1], "grade": r[2], "student_count": r[3] or 0} for r in rows]
        summary = (
            "共" + str(len(classes)) + "个班级：" + "、".join(
                c["name"] + "(" + str(c["student_count"]) + "人)" for c in classes
            )
        )
        return json.dumps({"result": summary, "classes": classes, "total": len(classes)}, ensure_ascii=False)

    cls_row = session.execute(
        text("SELECT name FROM classes WHERE class_id = :cid"), {"cid": class_id}
    ).fetchone()
    resolved_class_name = cls_row[0] if cls_row else class_id

    if not _caller_scope(session).allows_class(class_id):
        session.close()
        return _scope_denied("该班级")

    rows = session.execute(
        text(
            "SELECT student_id, name, barrier_type, exercises_completed FROM students "
            "WHERE class_id = :cid ORDER BY exercises_completed ASC"
        ),
        {"cid": class_id},
    ).fetchall()
    session.close()

    if not rows:
        return json.dumps({"message": f"{resolved_class_name} 暂无学生", "_component": None}, ensure_ascii=False)

    students = []
    for r in rows:
        barrier = _safe_barrier(r[2])
        if barrier:
            dominant = _dominant(barrier)
            barrier_type = dominant[0]
            barrier_score = dominant[1]
        else:
            barrier_type = "unknown"
            barrier_score = 0

        if filter_barrier:
            bt_map = {
                "计算": "concept", "概念": "concept", "审题": "reading",
                "阅读": "reading", "表述": "expression", "表达": "expression",
            }
            target = bt_map.get(filter_barrier, filter_barrier)
            if barrier_type != target:
                continue

        students.append({
            "student_id": r[0], "name": r[1],
            "dominant_barrier": barrier_type,
            "barrier_score": round(barrier_score, 2),
            "exercises_completed": r[3] or 0,
        })

    if filter_barrier and not students:
        return json.dumps({
            "message": f"{resolved_class_name} 没有 {filter_barrier} 障碍的学生",
            "_component": None,
        }, ensure_ascii=False)

    students.sort(key=lambda s: s["barrier_score"], reverse=True)

    barrier_labels = {"concept": "计算能力", "reading": "审题障碍", "expression": "表述障碍", "unknown": "未诊断"}
    top5 = students[:5]
    top_summary = "、".join(
        f"{s['name']}({barrier_labels.get(s['dominant_barrier'], s['dominant_barrier'])} "
        f"{int(s['barrier_score'] * 100)}%)"
        for s in top5
    )

    return json.dumps({
        "result": (
            f"已找到{resolved_class_name} {len(students)}名学生，已在面板中展示。"
            f"障碍最严重的前5名：{top_summary}。用户可在面板中搜索、点击学生卡片进行诊断。"
        ),
        "student_count": len(students),
        "top_barriers": [
            {
                "name": s["name"],
                "barrier": barrier_labels.get(s["dominant_barrier"], s["dominant_barrier"]),
                "score": s["barrier_score"],
            }
            for s in top5
        ],
        "_component": {
            "component": "student-list",
            "params": {"class_name": resolved_class_name, "class_id": class_id, "students": students},
        },
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# weekly_report
# ═══════════════════════════════════════════════════════════════════════

async def weekly_report(student_id: str = "", student_name: str = "", class_name: str = "") -> str:
    """学习报告 — 生成学生或班级的化学学习周报

    何时用：用户（通常为家长或老师）要求查看学习报告、本周学习情况
    会发生什么：个人报告包含学习内容、掌握情况、成长空间和家庭配合建议；班级报告包含整体统计
    下一步：个人报告 → 对话中展示；班级报告 → 可跳转诊断页面查看图表
    NOT for 查薄弱环节/学情分析/障碍分布 — 用 diagnose_barrier"""
    from agent.provider.deepseek import DeepSeekProvider
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    if student_id and not student_id.isdigit():
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_id}%"},
        ).fetchall()
        rows = _in_scope(session, rows)   # 姓名搜索按调用者范围收窄，不列别班同名
        if not rows:
            session.close()
            return json.dumps({"error": f"未找到名为 '{student_id}' 的学生", "_route": {"navigate": False}})
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({
                "multiple_matches": candidates,
                "hint": "找到多个匹配学生，请提供完整学号",
                "_route": {"navigate": False},
            })
        student_id = rows[0][0]

    if student_name and not student_id:
        _by_id = _student_ref_to_id(session, student_name)
        if _by_id:
            student_id = _by_id
    if student_name and not student_id:
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        rows = _in_scope(session, rows)   # 姓名搜索按调用者范围收窄，不列别班同名
        if not rows:
            session.close()
            return json.dumps({"error": f"未找到名为 '{student_name}' 的学生", "_route": {"navigate": False}})
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({
                "multiple_matches": candidates,
                "hint": "找到多个匹配学生，请指定学号",
                "_route": {"navigate": False},
            })
        student_id = rows[0][0]

    if not _caller_scope(session).allows_student(student_id):
        session.close()
        return _scope_denied()

    student_row = session.execute(
        text("SELECT name, class_id, barrier_type, exercises_completed FROM students WHERE student_id = :sid"),
        {"sid": student_id},
    ).fetchone()

    if not student_row:
        session.close()
        return json.dumps({"error": f"学生 {student_id} 不存在", "_route": {"navigate": False}})

    student_name_resolved = student_row[0]
    barrier = json.loads(student_row[2]) if isinstance(student_row[2], str) else student_row[2]

    # 本周练习次数 = 该生本周有作答的场次（原来按「该班全库全时间」记录数冒充，
    # 会把往年记录当成孩子这周参加的练习次数写进给家长的周报）
    from datetime import datetime as _dt, timedelta as _td
    week_start = _dt.utcnow() - _td(days=7)
    exam_count = session.execute(
        text("SELECT COUNT(DISTINCT er.record_id) FROM exam_records er "
             "JOIN student_answers sa ON sa.exam_record_id = er.record_id "
             "WHERE sa.student_id = :sid AND er.exam_date >= :ws"),
        {"sid": student_id, "ws": week_start},
    ).fetchone()[0]

    session.close()

    provider = DeepSeekProvider()

    system_prompt = """你是ChemAI家长助手。生成学生本周学习报告。

原则:
- 鼓励为主，先肯定进步
- 用通俗语言，不用教育学术语
- 给出家长可操作的建议
- 不制造焦虑"""

    prompt = f"""请为 {student_name_resolved} 生成本周化学学习报告:

学习数据:
- 本周参加了 {exam_count} 次课堂练习
- 学习特点: {json.dumps(barrier, ensure_ascii=False)}

请生成200字以内的报告，直接回复文本，不要JSON."""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7, max_tokens=512,
    )

    await provider.close()

    return json.dumps({
        "student_name": student_name_resolved,
        "report": result.content,
        "exam_count": exam_count,
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# assign_adaptive_practice
# ═══════════════════════════════════════════════════════════════════════

async def assign_adaptive_practice(
    class_id: str = "",
    student_id: str = "",
    student_name: str = "",
    knowledge_points: str = "",
    question_count: int = 5,
) -> str:
    """自适应练习 — 根据学生障碍类型布置个性化练习

    何时用：诊断完成后，老师要求给班级/学生布置针对性练习题
    会发生什么：为指定学生（student_id/student_name，如"李雨萱"）或班级
               （class_id，如 class_2025_1）生成符合其最近发展区的个性化化学题，
               经四维审核后真实落库（学生任务列表立即可见）；>5 人转后台批次稍后完成
    下一步：同步完成 → 展示逐生结果；异步批次 → 告知老师稍后用 query_assignment_progress 查进度；
        ⚠ 此工具需要先调 request_approval 确认
    NOT for 生成学习计划/学习方案/学习规划 — 用 generate_learning_plan
    参数：给单个学生布置 → student_name（中文姓名即可）或 student_id；
         给全班布置 → class_id。三选一，不填会返回参数错误提示。"""
    from agent.tools.context import current_teacher
    from app.middleware.scope import STAFF_ROLES, RequestScope, resolve_identity
    from app.models.database import get_db, Student
    from app.services import assignment_service

    db = next(get_db())
    try:
        identity = resolve_identity(db, current_teacher())
        if identity.get("role") not in STAFF_ROLES:
            return json.dumps({"error": "缺少教师身份，无法布置练习",
                               "_route": {"navigate": False}}, ensure_ascii=False)
        scope = RequestScope.from_user(identity, db)

        # 布置目标解析：单学生（student_id/student_name）优先，其次班级（class_id）
        target_students = []
        if student_id or student_name:
            q = db.query(Student)
            if student_id:
                s = q.filter(Student.student_id == student_id).first()
            elif str(student_name or "").strip().isdigit():
                # LLM 常把学号填进姓名参数：纯数字先按学号精确查，再回退姓名
                s = q.filter(Student.student_id == student_name.strip()).first()
                if not s:
                    s = q.filter(Student.name == student_name).first()
            else:
                s = q.filter(Student.name == student_name).first()
            if not s:
                return json.dumps({
                    "error": f"未找到学生（student_id={student_id or ''}，student_name={student_name or ''}）",
                    "_route": {"navigate": False},
                }, ensure_ascii=False)
            target_students = [s]
        elif class_id:
            target_students = db.query(Student).filter(Student.class_id == class_id).all()
            if not target_students:
                return json.dumps(
                    {"error": f"班级 {class_id} 无学生", "_route": {"navigate": False}},
                    ensure_ascii=False,
                )
        else:
            return json.dumps({
                "error": "请提供布置目标：student_name/student_id（单个学生，如 李世睿）或 class_id（班级）",
                "_route": {"navigate": False},
            }, ensure_ascii=False)

        # 越界拦截：与 HTTP /assign 的 allows_class 同一口径（逐生落到其所在班）
        if any(not scope.allows_student(s.student_id) for s in target_students):
            return json.dumps({
                "error": "无权给这些学生布置练习：不在你的班级范围内",
                "_route": {"navigate": False},
            }, ensure_ascii=False)

        kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]
        out = assignment_service.assign(
            db, [s.student_id for s in target_students],
            {"kind": "adaptive", "knowledge_points": kps,
             "question_count": int(question_count)},
        )

        if out["mode"] == "batch":
            return json.dumps({
                "message": f"已开始为 {out['total']} 名学生布置练习（后台逐生生成中）",
                "batch_id": out["batch_id"],
                "total": out["total"],
                "next_action": "稍后用 query_assignment_progress 查询完成进度",
                "_route": {"navigate": False},
            }, ensure_ascii=False)

        assigned = [
            {"student_name": r["student_name"], "record_id": r["record_id"],
             "question_count": r["question_count"], "status": r["status"],
             "audit": r.get("audit")}
            for r in out["results"]
        ]
        done = sum(1 for a in assigned if a["status"] == "assigned")
        return json.dumps({
            "message": f"已为 {done}/{len(assigned)} 名学生布置练习（题目已落库，学生任务列表可见）",
            "assigned_count": len(assigned),
            "assigned": assigned,
            "_route": {"navigate": False},
        }, ensure_ascii=False)
    finally:
        db.close()


async def query_assignment_progress(batch_id: str = "") -> str:
    """布置进度查询 — 查询异步布置批次的完成情况

    何时用：老师问"练习布置好了吗""布置进度怎么样"（此前 assign_adaptive_practice
           返回了 batch_id）
    会发生什么：返回该批次目标人数与已完成学生的逐生结果（练习记录/题数）；
        只查得到自己班级范围内的批次（身份取自 token）
    下一步：全部完成后告知老师可以在学生任务列表查看
    NOT for 查识别/批改进度 — 用 query_ocr_progress"""
    from agent.tools.context import current_teacher
    from app.middleware.scope import STAFF_ROLES, RequestScope, resolve_identity
    from app.models.database import get_db
    from app.services import assignment_service

    db = next(get_db())
    try:
        identity = resolve_identity(db, current_teacher())
        if identity.get("role") not in STAFF_ROLES:
            return json.dumps({"error": "缺少教师身份，无法查询布置进度",
                               "_route": {"navigate": False}}, ensure_ascii=False)
        out = assignment_service.progress(
            db, batch_id, class_ids=RequestScope.from_user(identity, db).class_ids())
        out["_route"] = {"navigate": False}
        return json.dumps(out, ensure_ascii=False)
    finally:
        db.close()


# ── generate_learning_plan ──

async def generate_learning_plan(
    student_id: str = "",
    student_name: str = "",
) -> str:
    """学习计划生成 — 为指定学生生成可预览的学习计划草稿（不跳页）

    何时用：教师说"生成学习计划""给XX做一份学习方案""帮XX规划学习""制定学习计划"
    会发生什么：生成计划草稿（版本链第 1 版）并内联展示；发送前系统会弹确认卡，
               老师可打回修改（ agent 按反馈修订出新版本）后再次确认。
    返回：草稿预览卡片，含 draft_id
    下一步：老师确认后用 send_learning_plan 发送；要求修改时按老师意见调
            revise_learning_plan（不要自己改写计划内容）
    ⚠ NOT for 出题/布置练习/做题/针对性训练 — 用 assign_adaptive_practice
    ⚠ NOT for 查障碍/诊断数据 — 用 diagnose_barrier"""
    from agent.tools.context import current_teacher
    from app.models.database import get_db as _gdb
    from app.services.plan_draft_service import plan_draft_service

    out = plan_draft_service.create_draft(
        next(_gdb()), student_id=student_id, student_name=student_name,
        created_by=current_teacher() or "",
    )
    if "error" in out or "multiple_matches" in out:
        out.setdefault("_route", {"navigate": False})
        return json.dumps(out, ensure_ascii=False)

    name = out.get("student_name") or out["student_id"]
    return json.dumps({
        "message": (f"已为 {name} 生成学习计划草稿（第 {out['version']} 版），请在下方预览；"
                    "老师可打回修改，确认后才会发送给学生。"),
        # 生成即门（ADR-0013/#13）：guard 登记发送调用，门卡即刻弹出——
        # 「生成后停等确认」不依赖模型自觉调发送工具
        "approval_needed": True,
        "message_gate": f"学习计划（第 {out['version']} 版）等待老师确认，可打回修改",
        "target": out["student_id"],
        "action": "send_student",
        "student_id": out["student_id"],
        "student_name": name,
        "draft_id": out["draft_id"],
        "version": out["version"],
        "plan": out["content"],
        "_route": {"navigate": False},
        "_component": {
            "component": "learning_plan",
            "params": {
                "student_id": out["student_id"],
                "student_name": name,
                "draft_id": out["draft_id"],
                "version": out["version"],
                "data": {"student_id": out["student_id"], "student_name": name,
                         "draft_id": out["draft_id"], "plan": out["content"]},
            },
        },
    }, ensure_ascii=False)


# ── revise_learning_plan ──

async def revise_learning_plan(
    draft_id: str = "",
    feedback: str = "",
    student_id: str = "",
) -> str:
    """学习计划修订 — 按老师的修改意见修订草稿，生成新版本（不发送）

    何时用：老师对已生成的学习计划提出修改要求（如"第二周改成盐类水解专题"）
    会发生什么：service 按反馈修订草稿，同链生成新版本并内联展示；
               修订后仍需老师确认才会发送
    返回：修订后的草稿卡片，含 draft_id 与新版本号
    NOT for 重新生成 — 老师想推翻重来时用 generate_learning_plan；
    NOT for 发送 — 用 send_learning_plan"""
    from agent.tools.context import current_teacher
    from app.models.database import get_db as _g, LearningPlanDraft
    from app.services.plan_draft_service import plan_draft_service

    if not draft_id and student_id:
        active = plan_draft_service.get_active_draft(next(_g()), student_id)
        if not active:
            return json.dumps({"error": f"学生 {student_id} 没有待确认的计划草稿，请先生成"},
                              ensure_ascii=False)
        draft_id = active["draft_id"]
    if not draft_id:
        return json.dumps({"error": "请提供 draft_id 或 student_id"}, ensure_ascii=False)

    out = plan_draft_service.revise_draft(
        next(_g()), draft_id=draft_id, feedback=feedback,
        revised_by=current_teacher() or "",
    )
    if "error" in out:
        return json.dumps(out, ensure_ascii=False)

    name = out.get("student_name") or out["student_id"]
    return json.dumps({
        "message": (f"已按老师意见修订为第 {out['version']} 版，请在下方预览；"
                    "确认后才发送。"),
        "student_id": out["student_id"],
        "draft_id": out["draft_id"],
        "version": out["version"],
        "plan": out["content"],
        "_component": {
            "component": "learning_plan",
            "params": {
                "student_id": out["student_id"],
                "draft_id": out["draft_id"],
                "version": out["version"],
                "data": {"student_id": out["student_id"],
                         "draft_id": out["draft_id"], "plan": out["content"]},
            },
        },
    }, ensure_ascii=False)


# ── send_learning_plan ──

async def send_learning_plan(
    student_id: str = "",
    draft_id: str = "",
    plan_data: str = "",
    teacher_id: str = "",
) -> str:
    """发送学习计划 — 将老师确认过的计划草稿发送给学生（唯一的学生发送通道）

    何时用：老师明确确认计划无误后，说"发送""发给学生""推送给XX"
    会发生什么：发送前系统会弹确认卡等老师决定（批准/打回/放弃）；批准后
               持久化到学生端并投递收件箱通知
    返回：确认消息，含学生姓名；未确认时返回确认请求（弹卡）
    铁律（ADR-0013 确认门）：门由草稿状态强制——未确认的草稿发送会被拒绝并弹卡，
    禁止重复调用重试；打回后由系统修订，不要在本工具上重试
    NOT for 生成计划 — 用 generate_learning_plan；NOT for 修订 — 用 revise_learning_plan；
    NOT for 发给家长 — 用 send_report_to_parent"""
    from agent.tools.context import current_teacher
    from app.models.database import get_db as _g
    from app.services.plan_draft_service import plan_draft_service

    if not student_id:
        return json.dumps({"error": "请提供 student_id"}, ensure_ascii=False)
    if not teacher_id.strip():
        teacher_id = current_teacher() or ""

    out = plan_draft_service.send_draft(
        next(_g()), student_id=student_id, draft_id=draft_id or "",
        sender_id=teacher_id,
    )
    if out.get("approval_needed"):
        out.setdefault("message", f"即将把学习计划发送给学生 {student_id}")
        return json.dumps(out, ensure_ascii=False)
    return json.dumps(out, ensure_ascii=False)


# ── generate_parent_report ──

async def generate_parent_report(
    student_name: str = "",
    student_id: str = "",
) -> str:
    """家长报告生成 — 为指定学生生成面向家长的报告草稿预览（不跳页）

    何时用：教师说"发报告给XX家长""把XX的学习报告发给家长""给家长发学习报告"
    会发生什么：聚合练习数据与障碍诊断，生成报告草稿（版本链第 1 版）并在聊天中
               展示预览；发送前系统会弹确认卡，老师可打回修改后再次确认
    返回：报告预览卡片，含 draft_id
    下一步：教师确认后调 send_report_to_parent 发送；打回由系统按意见修订
    NOT for 直接发送 — 必须先预览确认"""
    from agent.tools.context import current_teacher
    from app.models.database import get_db as _gdb
    from app.services.parent_report_draft_service import parent_report_draft_service

    sid = student_id
    if student_name and not sid:
        from app.models.database import get_db as _g2
        from sqlalchemy import text as _text
        session = next(_g2())
        try:
            _by_id = _student_ref_to_id(session, student_name)
            if _by_id:
                sid = _by_id
            rows = session.execute(
                _text("SELECT student_id FROM students WHERE name LIKE :n"),
                {"n": f"%{student_name}%"},
            ).fetchall() if not sid else None
        finally:
            session.close()
        if not sid and not rows:
            return json.dumps({"error": f"未找到名为 '{student_name}' 的学生"}, ensure_ascii=False)
        if rows and len(rows) > 1:
            return json.dumps({"error": f"找到 {len(rows)} 个匹配学生, 请指定学号",
                               "multiple_matches": True}, ensure_ascii=False)
        sid = rows[0][0]
    if not sid:
        return json.dumps({"error": "请提供 student_id 或 student_name"}, ensure_ascii=False)

    out = parent_report_draft_service.create_draft(
        next(_gdb()), sid, created_by=current_teacher() or "")
    if "error" in out:
        return json.dumps(out, ensure_ascii=False)

    content = out["content"]
    weak = content.get("weak_knowledge_points") or []
    kp_text = "、".join(f"{k['name']}({k['errors']}次)" for k in weak[:5]) if weak else "暂无薄弱数据"
    preview = (
        f"📋 **{content.get('student_name')} · 家长学习报告 (预览 · 第 {out['version']} 版)**\n\n"
        f"📊 本周完成 {content.get('week_practice_count')} 道练习，正确率 {content.get('week_accuracy')}%\n"
        f"🎯 薄弱知识点: {kp_text}\n"
        f"🧠 主要学习特点: {content.get('dominant_barrier')}\n"
        f"💡 {content.get('suggestion')}\n\n"
        "⚠️ 以上为预览。发送前会弹确认卡等老师决定（批准/打回/放弃）。"
    )
    return json.dumps({
        "preview": preview,
        "report_data": content,
        "student_id": out["student_id"],
        "student_name": content.get("student_name", ""),
        "draft_id": out["draft_id"],
        "version": out["version"],
        # 生成即门（同学习计划）
        "approval_needed": True,
        "message_gate": f"学习报告（第 {out['version']} 版）等待老师确认，可打回修改",
        "target": out["student_id"],
        "action": "send_parent",
        "next_action": "教师确认后调 send_report_to_parent 发送；打回由系统按意见修订",
        "_component": {
            "component": "parent_report",
            "params": {
                "student_id": out["student_id"],
                "draft_id": out["draft_id"],
                "version": out["version"],
                "data": {"student_id": out["student_id"],
                         "draft_id": out["draft_id"], "report_data": content},
            },
        },
    }, ensure_ascii=False)


# ── send_report_to_parent ──

async def send_report_to_parent(
    student_id: str = "",
    draft_id: str = "",
    report_data: str = "",
) -> str:
    """发送家长报告 — 将确认过的报告草稿推送给绑定家长

    何时用：教师确认报告无误后说"发送""发给家长""推送"
    会发生什么：发送前系统会弹确认卡等老师决定（批准/打回/放弃）；批准后
               写家长通知（幂等），家长端消息Tab可见
    返回：确认发送结果；未确认时返回确认请求（弹卡）
    铁律（ADR-0013 确认门）：门由草稿状态强制——未确认的草稿发送会被拒绝并弹卡，
    禁止重复调用重试
    NOT for 预览 — 先用 generate_parent_report；题目/练习不发家长（send_learning_plan）"""
    from agent.tools.context import current_teacher
    from app.models.database import get_db as _gdb
    from app.services.parent_report_draft_service import parent_report_draft_service

    if not student_id:
        return json.dumps({"error": "请提供 student_id"}, ensure_ascii=False)

    out = parent_report_draft_service.send_draft(
        next(_gdb()), student_id=student_id, draft_id=draft_id or "",
        sender_id=current_teacher() or "",
    )
    return json.dumps(out, ensure_ascii=False)


# ── Diagnosis writeback helper ──

def _writeback_diagnosis(student_id: str, result_data: dict):
    """Best-effort write diagnosis result to SqliteStore."""
    try:
        store = _get_store_context()
        if not store:
            return
        import asyncio
        from datetime import datetime

        async def _write():
            ns = ("student", student_id, "diagnosis")
            try:
                existing = await store.asearch(ns, limit=5)
                if existing and len(existing) >= 5:
                    oldest = existing[-1]
                    oldest_key = getattr(oldest, "key", "")
                    if oldest_key:
                        await store.adelete(ns, oldest_key)
            except Exception:
                pass
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            await store.aput(ns, f"diag_{ts}", {
                "barrier_type": result_data.get("dominant_barrier"),
                "barrier_distribution": result_data.get("barrier_distribution"),
                "timestamp": ts,
            })

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_write())
        except RuntimeError:
            pass
    except Exception:
        pass


def _get_store_context():
    """Get SqliteStore from agent context."""
    try:
        from agent.langgraph_agent_v2 import get_store_context
        return get_store_context()
    except Exception:
        return None
