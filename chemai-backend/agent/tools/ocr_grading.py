"""OCR and grading tools — answer sheet OCR progress, grading, and result saving."""

import json

from dotenv import load_dotenv
load_dotenv()


async def query_ocr_progress(teacher_id: str = "", batch_id: str = "") -> str:
    """答题卡识别进度 — 查询 OCR 识别任务的实时进度

    何时用：老师刚上传了答题卡批，或问"识别完了吗""进度怎么样了""答题卡识别进度"
    会发生什么：查询 ocr_tasks 表，返回每批每张答题卡的状态、百分比、学生信息；
        只看得到自己上传的批次（身份取自 token，校级管理员看全校）
    下一步：全部完成后引导老师选考试（list_teacher_exams）再批改；部分失败可让老师重试；
       还在识别中（未全部完成）时告知老师"识别通常约需 1 分钟，可稍后回来问我进度"，不要后台轮询
    NOT for 查成绩/批改结果 — 用 query_batch_grades；NOT for 执行批改 — 用 grade_answer_sheets"""
    from app.models.database import get_db
    from app.models.ocr_task import OCRTask

    db = next(get_db())
    try:
        scope = _caller_scope(db)
        if not scope.caller_id:
            return json.dumps({"error": "缺少教师身份，无法查询识别进度",
                               "_route": {"navigate": False}}, ensure_ascii=False)
        q = db.query(OCRTask)
        if batch_id:
            # 点名要看别批时先验归属——不能靠「按自己过滤后为空」蒙混放行
            named = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
            if any(not scope.allows_batch(t.teacher_id) for t in named):
                return json.dumps({"error": "无权查看该答题卡批次：不是你的批次",
                                   "_route": {"navigate": False}}, ensure_ascii=False)
            q = q.filter(OCRTask.batch_id == batch_id)
        q = q.filter(OCRTask.teacher_id.in_(scope.visible_batch_owners()))
        tasks = q.order_by(OCRTask.created_at.desc()).limit(30).all()

        batches = {}
        for t in tasks:
            bid = t.batch_id
            if bid not in batches:
                batches[bid] = {"total": 0, "done": 0, "failed": 0, "tasks": []}
            batches[bid]["total"] += 1
            if t.status == "done":
                batches[bid]["done"] += 1
            elif t.status == "failed":
                batches[bid]["failed"] += 1
            batches[bid]["tasks"].append(f"{t.title}: {t.status}({t.progress}%) {t.student_name or ''}")

        if not batches:
            return json.dumps({"message": "没有进行中的识别任务", "batches": {}}, ensure_ascii=False)

        summary_parts = []
        for bid, b in batches.items():
            pct = int(b["done"] / b["total"] * 100) if b["total"] else 0
            summary_parts.append(f"批次{bid}: {b['done']}/{b['total']}完成({pct}%), {b['failed']}失败")
            if b["tasks"]:
                summary_parts.append("  " + "; ".join(b["tasks"][:5]))

        all_done = all(b["done"] + b["failed"] == b["total"] for b in batches.values())
        return json.dumps({
            "summary": " | ".join(summary_parts),
            "all_done": all_done,
            "next_action": "全部识别完成，可开始批改" if all_done else "继续等待识别完成",
            "batches": batches,
        }, ensure_ascii=False)
    finally:
        db.close()


async def grade_answer_sheets(
    teacher_id: str = "", batch_id: str = "", exam_id: str = "", correct_answers: str = "",
) -> str:
    """答题卡批改 — 对已完成 OCR 识别的答题卡进行 LLM 批改

    何时用：OCR 识别全部完成后，老师说"开始批改""批改答题卡"
    会发生什么：对 batch 内所有 status=done 的任务跑 LLM 语义批改，返回逐学生结果
    先决条件：本批已全部识别完成（先调 query_ocr_progress 确认）；判卷前必须先向老师要标准答案，
       或提供已关联的 exam_id（题库考试）可免贴答案直接批改
    下一步：展示结果卡片给老师，老师确认或修正后调 save_grading_results 保存
    NOT for 查识别进度 — 用 query_ocr_progress"""
    from app.models.database import get_db
    from app.services import grading_center
    from app.services.llm_grading import parse_correct_answers

    db = next(get_db())
    try:
        # correct_answers: 老师粘贴的原始文本（"1.A 2.B\n13. Cu+2H2SO4(浓)..."）
        # 或 Agent 整理成的 JSON 字符串 [{"q_number": 1, "answer": "B"}, ...]；
        # 优先级高于题库匹配。先试 JSON，失败则用确定性解析器拆原始文本（ADR-0005 B1）。
        parsed_answers = None
        if correct_answers:
            try:
                parsed_answers = json.loads(correct_answers)
                if not isinstance(parsed_answers, list):
                    parsed_answers = None
            except (ValueError, TypeError):
                parsed_answers = None
            if parsed_answers is None:
                parsed_answers = parse_correct_answers(correct_answers)
                if not parsed_answers:
                    return json.dumps({
                        "error": "correct_answers 既不是合法 JSON 数组，也解析不出题号"
                                 "（例：1.A 2.B 或 13. Cu+2H2SO4(浓)...）",
                    }, ensure_ascii=False)

        results = grading_center.grade_ocr_batch(
            db, batch_id=batch_id, parsed_answers=parsed_answers, exam_id=exam_id or None,
            scope=_caller_scope(db),
        )
        if not results:
            return json.dumps({"error": "没有完成识别的答题卡", "batch_id": batch_id}, ensure_ascii=False)
        denied = next((r["error"] for r in results if r.get("denied")), None)
        if denied:
            return json.dumps({"error": denied, "batch_id": batch_id}, ensure_ascii=False)

        lines = []
        for r in results:
            name = r.get("student_name") or r["task_id"]
            if "error" in r:
                lines.append(f"{name}: {r['error']}")
            else:
                lines.append(f"{name}: {r['score']}/{r['total']}分")
        summary = "\n".join(lines)
        has_error = any("error" in r for r in results)
        return json.dumps({
            "message": f"批改完成，共{len(results)}份" + ("（部分失败）" if has_error else ""),
            "summary": summary, "results": results,
            "next_action": "请确认批改结果，确认后可保存",
        }, ensure_ascii=False)
    finally:
        db.close()


async def save_grading_results(teacher_id: str = "", batch_id: str = "", exam_id: str = "") -> str:
    """保存批改结果 — 将确认后的批改结果写入学生答题记录并触发诊断

    何时用：老师确认批改结果后，说"保存""确认保存"
    会发生什么：校验 exam_id 关联的真实考试存在；逐学生按真实 Question 写入 StudentAnswer，
        学生/题目匹配失败计数不静默；幂等防重复累加；保存后触发 LLM barrier 诊断
    下一步：返回保存统计和诊断状态
    NOT for 批改 — 用 grade_answer_sheets"""
    from app.models.database import get_db
    from app.services import grading_center

    db = next(get_db())
    try:
        out = grading_center.save_batch(db, batch_id=batch_id, exam_id=exam_id,
                                        scope=_caller_scope(db))
        if out.get("error"):
            return json.dumps({"error": out["error"]}, ensure_ascii=False)

        return json.dumps({
            "message": out.get("message", ""),
            "saved_count": out["saved"],
            "total": out["total"],
            "skipped_no_student": out["skipped_no_student"],
            "skipped_duplicate": out["skipped_duplicate"],
            "question_missing": out["question_missing"],
            "diagnosis": out["diagnosis"],
            "details": out["details"],
        }, ensure_ascii=False)
    finally:
        db.close()


async def query_batch_grades(teacher_id: str = "", batch_id: str = "", exam_id: str = "") -> str:
    """查询答题卡成绩 — 查批改结果或已保存的考试成绩

    何时用：老师问"上次那批批了多少分""这次考试谁考多少""成绩出来了吗"
    会发生什么：传 batch_id 查该批 OCRTask.grading_result（批改未保存）；传 exam_id 查
        StudentAnswer（已保存成绩，按学生聚合分数/对错）；两者都按调用者范围收窄
        （批次认上传者，考试认班级范围）
    数据来源会在返回里标注："批改未保存" vs "已保存"，避免误读
    下一步：批改未保存时提醒老师先确认保存；已保存时可按考试看班级分布
    NOT for 查识别进度 — 用 query_ocr_progress"""
    from app.models.database import get_db
    from app.models.ocr_task import OCRTask

    db = next(get_db())
    try:
        scope = _caller_scope(db)
        if not scope.caller_id:
            return json.dumps({"error": "缺少教师身份，无法查询成绩",
                               "_route": {"navigate": False}}, ensure_ascii=False)
        if exam_id:
            from app.models.database import ExamRecord, StudentAnswer
            exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
            if exam is None:
                return json.dumps({"error": f"考试记录不存在：{exam_id}"}, ensure_ascii=False)
            if not scope.allows_exam_class(exam.class_id):
                return json.dumps({"error": "无权查看该考试的成绩：不在你的班级范围内"},
                                  ensure_ascii=False)
            answers = db.query(StudentAnswer).filter(
                StudentAnswer.exam_record_id == exam_id,
            ).all()
            if not answers:
                return json.dumps({
                    "message": f"考试 {exam_id} 暂无已保存的答题记录",
                    "exam_id": exam_id, "saved": True, "source": "已保存", "results": [],
                }, ensure_ascii=False)
            by_student = {}
            for a in answers:
                sid = a.student_id
                st = by_student.setdefault(sid, {"student_id": sid, "correct": 0, "total": 0, "questions": []})
                st["total"] += 1
                if a.is_correct:
                    st["correct"] += 1
                st["questions"].append({
                    "question_id": a.question_id, "student_answer": a.student_answer,
                    "is_correct": a.is_correct,
                })
            results = [{
                "student_id": s["student_id"],
                "score": s["correct"], "total": s["total"],
                "questions": s["questions"],
            } for s in by_student.values()]
            return json.dumps({
                "message": f"考试 {exam_id} 已保存 {len(results)} 位学生成绩",
                "exam_id": exam_id, "saved": True, "source": "已保存",
                "results": results,
            }, ensure_ascii=False)

        # batch_id: 查该批批改结果（grading_result）
        tasks = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
        if any(not scope.allows_batch(t.teacher_id) for t in tasks):
            return json.dumps({"error": "无权查看该答题卡批次：不是你的批次"},
                              ensure_ascii=False)
        graded = [t for t in tasks if t.grading_result]
        if not graded:
            return json.dumps({
                "message": f"批次 {batch_id} 暂无批改结果，请先批改",
                "batch_id": batch_id, "saved": False, "results": [],
            }, ensure_ascii=False)
        results = [t.grading_result for t in graded]
        return json.dumps({
            "message": f"批次 {batch_id} 有 {len(results)} 份批改结果（未保存）",
            "batch_id": batch_id, "saved": False, "source": "批改未保存",
            "results": results,
        }, ensure_ascii=False)
    finally:
        db.close()


async def list_teacher_exams(teacher_id: str = "") -> str:
    """列出老师名下考试 — 反问答题卡归类考试用

    何时用：老师丢了一批答题卡，agent 需要反问她"这批是哪场考试"，先列候选
    会发生什么：按调用者（token 身份）可触达的班级查考试记录，返回候选列表
    下一步：老师从中选一场，agent 拿到 record_id 作为 exam_id 传给 grade_answer_sheets / save_grading_results
    NOT for 查成绩 — 用 query_batch_grades"""
    from app.models.database import get_db, Class, ExamRecord

    db = next(get_db())
    try:
        scope = _caller_scope(db)
        if not scope.caller_id:
            return json.dumps({"error": "缺少教师身份，无法列出考试"}, ensure_ascii=False)

        class_ids = sorted(scope.class_ids)
        if not class_ids:
            return json.dumps({
                "message": "该老师名下没有任教班级，无法列出考试",
                "total": 0, "classes": [],
            }, ensure_ascii=False)

        # 与前端考试下拉一致：每班查考试记录（仅列前 5 个班，与页面 classes.slice(0,5) 对齐）
        classes = db.query(Class).filter(Class.class_id.in_(class_ids[:5])).all()
        out_classes = []
        total = 0
        for c in classes:
            exams = db.query(ExamRecord).filter(
                ExamRecord.class_id == c.class_id,
            ).order_by(ExamRecord.exam_date.desc()).all()
            exam_list = [{
                "record_id": e.record_id,
                "name": e.name,
                "class_name": c.name,
            } for e in exams]
            total += len(exam_list)
            out_classes.append({
                "class_id": c.class_id,
                "class_name": c.name,
                "exams": exam_list,
            })

        return json.dumps({
            "message": f"共列出 {total} 场考试，请老师选择这场答题卡对应的考试",
            "total": total,
            "classes": out_classes,
        }, ensure_ascii=False)
    finally:
        db.close()

def _caller_scope(db):
    """Agent 工具的调用者范围——身份取服务端上下文，模型传参一律不采信。

    学生/家长/未知身份（persona 可由请求体自报）拿到的是空范围。
    """
    from agent.tools.context import current_teacher
    from app.services.grading_center import CallerScope

    return CallerScope.from_user_id(db, current_teacher())


async def query_grading_queue(teacher_id: str = "", batch_id: str = "", exam_id: str = "") -> str:
    """判卷队列查询 — 查看待确认批次的判卷任务与已保存成绩概况

    何时用：老师问"有多少要批的""有哪些待确认""批改保存了多少"
    会发生什么：返回已批改未确认的答题卡批次列表（待确认队列）+ 线上考试里等待教师
        确认的成绩（unconfirmed_exams，AI 判定已落库但未生效）；传 exam_id 时附带已保存作答量；
        按调用者（token 身份）的班级范围收窄，看不到范围外的考试
    下一步：待确认批 → 提醒老师核对后用 save_grading_results 保存入成绩；
       待确认成绩 → 核对无误后用 confirm_exam_grades 让成绩生效
    NOT for 识别进度 — 用 query_ocr_progress"""
    from agent.tools.context import current_teacher
    from app.models.database import get_db
    from app.services import grading_center

    caller_id = current_teacher()
    if not caller_id:
        return json.dumps({"error": "缺少教师身份，无法查询判卷队列",
                           "_route": {"navigate": False}}, ensure_ascii=False)

    db = next(get_db())
    try:
        out = grading_center.grading_queue(
            db, _caller_scope(db), batch_id=batch_id, exam_id=exam_id,
        )
        out["_route"] = {"navigate": False}
        return json.dumps(out, ensure_ascii=False)
    finally:
        db.close()


async def confirm_exam_grades(exam_id: str) -> str:
    """成绩确认 — 把一场线上考试 AI 判定的成绩批量生效并触发诊断

    何时用：老师看到待确认成绩后说"这场没问题，确认""成绩生效吧"（exam_id 来自
            query_grading_queue 的 unconfirmed_exams 或 list_teacher_exams）
    会发生什么：该考试全部未确认作答翻转为生效（成绩确认门），此前 finalize/诊断/错题本
        都看不到这些作答；确认后触发一次障碍诊断，学生收件箱收到判卷完成通知；重复确认无副作用。
        只允许确认自己班级范围内的考试（身份取自 token，不看模型传参）
    下一步：告知老师成绩已生效、诊断已触发
    NOT for 单题改判 — 在判卷中心页逐题改判；NOT for 保存答题卡结果 — 用 save_grading_results"""
    from agent.tools.context import current_teacher
    from app.models.database import ExamRecord, get_db
    from app.services import grading_center

    caller_id = current_teacher()
    if not caller_id:
        return json.dumps({"error": "缺少教师身份，无法确认成绩",
                           "_route": {"navigate": False}}, ensure_ascii=False)

    db = next(get_db())
    try:
        exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
        if exam is None:
            return json.dumps({"error": f"考试记录不存在：{exam_id}",
                               "_route": {"navigate": False}}, ensure_ascii=False)
        if not _caller_scope(db).allows_exam_class(exam.class_id):
            return json.dumps({"error": "无权确认该考试的成绩（不在你的班级范围内）",
                               "_route": {"navigate": False}}, ensure_ascii=False)

        out = grading_center.confirm(db, exam_id)
        if out.get("error"):
            return json.dumps({"error": out["error"], "_route": {"navigate": False}},
                              ensure_ascii=False)
        return json.dumps({
            "message": f"已确认 {out['confirmed']} 条作答生效，诊断：{out.get('diagnosis', '未触发')}",
            "exam_id": exam_id,
            "confirmed": out["confirmed"],
            "diagnosis": out.get("diagnosis", "未触发"),
            "_route": {"navigate": False},
        }, ensure_ascii=False)
    finally:
        db.close()
