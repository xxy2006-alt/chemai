"""LLM Grading engine — comparison of student answers vs correct answers.

Supports two answer sources (in priority order):
1. Teacher-provided answers (``correct_answers`` param)
2. Exam bank match (real ExamRecord's Questions, keyed by ``exam_id``)

No-answer auto-judgment is intentionally NOT supported (v1) — the caller must
ask the teacher for answers before grading.

Comparison is layered:
1. Normalized exact match (whitespace/case + chemical-formula standardization).
2. For non-choice answers that differ after normalization: one batch LLM
   semantic call per card (equations / ion formulas / calculation steps).
"""
import logging
import re

logger = logging.getLogger(__name__)


# ── 老师粘贴的标准答案：确定性解析（不走 LLM），b3 ──
_CORRECT_ANCHOR_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*[\.\、\)）．]")
_CORRECT_CHOICE_RE = re.compile(r"(?<![\d.])(\d{1,2})(?=[A-Ea-e]{1,4}(?![A-Za-z0-9]))")


def parse_correct_answers(text: str) -> list:
    """把老师粘贴的标准答案文本解析为 [{q_number, answer}]。

    支持 "1.A 2.B"、"1、B"、"1) C"、"1A" 及自由作答 "13. Cu + 2H2SO4(浓)..."，
    答案文本保留到下一个题号；选择题归一为大写字母。解析失败/空输入返回空列表。
    """
    if not text or not text.strip():
        return []
    matches = sorted(
        list(_CORRECT_ANCHOR_RE.finditer(text)) + list(_CORRECT_CHOICE_RE.finditer(text)),
        key=lambda m: m.start(),
    )
    out = []
    for i, m in enumerate(matches):
        q_num = int(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw = text[m.end():end].strip()
        if not raw:
            continue
        answer = raw.upper() if _is_choice(raw) else raw
        out.append({"q_number": q_num, "answer": answer})
    return out


def grade_batch_answers(ocr_tasks: list, correct_answers: list = None, exam_id: str = None, db=None) -> list:
    """OCR adapter — 把答题卡任务转成来源无关作答后交判卷中心判定。

    Args:
        ocr_tasks: list of OCRTask instances with ocr_result populated
        correct_answers: list of {"q_number": N, "answer": "..."} from teacher (highest priority)
        exam_id: if provided and no correct_answers, auto-match from exam bank
        db: optional SQLAlchemy session (exam match); defaults to get_db()

    Returns: list of grading results per task（q_number 形状，供确认/保存）
    """
    from app.services import grading_center

    results = []

    # Resolve answer source once (teacher paste > exam bank > error).
    source_answers = correct_answers
    if not source_answers and exam_id:
        source_answers = _match_exam_answers(exam_id, db)

    for task in ocr_tasks:
        student_answers = (task.ocr_result or {}).get("answers") or []
        if not student_answers:
            results.append({"task_id": task.task_id, "error": "No OCR answers found"})
            continue

        if not source_answers:
            results.append({
                "task_id": task.task_id,
                "error": "缺少正确答案：请老师先粘贴标准答案，或关联已建题库的考试",
            })
            continue

        # OCR → 判卷中心：题号作引用，等价规则/语义判定与线上完全同源
        entries = [
            {"question_id": str(sa["q_number"]), "answer": sa.get("answer", "")}
            for sa in student_answers
        ]
        key = []
        for a in source_answers:
            item = {"question_id": str(a.get("q_number")), "answer": a.get("answer", "")}
            # 只有真拿到 options 元数据才写 choice；老师粘贴的标准答案没有 options，
            # 留空才会回退到判卷中心的双边形态启发式（字母对字母直接判错，不劳 LLM）
            if a.get("options"):
                item["choice"] = grading_center.answer_key_choice(
                    item["answer"], a.get("options"))
            key.append(item)
        graded = grading_center.grade(entries, key, semantic=True)

        questions = []
        unjudged = 0
        for q in graded["questions"]:
            # 判定没落地（LLM 失败）/ 没标准答案 → 未判，不按答错固化（ADR-0013）
            row = grading_center.pending_row(q)
            if row["reason"] in (grading_center.PENDING_REASON, grading_center.NO_KEY_REASON):
                unjudged += 1
            ref = row["question_id"]
            questions.append({
                "q_number": int(ref) if str(ref).isdigit() else ref,
                "student_answer": row["student_answer"],
                "correct_answer": row["correct_answer"],
                "is_correct": row["is_correct"],
                "reason": row["reason"],
            })
        results.append({
            "task_id": task.task_id,
            "student_id": task.student_id,
            "student_name": task.student_name,
            "score": graded["correct_count"],
            "total": graded["total"],
            "unjudged": unjudged,
            "questions": questions,
        })

    return results


def _match_exam_answers(exam_id: str, db=None) -> list:
    """Look up correct answers from exam bank (real ExamRecord Questions)."""
    from app.models.database import get_db
    from app.models.database import Question
    close = False
    if db is None:
        db = next(get_db())
        close = True
    try:
        questions = db.query(Question).filter(Question.record_id == exam_id).all()
        return [
            {"q_number": _question_number(q), "answer": q.answer, "options": q.options}
            for q in questions
        ]
    finally:
        if close:
            db.close()


def _question_number(q) -> int:
    """Question 题号按约定 `{exam_id}_{题号}` 从 question_id 末段解析，解析失败回退 0。"""
    suffix = (q.question_id or "").rsplit("_", 1)[-1]
    return int(suffix) if suffix.isdigit() else 0


def _find_answer(q_number: int, answers: list) -> str:
    for a in (answers or []):
        if a.get("q_number") == q_number:
            return a.get("answer", "")
    return ""


def _compare_answers(student_ans: str, correct_ans: str) -> bool:
    """Layer-1 deterministic comparison: normalized exact match.

    Normalizes whitespace/case and standardizes chemical formulas via
    ``latex_standardizer``. Semantic (LLM) comparison for non-matching
    free-form answers happens at the ``grade_batch_answers`` level.
    """
    if not student_ans or not correct_ans:
        return False
    return _normalize_text(student_ans) == _normalize_text(correct_ans)


# unicode 上下标 → 普通字符，保证 LaTeX/unicode/纯文本三种形态归一后可比
_SUB_SCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "01234567890123456789+-")


def _normalize_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from chem_skills.chemistry_parser.engine.latex_standardizer import standardize_latex_chemical
        text = standardize_latex_chemical(text)
    except Exception:  # standardization is best-effort
        pass
    # `_`/`^` 是 LaTeX 上下标结构标记，非答案内容，归一时剔除
    return "".join(text.upper().translate(_SUB_SCRIPT_MAP).replace("_", "").replace("^", "").split())


def _is_choice(answer: str) -> bool:
    """单字母选择题（A-E，可多选 AB）判为选择题，不需要语义比对。"""
    a = (answer or "").strip().upper()
    return bool(a) and len(a) <= 4 and all(ch in "ABCDEFGH" for ch in a)


# 卡内主观题的语义判定已收敛到判卷中心（grading_center.grade → _semantic_judge_batch）：
# 这里不再维护第二份 OCR 专用提示词/解析，避免改错对象。
