"""
数据可视化服务
P2-2: 提供班级学情热力图、学生排名、障碍分布等数据分析
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models.database import (
    Student, Class, ExamRecord, Question, StudentAnswer,
    TeacherClassSubject
)


class DataVisualizationService:
    """数据可视化服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_class_overview(self, class_id: str) -> Dict[str, Any]:
        """获取班级概览数据"""
        class_obj = self.db.query(Class).filter(Class.class_id == class_id).first()
        if not class_obj:
            return {}

        # 获取学生数量
        student_count = self.db.query(Student).filter(
            Student.class_id == class_id
        ).count()

        # 获取练习记录统计
        exam_records = self.db.query(ExamRecord).filter(
            ExamRecord.class_id == class_id
        ).all()

        total_practice = len([e for e in exam_records if e.type == "practice"])
        total_exams = len([e for e in exam_records if e.type == "exam"])

        # 计算平均分
        avg_scores = [e.avg_score for e in exam_records if e.avg_score is not None]
        overall_avg = sum(avg_scores) / len(avg_scores) if avg_scores else 0

        return {
            "class_id": class_id,
            "class_name": class_obj.name,
            "student_count": student_count,
            "total_practice": total_practice,
            "total_exams": total_exams,
            "overall_avg_score": round(overall_avg, 1),
            "grade": class_obj.grade
        }

    def get_student_ranking(
        self,
        class_id: str,
        metric: str = "avg_score",
        limit: int = 10,
        order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        获取学生排名
        metric: avg_score / completion_rate / error_rate / consecutive_days
        """
        students = self.db.query(Student).filter(
            Student.class_id == class_id
        ).all()

        rankings = []
        for student in students:
            # 计算平均成绩
            answers = self.db.query(StudentAnswer).filter(
                StudentAnswer.student_id == student.student_id
            ).all()

            if not answers:
                continue

            total = len(answers)
            correct = sum(1 for a in answers if a.is_correct)
            avg_score = (correct / total * 100) if total > 0 else 0
            completion_rate = min(100, student.exercises_completed * 10)  # 估算

            # 连续学习天数(估算)
            consecutive_days = 0
            if student.last_exercise_at:
                days_ago = (datetime.now() - student.last_exercise_at).days
                consecutive_days = max(0, 7 - days_ago)  # 简化估算

            rankings.append({
                "student_id": student.student_id,
                "student_name": student.name,
                "avg_score": round(avg_score, 1),
                "completion_rate": min(100, completion_rate),
                "error_rate": round(100 - avg_score, 1),
                "consecutive_days": consecutive_days,
                "exercises_completed": student.exercises_completed
            })

        # 排序
        if order == "desc":
            rankings.sort(key=lambda x: x.get(metric, 0), reverse=True)
        else:
            rankings.sort(key=lambda x: x.get(metric, 0))

        return rankings[:limit]

    def get_top_bottom_students(
        self,
        class_id: str,
        limit: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """获取TOP和BOTTOM学生"""
        all_rankings = self.get_student_ranking(class_id, metric="avg_score", limit=1000)

        return {
            "top": all_rankings[:limit],
            "bottom": all_rankings[-limit:] if len(all_rankings) >= limit else all_rankings
        }

    def get_barrier_distribution(self, class_id: str) -> Dict[str, Any]:
        """获取班级障碍类型分布"""
        students = self.db.query(Student).filter(
            Student.class_id == class_id
        ).all()

        barrier_stats = {
            "concept": 0,
            "reading": 0,
            "expression": 0
        }

        total_students = len(students)
        if total_students == 0:
            return {"distribution": barrier_stats, "total": 0}

        for student in students:
            barrier = student.barrier_type or {}
            barrier_stats["concept"] += barrier.get("concept", 0)
            barrier_stats["reading"] += barrier.get("reading", 0)
            barrier_stats["expression"] += barrier.get("expression", 0)

        # 转换为百分比
        for k in barrier_stats:
            barrier_stats[k] = round(barrier_stats[k] / total_students * 100, 1)

        return {
            "distribution": barrier_stats,
            "total": total_students,
            "labels": ["概念理解型", "审题障碍型", "表述障碍型"]
        }

    def get_knowledge_heatmap(self, class_id: str) -> List[Dict[str, Any]]:
        """获取知识点掌握热力图数据"""
        students = self.db.query(Student).filter(
            Student.class_id == class_id
        ).all()

        # 收集所有知识点
        knowledge_stats = {}

        for student in students:
            answers = self.db.query(StudentAnswer).filter(
                StudentAnswer.student_id == student.student_id
            ).join(Question).all()

            for answer in answers:
                kps = answer.question.knowledge_points or []
                for kp in kps:
                    if kp not in knowledge_stats:
                        knowledge_stats[kp] = {"total": 0, "correct": 0}
                    knowledge_stats[kp]["total"] += 1
                    if answer.is_correct:
                        knowledge_stats[kp]["correct"] += 1

        # 转换为热力图数据
        heatmap = []
        for kp, stats in knowledge_stats.items():
            error_rate = 0
            if stats["total"] > 0:
                error_rate = round((1 - stats["correct"] / stats["total"]) * 100, 1)
            heatmap.append({
                "knowledge_point": kp,
                "error_rate": error_rate,
                "total_questions": stats["total"],
                "level": "high" if error_rate > 50 else "medium" if error_rate > 30 else "low"
            })

        # 按错误率排序
        heatmap.sort(key=lambda x: x["error_rate"], reverse=True)

        return heatmap

    def get_score_distribution(self, class_id: str) -> Dict[str, Any]:
        """获取成绩分布直方图数据"""
        students = self.db.query(Student).filter(
            Student.class_id == class_id
        ).all()

        # 分段统计
        ranges = [
            (0, 60, "不及格"),
            (60, 70, "及格"),
            (70, 80, "中等"),
            (80, 90, "良好"),
            (90, 100, "优秀")
        ]

        distribution = {label: 0 for _, _, label in ranges}

        for student in students:
            answers = self.db.query(StudentAnswer).filter(
                StudentAnswer.student_id == student.student_id
            ).all()

            if not answers:
                continue

            correct = sum(1 for a in answers if a.is_correct)
            avg_score = (correct / len(answers) * 100) if answers else 0

            for low, high, label in ranges:
                if low <= avg_score < high:
                    distribution[label] += 1
                    break

        return {
            "distribution": distribution,
            "labels": list(distribution.keys()),
            "values": list(distribution.values())
        }

    def get_practice_trend(
        self,
        class_id: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """获取练习完成趋势"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        trend = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            # 统计当日练习数量
            day_answers = self.db.query(StudentAnswer).filter(
                StudentAnswer.answered_at >= date,
                StudentAnswer.answered_at < date + timedelta(days=1)
            ).all()

            student_ids = set(a.student_id for a in day_answers if a.student_id)
            practice_count = len(day_answers)
            completion_rate = len(student_ids) / 10 * 100  # 简化估算

            trend.append({
                "date": date_str,
                "day_name": date.strftime("%m/%d"),
                "practice_count": practice_count,
                "completion_rate": min(100, completion_rate)
            })

        return trend

    def get_teacher_workload(self, teacher_id: str) -> Dict[str, Any]:
        """获取教师工作量统计"""
        # 获取教师关联的班级
        teacher_classes = self.db.query(TeacherClassSubject).filter(
            TeacherClassSubject.teacher_id == teacher_id
        ).all()

        class_ids = [tc.class_id for tc in teacher_classes]

        # 统计出题数
        questions_created = self.db.query(Question).join(ExamRecord).filter(
            ExamRecord.class_id.in_(class_ids)
        ).count() if class_ids else 0

        # 统计批改数(作答记录数)
        if class_ids:
            students = self.db.query(Student).filter(
                Student.class_id.in_(class_ids)
            ).all()
            student_ids = [s.student_id for s in students]
            corrections = self.db.query(StudentAnswer).filter(
                StudentAnswer.student_id.in_(student_ids)
            ).count() if student_ids else 0
        else:
            corrections = 0

        # 统计预警处理数(按学生所属班级查询)
        from app.models.warning_log import WarningLog
        warnings_processed = self.db.query(WarningLog).filter(
            WarningLog.student_id.in_(student_ids),
            WarningLog.status == "processed"
        ).count() if student_ids else 0

        # 统计布置练习数
        exams_arranged = self.db.query(ExamRecord).filter(
            ExamRecord.class_id.in_(class_ids)
        ).count() if class_ids else 0

        return {
            "questions_created": questions_created,
            "corrections": corrections,
            "warnings_processed": warnings_processed,
            "exams_arranged": exams_arranged
        }

    def get_student_personal_stats(self, student_id: str) -> Dict[str, Any]:
        """获取学生个人统计数据"""
        student = self.db.query(Student).filter(
            Student.student_id == student_id
        ).first()

        if not student:
            return {}

        # 获取作答记录
        answers = self.db.query(StudentAnswer).filter(
            StudentAnswer.student_id == student_id
        ).all()

        total = len(answers)
        correct = sum(1 for a in answers if a.is_correct)
        accuracy = (correct / total * 100) if total > 0 else 0

        # 按障碍类型统计
        barrier_correct = {"concept": 0, "reading": 0, "expression": 0}
        barrier_total = {"concept": 0, "reading": 0, "expression": 0}

        for answer in answers:
            bt = answer.barrier_type.value if answer.barrier_type else None
            if bt in barrier_correct:
                barrier_total[bt] += 1
                if answer.is_correct:
                    barrier_correct[bt] += 1

        # 知识点掌握情况
        knowledge_stats = {}
        for answer in answers:
            kps = answer.question.knowledge_points or []
            for kp in kps:
                if kp not in knowledge_stats:
                    knowledge_stats[kp] = {"total": 0, "correct": 0}
                knowledge_stats[kp]["total"] += 1
                if answer.is_correct:
                    knowledge_stats[kp]["correct"] += 1

        knowledge_mastery = []
        for kp, stats in knowledge_stats.items():
            mastery = round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
            knowledge_mastery.append({
                "knowledge_point": kp,
                "mastery_rate": mastery,
                "questions_count": stats["total"]
            })

        # 排序(按掌握率)
        knowledge_mastery.sort(key=lambda x: x["mastery_rate"])

        return {
            "student_id": student_id,
            "student_name": student.name,
            "total_exercises": student.exercises_completed,
            "total_answers": total,
            "accuracy": round(accuracy, 1),
            "consecutive_days": self._calculate_consecutive_days(student),
            "barrier_breakdown": {
                bt: round((barrier_correct[bt] / barrier_total[bt] * 100) if barrier_total[bt] > 0 else 0, 1)
                for bt in barrier_correct
            },
            "knowledge_mastery": knowledge_mastery[-10:]  # 掌握最差的10个知识点
        }

    def _calculate_consecutive_days(self, student: Student) -> int:
        """计算连续学习天数"""
        if not student.last_exercise_at:
            return 0
        days_ago = (datetime.now() - student.last_exercise_at).days
        # 简化: 假设学生每天完成至少1次练习
        return max(0, min(30, 7 - days_ago))  # 最多30天

    def get_class_comparison(
        self,
        teacher_id: str,
        metric: str = "avg_score"
    ) -> List[Dict[str, Any]]:
        """获取教师所辖班级对比"""
        teacher_classes = self.db.query(TeacherClassSubject).filter(
            TeacherClassSubject.teacher_id == teacher_id
        ).all()

        comparison = []
        for tc in teacher_classes:
            class_id = tc.class_id
            class_overview = self.get_class_overview(class_id)
            rankings = self.get_student_ranking(class_id, metric="avg_score", limit=100)

            if rankings:
                avg_score = sum(s["avg_score"] for s in rankings) / len(rankings)
            else:
                avg_score = 0

            comparison.append({
                "class_id": class_id,
                "class_name": class_overview.get("class_name", ""),
                "student_count": class_overview.get("student_count", 0),
                "avg_score": round(avg_score, 1),
                "metric_value": round(avg_score, 1)
            })

        # 按指标值排序
        comparison.sort(key=lambda x: x.get(metric, 0), reverse=True)

        return comparison


# 全局服务实例
_data_viz_service = None

def get_data_visualization_service(db: Session = None):
    """获取数据可视化服务实例"""
    global _data_viz_service
    if db:
        return DataVisualizationService(db)
    from app.models.database import get_db as _get_db
    session = next(_get_db())
    return DataVisualizationService(session)
