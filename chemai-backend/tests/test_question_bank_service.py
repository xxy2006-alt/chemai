"""QuestionBankService 集成测试 — 覆盖 spec question-bank 的 5 条行为。

使用 conftest 的内存 SQLite db_session，打真实 DB，不 mock。
"""
from app.models.database import Question, QuestionSet, QuestionSetItem
from app.services.question_bank import QuestionBankService

service = QuestionBankService()


def _sample_questions():
    return [
        {
            "content": "下列物质属于电解质的是（　）A.铜 B.蔗糖 C.氯化钠 D.乙醇",
            "options": ["A. 铜", "B. 蔗糖", "C. 氯化钠", "D. 乙醇"],
            "answer": "C",
            "knowledge_points": ["电解质"],
            "difficulty": "medium",
            "type": "single_choice",
        },
        {
            "content": "氧化还原反应的本质是（　）",
            "options": None,
            "answer": "电子转移",
            "knowledge_points": ["氧化还原反应"],
            "difficulty": "easy",
            "type": "fill_blank",
        },
    ]


# ── Requirement: 保存题目时按正文去重 ───────────────────────────

def test_add_questions_dedup_by_content(db_session):
    set_id = service.create_set(db_session, name="测试题库")["set_id"]
    qs = _sample_questions()

    first = service.add_questions(db_session, set_id, qs)
    assert first["count"] == 2

    # 再次保存完全相同的内容（第一道重复）
    second = service.add_questions(db_session, set_id, qs[:1])
    assert second["count"] == 0  # 无新增

    # 数据库里只存在 2 条题目记录，而非 3 条
    total = db_session.query(Question).count()
    assert total == 2

    # 重复保存复用已有 question_id
    items = db_session.query(QuestionSetItem).filter(
        QuestionSetItem.set_id == set_id
    ).all()
    assert len(items) == 2  # 关联数也不增长


def test_add_questions_distinct_contents_not_merged(db_session):
    set_id = service.create_set(db_session, name="测试题库")["set_id"]
    qs = _sample_questions()

    service.add_questions(db_session, set_id, qs)
    service.add_questions(db_session, set_id, qs[1:])  # 只加第二道（不同内容）

    total = db_session.query(Question).count()
    assert total == 2  # 仍是 2 条，不同内容不合并


# ── Requirement: 系统题库删除守卫 ──────────────────────────────

def test_delete_system_set_guarded(db_session):
    set_id = service.create_set(db_session, name="系统模板", is_system=True)["set_id"]

    result = service.delete_set(db_session, set_id)
    assert result["success"] is False

    # 题库仍在
    assert db_session.query(QuestionSet).filter(QuestionSet.set_id == set_id).first() is not None


def test_delete_custom_set_succeeds(db_session):
    set_id = service.create_set(db_session, name="自定义题库")["set_id"]
    service.add_questions(db_session, set_id, _sample_questions())

    result = service.delete_set(db_session, set_id)
    assert result["success"] is True

    assert db_session.query(QuestionSet).filter(QuestionSet.set_id == set_id).first() is None
    # 关联被清除
    assert db_session.query(QuestionSetItem).filter(
        QuestionSetItem.set_id == set_id
    ).count() == 0


# ── Requirement: 保存即同步，保存后可被搜索命中 ─────────────────

def test_search_ai_generated_finds_saved_with_keyword(db_session):
    set_id = service.create_set(db_session, name="测试题库")["set_id"]
    service.add_questions(db_session, set_id, _sample_questions())

    hits = service.search_ai_generated(db_session, keyword="电解质")
    assert len(hits) >= 1
    assert any("电解质" in h["content"] or "电解质" in h.get("knowledge_points", [])
               for h in hits)


def test_search_ai_generated_finds_saved_without_keyword(db_session):
    set_id = service.create_set(db_session, name="测试题库")["set_id"]
    service.add_questions(db_session, set_id, _sample_questions())

    hits = service.search_ai_generated(db_session, keyword=None)
    assert len(hits) == 2  # 不带 keyword 也能命中全部已保存题目


# ── Requirement: 所有写入入口行为一致（服务层单一入口）─────────

def test_same_content_via_repeated_service_calls_stays_unique(db_session):
    """同一服务方法多次调用与多入口调用等价：都走去重。"""
    set_id = service.create_set(db_session, name="测试题库")["set_id"]
    service.add_questions(db_session, set_id, _sample_questions())
    service.add_questions(db_session, set_id, _sample_questions())  # 重复全量

    total = db_session.query(Question).count()
    assert total == 2
    qs = db_session.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
    assert qs.question_count == 2


# ── create_set / get_set / list_sets 基础能力 ──────────────────

def test_create_get_list_set(db_session):
    set_id = service.create_set(
        db_session, name="2024真题", teacher_id="t1",
        region="全国卷", year=2024, source="manual",
    )["set_id"]

    detail = service.get_set(db_session, set_id)
    assert detail is not None
    assert detail["name"] == "2024真题"

    listed = service.list_sets(db_session, teacher_id="t1")
    assert any(s["set_id"] == set_id for s in listed["exam_sets"])

    assert service.get_set(db_session, "not-exist") is None
