"""历史数据导入服务测试：名册去重、考试写入、障碍归因、幂等。"""

from app.models.database import (
    Account, Class, ExamRecord, Question, Student, StudentAnswer,
)
from app.services.data_import import data_import_service
from app.services.barrier_service import aggregate_barrier_from_answers


ROSTER_ROWS = [
    {"class_name": "2419班", "student_no": "241901", "name": "周翔"},
    {"class_name": "2419班", "student_no": "241902", "name": "危恩泽"},
    {"class_name": "2420班", "student_no": "242001", "name": "李文博"},
]


class TestRosterImport:
    def test_creates_classes_students_accounts(self, db_session):
        result = data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS)
        assert result["created_classes"] == 2
        assert result["created_students"] == 3
        assert result["skipped"] == []

        classes = db_session.query(Class).all()
        assert {c.name for c in classes} == {"2419班", "2420班"}
        # student_count 与在读人数一致
        counts = {c.name: c.student_count for c in classes}
        assert counts == {"2419班": 2, "2420班": 1}

        # 学生账号开通（学号即用户名）
        acc = db_session.query(Account).filter(Account.username == "241901").first()
        assert acc is not None and acc.role == "student"

    def test_dedup_by_student_no(self, db_session):
        data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS)
        result = data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS)
        assert result["created_students"] == 0
        assert len(result["skipped"]) == 3
        assert db_session.query(Student).count() == 3

    def test_skips_incomplete_rows(self, db_session):
        rows = [{"class_name": "2419班", "student_no": "", "name": "无学号"}]
        result = data_import_service.import_roster(db_session, "admin_001", rows)
        assert result["created_students"] == 0
        assert db_session.query(Student).count() == 0


def _exam_payload(**overrides):
    payload = {
        "name": "长沙市2026年9月高三第一次联考·化学",
        "class_name": "2419班",
        "subject": "化学",
        "exam_date": "2026-09-10",
        "grade_name": "高三",
        "grade_year": 2024,
        "questions": [
            {"no": "客观题1", "qtype": "single_choice", "full_score": 3,
             "answer": "C", "content": "下列说法正确的是",
             "knowledge_points": ["化学与STSE"], "probe_dimension": "concept",
             "difficulty": 2},
            {"no": "客观题2", "qtype": "single_choice", "full_score": 3,
             "answer": "B", "content": "设NA为阿伏伽德罗常数的值",
             "knowledge_points": ["物质的量"], "probe_dimension": "reading",
             "difficulty": 3},
            {"no": "主观题15.3", "qtype": "fill_blank", "full_score": 5,
             "answer": "2Na+2H2O=2NaOH+H2↑", "content": "写出钠与水反应的化学方程式",
             "knowledge_points": ["钠及其化合物"], "probe_dimension": "expression",
             "difficulty": 3},
        ],
        "scores": [
            {"student_no": "241901", "total": 8,
             "items": {"客观题1": 3, "客观题2": 3, "主观题15.3": 2},
             "answer_texts": {"主观题15.3": "2Na+2H2O=2NaOH+H2↑(漏气体符号)"}},
            {"student_no": "241902", "total": 11,
             "items": {"客观题1": 3, "客观题2": 0, "主观题15.3": 5},
             "answer_texts": {}},
        ],
    }
    payload.update(overrides)
    return payload


class TestExamImport:
    def test_full_landing(self, db_session):
        data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS[:2])
        result = data_import_service.import_exam(db_session, "admin_001", _exam_payload())
        assert result["created"] is True
        assert result["present"] == 2
        assert result["questions"] == 3
        assert result["answers"] == 6

        exam = db_session.query(ExamRecord).filter(
            ExamRecord.name.contains("第一次联考")
        ).first()
        assert exam is not None
        assert exam.present_students == 2
        # 跨表一致：question_stats 由作答聚合而来
        stats = exam.question_stats
        assert len(stats) == 3  # 3 道题各有统计
        assert all(v["total"] == 2 for v in stats.values())

        # 作答判定：客观题=满分；主观题=≥60%
        answers = db_session.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == exam.record_id
        ).all()
        by_student = {}
        for a in answers:
            by_student.setdefault(a.student_id, []).append(a)
        zhou = {a.question_id.rsplit("_", 1)[-1]: a for a in by_student["241901"]}
        wei = {a.question_id.rsplit("_", 1)[-1]: a for a in by_student["241902"]}
        # 周翔：客观全对，主观 2/5 < 60% → 错
        assert not zhou["主观题15.3"].is_correct
        assert zhou["客观题1"].is_correct and zhou["客观题2"].is_correct
        # 危恩泽：客观题2 得 0 分 → 错
        assert not wei["客观题2"].is_correct
        assert wei["主观题15.3"].is_correct  # 5/5 ≥ 60%

    def test_barrier_attribution_follows_probe_dimension(self, db_session):
        data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS[:2])
        data_import_service.import_exam(db_session, "admin_001", _exam_payload())

        dist = aggregate_barrier_from_answers(db_session, "241901")
        # 周翔唯一错题是主观题15.3（expression）
        assert dist["expression"] == 1.0
        dist2 = aggregate_barrier_from_answers(db_session, "241902")
        # 危恩泽唯一错题是客观题2（reading）
        assert dist2["reading"] == 1.0

        student = db_session.query(Student).filter(Student.student_id == "241901").first()
        assert student.barrier_type["expression"] == 1.0

    def test_idempotent_by_class_and_name(self, db_session):
        data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS[:2])
        first = data_import_service.import_exam(db_session, "admin_001", _exam_payload())
        second = data_import_service.import_exam(db_session, "admin_001", _exam_payload())
        assert first["created"] is True
        assert second == {"record_id": first["record_id"], "created": False}

    def test_question_probe_dimension_persisted(self, db_session):
        data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS[:2])
        data_import_service.import_exam(db_session, "admin_001", _exam_payload())
        dims = {
            q.probe_dimension for q in db_session.query(Question).all()
        }
        assert dims == {"concept", "reading", "expression"}


class TestTeachingAssignments:
    def test_creates_teacher_and_link(self, db_session):
        data_import_service.import_roster(db_session, "admin_001", ROSTER_ROWS[:1])
        result = data_import_service.import_teaching_assignments(db_session, "admin_001", [
            {"teacher_id": "teacher_qian", "teacher_name": "钱老师", "username": "qian",
             "password": "qian123456", "class_name": "2419班",
             "subject": "化学", "is_class_teacher": True},
        ])
        assert result["created_teachers"] == 1
        assert result["created_links"] == 1
        from app.models.database import TeacherClassSubject
        link = db_session.query(TeacherClassSubject).first()
        assert link.subject == "化学" and link.is_class_teacher is True
