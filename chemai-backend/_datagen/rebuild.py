# -*- coding: utf-8 -*-
"""
一键重建数据库（私有工具，不入交付源码）

流程：备份 → 重建空库（新schema）→ init_database（学校/教师/账号）
     → 教学安排导入 → 学籍名册导入 → 历次考试导入（真实锚点+合成）
     → 每日练习使用痕迹（近7个自然日，产品代码路径）→ 预警作业 → 就绪校验

用法：python rebuild.py [--skip-backup]
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))
import os
os.chdir(BACKEND)  # 产品代码内多处使用相对路径（data/exam_questions 等），统一以 backend 为 CWD

# 影子库构建：全部导入/写入指向 chemai_new.db，完成后原子换名，
# 避免与常驻服务（uvicorn）抢占 chemai.db 的文件锁。
SHADOW = BACKEND / "chemai_new.db"
os.environ["DATABASE_URL"] = f"sqlite:///{SHADOW.as_posix()}"


SEED = 20260914

STEP_LOG = []


def log(msg):
    line = f"[rebuild {datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    STEP_LOG.append(line)


def step_backup():
    import shutil
    src = BACKEND / "chemai.db"
    if src.exists():
        dst = BACKEND / "data" / f"db_backup_{datetime.now():%Y%m%d_%H%M%S}"
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst / "chemai.db")
        for extra in ("chemai.db-wal", "chemai.db-shm"):
            if (BACKEND / extra).exists():
                shutil.copy2(BACKEND / extra, dst / extra)
        log(f"备份完成 → {dst}")


def step_fresh_db():
    for p in (SHADOW, BACKEND / "chemai_new.db-wal", BACKEND / "chemai_new.db-shm"):
        if p.exists():
            p.unlink()
    from app.models.database import init_db
    # 独立模型文件需先导入注册到 metadata，create_all 才会建表
    import app.models.warning_log  # noqa: F401
    import app.models.ocr_task  # noqa: F401
    import app.models.review_task  # noqa: F401
    import app.models.conversation_owner  # noqa: F401
    init_db()
    log("影子空库重建完成（新schema）")


def get_session():
    from app.models.database import get_db
    return next(get_db())


def step_init_school(db):
    from app.utils.init_db import create_school, create_grade, create_teachers
    school = create_school(db)
    create_grade(db, school)
    create_teachers(db, school)
    log("学校/年级/教师/账号初始化完成")


def step_teaching_assignments(db):
    from app.services.data_import import data_import_service
    rows = []
    groups = [
        ("teacher_qian", "钱老师", ["2419班", "2420班", "2421班"], "2419班"),
        ("teacher_wu", "吴老师", ["2422班", "2423班", "2424班"], "2423班"),
        ("teacher_zheng", "郑老师", ["2425班", "2426班", "2427班"], "2427班"),
        ("teacher_zhou", "周老师", ["2419班", "2423班", "2427班"], None),
    ]
    for teacher_id, teacher_name, class_names, head_class in groups:
        for cn in class_names:
            rows.append({
                "teacher_id": teacher_id, "teacher_name": teacher_name,
                "username": teacher_id.replace("teacher_", ""),
                "password": f"{teacher_id.replace('teacher_', '')}123456",
                "class_name": cn, "subject": "化学",
                "is_class_teacher": cn == head_class,
                "grade_name": "高三", "grade_year": 2024,
            })
    result = data_import_service.import_teaching_assignments(db, "admin_001", rows)
    log(f"教学安排导入：{result}")


def step_roster(db):
    from app.services.data_import import data_import_service
    school = json.loads((HERE / "school.json").read_text(encoding="utf-8"))
    rows = []
    for cls_name, students in school["roster"].items():
        for s in students:
            rows.append({"class_name": cls_name, "student_no": s["student_no"], "name": s["name"]})
    result = data_import_service.import_roster(
        db, "admin_001", rows, grade_name="高三", grade_year=2024
    )
    log(f"学籍名册导入：班级={result['created_classes']} 学生={result['created_students']} 跳过={len(result['skipped'])}")


def step_exams(db):
    from app.services.data_import import data_import_service
    from synthesize import SCHOOL, EXAMS, build_exam_payload_for_class
    import random

    rng = random.Random(SEED)
    total_answers = 0
    for exam_index, exam in enumerate(EXAMS):
        for cls_name in SCHOOL["roster"].keys():
            roster = SCHOOL["roster"][cls_name]
            payload = build_exam_payload_for_class(cls_name, roster, exam, rng,
                                                   exam_index=exam_index)
            result = data_import_service.import_exam(db, "admin_001", payload)
            total_answers += result.get("answers", 0)
        log(f"考试 {exam['date']} {exam['label']} 导入完成（累计作答 {total_answers}）")


def step_daily_practice(db, days: int = 7):
    """近 N 天每日练习使用痕迹：create_daily_practice 产品路径 + 与 submit 同形作答落库"""
    from datetime import datetime, timedelta
    from app.models.database import Student, Question, StudentAnswer
    from app.services.barrier_service import recompute_class_barriers
    from app.scheduler.daily_practice import create_daily_practice
    import random

    rng = random.Random(SEED + 1)
    students = db.query(Student).filter(Student.status == "approved").all()
    log(f"每日练习：{len(students)} 名学生 × 近{days}天")

    base_day = datetime.utcnow().date()
    total_new = 0
    letters = ("A", "B", "C", "D")

    for offset in range(days - 1, -1, -1):
        day = base_day - timedelta(days=offset)
        for student in students:
            practice = create_daily_practice(db, student, day=day)
            if not practice:
                continue
            # 快速跳过：该人日已有作答（幂等续跑）
            if db.query(StudentAnswer).filter(
                StudentAnswer.exam_record_id == practice.record_id,
                StudentAnswer.student_id == student.student_id,
            ).count() > 0:
                continue
            questions = db.query(Question).filter(
                Question.record_id == practice.record_id
            ).all()
            ability = min(0.95, max(0.15, 0.55 + rng.uniform(-0.25, 0.30)))
            for i, q in enumerate(questions):
                answer_id = f"dans_{student.student_id}_{practice.record_id}_{q.question_id}"[:64]
                if db.query(StudentAnswer).filter(StudentAnswer.answer_id == answer_id).first():
                    continue
                hit = rng.random() < ability
                is_choice = (q.options is not None) and (q.answer in letters)
                if is_choice:
                    if hit:
                        ans = q.answer
                    else:
                        wrong = [l for l in letters if l != q.answer]
                        ans = rng.choice(wrong)
                    correct = hit
                else:
                    ans = (q.answer or "") if hit else "（表述不完整）"
                    correct = hit
                db.add(StudentAnswer(
                    answer_id=answer_id,
                    student_id=student.student_id,
                    question_id=q.question_id,
                    exam_record_id=practice.record_id,
                    student_answer=ans,
                    is_correct=correct,
                    answered_at=datetime.combine(day, datetime.min.time()) +
                    timedelta(minutes=20 + i * 4 + rng.randint(0, 3)),
                ))
                total_new += 1
            student.exercises_completed = (student.exercises_completed or 0) + 1
            student.last_exercise_at = datetime.combine(day, datetime.min.time()) + timedelta(hours=21)
            # 回写练习记录统计（与 /api/practice/submit 同口径）
            answers = db.query(StudentAnswer).filter(
                StudentAnswer.exam_record_id == practice.record_id,
                StudentAnswer.student_id == student.student_id,
            ).all()
            if answers:
                stats = {}
                for a in answers:
                    st = stats.setdefault(a.question_id, {"total": 0, "correct": 0, "wrong": 0})
                    st["total"] += 1
                    st["correct" if a.is_correct else "wrong"] += 1
                practice.question_stats = stats
                practice.avg_score = round(
                    sum(1 for a in answers if a.is_correct) / len(answers) * 100, 1
                )
                practice.present_students = 1
            db.commit()
            # 家长端通知（产品路径，幂等）
            from app.services.notification_service import notification_service
            notification_service.send_practice_notification(
                student.student_id, practice.name, idempotency_key=practice.record_id
            )

    for cid in {s.class_id for s in students}:
        recompute_class_barriers(db, cid)
    log(f"每日练习作答落库 {total_new} 条，障碍分布重算完成")


def step_parents(db):
    """全员家长建档 + 绑定；锚点学生（2419班化学中位生）家长开通登录账号"""
    import random
    from app.models.database import (
        Account, Parent, Student, StudentParentBinding,
    )

    rng = random.Random(SEED + 2)
    students = db.query(Student).filter(Student.status == "approved").order_by(Student.student_id).all()
    male_given = ["建国", "志强", "建军", "卫东", "国平", "德华", "永强", "志明"]
    female_given = ["秀兰", "丽华", "淑英", "桂英", "秀珍", "雅琴", "慧敏", "春梅", "雪芬", "玉华"]
    mom_surnames = ["王", "李", "张", "刘", "黄", "吴", "杨", "林", "罗"]

    # 锚点学生：2419班化学总分中位数学生
    detail = json.loads((HERE / "school.json").read_text(encoding="utf-8"))
    scores = detail["anchors"]["2026-09-10"]["per_class"].get("2419班", {})
    cls_students = [s for s in students if s.class_id == "class_2419"]
    cls_students = [s for s in cls_students if s.name in scores] or cls_students
    cls_students.sort(key=lambda s: scores.get(s.name, 0))
    anchor = cls_students[len(cls_students) // 2]

    created = 0
    for s in students:
        if db.query(StudentParentBinding).filter(
            StudentParentBinding.student_id == s.student_id,
            StudentParentBinding.status == "active",
        ).first():
            continue
        surname = s.name[0]
        # 父亲随学生姓，母亲他姓；双亲均建档绑定
        father_pid = f"parent_{s.student_id}"
        mother_pid = f"parent_{s.student_id}_m"
        mom_surname = rng.choice([x for x in mom_surnames if x != surname])
        pwd = __import__("hashlib").sha256(b"123456").hexdigest()
        db.add(Parent(parent_id=father_pid, name=surname + rng.choice(male_given),
                      phone=f"138{rng.randint(10000000, 99999999)}",
                      password_hash=pwd, status="active"))
        db.add(Parent(parent_id=mother_pid, name=mom_surname + rng.choice(female_given),
                      phone=f"139{rng.randint(10000000, 99999999)}",
                      password_hash=pwd, status="active"))
        db.add(StudentParentBinding(
            binding_id=f"bind_{father_pid}", student_id=s.student_id,
            parent_id=father_pid, relation="父亲", status="active",
            bind_code=f"BIND{rng.randint(100000, 999999)}"))
        db.add(StudentParentBinding(
            binding_id=f"bind_{mother_pid}", student_id=s.student_id,
            parent_id=mother_pid, relation="母亲", status="active",
            bind_code=f"BIND{rng.randint(100000, 999999)}"))
        created += 1

    # 演示家长账号（绑定锚点学生的父亲）
    anchor_binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == anchor.student_id,
        StudentParentBinding.relation == "父亲",
        StudentParentBinding.status == "active",
    ).first()
    anchor_parent = db.query(Parent).filter(
        Parent.parent_id == anchor_binding.parent_id).first()
    if not db.query(Account).filter(Account.username == "parent001").first():
        db.add(Account(
            account_id="acc_parent001",
            username="parent001",
            password_hash=__import__("hashlib").sha256(b"123456").hexdigest(),
            role="parent",
            parent_id=anchor_parent.parent_id,
            status="active",
        ))
    db.commit()
    log(f"家长建档绑定 {created} 人；演示家长 parent001/123456 → {anchor.name}({anchor.student_id})")


def step_warnings(db):
    """预警作业（产品路径）"""
    try:
        from app.scheduler.early_warning_check import check_warnings_job
        check_warnings_job()
        log("预警作业执行完成")
    except Exception as e:
        log(f"预警作业跳过：{e}")


def step_swap():
    import time
    live = BACKEND / "chemai.db"
    for attempt in range(15):
        try:
            for extra in ("chemai.db-wal", "chemai.db-shm"):
                f = BACKEND / extra
                if f.exists():
                    f.unlink()
            if live.exists():
                live.unlink()
            SHADOW.rename(live)
            log("换库完成：chemai_new.db → chemai.db")
            return
        except PermissionError:
            if attempt == 0:
                log("chemai.db 被常驻服务占用，等待重试（请停止 uvicorn 后自动继续）...")
            time.sleep(2)
    log("换库失败：chemai.db 持续被占用。影子库已就绪，请手动：")
    log(f"  1) 停止后端服务  2) 删除 chemai.db  3) 将 {SHADOW} 改名为 chemai.db")
    sys.exit(2)


def main():
    if "--verify-only" in sys.argv:
        rc = os.system(f'"{sys.executable}" tools/verify_data_ready.py')
        sys.exit(1 if rc else 0)
    skip_backup = "--skip-backup" in sys.argv
    if not skip_backup:
        step_backup()
    step_fresh_db()
    db = get_session()
    try:
        step_init_school(db)
        step_teaching_assignments(db)
        step_roster(db)
        step_exams(db)
        # 真题库落库 historical_exams（产品路径：与 app 启动同步同一函数）
        from app.services.exam_bank import exam_bank_service
        synced = exam_bank_service.sync_all_to_db()
        log(f"真题库同步 {synced} 条 → historical_exams")
        step_parents(db)
        step_daily_practice(db)
        step_warnings(db)
    finally:
        db.close()
    step_swap()
    log("重建完成。执行就绪校验：python tools/verify_data_ready.py")


if __name__ == "__main__":
    main()
