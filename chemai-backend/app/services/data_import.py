"""
历史数据导入服务

学校上线时的正当数据入口：
- 学籍名册导入（班级-学生，按学号去重合并）
- 历次考试成绩导入（逐题明细 → 考试记录 + 题目 + 作答记录，可只导总分）
- 教学安排导入（教师-班级-科目）

导入后的数据与原生录入走同一套表与查询路径，无差别。
所有导入动作写操作审计（operation_logs）。
"""
from datetime import datetime
from typing import Dict, List, Optional

from app.models.database import (
    Account, Class, Grade, OperationLog, Student,
    StudentAnswer, Teacher, TeacherClassSubject,
    ExamRecord, Question, QuestionSource, AuditStatus,
    BarrierType, Difficulty, RecordType,
)
from app.services.barrier_service import recompute_class_barriers

DEFAULT_STUDENT_PASSWORD = "123456"
SUBJECTIVE_PASS_RATIO = 0.6  # 主观题得分 ≥ 满分60% 记为答对


def _hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def _audit(db, user_id: str, action: str, target_type: str, target_id: str, detail: dict):
    db.add(OperationLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    ))


def uuid_hex() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def _to_float(value) -> Optional[float]:
    try:
        f = float(value)
        return f
    except (TypeError, ValueError):
        return None


class DataImportService:
    """历史数据导入：名册 / 考试成绩 / 教学安排"""

    # ---------- 学籍名册 ----------

    def import_roster(self, db, operator_id: str, rows: List[dict],
                      grade_name: Optional[str] = None,
                      grade_year: Optional[int] = None) -> dict:
        """
        rows: [{"class_name": "2419班", "student_no": "241901", "name": "周翔"}, ...]
        按 student_no 去重；已存在学号跳过（不覆盖）。
        学生账号同步开通（学号即用户名）。
        """
        created_classes, created_students, skipped = {}, 0, []
        for row in rows:
            class_name = (row.get("class_name") or "").strip()
            name = (row.get("name") or "").strip()
            student_no = (row.get("student_no") or "").strip()
            if not (class_name and name and student_no):
                skipped.append({"student_no": student_no, "reason": "字段缺失"})
                continue

            cls = self._ensure_class(db, class_name, grade_name, grade_year)
            created_classes[cls.class_id] = cls.name

            existing = db.query(Student).filter(Student.student_id == student_no).first()
            if existing:
                skipped.append({"student_no": student_no, "reason": "学号已存在"})
                continue

            student = Student(
                student_id=student_no,
                class_id=cls.class_id,
                name=name,
                status="approved",
                bind_code=f"BIND{uuid_hex()[:6].upper()}",
            )
            db.add(student)
            db.add(Account(
                account_id=f"acc_{student_no}",
                username=student_no,
                password_hash=_hash_password(DEFAULT_STUDENT_PASSWORD),
                role="student",
                student_id=student_no,
                status="active",
            ))
            created_students += 1

        db.flush()
        self._sync_class_counts(db, list(created_classes.keys()))
        _audit(db, operator_id, "import", "roster", "roster", {
            "classes": created_classes, "created": created_students, "skipped": len(skipped),
        })
        db.commit()
        return {
            "created_classes": len(created_classes),
            "created_students": created_students,
            "skipped": skipped,
        }

    # ---------- 教学安排 ----------

    def import_teaching_assignments(self, db, operator_id: str,
                                    rows: List[dict]) -> dict:
        """
        rows: [{"teacher_id": "teacher_zhao", "teacher_name": "赵老师", "class_name": "2419班",
                "subject": "化学", "is_class_teacher": true}, ...]
        教师不存在则先建档（含登录账号，用户名=teacher_id）。
        """
        created_teachers, created_links, skipped = 0, 0, []
        for row in rows:
            teacher_id = (row.get("teacher_id") or "").strip()
            class_name = (row.get("class_name") or "").strip()
            subject = (row.get("subject") or "化学").strip()
            if not (teacher_id and class_name):
                skipped.append(row)
                continue

            teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
            if not teacher:
                teacher = Teacher(
                    teacher_id=teacher_id,
                    name=row.get("teacher_name") or teacher_id,
                    status="approved",
                )
                db.add(teacher)
                db.add(Account(
                    account_id=f"acc_{teacher_id}",
                    username=row.get("username") or teacher_id,
                    password_hash=_hash_password(row.get("password") or "123456"),
                    role=row.get("role") or "teacher",
                    teacher_id=teacher_id,
                    status="active",
                ))
                created_teachers += 1

            cls = self._ensure_class(db, class_name, row.get("grade_name"), row.get("grade_year"))
            # 合并说明：原先这里写 `cls.teacher_id = teacher_id`，但 `classes.teacher_id`
            # 已随阶段 6.2 删除（班主任真源是下面这行 tcs 的 is_class_teacher）。

            link_id = f"tcs_{uuid_hex()}"
            exists = db.query(TeacherClassSubject).filter(
                TeacherClassSubject.teacher_id == teacher_id,
                TeacherClassSubject.class_id == cls.class_id,
                TeacherClassSubject.subject == subject,
            ).first()
            if exists:
                continue
            db.add(TeacherClassSubject(
                id=link_id,
                teacher_id=teacher_id,
                class_id=cls.class_id,
                subject=subject,
                is_class_teacher=bool(row.get("is_class_teacher")),
                assigned_at=datetime.utcnow(),
            ))
            created_links += 1

        _audit(db, operator_id, "import", "teaching_assignment", "tcs", {
            "created_teachers": created_teachers, "created_links": created_links,
        })
        db.commit()
        return {"created_teachers": created_teachers, "created_links": created_links,
                "skipped": len(skipped)}

    # ---------- 考试成绩 ----------

    def import_exam(self, db, operator_id: str, payload: dict) -> dict:
        """
        payload: {
          "name": "长沙市2026年9月高三第一次联考·化学",
          "class_name": "2419班", "subject": "化学", "exam_date": "2026-09-10",
          "questions": [  # 可选；缺省则只落考试记录与总分
             {"no": "客观题1", "qtype": "single_choice", "full_score": 3,
              "answer": "C", "content": "...", "options": [...], "analysis": "...",
              "knowledge_points": ["氧化还原反应"], "probe_dimension": "concept",
              "difficulty": 3},
             {"no": "主观题15.3", "qtype": "fill_blank", "full_score": 5, ...},
          ],
          "scores": [
             {"student_no": "241901", "total": 56, "items": {"客观题1": 3, "主观题15.3": 2, ...}},
          ],
        }
        幂等：同班同名同日期的考试已存在则返回已存在记录。
        作答判定：客观题=满分；主观题=得分 ≥ 满分×60%。
        答错按题目考察维度落 barrier_type，考后重算全班障碍分布。
        """
        class_name = (payload.get("class_name") or "").strip()
        name = (payload.get("name") or "").strip()
        if not (class_name and name):
            raise ValueError("class_name / name 必填")

        cls = self._ensure_class(db, class_name, payload.get("grade_name"), payload.get("grade_year"))
        exam_date = self._parse_date(payload.get("exam_date")) or datetime.utcnow()

        existing = db.query(ExamRecord).filter(
            ExamRecord.class_id == cls.class_id,
            ExamRecord.name == name,
        ).first()
        if existing:
            return {"record_id": existing.record_id, "created": False}

        record_id = f"exam_{cls.class_id}_{exam_date.strftime('%Y%m')}"
        suffix = 1
        while db.query(ExamRecord).filter(ExamRecord.record_id == record_id).first():
            suffix += 1
            record_id = f"exam_{cls.class_id}_{exam_date.strftime('%Y%m')}_{suffix}"

        questions_payload = payload.get("questions") or []
        exam = ExamRecord(
            record_id=record_id,
            class_id=cls.class_id,
            type=RecordType.EXAM,
            name=name,
            source=QuestionSource.MANUAL_SELECTED,
            exam_date=exam_date,
            generated_at=exam_date,
        )
        db.add(exam)

        qno_to_qid, spec_by_no = {}, {}
        for spec in questions_payload:
            qno = str(spec.get("no", "")).strip()
            if not qno:
                continue
            qid = f"q_{record_id}_{self._safe_no(qno)}"
            qno_to_qid[qno] = qid
            spec_by_no[qno] = spec
            db.add(Question(
                question_id=qid,
                record_id=record_id,
                content=spec.get("content") or f"（{name} 第{qno}题）",
                options=spec.get("options"),
                answer=spec.get("answer"),
                analysis=spec.get("analysis"),
                knowledge_points=spec.get("knowledge_points") or [],
                probe_dimension=spec.get("probe_dimension"),
                difficulty=Difficulty.coerce(spec.get("difficulty", 3)).value,
                source=QuestionSource.MANUAL_SELECTED,
                source_exam=name,
                audit_status=AuditStatus.PASSED,
            ))
        db.flush()

        question_stats: Dict[str, dict] = {}
        present, total_ans, total_correct_ans = 0, 0, 0
        full_total = sum(_to_float(q.get("full_score")) or 0.0 for q in questions_payload)
        totals_sum = 0.0
        touched_classes = set()

        for row in payload.get("scores") or []:
            student_no = (row.get("student_no") or "").strip()
            student = db.query(Student).filter(Student.student_id == student_no).first()
            if not student:
                continue
            present += 1
            items = row.get("items") or {}
            totals_sum += _to_float(row.get("total")) or sum(
                _to_float(v) or 0.0 for v in items.values()
            )

            for qno, qid in qno_to_qid.items():
                spec = spec_by_no[qno]
                full = _to_float(spec.get("full_score")) or 0.0
                raw = items.get(qno)
                score = _to_float(raw)
                if score is None:
                    continue  # 缺考/未评阅小题不落作答
                objective = str(spec.get("qtype", "single_choice")) == "single_choice"
                answer_texts = row.get("answer_texts") or {}
                if objective:
                    is_correct = full > 0 and score >= full
                    answer_text = answer_texts.get(qno) or (
                        str(spec.get("answer") or "") if is_correct else ""
                    )
                else:
                    is_correct = full > 0 and score >= full * SUBJECTIVE_PASS_RATIO
                    answer_text = answer_texts.get(qno, "")
                probe = spec.get("probe_dimension")
                total_ans += 1
                total_correct_ans += 1 if is_correct else 0

                db.add(StudentAnswer(
                    answer_id=f"sa_{student_no}_{qid}"[:64],
                    student_id=student_no,
                    question_id=qid,
                    exam_record_id=record_id,
                    student_answer=answer_text or None,
                    is_correct=is_correct,
                    barrier_type=(
                        BarrierType(probe)
                        if (not is_correct and probe in ("concept", "reading", "expression"))
                        else None
                    ),
                    answered_at=exam_date,
                ))

                stat = question_stats.setdefault(qid, {"total": 0, "correct": 0, "wrong": 0})
                stat["total"] += 1
                stat["correct"] += 1 if is_correct else 0
                stat["wrong"] += 0 if is_correct else 1

            touched_classes.add(student.class_id)

        exam.present_students = present
        exam.total_students = present
        exam.question_stats = question_stats
        # 班级均分（百分制）：学生总分均值 / 卷面满分
        exam.avg_score = (
            round(totals_sum / present / full_total * 100, 1) if present and full_total else None
        )

        _audit(db, operator_id, "import", "exam", record_id, {
            "name": name, "class": class_name, "present": present,
            "questions": len(qno_to_qid), "answers": total_ans,
        })
        db.commit()

        # 障碍分布重算（统一口径，可重放）
        for cid in touched_classes:
            recompute_class_barriers(db, cid)

        return {"record_id": record_id, "created": True, "present": present,
                "questions": len(qno_to_qid), "answers": total_ans}

    # ---------- 内部工具 ----------

    def _ensure_class(self, db, class_name: str,
                      grade_name: Optional[str], grade_year: Optional[int]) -> Class:
        cls = db.query(Class).filter(Class.name == class_name).first()
        if cls:
            return cls
        grade = None
        if grade_name:
            grade = db.query(Grade).filter(Grade.name == grade_name).first()
            if not grade:
                grade = Grade(
                    grade_id=f"grade_{grade_year or datetime.utcnow().year}_{grade_name}",
                    name=grade_name,
                    year=grade_year or datetime.utcnow().year,
                    status=1,
                )
                db.add(grade)
                db.flush()
        import re as _re
        base = "class_" + (_re.sub(r"[^0-9A-Za-z]", "", class_name) or uuid_hex())
        class_id, n = base, 1
        while db.query(Class).filter(Class.class_id == class_id).first():
            n += 1
            class_id = f"{base}_{n}"
        cls = Class(
            class_id=class_id,
            name=class_name,
            grade=grade_name or "高三",
            grade_id=grade.grade_id if grade else None,
            subject="化学",
        )
        db.add(cls)
        db.flush()
        return cls

    def _sync_class_counts(self, db, class_ids: List[str]):
        for cid in class_ids:
            count = db.query(Student).filter(
                Student.class_id == cid, Student.status == "approved"
            ).count()
            cls = db.query(Class).filter(Class.class_id == cid).first()
            if cls:
                cls.student_count = count

    @staticmethod
    def _parse_date(value) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _safe_no(qno: str) -> str:
        return "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in qno)


data_import_service = DataImportService()
