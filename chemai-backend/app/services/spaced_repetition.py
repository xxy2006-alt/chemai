"""
间隔重复复习引擎
基于艾宾浩斯遗忘曲线的智能复习安排
"""

from datetime import datetime
from typing import List, Optional
from app.models.database import (
    Question, StudentAnswer, get_db
)
from app.models.review_task import ReviewTask, calculate_next_review_date


class SpacedRepetitionEngine:
    """间隔重复复习引擎"""

    def __init__(self):
        pass

    def create_review_task(self, student_id: str, question_id: str) -> ReviewTask:
        """为学生创建复习任务"""
        db_gen = get_db()
        db = next(db_gen)

        try:
            # 检查是否已有该题目的复习任务
            existing = db.query(ReviewTask).filter(
                ReviewTask.student_id == student_id,
                ReviewTask.question_id == question_id
            ).first()

            if existing:
                return existing

            # 创建新的复习任务
            task_id = f"review_{student_id}_{question_id}_{int(datetime.utcnow().timestamp())}"
            task = ReviewTask(
                task_id=task_id,
                student_id=student_id,
                question_id=question_id,
                review_level=0,
                status="pending",
                first_review_at=datetime.utcnow(),
                next_review_at=datetime.utcnow(),  # 立即可复习
                consecutive_correct=0,
                consecutive_errors=0,
                review_history=[]
            )

            db.add(task)
            db.commit()
            return task
        finally:
            db.close()

    def get_due_review_tasks(self, student_id: str) -> List[ReviewTask]:
        """获取学生到期应复习的任务"""
        db_gen = get_db()
        db = next(db_gen)

        try:
            now = datetime.utcnow()
            tasks = db.query(ReviewTask).filter(
                ReviewTask.student_id == student_id,
                ReviewTask.status.in_(["pending", "overdue"]),
                ReviewTask.next_review_at <= now
            ).all()

            return tasks
        finally:
            db.close()

    def get_review_task_by_id(self, task_id: str) -> Optional[ReviewTask]:
        """获取指定复习任务"""
        db_gen = get_db()
        db = next(db_gen)

        try:
            return db.query(ReviewTask).filter(ReviewTask.task_id == task_id).first()
        finally:
            db.close()

    def complete_review(self, task_id: str, is_correct: bool) -> ReviewTask:
        """
        完成复习，更新任务状态
        返回更新后的任务
        """
        db_gen = get_db()
        db = next(db_gen)

        try:
            task = db.query(ReviewTask).filter(ReviewTask.task_id == task_id).first()
            if not task:
                return None

            # 更新历史（复制新列表再赋值，普通 JSON 列不跟踪原地 append）
            history = list(task.review_history or [])
            history.append({
                "reviewed_at": datetime.utcnow().isoformat(),
                "is_correct": is_correct,
                "level_before": task.review_level
            })

            if is_correct:
                task.consecutive_correct += 1
                task.consecutive_errors = 0

                # 答对了，升级复习级别
                if task.consecutive_correct >= 2:  # 连续答对2次才升级
                    if task.review_level < 5:
                        task.review_level += 1
                    task.consecutive_correct = 0
            else:
                task.consecutive_errors += 1
                task.consecutive_correct = 0

                # 答错了，降级复习级别
                if task.review_level > 0:
                    task.review_level -= 1
                task.consecutive_errors = 0

            # 计算下次复习时间
            task.next_review_at = calculate_next_review_date(task.review_level)
            task.completed_at = datetime.utcnow()
            task.review_history = history

            # 如果没有更多复习次数（已掌握），标记为done
            if task.next_review_at is None:
                task.status = "done"
            else:
                task.status = "pending"

            db.commit()
            return task
        finally:
            db.close()

    def generate_review_for_student(self, student_id: str, limit: int = 10) -> List[dict]:
        """
        为学生生成复习任务列表
        返回包含题目详情的复习任务
        """
        tasks = self.get_due_review_tasks(student_id)

        if not tasks:
            return []

        db_gen = get_db()
        db = next(db_gen)
        try:
            result = []
            for task in tasks[:limit]:
                question = db.query(Question).filter(Question.question_id == task.question_id).first()
                if question:
                    result.append({
                        "task_id": task.task_id,
                        "question_id": question.question_id,
                        "content": question.content,
                        "options": question.options,
                        "answer": question.answer,
                        "analysis": question.analysis,
                        "knowledge_points": question.knowledge_points,
                        "difficulty": question.difficulty if question.difficulty is not None else 3,
                        "review_level": task.review_level,
                        "next_review_at": task.next_review_at.isoformat() if task.next_review_at else None,
                        "consecutive_correct": task.consecutive_correct,
                        "consecutive_errors": task.consecutive_errors
                    })

            return result
        finally:
            db.close()

    def sync_review_tasks_from_wrong_answers(self, student_id: str):
        """
        从学生的错题历史同步复习任务
        当学生答题错误时，自动创建复习任务
        """
        db_gen = get_db()
        db = next(db_gen)

        try:
            # 获取学生最近的错题
            wrong_answers = db.query(StudentAnswer).filter(
                StudentAnswer.student_id == student_id,
                StudentAnswer.is_correct.is_(False)
            ).order_by(StudentAnswer.answered_at.desc()).limit(50).all()

            for answer in wrong_answers:
                # 检查是否已有复习任务
                existing = db.query(ReviewTask).filter(
                    ReviewTask.student_id == student_id,
                    ReviewTask.question_id == answer.question_id
                ).first()

                if not existing:
                    self.create_review_task(student_id, answer.question_id)

        finally:
            db.close()


# 全局实例
sre = SpacedRepetitionEngine()


def create_review_task(student_id: str, question_id: str) -> ReviewTask:
    return sre.create_review_task(student_id, question_id)


def get_due_review_tasks(student_id: str) -> List[ReviewTask]:
    return sre.get_due_review_tasks(student_id)


def complete_review(task_id: str, is_correct: bool) -> ReviewTask:
    return sre.complete_review(task_id, is_correct)


def generate_review_for_student(student_id: str, limit: int = 10) -> List[dict]:
    return sre.generate_review_for_student(student_id, limit)
