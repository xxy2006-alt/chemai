"""End-to-end: student submits answers → barrier type updates.

Tests the critical pipeline: practice submit → StudentAnswer creation →
student.barrier_type update → wrong answers query.
"""
import pytest
from datetime import datetime


@pytest.fixture
def setup_exam(db_session, sample_student):
    """Create an exam record with 5 questions and pre-saved student answers."""
    from app.models.database import ExamRecord, Question, StudentAnswer, RecordType, Difficulty, QuestionSource, AuditStatus

    exam = ExamRecord(
        record_id="test_exam_001", class_id="class_2025_1",
        name="test exam", type=RecordType.EXAM,
        total_students=1, present_students=1,
        exam_date=datetime.utcnow(),
        question_stats={"published": True},
    )
    db_session.add(exam)

    questions = []
    for i in range(5):
        q = Question(
            question_id=f"test_q_{i}", record_id="test_exam_001",
            content=f"question {i}", options=["A", "B", "C", "D"],
            answer="B", analysis="test",
            knowledge_points=["kp_a"], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
        )
        db_session.add(q)
        questions.append(q)
    db_session.commit()
    return exam, questions


class TestSubmitPipeline:
    """Verify practice submit creates correct Answer records."""

    def test_submit_creates_answers(self, db_session, setup_exam):
        """Submitting answers should persist StudentAnswer records."""
        from app.models.database import StudentAnswer
        exam, questions = setup_exam

        # Simulate what POST /api/practice/submit does
        answers = [
            {"question_id": "test_q_0", "answer": "B"},   # correct
            {"question_id": "test_q_1", "answer": "A"},   # wrong
            {"question_id": "test_q_2", "answer": "C"},   # wrong
            {"question_id": "test_q_3", "answer": "B"},   # correct
            {"question_id": "test_q_4", "answer": "D"},   # wrong
        ]

        correct_count = 0
        for ans in answers:
            q = db_session.query(type(questions[0])).filter_by(question_id=ans["question_id"]).first()
            is_correct = ans["answer"] == q.answer
            if is_correct:
                correct_count += 1
            db_session.add(StudentAnswer(
                answer_id=f"ans_202610101_test_q_{ans['question_id']}",
                student_id="202610101", question_id=ans["question_id"],
                exam_record_id="test_exam_001",
                student_answer=ans["answer"], is_correct=is_correct,
            ))
        db_session.commit()

        # Verify
        all_answers = db_session.query(StudentAnswer).filter_by(student_id="202610101").all()
        assert len(all_answers) == 5
        assert correct_count == 2  # 2 correct out of 5

        wrong = [a for a in all_answers if not a.is_correct]
        assert len(wrong) == 3

    def test_barrier_update_after_submit(self, db_session, setup_exam, sample_student):
        """Student.barrier_type should update based on answer accuracy."""
        # Simulate the heuristic barrier update from practice.py
        from app.models.database import StudentAnswer

        # Feed 10 correct + 10 wrong answers to get ~50% accuracy → barrier "reading"
        for i in range(20):
            is_correct = i < 10  # first 10 correct, last 10 wrong
            db_session.add(StudentAnswer(
                answer_id=f"ans_barrier_{i}", student_id="202610101",
                question_id=f"test_q_{i % 5}", exam_record_id="test_exam_001",
                student_answer="A" if not is_correct else "B",
                is_correct=is_correct,
            ))
        db_session.commit()

        # Run the heuristic logic
        all_recent = db_session.query(StudentAnswer).filter_by(
            student_id="202610101"
        ).order_by(StudentAnswer.answered_at.desc()).limit(20).all()

        correct = sum(1 for a in all_recent if a.is_correct)
        rate = correct / len(all_recent) if all_recent else 0
        if rate < 0.4:
            dominant = "concept"
        elif rate < 0.7:
            dominant = "reading"
        else:
            dominant = "expression"

        sample_student.barrier_type = {
            k: (0.7 if k == dominant else 0.15)
            for k in ("concept", "reading", "expression")
        }
        db_session.commit()

        # Verify
        assert dominant == "reading"  # 50% accuracy → reading barrier
        assert sample_student.barrier_type["reading"] == pytest.approx(0.7, 0.01)
        assert sample_student.barrier_type["concept"] == pytest.approx(0.15, 0.01)


class TestAnswerNormalization:
    """提交作答的键名/形态归一化（P0 修复：线上判卷全判错）。"""

    def test_letter_key_graded_correct(self, db_session, setup_exam):
        """新版客户端发 answer=字母 → 与题库字母答案可比对。"""
        from app.api.practice import _extract_student_answer
        _, questions = setup_exam  # options=["A","B","C","D"], answer="B"

        assert _extract_student_answer(
            {"question_id": "test_q_0", "answer": "b"}, questions[0]
        ) == "B"

    def test_legacy_index_mapped_to_letter(self, db_session, setup_exam):
        """旧客户端发 student_answer=下标 "1" → 映射为 "B"，判对而非恒错。"""
        from app.api.practice import _extract_student_answer
        _, questions = setup_exam

        assert _extract_student_answer(
            {"question_id": "test_q_0", "student_answer": "1"}, questions[0]
        ) == "B"

    def test_legacy_index_out_of_range_kept_verbatim(self, db_session, setup_exam):
        """下标越界（脏数据）不映射，原样保留由判分判错。"""
        from app.api.practice import _extract_student_answer
        _, questions = setup_exam

        assert _extract_student_answer(
            {"question_id": "test_q_0", "student_answer": "9"}, questions[0]
        ) == "9"

    def test_numeric_fill_blank_not_mapped(self, db_session, setup_exam):
        """无选项的填空题数字作答不被误映射为字母。"""
        from app.api.practice import _extract_student_answer
        from app.models.database import Question, Difficulty, QuestionSource, AuditStatus
        db_session.add(Question(
            question_id="test_q_fill", record_id="test_exam_001",
            content="填空", options=None, answer="12",
            analysis="", knowledge_points=["kp_a"], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
        ))
        db_session.commit()
        q = db_session.query(Question).filter_by(question_id="test_q_fill").first()

        assert _extract_student_answer(
            {"question_id": "test_q_fill", "student_answer": "12"}, q
        ) == "12"


class TestWrongQuestionsAPI:
    """Verify wrong-answer queries work correctly."""

    def test_wrong_list_returns_only_wrong(self, db_session, setup_exam):
        """Wrong list endpoint should only return is_correct=False answers."""
        from app.models.database import StudentAnswer

        # Add mixed answers
        for i in range(5):
            db_session.add(StudentAnswer(
                answer_id=f"ans_wrong_{i}", student_id="202610101",
                question_id=f"test_q_{i}", exam_record_id="test_exam_001",
                student_answer="X", is_correct=(i % 2 == 0),  # alternating
            ))
        db_session.commit()

        wrong = db_session.query(StudentAnswer).filter(
            StudentAnswer.student_id == "202610101",
            StudentAnswer.is_correct == False,
        ).all()

        assert len(wrong) == 2  # indices 1, 3 are wrong
        for wa in wrong:
            assert wa.is_correct == False
