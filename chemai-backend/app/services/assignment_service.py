"""练习分发（Assignment）— 把练习真实送达每个学生的唯一入口（ADR-0012 service module）。

interface（grilling 定案 C2-2）:
- assign(targets, source, name_hint)  单一入口；source 三取题策略：
    {"kind": "adaptive", "knowledge_points"?, "question_count"?}  AI 按最近发展区逐生生成（四维机器闸）
    {"kind": "bank",     "knowledge_points"?, "question_count"?}  题库/真题按知识点取题（关联副本）
    {"kind": "manual",   "question_ids"}                          教师指定题目（副本引用，不偷原题）
- progress(batch_id)                  异步批次进度

批处理（C2-4）: ≤SYNC_LIMIT 人同步返回逐生真实结果；超出转后台批次（逐生
student 作业以 record_id 幂等），Agent/页面凭 batch_id 查进度。
"""
import json
import re
import time
from datetime import datetime

from app.models.database import (
    ExamRecord, Question, RecordType, Difficulty, QuestionSource, AuditStatus,
    Student, StudentAnswer, AssignmentBatch, get_db,
)

# 同步批处理阈值（grilling C2-4 定案）
SYNC_LIMIT = 5


# ═══════════════════ 入口 ═══════════════════

def assign(db, targets: list, source: dict, name_hint: str = "") -> dict:
    """布置练习给指定学生（调用方负责解析 class→student_ids）。

    Returns:
        同步: {"mode": "sync", "results": [{student_id, student_name, record_id,
               question_count, status, audit?}]}
        批次: {"mode": "batch", "batch_id", "total"}
    """
    student_ids = [t for t in (targets or []) if t]
    if not student_ids:
        return {"mode": "sync", "results": [], "error": "未提供布置目标"}

    students = db.query(Student).filter(Student.student_id.in_(student_ids)).all()
    by_id = {s.student_id: s for s in students}

    if len(students) <= SYNC_LIMIT:
        results = [_assign_one(db, by_id[sid], source, name_hint=name_hint)
                   for sid in student_ids if sid in by_id]
        db.commit()
        for r in results:
            if r.get("status") == "assigned":
                _notify_assigned(r["student_id"], r["record_id"], r.get("record_name", ""))
        return {
            "mode": "sync",
            "results": results,
            "assigned_count": sum(1 for r in results if r.get("status") == "assigned"),
        }

    valid_targets = [sid for sid in student_ids if sid in by_id]
    batch_id = f"asgb_{int(time.time() * 1000)}"
    db.add(AssignmentBatch(
        batch_id=batch_id,
        targets=valid_targets,
        source=source,
        name_hint=name_hint or None,
        status="pending",
        failed_targets={},
    ))
    db.commit()
    for sid in valid_targets:
        _enqueue_assignment(batch_id, sid)
    return {"mode": "batch", "batch_id": batch_id, "total": len(valid_targets)}


def progress(db, batch_id: str, *, class_ids) -> dict:
    """异步批次进度：目标数 / 已完成逐生结果 / 失败终态与原因。

    class_ids 必传（adapter 从身份解析，无默认值 → 忘了传就是 TypeError 而非全量放行）：
    批次目标学生必须全部落在该范围内，否则不返回任何学情。
    """
    batch = db.query(AssignmentBatch).filter(AssignmentBatch.batch_id == batch_id).first()
    if not batch:
        return {"batch_id": batch_id, "error": "批次不存在"}

    target_classes = {
        r[0] for r in db.query(Student.class_id).filter(
            Student.student_id.in_(batch.targets or [])
        ).all() if r[0]
    }
    if not target_classes or not target_classes <= set(class_ids or ()):
        return {"batch_id": batch_id, "error": f"批次 {batch_id} 不存在"}

    records = _batch_records(db, batch_id)
    failed = dict(batch.failed_targets or {})
    return {
        "batch_id": batch_id,
        "total": len(batch.targets or []),
        "completed": len(records),
        "failed": len(failed),
        "status": batch.status or _settle_status(db, batch),
        "failed_targets": failed,
        "records": [
            {
                "record_id": r.record_id,
                "student_id": (r.question_stats or {}).get("student_id"),
                "question_count": (r.question_stats or {}).get("question_count", 0),
                "status": (r.question_stats or {}).get("status", "assigned"),
            }
            for r in records
        ],
    }


def _batch_records(db, batch_id: str) -> list:
    """该批次已落库的逐生卷子（record_id 确定性派生）。"""
    return db.query(ExamRecord).filter(
        ExamRecord.record_id.like(f"asg_{batch_id}_%")
    ).all()


def _settle_status(db, batch) -> str:
    """按已落卷/已失败的目标数算出批次终态（纯计算，写回与 commit 归调用方）。"""
    targets = batch.targets or []
    done = {(r.question_stats or {}).get("student_id") for r in _batch_records(db, batch.batch_id)}
    failed = dict(batch.failed_targets or {})
    settled = sum(1 for t in targets if t in done or t in failed)
    if settled < len(targets):
        status = "running" if settled else "pending"
    elif not (done & set(targets)):
        status = "failed"          # 全批都没出卷：老师需要看到「已失败」而不是「还在跑」
    else:
        status = "partial" if failed else "done"
    return status


# ═══════════════════ 逐生布置 ═══════════════════

def _assign_one(db, student: Student, source: dict, name_hint: str = "",
                batch_id: str = None) -> dict:
    """为单个学生布置（幂等：record_id 确定性派生，重放返回已存在）。"""
    kind = (source or {}).get("kind", "adaptive")
    if batch_id:
        record_id = f"asg_{batch_id}_{student.student_id}"
    else:
        # 同步布置幂等：内容摘要（学生+来源要点+名称）——双触发不再重复建卷
        import hashlib as _hl
        import json as _json
        digest = _hl.sha1(_json.dumps(
            {"s": student.student_id, "src": source, "h": name_hint},
            sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        record_id = f"asg_{digest}"

    existing = db.query(ExamRecord).filter(ExamRecord.record_id == record_id).first()
    if existing:
        # 幂等命中：卷子已存在（同任务重跑/双触发）。返回真实题数——此前固定
        # 返回 0，前端布置卡显示「题数 0」误导老师（2026-09-21 实测）
        stats = (existing.question_stats or {})
        return {"student_id": student.student_id, "student_name": student.name,
                "record_id": record_id,
                "question_count": int(stats.get("question_count", 0)),
                "status": "exists"}

    questions, audit, zpd, weak, barrier = [], {}, None, [], None
    kps = []
    if kind == "adaptive":
        zpd = _calculate_zpd_difficulty(student.student_id, db)
        weak = _get_weak_kps(student.student_id, db)
        barrier = _get_dominant_barrier(student.student_id, db)
        kps = (source.get("knowledge_points") or weak or ["高中化学综合"])
        count = int(source.get("question_count", 5))
        questions, audit = _compose_adaptive(
            student, kps, count, zpd,
            question_types=source.get("question_types") or ["choice"])
        audit["zpd_difficulty"] = zpd
        audit["barrier"] = barrier
    elif kind == "bank":
        kps = source.get("knowledge_points") or []
        count = int(source.get("question_count", 5))
        questions, audit = _compose_bank(kps, source.get("difficulty"), count)
    elif kind == "manual":
        questions, audit = _compose_manual(db, source.get("question_ids") or [])
    else:
        return {"student_id": student.student_id, "student_name": student.name,
                "record_id": "", "question_count": 0, "status": "skipped",
                "error": f"未知来源: {kind}"}

    if not questions:
        return {"student_id": student.student_id, "student_name": student.name,
                "record_id": "", "question_count": 0, "status": "skipped",
                "audit": audit}

    stats = {
        "source_kind": kind,
        "student_id": student.student_id,
        "question_count": len(questions),
        "status": "assigned",
        "audit": audit,
    }
    if kps:
        # 学生任务列表/取题接口按 question_stats.knowledge_points 渲染知识点标签
        stats["knowledge_points"] = list(kps)
    if batch_id:
        stats["batch_id"] = batch_id

    if name_hint:
        record_name = name_hint
    elif kind == "adaptive":
        record_name = f"自适应练习-{student.name}"
    else:
        record_name = f"练习-{student.name}"

    rec = ExamRecord(
        record_id=record_id,
        class_id=student.class_id,
        name=record_name,
        type=RecordType.PRACTICE,
        total_students=1,
        present_students=1,
        exam_date=datetime.utcnow(),
        question_stats=stats,
    )
    db.add(rec)

    for i, q in enumerate(questions):
        db.add(Question(
            question_id=f"q_{record_id}_{i}",
            record_id=record_id,
            content=q.get("content", ""),
            options=q.get("options"),
            answer=q.get("answer", ""),
            analysis=q.get("analysis", ""),
            knowledge_points=q.get("knowledge_points", []),
            difficulty=_difficulty_of(zpd),
            source=QuestionSource.AI_GENERATED if kind == "adaptive" else QuestionSource.MANUAL_SELECTED,
            audit_status=AuditStatus.PASSED,
        ))

    return {"student_id": student.student_id, "student_name": student.name,
            "record_id": record_id, "record_name": record_name,
            "question_count": len(questions),
            "status": "assigned", "audit": audit}


# ═══════════════════ 取题策略（compose）═══════════════════

def _compose_adaptive(student: Student, kps: list, count: int, zpd: str,
                      question_types: list = None):
    """逐生生成 + 四维审核机器闸（C2-3）：不过审重生成；仍不够则按缺口补足
    （有界：生成 + 重生成 + 补足，至多 3 次 LLM 调用）；最终仍缺则如实计 dropped。"""
    rag = _bank_find(kps, zpd, 3)  # RAG 真题上下文（老 practice.py 行为恢复）
    raw = _llm_generate(kps, zpd, count, rag_context=rag, question_types=question_types)
    passed, blocked = _audit_gate(raw)

    regenerated = 0
    for _ in range(2):  # 重生成 + 补足，各一轮
        shortfall = count - len(passed)
        if shortfall <= 0:
            break
        regenerated += shortfall
        regen = _llm_generate(kps, zpd, shortfall, rag_context=rag, question_types=question_types)
        regen_passed, _ = _audit_gate(regen)
        passed = passed + regen_passed

    final = passed[:count]
    audit = {
        "generated": len(raw) + regenerated,
        "regenerated": regenerated,
        "dropped": max(0, count - len(final)),
        "weak_kps": kps if len(kps) <= 5 else kps[:5],
    }
    return final, audit


def _compose_bank(kps: list, difficulty: str, count: int):
    """题库/真题检索 → 关联副本（原题归属不动）。"""
    found = _bank_find(kps, difficulty, count)
    questions = [
        {
            "content": f.get("content", ""),
            "options": f.get("options"),
            "answer": f.get("answer", ""),
            "analysis": f.get("analysis", ""),
            "knowledge_points": f.get("knowledge_points", kps),
        }
        for f in (found or [])[:count]
    ]
    return questions, {"generated": len(questions), "regenerated": 0, "dropped": 0}


def _compose_manual(db, question_ids: list):
    """教师指定 → 副本引用（消灭 batch-assign 式外键重指偷题）。"""
    rows = db.query(Question).filter(Question.question_id.in_(question_ids)).all() \
        if question_ids else []
    questions = [
        {
            "content": q.content, "options": q.options, "answer": q.answer,
            "analysis": q.analysis, "knowledge_points": q.knowledge_points or [],
        }
        for q in rows
    ]
    return questions, {"generated": len(questions), "regenerated": 0, "dropped": 0}


# 片段抽取：生成器被要求输出 $...$ + LaTeX 下标/箭头（llm_service 提示），
# 字符集必须覆盖 \ _ ^ { } ⇌ → ↑ ↓ -> 与负号（- / −：离子电荷、电子），
# 否则片段在缺的字符处被截断、方程式根本进不了审核。
# $ 不在字符集里：它是格式契约里的式子边界，留着会把相邻两条式子（或式子与后随 ASCII 串）
# 粘成一条「三个半边」的片段，被 _is_chemical_equation 拒绝后整条漏审
_EQUATION_FRAGMENT_RE = re.compile(r"[A-Za-z0-9\(\)\[\]→=+\-\s\\_\^{}⇌↑↓>−]+")
# 箭头族一律归一为 =：LaTeX（\rightarrow/\to/\longleftrightarrow/\rightleftharpoons）、
# 带条件的 \xrightarrow{条件}（条件词不是物种，连同参数一起丢）、Unicode ⇌ → 与 ASCII ->/-->
# 条件参数允许一层嵌套（\xrightarrow{\text{点燃}}）——嵌套花括号漏在外面时，
# 条件里的中文会把式子切成两段谁也认不出的片段
_ARROW_RE = re.compile(
    r"-{2,}(?:[^-]*?-{1,})?>"                          # ASCII 条件箭头（--MnO2--> / -->）
    r"|\\x(?:right|left)(?:harpoons|arrow)"
    r"(?:\s*\[[^\[\]]*\])?(?:\s*\{(?:[^{}]|\{[^{}]*\})*\})?"
    r"|\\(?:long)?(?:right|left)(?:left|right)?(?:harpoons|arrow)"
    r"|\\to(?![a-z])"
    r"|->|⇌|→"
)
# 气/沉状态符号不是参与计数的物种：送审前剔除（Unicode 与 LaTeX 两种拼写）
_STATE_SYMBOL_RE = re.compile(r"\\(?:up|down)arrow|[↑↓]")


def _plain_equation(fragment: str) -> str:
    """LaTeX 形态 → 审核引擎认得的裸方程式（箭头归一为 =、状态符剔除、去掉上下标标记）。"""
    text = _STATE_SYMBOL_RE.sub("", _ARROW_RE.sub("=", fragment))
    return (text.replace("\\", "").replace("$", "").replace("{", "").replace("}", "")
                .replace("_", "").replace("^", "").strip())


# 审核引擎只数元素、不认电荷：带着电荷送审会把 Mn2+/MnO4- 的电荷数当成原子个数，
# 把配平正确的离子方程式误杀。送审前剥成纯化学计量形态（LaTeX 上标即电荷，精确；
# 裸文本按「多位数字链的末位是电荷、紧跟小写字母的数字是电荷（Cu2+/Fe3+）、独元素
# 物种末尾的数字是电荷（S2-/O2-），其余（NO3-/HCO3-/ClO3- 这类多元素含氧酸根）的数字
# 是下标」的启发式：宁可保留下标让计数偏大被拦，也不把下标当电荷吃掉）
_LATEX_SUPERSCRIPT_RE = re.compile(r"\^\s*(?:\{[^{}]*\}|[+\-]?\w?[+\-]?)")
_LATEX_SUBSCRIPT_RE = re.compile(r"_\s*(?:\{([^{}]*)\}|(\w))")
_PLAIN_CHARGE_RE = re.compile(r"(?<=[A-Za-z0-9\)\]])(\d*)([+\-])(?![A-Za-z0-9\(])")
_ELECTRON_TERM_RE = re.compile(r"(?<![A-Za-z])\d*e(?![a-z])")
_OPERATOR_TAIL_RE = re.compile(r"\s*[A-Za-z0-9\(]")


def _strip_plain_charge(match) -> str:
    digits, sign = match.group(1), match.group(2)
    if sign == "+" and _OPERATOR_TAIL_RE.match(match.string[match.end():]):
        return match.group(0)      # "2H2+ O2"：缺空格的加号是算子不是电荷，整段保留
    if not digits:
        return ""                  # H+/OH-/e-：没有数字的电荷符号直接丢
    if len(digits) > 1:
        return digits[:-1]         # SO42-/PO43-/Cr2O72-：末位是电荷，前面的数字是下标
    if match.string[match.start() - 1].islower():
        return ""                  # Cu2+/Fe3+/Al3+：元素符号后的数字是电荷
    term = re.split(r"[+\s=]", match.string[:match.start()])[-1]
    return "" if term in _ELEMENT_SYMBOLS else digits   # S2-/O2- 是电荷，NO3-/HCO3- 是下标


def _audit_form(fragment: str) -> str:
    """送审前剥离电荷与电子，例：MnO4- + 8H+ + 5e- = Mn2+ + 4H2O → MnO4 + 8H = Mn + 4H2O。"""
    text = _STATE_SYMBOL_RE.sub("", _ARROW_RE.sub("=", fragment))
    text = _LATEX_SUPERSCRIPT_RE.sub("", text)                  # ^{2-} / ^- 整组丢弃
    text = _LATEX_SUBSCRIPT_RE.sub(lambda m: m.group(1) or m.group(2) or "", text)
    text = (text.replace("\\", "").replace("$", "").replace("{", "").replace("}", ""))
    text = _PLAIN_CHARGE_RE.sub(_strip_plain_charge, text)
    text = _ELECTRON_TERM_RE.sub("", text)
    text = re.sub(r"\+\s*\+", "+", text)          # 剥离后留下的空 + 项折叠
    text = re.sub(r"\+\s*(?==)", "", text)        # 收尾的空项（... + = ...）
    return re.sub(r"^\s*\+\s*", "", re.sub(r"\s+", " ", text)).strip()


# 方程式两侧的「物种」式样：元素符号（含下标/基团/电荷/↑↓），或电子 e-
_SPECIES_RE = re.compile(r"^(?:[A-Z][a-z]?\d*|\([A-Za-z0-9]+\)\d*)+(?:[+\-]\d*)?[↓↑]?$|^\d*e-$")
_SPECIES_ELEMENT_RE = re.compile(r"[A-Z][a-z]?")
_COEFF_RE = re.compile(r"^\d+(?:\.\d+)?\s*")

# 真实元素符号表：用来分辨「L/22.4 L」这类单位字母 —— 引擎会把 L 当元素解析
_ELEMENT_SYMBOLS = frozenset(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn "
    "Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce "
    "Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn "
    "Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl "
    "Mc Lv Ts Og".split()
)


def _is_species(term: str) -> bool:
    """单个物种（已可含计量数）：形态像化学式，且每个元素符号都真实存在。"""
    text = _COEFF_RE.sub("", term)
    if not _SPECIES_RE.match(text):
        return False
    return all(sym in _ELEMENT_SYMBOLS for sym in _SPECIES_ELEMENT_RE.findall(text))


def _is_chemical_equation(eq: str) -> bool:
    """片段是不是真方程式：按 = / → 切两半，两侧每个物种都得是化学物种。

    审核引擎对解析不出的输入一律返回 blocked（'pH = 7'、'V = 22.4'、'Ksp = ...'
    都中招），不先筛一遍就会把含等号的散文当方程式，好题被整批误杀。
    """
    if "→" in eq:
        sides = eq.split("→")
    elif "=" in eq:
        sides = eq.split("=")
    else:
        return False
    if len(sides) != 2:
        return False
    for side in sides:
        terms = [t.strip() for t in side.split("+") if t.strip()]
        if not terms or not all(_is_species(t) for t in terms):
            return False
    return True


def _audit_gate(questions: list):
    """四维审核机器闸：抽题面方程式交审核引擎，blocked 即不达标。

    逐字段抽（题干/选项/答案/解析分开）——拼成一串会把题干的方程式和答案里的式子
    并成一条根本不存在的反应，好题被误判 blocked。只有真正像方程式的片段才送审，
    散文里的等号（pH = 7）不算坏题。

    箭头/状态符在**抽片段之前**先归一：`\\xrightarrow{条件}` 的条件词是中文
    （点燃/浓硫酸/催化剂），而片段字符集只收 ASCII —— 不先归一，方程式会在条件词处
    被切成两段，两段都不像方程式，整条式子静默绕过闸门。
    """
    passed, blocked = [], []
    for q in questions or []:
        is_blocked = False
        fields = [q.get("content"), q.get("answer"), q.get("analysis")]
        options = q.get("options")
        # 选项与题干同等对待：生成器的示例就是把方程式写在选项里（llm_service 提示）
        fields.extend(options if isinstance(options, (list, tuple)) else [options])
        for field in fields:
            normalized = _STATE_SYMBOL_RE.sub("", _ARROW_RE.sub("=", str(field or "")))
            for raw in _EQUATION_FRAGMENT_RE.findall(normalized):
                eq = _plain_equation(raw)
                if _is_chemical_equation(eq) and \
                        _audit_equation(_audit_form(raw)).get("overall_status") == "blocked":
                    is_blocked = True
                    break
            if is_blocked:
                break
        (blocked if is_blocked else passed).append(q)
    return passed, blocked


# ═══════════════════ 批次作业（handler 面，幂等）═══════════════════

def run_batch_student(db, batch_id: str, student_id: str) -> dict:
    """逐生布置作业：自开会话路径的持久化点（commit），幂等由 record_id 确定性保证。"""
    batch = db.query(AssignmentBatch).filter(AssignmentBatch.batch_id == batch_id).first()
    if not batch:
        return {"error": f"批次不存在: {batch_id}"}
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        return {"error": f"学生不存在: {student_id}"}
    out = _assign_one(db, student, batch.source or {}, name_hint=batch.name_hint or "",
                      batch_id=batch_id)
    if out.get("status") == "assigned":
        _notify_assigned(student_id, out["record_id"], out.get("record_name", ""))
    elif out.get("status") != "exists":
        # 没出卷（模型无输出/限流或全被审核拦下）：记原因，批次才能走到失败终态
        failed = dict(batch.failed_targets or {})
        failed[student_id] = out.get("error") or "未生成题目：模型无输出或审核未通过"
        batch.failed_targets = failed
    batch.status = _settle_status(db, batch)
    db.commit()  # Celery/降级路径的持久化点——缺此则记录随会话关闭而丢失
    return out


def handle_batch_student(batch_id: str, student_id: str) -> dict:
    """队列作业入口：自开会话（可被 at-least-once 重复投递）。"""
    db_gen = get_db()
    db = next(db_gen)
    try:
        return run_batch_student(db, batch_id, student_id)
    finally:
        db.close()


BATCH_DRAIN_PER_TICK = 3


def pending_batch_targets(db, limit: int = BATCH_DRAIN_PER_TICK) -> list:
    """未完成批次的待办目标 [(batch_id, student_id)]（按批次创建顺序，有界）。"""
    from sqlalchemy import or_
    batches = db.query(AssignmentBatch).filter(
        or_(AssignmentBatch.status.is_(None),
            AssignmentBatch.status.notin_(("done", "failed", "partial"))),
    ).order_by(AssignmentBatch.created_at).all()
    out = []
    for batch in batches:
        done = {(r.question_stats or {}).get("student_id") for r in _batch_records(db, batch.batch_id)}
        failed = set((batch.failed_targets or {}).keys())
        for sid in (batch.targets or []):
            if sid in done or sid in failed:
                continue
            out.append((batch.batch_id, sid))
            if len(out) >= limit:
                return out
    return out


def handle_pending_batch_targets(limit: int = BATCH_DRAIN_PER_TICK) -> dict:
    """调度器入口（无 Redis 部署的兜底消费）：自开会话逐生推进未完成批次。

    幂等：record_id 确定性 + 已落卷/已记失败的目标不再重复取；每轮有界。
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        picked = pending_batch_targets(db, limit=limit)
        for batch_id, student_id in picked:
            run_batch_student(db, batch_id, student_id)
        return {"processed": len(picked)}
    finally:
        db.close()


# ═══════════════════ 学情辅助（自 practice.py 迁入）═══════════════════

def _calculate_zpd_difficulty(student_id: str, db) -> str:
    """最近发展区难度：最近 30 次作答正确率 <40% easy / ≤70% medium / >70% hard。

    只看生效行：待判定/未确认的作答不是定论，不能左右下一次布置的难度。
    """
    from app.services.grading_center import effective_conditions
    recent = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id,
        effective_conditions(),
    ).order_by(StudentAnswer.answered_at.desc()).limit(30).all()
    if not recent:
        return "medium"
    rate = sum(1 for a in recent if a.is_correct) / len(recent)
    if rate < 0.4:
        return "easy"
    if rate <= 0.7:
        return "medium"
    return "hard"


def _get_weak_kps(student_id: str, db, top_n: int = 3) -> list:
    """薄弱知识点 TOP N（学生错题统计，只认生效行）。"""
    from collections import Counter
    from app.services.grading_center import effective_conditions
    wrong = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.is_correct.is_(False),
        effective_conditions(),
    ).all()
    counter = Counter()
    for a in wrong:
        q = db.query(Question).filter(Question.question_id == a.question_id).first()
        for kp in (q.knowledge_points or []) if q else []:
            counter[kp] += 1
    return [kp for kp, _ in counter.most_common(top_n)]


def _get_dominant_barrier(student_id: str, db) -> str:
    """主导障碍类型（学生 barrier 分布最大项，缺省 concept）。"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    barrier = (student.barrier_type or {}) if student else {}
    if not isinstance(barrier, dict) or not barrier:
        return "concept"
    return max(barrier, key=barrier.get)


def _difficulty_of(zpd: str):
    return {"easy": Difficulty.EASY, "hard": Difficulty.HARD}.get(zpd, Difficulty.MEDIUM)


# ═══════════════════ 可注入 seam（外部依赖薄包装）═══════════════════

def _llm_generate(kps: list, difficulty: str, quantity: int, rag_context: list = None,
                  question_types: list = None) -> list:
    """LLM 生成并解析（失败/解析不出返回空列表，由上游如实报告）。"""
    from app.services.llm_service import llm_service

    result = llm_service.generate_questions(
        knowledge_points=kps, difficulty=difficulty, quantity=quantity,
        question_types=question_types or ["choice"], rag_context=rag_context,
    )
    if not result.get("success"):
        return []
    match = re.search(r"\{[\s\S]*\}", result.get("content", ""))
    try:
        return json.loads(match.group()).get("questions", []) if match else []
    except (ValueError, TypeError):
        return []


def _audit_equation(equation: str) -> dict:
    """四维审核引擎入口（配平/条件/产物/结构）。"""
    from app.services.chemical_balance import audit_chemical_equation
    return audit_chemical_equation(equation)


def _bank_find(kps: list, difficulty: str, limit: int) -> list:
    """题库/真题检索（历年真题库 find_similar_questions）。"""
    from app.services.exam_bank import exam_bank_service
    rows = exam_bank_service.find_similar_questions(
        knowledge_points=kps, difficulty=difficulty, limit=limit,
    )
    return [
        {
            "content": q.content, "options": getattr(q, "options", None),
            "answer": q.answer, "analysis": getattr(q, "analysis", "") or "",
            "knowledge_points": q.knowledge_points or [],
        }
        for q in (rows or [])
    ]


def _notify_assigned(student_id: str, record_id: str, record_name: str):
    """布置完成事件挂钩：经通知分发进学生收件箱（失败不阻断布置）。"""
    try:
        from app.services.notification_service import notification_service
        notification_service.dispatch(
            recipient={"role": "student", "id": student_id},
            event={"type": "assignment", "title": "新练习已送达",
                   "content": record_name or "老师布置了新的练习",
                   "payload": {"record_id": record_id}},
            idempotency_key=f"asg_{record_id}",
        )
    except Exception as e:  # 通知失败不影响布置主流程
        import logging
        logging.getLogger(__name__).warning("assignment notify failed: %s", e)


def _enqueue_assignment(batch_id: str, student_id: str):
    """投递逐生布置作业（Celery；broker 不可达时同步降级）。"""
    from app.jobs import enqueue_job
    enqueue_job("assignment_student", {"batch_id": batch_id, "student_id": student_id})
