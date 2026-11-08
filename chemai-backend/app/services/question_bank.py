"""AI 生成题库（QuestionSet）管理服务。

题库持久化的唯一入口：统一 create / list / get / add（按内容去重）/ delete（is_system 守卫），
并在保存时同步向量索引与历史真题库，保证保存后的题目可被搜索命中（spec: question-bank）。

与 ExamBankService（历史真题库，内存 JSON）是并列的两个服务；本服务保存时以依赖方式同步历史真题库。
"""
from datetime import datetime
from typing import List, Dict, Optional

from sqlalchemy import Text
from sqlalchemy.orm import Session

from app.models.database import (
    QuestionSet, QuestionSetItem, Question,
    Difficulty, QuestionSource, AuditStatus,
)


def _map_difficulty(value) -> Difficulty:
    """把 "easy"/"medium"/"hard" 或 Difficulty 枚举映射为标准枚举，未知一律 MEDIUM。"""
    return Difficulty.coerce(value)


class QuestionBankService:
    """题库（QuestionSet）深模块：持久化 + 检索的统一入口。"""

    def create_set(
        self,
        db: Session,
        name: str,
        teacher_id: Optional[str] = None,
        region: Optional[str] = None,
        year: Optional[int] = None,
        source: Optional[str] = None,
        description: Optional[str] = None,
        is_system: bool = False,
    ) -> Dict:
        """创建题库，返回含 set_id 的字典。"""
        set_id = f"qset_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        question_set = QuestionSet(
            set_id=set_id, name=name, teacher_id=teacher_id,
            region=region, year=year, source=source,
            description=description, question_count=0, is_system=is_system,
        )
        db.add(question_set)
        db.commit()
        return {
            "success": True, "set_id": set_id, "name": name,
            "question_count": 0, "is_system": is_system,
            "created_at": question_set.created_at.isoformat() if question_set.created_at else "",
        }

    def list_sets(
        self,
        db: Session,
        teacher_id: Optional[str] = None,
        region: Optional[str] = None,
        year: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict:
        """列出题库，支持按教师/地区/年份筛选 + 分页。返回 {"total", "page", "exam_sets"}。"""
        query = db.query(QuestionSet)
        if teacher_id:
            query = query.filter(QuestionSet.teacher_id == teacher_id)
        if region:
            query = query.filter(QuestionSet.region == region)
        if year:
            query = query.filter(QuestionSet.year == year)
        query = query.order_by(QuestionSet.is_system.asc(), QuestionSet.created_at.desc())

        total = query.count()
        sets = query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "total": total, "page": page, "page_size": page_size,
            "exam_sets": [
                {
                    "set_id": s.set_id, "name": s.name, "region": s.region,
                    "year": s.year, "source": s.source, "description": s.description,
                    "question_count": s.question_count, "is_system": s.is_system,
                    "created_at": s.created_at.isoformat() if s.created_at else "",
                }
                for s in sets
            ],
        }

    def get_set(self, db: Session, set_id: str) -> Optional[Dict]:
        """获取题库详情（含题目），不存在返回 None。"""
        question_set = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
        if not question_set:
            return None

        items = db.query(QuestionSetItem).filter(
            QuestionSetItem.set_id == set_id
        ).order_by(QuestionSetItem.sort_order).all()

        questions = []
        for item in items:
            question = db.query(Question).filter(Question.question_id == item.question_id).first()
            if question:
                questions.append({
                    "question_id": question.question_id,
                    "content": question.content,
                    "options": question.options,
                    "answer": question.answer,
                    "analysis": question.analysis,
                    "knowledge_points": question.knowledge_points,
                    "difficulty": question.difficulty.value if question.difficulty else "medium",
                    "sort_order": item.sort_order,
                })

        return {
            "set_id": question_set.set_id,
            "name": question_set.name,
            "region": question_set.region,
            "year": question_set.year,
            "source": question_set.source,
            "description": question_set.description,
            "question_count": len(questions),
            "is_system": question_set.is_system,
            "questions": questions,
            "created_at": question_set.created_at.isoformat() if question_set.created_at else "",
        }

    def add_questions(
        self,
        db: Session,
        set_id: str,
        questions: List[Dict],
        set_name: Optional[str] = None,
        description: Optional[str] = None,
        knowledge_points: Optional[str] = None,
    ) -> Dict:
        """把题目加入题库。

        行为契约（spec: question-bank）：
        - 按题目正文去重，内容相同的题目复用已有记录，不重复插入；
        - 保存后同步向量索引与历史真题库，使题目可被搜索命中。
        """
        question_set = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
        if not question_set:
            return {"success": False, "reason": "not_found", "count": 0}

        current_max_order = db.query(QuestionSetItem).filter(
            QuestionSetItem.set_id == set_id
        ).count()

        imported_count = 0
        inserted = []  # (question_id, q) 实际插入/关联的题目，用于同步索引
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        for i, q in enumerate(questions):
            content = q.get("content", "")
            if not content:
                continue

            # 去重：同一题库内已关联相同正文的题目，跳过（不重复插入、不重复关联）
            dup = (
                db.query(QuestionSetItem)
                .join(Question, Question.question_id == QuestionSetItem.question_id)
                .filter(QuestionSetItem.set_id == set_id, Question.content == content)
                .first()
            )
            if dup:
                continue

            existing = db.query(Question).filter(Question.content == content).first()
            if existing:
                question_id = existing.question_id
            else:
                question_id = f"q_{ts}_{i}"
                new_question = Question(
                    question_id=question_id,
                    record_id=None,
                    content=content,
                    options=q.get("options"),
                    answer=str(q.get("answer", "")),
                    analysis=q.get("explanation") or q.get("analysis"),
                    knowledge_points=q.get("knowledge_points", []),
                    difficulty=_map_difficulty(q.get("difficulty")),
                    source=QuestionSource.MANUAL_SELECTED,
                    source_exam=question_set.name,
                    audit_status=AuditStatus.PASSED,
                )
                db.add(new_question)

            current_max_order += 1
            set_item = QuestionSetItem(
                item_id=f"qsi_{ts}_{i}",
                set_id=set_id,
                question_id=question_id,
                sort_order=current_max_order,
            )
            db.add(set_item)
            inserted.append((question_id, q))
            imported_count += 1

        question_set.question_count = db.query(QuestionSetItem).filter(
            QuestionSetItem.set_id == set_id
        ).count()
        question_set.updated_at = datetime.utcnow()
        db.commit()

        self._sync_search_indexes(db, set_name or question_set.name, inserted)

        return {
            "success": True,
            "set_id": set_id,
            "set_name": set_name or question_set.name,
            "count": imported_count,
        }

    def delete_set(self, db: Session, set_id: str) -> Dict:
        """删除题库（is_system 守卫），同时清除题目关联。"""
        question_set = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
        if not question_set:
            return {"success": False, "reason": "not_found"}

        if question_set.is_system:
            return {"success": False, "reason": "is_system", "is_system": True}

        name = question_set.name
        count = question_set.question_count or 0

        db.query(QuestionSetItem).filter(QuestionSetItem.set_id == set_id).delete()
        db.delete(question_set)
        db.commit()

        return {
            "success": True, "set_id": set_id, "name": name, "question_count": count,
        }

    def search_ai_generated(
        self,
        db: Session,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """检索 AI 生成题库中已保存的题目（含不带 keyword 的全量）。

        只返回属于某个题库（QuestionSet）的题目；keyword 为空时返回全部，供搜索入口联合历史真题。
        """
        query = (
            db.query(Question)
            .join(QuestionSetItem, QuestionSetItem.question_id == Question.question_id)
            .distinct()
        )
        if keyword:
            kw = keyword.strip().lower()
            query = query.filter(
                Question.content.like(f"%{kw}%")
                | Question.knowledge_points.cast(Text).ilike(f"%{kw}%")
            )
        query = query.order_by(Question.created_at.desc()).limit(limit)

        return [
            {
                "question_id": q.question_id,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "analysis": q.analysis,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty if q.difficulty is not None else 3,
                "source": q.source.value if q.source else "ai_generated",
            }
            for q in query.all()
        ]

    # ── 内部：保存后的搜索索引同步（向量 + 历史真题库）────────────

    def _sync_search_indexes(self, db: Session, set_name: str, inserted: List[tuple]):
        """把本次实际插入的题目同步到 Chroma 向量索引与历史真题库内存列表。

        幂等且容错：任一同步失败只打日志，不回滚已提交的题库写入。
        只同步实际插入的题目（去重跳过的不会再同步）；exam_id 复用数据库 question_id，
        使历史真题库按 exam_id 覆盖更新，重复保存不产生重复条目。
        """
        try:
            from app.services.exam_bank import exam_bank_service
            from app.services.vector_search import vector_search_service
            from app.models.historical_exam import HistoricalQuestion

            for i, (question_id, q) in enumerate(inserted, 1):
                content = q.get("content", "")
                if not content:
                    continue
                hq = HistoricalQuestion(
                    exam_id=question_id,
                    source="AI生成", year=datetime.now().year, region="AI生成",
                    paper_name=set_name, question_number=str(i),
                    original_number=str(i),
                    question_type=q.get("type", "single_choice"),
                    content=content, options=q.get("options"),
                    answer=str(q.get("answer", "")),
                    analysis=q.get("explanation") or q.get("analysis", ""),
                    knowledge_points=q.get("knowledge_points", []),
                    difficulty=q.get("difficulty", "medium"),
                    discrimination=0.5, score=0, chapter="", page_image=None,
                )
                exam_bank_service.add_question(hq)

            idx_data = [{
                "exam_id": question_id,
                "content": q.get("content", ""),
                "knowledge_points": q.get("knowledge_points", []),
                "difficulty": q.get("difficulty", "medium"),
                "source": "AI生成", "year": datetime.now().year, "region": "AI生成",
            } for question_id, q in inserted if q.get("content")]
            if idx_data:
                vector_search_service.index_questions(idx_data, mode="append")
        except Exception as e:
            print(f"[QuestionBank] 索引同步跳过: {e}")


# 全局题库服务实例
question_bank_service = QuestionBankService()
