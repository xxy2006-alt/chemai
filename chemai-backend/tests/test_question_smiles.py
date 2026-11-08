"""015 — 工作台 AI 出题路径的 [SMILES:...] 结构图渲染（苯环功能回归，ADR-0005 H1）。

用户反馈：「AI出题出有机化学的时候可以画苯环等有机化学的结构的功能，
升级前端之后是否还保留？」—— 管线（RDKit 渲染 + /static/question_images 挂载）
完好，但 /api/question/generate 曾漏掉 replace_smiles_markers，
导致工作台生成的有机题显示原始 [SMILES:...] 文本而不是结构图。
本测试锁定 generate 端点：LLM 返回的 [SMILES:...] 标记必须被替换为结构图 <img>。
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.api import question as question_mod
from app.middleware.auth import create_access_token

# /api/question/generate 是 question:create（阶段 4.6 批次 A）—— 任课教师即可
TEACHER = {"Authorization": f"Bearer {create_access_token('T1', 'teacher', school_id='sch1')}"}


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(question_mod.router, prefix="/api/question", tags=["question"])

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # 屏蔽外部依赖：LLM 生成、向量检索、简单匹配、方程式审核
    # 注意：app.services/__init__.py 重导出了实例，须直接 patch 实例方法
    from app.services.llm_service import llm_service as llm_svc
    from app.services.exam_bank import exam_bank_service as bank_svc
    from app.services import chemical_balance as bal_mod
    from app.services import vector_search as vec_mod

    def fake_generate_questions(**kwargs):
        return {
            "success": True,
            "content": json.dumps({
                "questions": [{
                    "content": "下列有机物中属于苯的同系物的是[SMILES:C1=CC=CC=C1]",
                    "options": ["A. 甲苯", "B. 苯酚", "C. 苯乙烯", "D. 苯"],
                    "answer": "A",
                    "knowledge_points": ["有机化学"],
                    "difficulty": "medium",
                }]
            }, ensure_ascii=False),
        }

    monkeypatch.setattr(llm_svc, "generate_questions", fake_generate_questions)
    monkeypatch.setattr(bank_svc, "find_similar_questions", lambda **kw: [])
    monkeypatch.setattr(vec_mod.vector_search_service, "search_similar", lambda **kw: [])
    monkeypatch.setattr(
        bal_mod,
        "audit_chemical_equation",
        lambda eq: {"overall_status": "passed", "overall_message": "ok"},
    )

    with TestClient(app) as c:
        yield c


def test_generate_renders_smiles_to_structure_img(client):
    """[SMILES:C1=CC=CC=C1]（苯）→ 被替换为 /static/question_images 结构图 <img>"""
    resp = client.post("/api/question/generate", json={
        "knowledge_points": ["有机化学"],
        "difficulty": "medium",
        "quantity": 1,
        "question_types": ["choice"],
    }, headers=TEACHER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["questions"]) == 1
    content = data["questions"][0]["content"]
    # 原始标记必须消失，替换为结构图 img
    assert "[SMILES:" not in content
    assert '<img src="/static/question_images/' in content


def test_generate_renders_smiles_in_options_and_answer(client, monkeypatch):
    """用户反馈「有机化学分子式的结构呢？为什么实现不了」：
    LLM 把 [SMILES:...] 写在选项/答案里也必须替换为结构图（不只 content）"""
    from app.services.llm_service import llm_service as llm_svc

    def fake_generate_questions(**kwargs):
        return {
            "success": True,
            "content": json.dumps({
                "questions": [{
                    "content": "下列物质属于芳香烃的是（　　）",
                    "options": [
                        "A. 苯 [SMILES:C1=CC=CC=C1]",
                        "B. 乙醇 [SMILES:CCO]",
                        "C. 乙酸 [SMILES:CC(=O)O]",
                        "D. 乙酸乙酯 [SMILES:CCOC(=O)C]",
                    ],
                    "answer": "A [SMILES:C1=CC=CC=C1]",
                    "knowledge_points": ["有机化学"],
                    "difficulty": "medium",
                }]
            }, ensure_ascii=False),
        }

    monkeypatch.setattr(llm_svc, "generate_questions", fake_generate_questions)
    resp = client.post("/api/question/generate", json={
        "knowledge_points": ["有机化学"],
        "difficulty": "medium",
        "quantity": 1,
        "question_types": ["choice"],
    }, headers=TEACHER)
    assert resp.status_code == 200
    q = resp.json()["questions"][0]
    assert "[SMILES:" not in q["content"]
    assert "[SMILES:" not in q["answer"]
    assert all("[SMILES:" not in o for o in q["options"])
    assert '<img src="/static/question_images/' in q["options"][0]
    assert '<img src="/static/question_images/' in q["answer"]


def test_enrich_organic_structures_adds_structure_imgs(tmp_path):
    """用户反馈「有机化学分子式的结构呢？为什么实现不了」：
    LLM 不输出 [SMILES:...] 时，结构语境下的常见有机名（苯/乙醇等）自动补结构图"""
    from app.services.structure_render import enrich_organic_structures

    out = enrich_organic_structures(
        "苯、甲苯、乙醇的结构简式分别为：苯、甲苯；能与钠反应的是乙醇", out_dir=str(tmp_path))
    assert '<img src="/static/question_images/' in out
    assert 'alt="苯结构式"' in out
    assert 'alt="甲苯结构式"' in out
    assert 'alt="乙醇结构式"' in out
    # 每个名称只插入一次
    assert out.count('alt="苯结构式"') == 1


def test_enrich_skips_without_structure_context(tmp_path):
    """用户反馈「碰到有机化学的名字就自动生成结构式，有时候不用」：
    无语境词（结构/简式/如图等）时不得补图"""
    from app.services.structure_render import enrich_organic_structures

    out = enrich_organic_structures(
        "乙醇能与钠反应放出氢气，苯不能使酸性高锰酸钾褪色", out_dir=str(tmp_path))
    assert 'question_images' not in out


def test_enrich_compound_word_priority(tmp_path):
    """复合词优先：苯酚整体匹配，不被单字「苯」拆开"""
    from app.services.structure_render import enrich_organic_structures

    out = enrich_organic_structures("苯酚的结构简式是", out_dir=str(tmp_path))
    assert '苯酚<img' in out
    assert 'alt="苯酚结构式"' in out
    assert 'alt="苯结构式"' not in out


def test_render_whitelist_canonical_normalization(tmp_path):
    """用户反馈「生成的图是错的，结构式不对」：
    LLM 等价写法（如苯简写 c1ccccc1）归一化到教材白名单 SMILES，渲染同一张图"""
    from app.services.structure_render import render_smiles_png

    p1 = render_smiles_png("C1=CC=CC=C1", out_dir=str(tmp_path))
    p2 = render_smiles_png("c1ccccc1", out_dir=str(tmp_path))  # LLM 简写苯
    assert p1 and p2
    import os
    assert os.path.basename(p1) == os.path.basename(p2)  # 同一 hash → 同一教材图


def test_render_rejects_invalid_valence(tmp_path):
    """化学合法性校验：价态/键数非法（sanitize 拦截）→ 不渲染，返回 None"""
    from app.services.structure_render import render_smiles_png

    # [He]C：He 价态超限；C1=CC=CC=C1BrCl：Br 双键价态错误 → 均 None
    assert render_smiles_png("[He]C", out_dir=str(tmp_path)) is None
    assert render_smiles_png("C1=CC=CC=C1BrCl", out_dir=str(tmp_path)) is None
    assert render_smiles_png("NOT_A_SMILES", out_dir=str(tmp_path)) is None


def test_enrich_idempotent_when_image_exists(tmp_path):
    """已有结构图 → 不再重复插入"""
    from app.services.structure_render import enrich_organic_structures

    content = '苯<img src="/static/question_images/abc.png">'
    assert enrich_organic_structures(content, out_dir=str(tmp_path)) == content


def test_enrich_formula_to_structure(tmp_path):
    """分子式 $CH_3CH_2OH$ 等（LaTeX 写法）也补结构图"""
    from app.services.structure_render import enrich_organic_structures

    out = enrich_organic_structures(
        "下列物质能与钠反应的是 $CH_3CH_2OH$ 与 $CH_3COOH$", out_dir=str(tmp_path))
    assert out.count('alt="乙醇结构式"') == 1
    assert out.count('alt="乙酸结构式"') == 1
    # 原公式保留
    assert "$CH_3CH_2OH$" in out
    assert '$CH_3COOH$' in out


def test_enrich_unknown_formula_unchanged(tmp_path):
    """未收录分子式不误伤"""
    from app.services.structure_render import enrich_organic_structures

    content = "摩尔质量为 $M$ 的有机物"
    assert enrich_organic_structures(content, out_dir=str(tmp_path)) == content


def test_generate_without_smiles_unchanged(client, monkeypatch):
    """无 [SMILES:...] 标记的题目内容不受影响"""
    from app.services.llm_service import llm_service as llm_svc

    def fake_generate_questions(**kwargs):
        return {
            "success": True,
            "content": json.dumps({
                "questions": [{
                    "content": "下列气体中能使湿润的品红溶液褪色的是（　　）",
                    "options": ["A. CO₂", "B. SO₂", "C. H₂", "D. N₂"],
                    "answer": "B",
                    "knowledge_points": ["非金属元素"],
                    "difficulty": "easy",
                }]
            }, ensure_ascii=False),
        }

    monkeypatch.setattr(llm_svc, "generate_questions", fake_generate_questions)
    resp = client.post("/api/question/generate", json={
        "knowledge_points": ["非金属元素"],
        "difficulty": "easy",
        "quantity": 1,
        "question_types": ["choice"],
    }, headers=TEACHER)
    assert resp.status_code == 200
    q = resp.json()["questions"][0]
    assert "品红" in q["content"]
    assert "SO₂" in q["options"][1]
    assert "question_images" not in q["content"]
