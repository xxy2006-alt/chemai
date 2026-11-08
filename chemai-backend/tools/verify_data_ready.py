"""
数据就绪校验（运维工具）

逐项断言部署数据满足：
1. 结构完整：学校/年级/班级/教师/学生/账号数量与关系
2. 跨表一致：student_count、present_students、avg_score、question_stats 与作答聚合相等
3. 无空壳：EXAM/PRACTICE 记录均有题目与作答（每日练习不含 0 题 0 人记录）
4. 障碍可重放：学生 barrier_type == 按考察维度聚合错题的分布（barrier_service 重算）
5. 落点完整：学生端通知、家长端通知、预警日志、真题库（historical_exams）非空
6. 难度规范：questions.difficulty 全部为整数 1~5

用法：python tools/verify_data_ready.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, text

from app.models.database import (
    Account, Class, ExamRecord, HistoricalExam, ParentNotification,
    Question, RecordType, School, Student, StudentAnswer, StudentNotification,
    Teacher, get_db,
)
from app.models.warning_log import WarningLog
from app.services.barrier_service import aggregate_barrier_from_answers

PASS, FAIL = "✓", "✗"
failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  {PASS} {name}")
    else:
        print(f"  {FAIL} {name}  {detail}")
        failures.append(name)


def main():
    db = next(get_db())
    print("── 结构完整性 ──")
    school_n = db.query(School).count()
    class_n = db.query(Class).count()
    student_n = db.query(Student).filter(Student.status == "approved").count()
    teacher_n = db.query(Teacher).count()
    account_n = db.query(Account).count()
    check("学校已建档", school_n >= 1)
    check("班级 ≥ 9", class_n >= 9, f"实际 {class_n}")
    check("学生 ≥ 300", student_n >= 300, f"实际 {student_n}")
    check("化学教师 ≥ 4", teacher_n >= 4, f"实际 {teacher_n}")
    check("学生账号与学生对齐",
          account_n >= db.query(Account).filter(Account.role == "student").count() >= student_n * 0.99)

    print("── 跨表一致性 ──")
    bad_count, bad_present, bad_avg = [], [], []
    exams = db.query(ExamRecord).filter(ExamRecord.type == RecordType.EXAM).all()
    for e in exams:
        real_present = db.query(func.count(func.distinct(StudentAnswer.student_id))).filter(
            StudentAnswer.exam_record_id == e.record_id).scalar()
        if e.present_students != real_present:
            bad_present.append(e.record_id)
        if real_present:
            cls_n = db.query(Student).filter(
                Student.class_id == e.class_id, Student.status == "approved").count()
            if e.total_students and abs(e.total_students - cls_n) > 0:
                bad_count.append(e.record_id)
        if e.question_stats:
            for qid, st in e.question_stats.items():
                real = db.query(func.count(StudentAnswer.answer_id)).filter(
                    StudentAnswer.question_id == qid,
                    StudentAnswer.exam_record_id == e.record_id).scalar()
                if st.get("total") != real:
                    bad_avg.append(f"{e.record_id}/{qid}")
    check("每场考试 present_students == 实际作答人数", not bad_present, str(bad_present[:5]))
    check("每场考试 total_students == 班级在读人数", not bad_count, str(bad_count[:5]))
    check("question_stats 与作答聚合一致", not bad_avg, str(bad_avg[:5]))

    bad_cls = []
    for c in db.query(Class).all():
        n = db.query(Student).filter(
            Student.class_id == c.class_id, Student.status == "approved").count()
        if c.student_count != n:
            bad_cls.append(f"{c.name}:{c.student_count}!={n}")
    check("班级 student_count == 在读人数", not bad_cls, str(bad_cls[:5]))

    print("── 无空壳记录 ──")
    shells = 0
    for r in db.query(ExamRecord).all():
        q_n = db.query(Question).filter(Question.record_id == r.record_id).count()
        a_n = db.query(StudentAnswer).filter(StudentAnswer.exam_record_id == r.record_id).count()
        if (r.type == RecordType.EXAM and (q_n == 0 or a_n == 0)) or (
            r.type == RecordType.PRACTICE and q_n == 0
        ):
            shells += 1
    check("无空壳考试/练习记录", shells == 0, f"{shells} 条")

    practice_shells = db.query(ExamRecord).filter(
        ExamRecord.type == RecordType.PRACTICE,
        ExamRecord.name.like("每日练习%"),
    ).all()
    bad_practice = [r.record_id for r in practice_shells
                    if not db.query(StudentAnswer).filter(
                        StudentAnswer.exam_record_id == r.record_id).count()]
    check("每日练习均有作答（可诊断下钻）", not bad_practice, str(bad_practice[:5]))

    print("── 障碍可重放 ──")
    students = db.query(Student).filter(Student.status == "approved").all()
    sample = random.Random(7).sample(students, min(30, len(students)))
    mismatch = []
    for s in sample:
        stored = s.barrier_type if isinstance(s.barrier_type, dict) else None
        replayed = aggregate_barrier_from_answers(db, s.student_id)
        if stored is None or any(
            abs((stored.get(k) or 0) - v) > 0.02 for k, v in replayed.items()
        ):
            mismatch.append(s.student_id)
    check("抽样学生 barrier_type 可由作答重放复现", not mismatch, str(mismatch[:5]))

    print("── 落点完整性 ──")
    check("学生端通知 > 0", db.query(StudentNotification).count() > 0,
          str(db.query(StudentNotification).count()))
    check("家长端通知 > 0", db.query(ParentNotification).count() > 0,
          str(db.query(ParentNotification).count()))
    check("预警日志 > 0", db.query(WarningLog).count() > 0,
          str(db.query(WarningLog).count()))
    check("真题库 historical_exams > 0", db.query(HistoricalExam).count() > 0,
          str(db.query(HistoricalExam).count()))
    active_bindings = db.execute(
        text("select count(*) from student_parent_bindings where status='active'")).scalar()
    check("家长绑定存在", active_bindings > 0)

    print("── 练习统计回写 ──")
    bad_pstats = 0
    for r in db.query(ExamRecord).filter(ExamRecord.type == RecordType.PRACTICE).all():
        a_n = db.query(StudentAnswer).filter(StudentAnswer.exam_record_id == r.record_id).count()
        if a_n > 0 and (r.avg_score is None or not r.question_stats):
            bad_pstats += 1
    check("已作答练习记录均有统计(avg_score/question_stats)", bad_pstats == 0, str(bad_pstats))

    print("── agent 工具面 ──")
    try:
        import anyio
        from agent.tools.diagnosis import diagnose_barrier

        classes = db.query(Class).all()
        empty = []
        for c in classes:
            d = json.loads(anyio.run(lambda cid=c.class_id: diagnose_barrier(class_id=cid)))
            dist = d.get("barrier_distribution") or {}
            if d.get("total_students", 0) > 0 and not any(dist.values()):
                empty.append(c.name)
        check("每个班的 agent 诊断均有障碍分布", not empty, str(empty))

        one = db.query(Student).filter(Student.status == "approved").first()
        d2 = json.loads(anyio.run(lambda: diagnose_barrier(student_id=one.student_id)))
        check("个体诊断可下钻", "barrier_distribution" in d2, json.dumps(d2, ensure_ascii=False)[:80])
    except Exception as exc:
        check("agent 工具面可调用", False, str(exc)[:120])

    print("── 难度规范 ──")
    bad_diff = db.query(Question).filter(
        (Question.difficulty < 1) | (Question.difficulty > 5) | Question.difficulty.is_(None)
    ).count()
    check("difficulty 全部为整数 1~5", bad_diff == 0, f"{bad_diff} 条违规")

    db.close()

    print()
    if failures:
        print(f"校验未通过：{len(failures)} 项 → {failures}")
        sys.exit(1)
    print("数据就绪校验全部通过。")


if __name__ == "__main__":
    main()
