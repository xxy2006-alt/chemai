"""WrongQuestionTrainer 错题强化训练服务测试。

覆盖：错题聚合排序、知识点筛选、变式题 LLM 生成（成功/失败/markdown 围栏/原题缺失）、
训练会话创建、结果提交评分、建议分档。
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Question, StudentAnswer, Difficulty
import app.services.wrong_question_trainer as wqt_mod


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def wqt(monkeypatch, db_session):
    def fake_get_db():
        yield db_session

    monkeypatch.setattr(wqt_mod, "get_db", fake_get_db)
    return wqt_mod.wqt


def _mk_question(db, qid, content="测试题", kps=None, answer="A", difficulty=Difficulty.MEDIUM):
    q = Question(question_id=qid, content=content, knowledge_points=kps or ["氧化还原"],
                 answer=answer, difficulty=difficulty)
    db.add(q)
    db.commit()
    return q


def _mk_wrong(db, aid, sid, qid, answered_at):
    db.add(StudentAnswer(answer_id=aid, student_id=sid, question_id=qid,
                         is_correct=False, answered_at=answered_at))
    db.commit()


# ── 错题聚合 ──

def test_get_student_wrong_questions_sorted_by_count(wqt, db_session):
    _mk_question(db_session, "qA")
    _mk_question(db_session, "qB")
    t = datetime.utcnow()
    # qA 错 2 次、qB 错 1 次 → qA 在前
    _mk_wrong(db_session, "a1", "s1", "qA", t)
    _mk_wrong(db_session, "a2", "s1", "qA", t)
    _mk_wrong(db_session, "a3", "s1", "qB", t)

    items = wqt.get_student_wrong_questions("s1")
    assert [i["question_id"] for i in items] == ["qA", "qB"]
    assert items[0]["wrong_count"] == 2
    assert items[0]["content"] == "测试题"


def test_get_student_wrong_questions_limit(wqt, db_session):
    for qid in ["q1", "q2", "q3"]:
        _mk_question(db_session, qid)
        _mk_wrong(db_session, f"a_{qid}", "s2", qid, datetime.utcnow())
    items = wqt.get_student_wrong_questions("s2", limit=2)
    assert len(items) == 2


def test_get_student_wrong_questions_kp_filter(wqt, db_session):
    _mk_question(db_session, "q_redox", kps=["氧化还原"])
    _mk_question(db_session, "q_hydro", kps=["盐类水解"])
    _mk_wrong(db_session, "a1", "s3", "q_redox", datetime.utcnow())
    _mk_wrong(db_session, "a2", "s3", "q_hydro", datetime.utcnow())

    items = wqt.get_student_wrong_questions("s3", knowledge_point_filter="水解")
    assert [i["question_id"] for i in items] == ["q_hydro"]


def test_get_student_wrong_questions_empty(wqt):
    assert wqt.get_student_wrong_questions("no_such") == []


# ── 变式题生成 ──

_LLM_OK = {
    "success": True,
    "content": '{"questions": [{"content": "变式1", "type": "choice", "options": ["A. x"], '
               '"answer": "A", "knowledge_points": ["氧化还原"]}]}',
}


def test_generate_variant_questions(wqt, db_session, monkeypatch):
    _mk_question(db_session, "q_src", content="原题")
    monkeypatch.setattr(wqt_mod.llm_service, "generate_text", lambda *a, **k: _LLM_OK)
    variants = wqt.generate_variant_questions("q_src", quantity=3)
    assert len(variants) == 1
    assert variants[0]["content"] == "变式1"


def test_generate_variant_questions_markdown_fence(wqt, db_session, monkeypatch):
    _mk_question(db_session, "q_fence")
    content = "```json\n{\"questions\": [{\"content\": \"带围栏\", \"answer\": \"B\"}]}\n```"
    monkeypatch.setattr(wqt_mod.llm_service, "generate_text",
                        lambda *a, **k: {"success": True, "content": content})
    variants = wqt.generate_variant_questions("q_fence")
    assert len(variants) == 1
    assert variants[0]["content"] == "带围栏"


def test_generate_variant_questions_llm_failure(wqt, db_session, monkeypatch):
    _mk_question(db_session, "q_fail")
    # content 里没有 "questions" → 返回空
    monkeypatch.setattr(wqt_mod.llm_service, "generate_text",
                        lambda *a, **k: {"success": True, "content": "抱歉，无法生成"})
    assert wqt.generate_variant_questions("q_fail") == []


def test_generate_variant_questions_invalid_json(wqt, db_session, monkeypatch):
    _mk_question(db_session, "q_json")
    monkeypatch.setattr(wqt_mod.llm_service, "generate_text",
                        lambda *a, **k: {"success": True, "content": "{\"questions\": broken"})
    assert wqt.generate_variant_questions("q_json") == []


def test_generate_variant_questions_missing_original(wqt):
    assert wqt.generate_variant_questions("no_such") == []


def test_generate_variant_questions_string_kp(wqt, db_session, monkeypatch):
    # knowledge_points 存成字符串，也能 JSON 解析
    _mk_question(db_session, "q_strkp", kps='["电离平衡"]')
    monkeypatch.setattr(wqt_mod.llm_service, "generate_text", lambda *a, **k: _LLM_OK)
    assert len(wqt.generate_variant_questions("q_strkp")) == 1


# ── 训练会话 ──

def test_create_training_session(wqt, db_session):
    _mk_question(db_session, "q1")
    _mk_question(db_session, "q2")
    sess = wqt.create_training_session("s1", ["q1", "q2", "no_such"])
    assert sess["session_id"].startswith("train_s1_")
    assert sess["student_id"] == "s1"
    assert {q["question_id"] for q in sess["questions"]} == {"q1", "q2"}
    assert sess["total_count"] == 2


def test_create_training_session_empty_ids(wqt, db_session):
    sess = wqt.create_training_session("s1", [])
    assert sess["total_count"] == 0
    assert sess["questions"] == []


# ── 结果提交 ──

def test_submit_training_result_accuracy(wqt, db_session):
    _mk_question(db_session, "q1", answer="A")
    _mk_question(db_session, "q2", answer="B")
    _mk_question(db_session, "q3", answer="C")

    res = wqt.submit_training_result("t1", "s1", [
        {"question_id": "q1", "answer": "a"},  # 小写也对
        {"question_id": "q2", "answer": "B"},
        {"question_id": "q3", "answer": "D"},
    ])
    assert res["correct_count"] == 2
    assert res["total_count"] == 3
    assert res["accuracy"] == pytest.approx(0.67, abs=0.01)
    # 答题记录已入库
    assert db_session.query(StudentAnswer).count() == 3


def test_submit_training_result_empty(wqt, db_session):
    res = wqt.submit_training_result("t_empty", "s1", [])
    assert res["accuracy"] == 0
    assert res["correct_count"] == 0


def test_submit_training_result_unknown_question_skipped(wqt, db_session):
    res = wqt.submit_training_result("t_unk", "s1", [{"question_id": "no_such", "answer": "A"}])
    assert res["total_count"] == 1
    assert res["correct_count"] == 0
    assert res["results"] == []  # 不认识的题不进 results


# ── 建议分档 ──

@pytest.mark.parametrize("accuracy,expected_fragment", [
    (0.95, "掌握得很好了"),
    (0.8, "做得不错"),
    (0.6, "还需要继续努力"),
    (0.4, "还需要加强"),
])
def test_generate_suggestions_thresholds(wqt, accuracy, expected_fragment):
    assert expected_fragment in wqt._generate_suggestions(accuracy, [])


# ── 主观题走 PENDING 管线（与练习路径同源，不再直接判错固化）──

def test_submit_subjective_goes_pending_not_final_wrong(wqt, db_session):
    """训练里再答主观题：落 PENDING 行交扫描作业判定，而不是当成定论错答。"""
    from app.services import grading_center

    # 标准答案用箭头、学生写等号：写法不等价于字符串，但化学意义相同 → 必须交给语义判定
    _mk_question(db_session, "q_sub", content="写出方程式",
                 answer="Fe2O3 + 3CO → 2Fe + 3CO2")
    res = wqt.submit_training_result("t_sub", "s1", [
        {"question_id": "q_sub", "answer": "Fe2O3+3CO=2Fe+3CO2"},
    ])
    db_session.expire_all()

    row = db_session.query(StudentAnswer).filter_by(question_id="q_sub").one()
    assert row.grade_reason == grading_center.PENDING_REASON, "主观题必须是待判定态"
    assert row.is_correct is False
    assert res["pending_count"] == 1
    assert res["results"][0]["pending"] is True


def test_submit_choice_answer_judged_immediately(wqt, db_session):
    """选择题仍然当场判（同步判定不受影响）。"""
    from app.services import grading_center
    _mk_question(db_session, "q_obj", content="选择", answer="A")
    res = wqt.submit_training_result("t_obj", "s1", [{"question_id": "q_obj", "answer": "A"}])
    db_session.expire_all()
    row = db_session.query(StudentAnswer).filter_by(question_id="q_obj").one()
    assert row.is_correct is True and row.grade_reason != grading_center.PENDING_REASON
    assert res["correct_count"] == 1 and res["pending_count"] == 0
