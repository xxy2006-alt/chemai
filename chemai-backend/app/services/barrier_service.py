"""
障碍归因服务

Barrier Type（概念/审题/表述）的唯一归因口径：
- 每道题通过 questions.probe_dimension 声明考察维度
- 学生答错时作答行落 barrier_type = 该题维度
- 学生 barrier_type = 错题按维度的分布（可由作答记录重放复现）

任何写入/重算 barrier 的代码都必须经由本模块，禁止用正确率阈值推断障碍类型。
"""
from sqlalchemy import func

from app.models.database import Student, Question, StudentAnswer

DIMENSIONS = ("concept", "reading", "expression")


def aggregate_barrier_from_answers(db, student_id: str) -> dict:
    """按考察维度聚合该生错题 → 障碍分布 dict（三条维度归一后求和为 1）"""
    dim_rows = (
        db.query(Question.probe_dimension, func.count(StudentAnswer.answer_id))
        .join(Question, Question.question_id == StudentAnswer.question_id)
        .filter(
            StudentAnswer.student_id == student_id,
            StudentAnswer.is_correct.is_(False),
            Question.probe_dimension.isnot(None),
        )
        .group_by(Question.probe_dimension)
        .all()
    )
    counts = {dim: 0 for dim in DIMENSIONS}
    total_wrong = 0
    for dim, cnt in dim_rows:
        if dim in counts:
            counts[dim] += cnt
            total_wrong += cnt
    if total_wrong > 0:
        return {dim: round(counts[dim] / total_wrong, 3) for dim in DIMENSIONS}
    return {"concept": 0.34, "reading": 0.33, "expression": 0.33}


def recompute_student_barrier(db, student: Student) -> dict:
    """重算并写回学生 barrier_type（幂等，只依赖作答记录）"""
    distribution = aggregate_barrier_from_answers(db, student.student_id)
    student.barrier_type = distribution
    from datetime import datetime
    student.barrier_last_updated = datetime.utcnow()
    return distribution


def recompute_class_barriers(db, class_id: str) -> int:
    """重算一个班全部学生的 barrier_type（数据导入/诊断回放用）"""
    students = db.query(Student).filter(Student.class_id == class_id).all()
    for s in students:
        recompute_student_barrier(db, s)
    db.commit()
    return len(students)
