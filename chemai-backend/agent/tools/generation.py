"""Question generation tool."""

import json
import re

from dotenv import load_dotenv
load_dotenv()


async def generate_questions(
    knowledge_points: str = "",
    difficulty: str = "medium",
    quantity: int = 5,
    question_types: str = "",
    variant_qid: str = "",
    variant_source: str = "",
) -> str:
    """AI出题 — 根据参数直接生成题目

    何时用：用户明确说了知识点+题型+数量（如"出5道氧化还原选择题"），参数齐全直接出题
    会发生什么：调用 LLM 生成题目（选择题带选项，填空题用___标记，计算题含分步解答），
              运行方程式审核，返回题目列表并在对话中展示考试工作台面板
    下一步：用户可要求修改题目、保存到题库（save_to_bank）或重出
    NOT for 参数不全 — 用 show_exam_workbench 打开面板让用户补全
    question_types 格式："single_choice:3,fill_blank:2,calculation:1"
    """
    from agent.tools.tutoring import _normalize_chem_formulas

    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]
    if not kps:
        kps = ["高中化学综合"]

    type_map_reverse = {
        "single_choice": "choice", "fill_blank": "fill",
        "calculation": "calc", "experiment": "experiment", "inference": "inference",
    }
    types = []
    total_qty = quantity
    if question_types:
        for item in question_types.split(","):
            parts = item.strip().split(":")
            if len(parts) == 2:
                val, qty = parts[0].strip(), int(parts[1].strip())
                types.append({"val": val, "qty": qty})
        total_qty = sum(t["qty"] for t in types)

    llm_types = [type_map_reverse.get(t["val"], "choice") for t in types] if types else ["choice"]

    from app.services.exam_bank import exam_bank_service
    rag_context = []
    if variant_qid:
        blueprint_q = exam_bank_service.get_by_exam_id(variant_qid)
        if blueprint_q:
            rag_context = [{
                "content": blueprint_q.content, "answer": blueprint_q.answer,
                "knowledge_points": blueprint_q.knowledge_points,
                "difficulty": blueprint_q.difficulty, "source": blueprint_q.source,
                "exam_id": blueprint_q.exam_id, "similarity": 1.0, "match_method": "blueprint",
            }]
    else:
        similar = exam_bank_service.find_similar_questions(
            knowledge_points=kps, difficulty=difficulty, limit=3,
        )
        if similar:
            rag_context = [{
                "content": q.content, "answer": q.answer,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty, "source": q.source,
                "exam_id": q.exam_id, "similarity": 0.8, "match_method": "simple",
            } for q in similar]

    from app.services.llm_service import llm_service, parse_llm_json
    result = llm_service.generate_questions(
        knowledge_points=kps, difficulty=difficulty,
        quantity=total_qty, question_types=llm_types,
        rag_context=rag_context if rag_context else None,
    )

    questions = []
    if result.get("success") and "questions" in result.get("content", ""):
        try:
            data = parse_llm_json(result["content"])
            questions = data.get("questions", [])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    if not questions:
        return json.dumps({
            "result": f"已尝试生成{total_qty}道题但未获得有效结果，请检查知识点设置或重试",
            "total": 0, "questions": [],
        }, ensure_ascii=False)

    for q in questions:
        for field in ("content", "answer"):
            if field in q and q[field]:
                q[field] = _normalize_chem_formulas(q[field])
        if "options" in q and q["options"]:
            q["options"] = [_normalize_chem_formulas(o) for o in q["options"]]

    # [SMILES:...] 标记 → 结构图 <img> + 常见有机结构名兜底补图（非法 SMILES 退化为文本）
    # content/options/answer 三处都处理（有机结构常出现在选项或答案里）
    from app.services.structure_render import enrich_organic_content
    for q in questions:
        for field in ("content", "answer"):
            if q.get(field):
                q[field] = enrich_organic_content(q[field])
        if q.get("options"):
            q["options"] = [enrich_organic_content(o) for o in q["options"]]

    from app.services.chemical_balance import audit_chemical_equation
    for q in questions:
        if any(kw in q.get("content", "") for kw in ["→", "=", "->", "方程式", "反应"]):
            eq_match = re.search(r"([\d\w\(\)\+\s→=->]+)", q.get("content", ""))
            if eq_match:
                audit_chemical_equation(eq_match.group(1))

    return json.dumps({
        "result": f"已生成 {len(questions)} 道题目",
        "total": len(questions), "questions": questions,
        "knowledge_points": kps, "difficulty": difficulty,
        "_component": {
            "component": "exam-workbench",
            "params": {
                "knowledge_points": kps, "difficulty": difficulty,
                "types": types, "variant_source": variant_source,
                "questions": questions,
            },
        },
    }, ensure_ascii=False)
