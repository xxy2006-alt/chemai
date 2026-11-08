"""学生练习统计接口（design-upgrade #16 游戏化数据源）。

锁定三件事：
- 累计答题数 / 正确率（真实 StudentAnswer 聚合）
- 连续打卡 streak：今天有答题从今天回数，否则从昨天回数（口径与 parent weekly 一致）
- 未注册学生 → 404
"""
import asyncio

from datetime import datetime, timedelta

import pytest


@pytest.fixture
def seeded_student(db_session):
    from app.models.database import Student, StudentAnswer

    s = Student(student_id="202610101", name="张浩宇", class_id="class_2025_1", status="approved")
    db_session.add(s)
    db_session.commit()

    now = datetime.utcnow()
    rows = [
        # 今天：1 对 1 错
        ("a1", now - timedelta(hours=1), True),
        ("a2", now - timedelta(hours=2), False),
        # 昨天：1 对 → streak = 2（今天+昨天）
        ("a3", now - timedelta(days=1, hours=3), True),
        # 3 天前：1 对（隔天，不打断 streak，但计入累计/周练习）
        ("a4", now - timedelta(days=3), True),
        # 10 天前：1 错（出周窗口，计入累计）
        ("a5", now - timedelta(days=10), False),
    ]
    for aid, at, ok in rows:
        db_session.add(StudentAnswer(
            answer_id=aid, student_id="202610101", question_id="q1",
            student_answer="A", is_correct=ok, answered_at=at,
        ))
    db_session.commit()


def test_stats_aggregation(db_session, seeded_student):
    from app.api.practice import get_student_practice_stats

    out = asyncio.run(get_student_practice_stats(student_id="202610101", db=db_session, _perm=None))
    assert out["success"] is True
    assert out["total_answers"] == 5
    assert out["accuracy"] == round(3 / 5, 2)
    assert out["week_practice_count"] == 4  # a5 在 10 天前，出 7 天窗口
    assert out["streak_days"] == 2  # 今天+昨天
  # 今天+昨天


def test_stats_unknown_student_404(db_session):
    from fastapi import HTTPException

    from app.api.practice import get_student_practice_stats

    async def run():
        await get_student_practice_stats(student_id="ghost", db=db_session, _perm=None)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(run())
    assert ei.value.status_code == 404
