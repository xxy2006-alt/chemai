"""Agent 工具薄包装测试 — save_to_bank / list_banks / delete_bank / search_exam_bank。

这些工具现在委托 QuestionBankService（spec: question-bank），用共享内存 SQLite
（StaticPool）验证：保存→列表→搜索联合→删除 的完整往返行为。工具每次调用都通过
get_db() 新建 session，所以必须用 StaticPool 让所有连接共享同一块内存数据库。
"""
import asyncio
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.database as db_mod
from app.models.database import Base


@pytest.fixture
def agent_db(monkeypatch):
    """把 agent 工具里的 get_db 指向共享内存 SQLite（跨连接持久）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def _fake_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(db_mod, "get_db", _fake_get_db)
    return Session


def _qs_json():
    return json.dumps({
        "questions": [
            {
                "content": "下列物质属于电解质的是（　）",
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
    }, ensure_ascii=False)


def _run(coro):
    return asyncio.run(coro)


def _text_of(result):
    """search_exam_bank 可能返回 JSON 字符串（带 images）或纯文本。"""
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return result
    return data.get("text", json.dumps(data, ensure_ascii=False))


def test_save_to_bank_roundtrip(agent_db):
    """保存 → 列表可见 → 删除后消失。"""
    from agent.tools.exam_bank import save_to_bank, list_banks, delete_bank

    raw = _run(save_to_bank(questions=_qs_json(), knowledge_points="电解质"))
    data = json.loads(raw)
    assert data["saved"] is True
    assert data["count"] == 2
    assert data["set_id"].startswith("qset_")
    assert data["_route"]["navigate"] is True
    assert data["_route"]["page"] == "exam-v2"
    assert data["_route"]["actions"][0]["payload"] == "bank"

    set_id = data["set_id"]

    banks = json.loads(_run(list_banks()))
    assert any(b["set_id"] == set_id for b in banks["banks"])
    assert any(b["question_count"] == 2 for b in banks["banks"] if b["set_id"] == set_id)

    deleted = json.loads(_run(delete_bank(set_id=set_id)))
    assert deleted["deleted"] is True
    assert deleted["name"] == data["set_name"]

    banks2 = json.loads(_run(list_banks()))
    assert not any(b["set_id"] == set_id for b in banks2["banks"])


def test_save_to_bank_invalid_input(agent_db):
    from agent.tools.exam_bank import save_to_bank

    raw = _run(save_to_bank(questions="not json", knowledge_points="电解质"))
    assert json.loads(raw)["error"] == "题目数据格式无效"

    raw = _run(save_to_bank(questions='{"questions": []}', knowledge_points="电解质"))
    assert json.loads(raw)["error"] == "没有可保存的题目"


def test_delete_bank_missing_and_system_guard(agent_db):
    """删除守卫：不存在的题库报错；系统题库拒绝删除。"""
    from agent.tools.exam_bank import delete_bank
    from app.services.question_bank import question_bank_service

    raw = _run(delete_bank(set_id="not-exist"))
    assert "不存在" in json.loads(raw)["error"]

    db = agent_db()
    set_id = question_bank_service.create_set(db, name="系统模板", is_system=True)["set_id"]
    db.close()

    raw = _run(delete_bank(set_id=set_id))
    assert json.loads(raw)["error"] == "系统预设题库不能删除"


def test_search_exam_bank_unions_ai_questions(agent_db, monkeypatch):
    """带关键词搜索时，返回同时包含本地题库与 AI 生成题库。"""
    from agent.tools.exam_bank import save_to_bank, search_exam_bank
    from app.services.exam_bank import exam_bank_service

    class _EmptyResults:
        keyword_count = 0

        def __iter__(self):
            return iter([])

        def __len__(self):
            return 0

    # 本机持久化 Chroma 版本损坏（collections.topic 缺失，预置环境问题），
    # 关键词路径会触发向量召回并崩溃。这里把历史搜索置空以隔离该问题，
    # 只验证「AI 题库联合返回」逻辑本身。
    monkeypatch.setattr(exam_bank_service, "search_questions", lambda **kwargs: _EmptyResults())

    _run(save_to_bank(questions=_qs_json(), knowledge_points="电解质"))

    text = _text_of(_run(search_exam_bank(keyword="电解质", limit=5)))
    assert "🤖 AI生成题库" in text
    assert "电解质" in text


def test_search_exam_bank_without_keyword_includes_ai(agent_db):
    """不带关键词搜索时，AI 题库命中不遗漏（spec 场景：保存后不带关键词搜索）。"""
    from agent.tools.exam_bank import save_to_bank, search_exam_bank

    _run(save_to_bank(questions=_qs_json(), knowledge_points="电解质"))

    text = _text_of(_run(search_exam_bank(keyword="", limit=5)))
    assert "🤖 AI生成题库" in text
