"""班级学情「知识点薄弱」的确定性回归（2026-09-14）。

缺陷：面板（`/api/panel/class/{id}` 与其知识点下钻）读的是
`exam.question_stats["knowledge_point_stats"]` —— 这个聚合键**全库 0 条**有，
造数脚本不产、判卷流程也只落逐题统计，于是「知识点薄弱」永远空白。

修法：改为按「逐题统计 × 题目知识点」现算（`_kp_error_rates`），真实判卷数据同样适用。
这里用内存库钉住两件事：**不依赖 knowledge_point_stats 这个键**、**聚合口径正确**。
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import (
    Base, Class, ExamRecord, Grade, Question, RecordType, School,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(School(school_id="sch1", name="测试中学"))
    s.add(Grade(grade_id="g1", school_id="sch1", name="高三", year=2024))
    s.add(Class(class_id="c1", name="2419班", grade="高三", grade_id="g1", subject="化学"))
    # 两道题：一道考「有机化合物」，一道考「物质的量」
    s.add(Question(question_id="q1", content="题一", answer="A",
                   knowledge_points=["有机化合物"], record_id="e1"))
    s.add(Question(question_id="q2", content="题二", answer="B",
                   knowledge_points=["物质的量"], record_id="e1"))
    # ⚠️ question_stats 里**只有逐题键**，没有 knowledge_point_stats（复现线上形态）
    s.add(ExamRecord(
        record_id="e1", class_id="c1", name="期中", type=RecordType.EXAM,
        question_stats={"q1": {"total": 10, "correct": 3, "wrong": 7},
                        "q2": {"total": 10, "correct": 9, "wrong": 1}},
    ))
    s.commit()
    return s


def test_aggregates_error_rate_from_per_question_stats(db):
    """错误率按知识点聚合：q1 错 7/10 → 有机化合物 0.7；q2 错 1/10 → 物质的量 0.1。"""
    from app.api.panel import _kp_error_rates
    exams = db.query(ExamRecord).all()
    rates = _kp_error_rates(db, exams)

    assert set(rates) == {"有机化合物", "物质的量"}, rates
    assert rates["有机化合物"] == [0.7]
    assert rates["物质的量"] == [0.1]


def test_does_not_depend_on_missing_aggregate_key(db):
    """关键回归：数据里**没有** knowledge_point_stats 也要算得出来。

    改坏前的实现读的就是那个不存在的键 → 返回空 dict → UI 永远空白。
    """
    from app.api.panel import _kp_error_rates
    exams = db.query(ExamRecord).all()
    for e in exams:
        assert "knowledge_point_stats" not in (e.question_stats or {}), \
            "本 fixture 刻意不含该键（线上真实形态）"
    assert _kp_error_rates(db, exams), "没有 knowledge_point_stats 也必须能聚合出知识点"


def test_knowledge_points_as_json_string_is_parsed(db):
    """knowledge_points 存成 JSON 字符串时也要能解析（原生 SQL 回填的形态）。"""
    from app.api.panel import _kp_error_rates
    q = db.query(Question).filter(Question.question_id == "q1").first()
    q.knowledge_points = json.dumps(["有机化合物", "化学计算"])
    db.commit()
    rates = _kp_error_rates(db, db.query(ExamRecord).all())
    assert "化学计算" in rates and "有机化合物" in rates


def test_ignores_rows_without_total(db):
    """没有 total 的统计行跳过（不产生除零 / 假 0 分）。"""
    from app.api.panel import _kp_error_rates
    e = db.query(ExamRecord).first()
    e.question_stats = {"q1": {"total": 0, "correct": 0, "wrong": 0},
                        "q2": {"total": 4, "correct": 1}}
    db.commit()
    rates = _kp_error_rates(db, [e])
    assert rates == {"物质的量": [0.75]}, rates   # wrong 缺省时按 total-correct 算
