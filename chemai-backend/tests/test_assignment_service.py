"""练习分发服务测试 — 测试面 = assignment_service 的 assign / progress。

只断言外部行为：落库与否、题目数、审核闸效果、批次幂等与进度。
LLM 生成 / 四维审核 / 题库检索以模块级 seam（_llm_generate / _audit_equation /
_bank_find）注入假实现。
"""
import pytest

from app.services import assignment_service as svc


def _class_ids(class_ids=("class_2025_1",)):
    return set(class_ids)


def _q(i, eq=None):
    content = f"题目{i}：" + (eq or "下列说法正确的是____")
    return {"content": content, "options": ["A", "B", "C", "D"],
            "answer": "A", "analysis": "解析", "knowledge_points": ["kp_x"]}


@pytest.fixture
def students(db_session):
    from app.models.database import Student
    for i in range(1, 7):
        db_session.add(Student(student_id=f"20261010{i}", name=f"学生{i}",
                               class_id="class_2025_1"))
    db_session.commit()
    return db_session


_BAD_EQ = "H2 + O2 = H2O"   # 未配平：审核引擎判 blocked，且确实是方程式


def _clean(count):
    return [_q(i) for i in range(count)]


@pytest.fixture
def no_rag(monkeypatch):
    """屏蔽题库 RAG 检索（Adaptive compose 会取真题上下文，测试注入空）。"""
    monkeypatch.setattr(svc, "_bank_find", lambda kps, diff, limit: [])


class TestAdaptiveCompose:
    """Adaptive 来源：逐生生成 + 四维审核机器闸。"""

    def test_sync_assign_single_student(self, db_session, students, monkeypatch, no_rag):
        from app.models.database import ExamRecord, Question, RecordType

        monkeypatch.setattr(svc, "_llm_generate", lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "adaptive", "question_count": 3})
        db_session.commit()

        assert out["mode"] == "sync"
        r = out["results"][0]
        assert r["status"] == "assigned" and r["question_count"] == 3

        rec = db_session.query(ExamRecord).filter_by(record_id=r["record_id"]).one()
        assert rec.type == RecordType.PRACTICE
        assert rec.total_students == 1
        qs = db_session.query(Question).filter(Question.record_id == r["record_id"]).all()
        assert len(qs) == 3

    def test_gate_regenerates_blocked_once(self, db_session, students, monkeypatch, no_rag):
        """不过审的题自动重生成一次；替代题过审则补足，不发未过审的题。"""
        calls = []

        def fake_gen(kps, diff, n, rag_context=None, question_types=None):
            calls.append(n)
            if len(calls) == 1:
                qs = _clean(n)
                qs[0]["content"] = _BAD_EQ   # 未配平方程式，触发 blocked
                return qs
            return _clean(n)                                  # 重生成全部干净

        monkeypatch.setattr(svc, "_llm_generate", fake_gen)
        monkeypatch.setattr(svc, "_audit_equation",
                            lambda eq: {"overall_status": "blocked" if "H2O" in eq else "passed"})

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "adaptive", "question_count": 3})
        db_session.commit()

        assert calls == [3, 1]                    # 重生成只补 blocked 的 1 题
        assert out["results"][0]["question_count"] == 3
        assert out["results"][0]["audit"]["regenerated"] == 1
        assert out["results"][0]["audit"]["dropped"] == 0

    def test_gate_drops_after_second_failure(self, db_session, students, monkeypatch, no_rag):
        """重生成仍不过审 → 剔除，不落入题库；最终题数如实。"""
        monkeypatch.setattr(svc, "_llm_generate", lambda kps, diff, n, rag_context=None, question_types=None: [
            {**_q(0), "content": _BAD_EQ}, *_clean(n - 1)])
        monkeypatch.setattr(svc, "_audit_equation",
                            lambda eq: {"overall_status": "blocked" if "H2O" in eq else "passed"})

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "adaptive", "question_count": 2})
        db_session.commit()

        r = out["results"][0]
        assert r["question_count"] == 1           # blocked 的被剔除
        assert r["audit"]["dropped"] == 1
        from app.models.database import Question
        assert "H2O" not in "".join(
            q.content for q in db_session.query(Question).all()
        )

    def test_gate_tops_up_until_full(self, db_session, students, monkeypatch, no_rag):
        """重生成仍不过审 → 按缺口再补足一轮；补足成功则题数不低于约定数量。"""
        calls = []

        def fake_gen(kps, diff, n, rag_context=None, question_types=None):
            calls.append(n)
            if len(calls) <= 2:                      # 首轮 + 重生成轮：各带 1 道 blocked
                qs = _clean(n)
                qs[0]["content"] = _BAD_EQ
                return qs
            return _clean(n)                          # 补足轮干净

        monkeypatch.setattr(svc, "_llm_generate", fake_gen)
        monkeypatch.setattr(svc, "_audit_equation",
                            lambda eq: {"overall_status": "blocked" if "H2O" in eq else "passed"})

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "adaptive", "question_count": 2})
        db_session.commit()

        r = out["results"][0]
        assert r["question_count"] == 2               # 补足后达标
        assert r["audit"]["dropped"] == 0
        assert calls == [2, 1, 1]                     # 生成→重生成→补足，有界 3 次

    def test_zero_questions_no_record(self, db_session, students, monkeypatch, no_rag):
        """全部被剔除 → 不建空卷，结果如实标记。"""
        monkeypatch.setattr(svc, "_llm_generate", lambda kps, diff, n, rag_context=None, question_types=None: [
            {**_q(i), "content": _BAD_EQ} for i in range(n)])
        monkeypatch.setattr(svc, "_audit_equation",
                            lambda eq: {"overall_status": "blocked"})

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "adaptive", "question_count": 2})
        db_session.commit()

        from app.models.database import ExamRecord
        assert out["results"][0]["status"] == "skipped"
        assert db_session.query(ExamRecord).count() == 0


class TestBankAndManual:
    """题库 / 手动来源：建立关联副本，不偷原题。"""

    def test_bank_copies_questions(self, db_session, students, monkeypatch):
        from app.models.database import Question

        monkeypatch.setattr(svc, "_bank_find", lambda kps, diff, limit: [
            {"content": f"真题{i}", "options": None, "answer": "B",
             "analysis": "", "knowledge_points": ["kp_y"]} for i in range(4)
        ])

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "bank", "knowledge_points": ["kp_y"], "question_count": 4})
        db_session.commit()

        r = out["results"][0]
        assert r["status"] == "assigned" and r["question_count"] == 4
        qs = db_session.query(Question).filter(Question.record_id == r["record_id"]).all()
        assert len(qs) == 4 and all(q.source.value == "manual_selected" for q in qs)

    def test_manual_references_copy_not_repoint(self, db_session, students):
        """手动指定：练习引用副本，原题的归属不变（消灭偷题）。"""
        from app.models.database import Question, Difficulty, QuestionSource, AuditStatus

        src = Question(
            question_id="orig_q_1", record_id="other_exam", content="原题",
            options=["A", "B"], answer="A", analysis="",
            knowledge_points=["kp"], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
        )
        db_session.add(src)
        db_session.commit()

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "manual", "question_ids": ["orig_q_1"]})
        db_session.commit()

        r = out["results"][0]
        assert r["status"] == "assigned"
        copy = db_session.query(Question).filter(Question.record_id == r["record_id"]).one()
        assert copy.question_id != "orig_q_1"
        db_session.refresh(src)
        assert src.record_id == "other_exam"      # 原题归属未被动过


class TestBatch:
    """>5 人异步批次 + 幂等 + 进度。"""

    def test_large_class_goes_batch(self, db_session, students, monkeypatch, no_rag):
        monkeypatch.setattr(svc, "_llm_generate", lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})
        enqueued = []
        monkeypatch.setattr(svc, "_enqueue_assignment",
                            lambda batch_id, sid: enqueued.append((batch_id, sid)))

        out = svc.assign(db_session, [f"20261010{i}" for i in range(1, 7)],
                         {"kind": "adaptive", "question_count": 2}, name_hint="全班专项")
        db_session.commit()

        assert out["mode"] == "batch"
        assert len(enqueued) == 6
        batch = svc.progress(db_session, out["batch_id"], class_ids=_class_ids())
        assert batch["total"] == 6 and batch["completed"] == 0

    def test_batch_student_job_idempotent(self, db_session, students, monkeypatch, no_rag):
        """逐生作业重放不重复建卷（at-least-once 契约）。"""
        monkeypatch.setattr(svc, "_llm_generate", lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})
        enqueued = []
        monkeypatch.setattr(svc, "_enqueue_assignment",
                            lambda batch_id, sid: enqueued.append((batch_id, sid)))

        out = svc.assign(db_session, [f"20261010{i}" for i in range(1, 7)],
                         {"kind": "adaptive", "question_count": 2})
        db_session.commit()
        batch_id = out["batch_id"]

        svc.run_batch_student(db_session, batch_id, "202610101")
        db_session.commit()
        svc.run_batch_student(db_session, batch_id, "202610101")   # 重放
        db_session.commit()

        batch = svc.progress(db_session, batch_id, class_ids=_class_ids())
        assert batch["completed"] == 1
        assert batch["records"][0]["question_count"] == 2

    def test_sync_limit_boundary(self, db_session, students, monkeypatch, no_rag):
        """≤5 人同步、6 人批次的边界。"""
        monkeypatch.setattr(svc, "_llm_generate", lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})

        out5 = svc.assign(db_session, [f"20261010{i}" for i in range(1, 6)],
                          {"kind": "adaptive", "question_count": 1})
        assert out5["mode"] == "sync"


def _as_teacher(db_session):
    """判卷/布置工具的身份取服务端上下文：测试统一以 t1（任教 class_2025_1）执行。"""
    from agent.tools.context import set_current_teacher
    from app.models.database import Account, TeacherClassSubject

    db_session.add(Account(account_id="acc_t1", username="t1_user", role="teacher",
                           teacher_id="t1", password_hash="x"))
    db_session.add(TeacherClassSubject(id="tcs_scope", teacher_id="t1",
                                       class_id="class_2025_1", subject="化学"))
    db_session.commit()
    set_current_teacher("t1")


class TestProgressTool:
    """query_assignment_progress 薄壳：转发正确 + 返回 JSON 形状（ADR-0012 工具层测试）。"""

    @pytest.mark.asyncio
    async def test_progress_tool_reports_batch(self, db_session, students, monkeypatch, no_rag):
        import json as _json
        from agent.tools.diagnosis import query_assignment_progress

        monkeypatch.setattr(svc, "_llm_generate",
                            lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation",
                            lambda eq: {"overall_status": "passed"})
        monkeypatch.setattr(svc, "_enqueue_assignment", lambda b, s: None)

        out = svc.assign(db_session, [f"20261010{i}" for i in range(1, 7)],
                         {"kind": "adaptive", "question_count": 2})
        db_session.commit()

        _as_teacher(db_session)
        monkeypatch.setattr("app.models.database.get_db", lambda: iter([db_session]))
        try:
            result = _json.loads(await query_assignment_progress(batch_id=out["batch_id"]))
        finally:
            from agent.tools.context import set_current_teacher
            set_current_teacher("")

        assert result["batch_id"] == out["batch_id"]
        assert result["total"] == 6
        assert "records" in result and "_route" in result

    @pytest.mark.asyncio
    async def test_progress_tool_unknown_batch(self, db_session, monkeypatch):
        import json as _json
        from agent.tools.diagnosis import query_assignment_progress

        _as_teacher(db_session)
        monkeypatch.setattr("app.models.database.get_db", lambda: iter([db_session]))
        try:
            result = _json.loads(await query_assignment_progress(batch_id="ghost"))
        finally:
            from agent.tools.context import set_current_teacher
            set_current_teacher("")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_progress_tool_rejects_out_of_scope_batch(self, db_session, students, monkeypatch, no_rag):
        """别人班级的批次：工具不返回任何学情（无身份更是直接拒绝）。"""
        import json as _json
        from agent.tools.context import set_current_teacher
        from agent.tools.diagnosis import query_assignment_progress

        monkeypatch.setattr(svc, "_llm_generate",
                            lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})
        monkeypatch.setattr(svc, "_enqueue_assignment", lambda b, s: None)
        out = svc.assign(db_session, [f"20261010{i}" for i in range(1, 7)],
                         {"kind": "adaptive", "question_count": 2})
        db_session.commit()
        monkeypatch.setattr("app.models.database.get_db", lambda: iter([db_session]))

        _as_teacher(db_session)                        # t1 只教 class_2025_1
        try:
            assert svc.progress(db_session, out["batch_id"], class_ids={"c_other"}).get("error")
            denied = _json.loads(await query_assignment_progress(batch_id=out["batch_id"]))
            assert "error" not in denied                 # 本班批次正常返回
        finally:
            set_current_teacher("")

        set_current_teacher("")                       # 无身份 → 拒绝
        result = _json.loads(await query_assignment_progress(batch_id=out["batch_id"]))
        assert "error" in result


_LATEX_ARROW = chr(92) + "rightarrow"   # LaTeX 箭头；用 chr(92) 写，免源码层转义歧义
_LATEX_REVERSIBLE = chr(92) + "rightleftharpoons"
_LATEX_XARROW = chr(92) + "xrightarrow{MnO_2}"   # 提示词强制的条件箭头形态
_LATEX_UP = chr(92) + "uparrow"                  # 提示词强制的气体符号形态
_LATEX_DOWN = chr(92) + "downarrow"              # 提示词强制的沉淀符号形态
_UP, _DOWN = chr(0x2191), chr(0x2193)            # Unicode 气/沉符号


class TestAuditGateReadsGeneratorFormat:
    """四维审核机器闸必须看懂生成器被要求输出的形态（$...$ + LaTeX 下标 + LaTeX 箭头）。

    这些用例用**真实审核引擎**（不打桩）——桩掉的正是本节要守的格式契约。
    """

    def test_unbalanced_latex_equation_is_blocked(self):
        q = {"content": "配平：$2H_2 + O_2 " + _LATEX_ARROW + " H_2O$",
             "answer": "$2H_2O$", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [] and blocked == [q]

    def test_balanced_latex_equation_passes(self):
        q = {"content": "配平：$2H_2 + O_2 " + _LATEX_ARROW + " 2H_2O$",
             "answer": "$2H_2O$", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [q] and blocked == []

    def test_plain_equation_still_blocked_when_unbalanced(self):
        q = {"content": "2H2 + O2 = H2O", "answer": "H2O", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [] and blocked == [q]

    def test_condition_arrow_equation_is_audited(self):
        """\\xrightarrow{条件}（提示词里的正确示例）要连同条件词归一，不能整条绕过闸门。"""
        good = {"content": "$2KClO_3 " + _LATEX_XARROW + " 2KCl + 3O_2" + _LATEX_UP + "$",
                "answer": "", "analysis": ""}
        bad = {"content": "$2H_2 + O_2 " + _LATEX_XARROW + " H_2O" + _LATEX_UP + "$",
               "answer": "", "analysis": ""}
        assert svc._audit_gate([good]) == ([good], [])
        assert svc._audit_gate([bad]) == ([], [bad])

    def test_reversible_arrow_equation_is_audited(self):
        good = {"content": "$N_2 + 3H_2 " + _LATEX_REVERSIBLE + " 2NH_3$",
                "answer": "", "analysis": ""}
        bad = {"content": "$N_2 + 3H_2 " + _LATEX_REVERSIBLE + " NH_3$",
               "answer": "", "analysis": ""}
        assert svc._audit_gate([good]) == ([good], [])
        assert svc._audit_gate([bad]) == ([], [bad])

    @pytest.mark.parametrize("arrow", ["->", "--MnO2-->", "-->", "--->"])
    def test_ascii_arrow_equation_is_audited(self, arrow):
        good = {"content": "2H2 + O2 " + arrow + " 2H2O", "answer": "", "analysis": ""}
        bad = {"content": "2H2 + O2 " + arrow + " H2O", "answer": "", "analysis": ""}
        assert svc._audit_gate([good]) == ([good], [])
        assert svc._audit_gate([bad]) == ([], [bad])

    @pytest.mark.parametrize("symbol", [_UP, _DOWN, _LATEX_UP, _LATEX_DOWN])
    def test_state_symbol_does_not_truncate_equation(self, symbol):
        """气/沉符号后面的产物也要进审核：截断成半条式子会把配平的好题误杀。"""
        good = {"content": "Na2CO3 + Ca(OH)2 = CaCO3" + symbol + " + 2NaOH",
                "answer": "", "analysis": ""}
        bad = {"content": "Na2CO3 + Ca(OH)2 = CaCO3" + symbol + " + NaOH",
               "answer": "", "analysis": ""}
        assert svc._audit_gate([good]) == ([good], [])
        assert svc._audit_gate([bad]) == ([], [bad])

    @pytest.mark.parametrize("condition", [
        "点燃",                      # 教学里真实的条件词就是中文
        "浓硫酸",
        chr(92) + "text{点燃}",      # 嵌套花括号的写法
    ])
    def test_cjk_condition_arrow_equation_is_audited(self, condition):
        """条件词是中文时不能把式子切成两段：两段谁也认不出是方程式，整条静默漏审。"""
        xarrow = chr(92) + "xrightarrow{" + condition + "}"
        bad = {"content": "$2H_2 + O_2 " + xarrow + " H_2O$", "answer": "", "analysis": ""}
        good = {"content": "$2KClO_3 " + xarrow + " 2KCl + 3O_2" + _LATEX_UP + "$",
                "answer": "", "analysis": ""}
        assert svc._audit_gate([bad]) == ([], [bad])
        assert svc._audit_gate([good]) == ([good], [])

    def test_options_equations_are_audited(self):
        """方程式写在选项里（生成器示例的形态）也要送审。"""
        bad = {"content": "下列方程式书写正确的是",
               "options": ["A. $H_2 + O_2 " + _LATEX_ARROW + " H_2O$",
                           "B. $2H_2 + O_2 " + _LATEX_ARROW + " 2H_2O$"],
               "answer": "B", "analysis": ""}
        good = {"content": "下列方程式书写正确的是",
                "options": ["A. $2H_2 + O_2 " + _LATEX_ARROW + " 2H_2O$",
                            "B. $2KClO_3 = 2KCl + 3O_2$"],
                "answer": "A", "analysis": ""}
        assert svc._audit_gate([bad]) == ([], [bad])
        assert svc._audit_gate([good]) == ([good], [])

    def test_parenthesized_species_coefficient_is_counted(self):
        """带括号物种前的计量数要乘进括号内的原子数：2Fe(OH)_3 = Fe_2O_3 + 3H_2O 是配平的。"""
        good = {"content": "$2Fe(OH)_3 = Fe_2O_3 + 3H_2O$", "answer": "", "analysis": ""}
        bad = {"content": "$2Fe(OH)_3 = Fe_2O_3 + H_2O$", "answer": "", "analysis": ""}
        assert svc._audit_gate([good]) == ([good], [])
        assert svc._audit_gate([bad]) == ([], [bad])


class TestBatchFailureTerminalState:
    """批次失败终态：老师要能区分「还在跑」与「已失败」，不能永远 completed<total。"""

    def _assign_all_failing(self, db_session, monkeypatch, no_rag):
        monkeypatch.setattr(svc, "_llm_generate",
                            lambda kps, diff, n, rag_context=None, question_types=None: [])
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})
        monkeypatch.setattr(svc, "_enqueue_assignment", lambda batch_id, sid: None)
        return svc.assign(db_session, [f"20261010{i}" for i in range(1, 7)],
                          {"kind": "adaptive", "question_count": 2})

    def test_all_targets_failed_marks_batch_failed(self, db_session, students, monkeypatch, no_rag):
        out = self._assign_all_failing(db_session, monkeypatch, no_rag)
        for sid in [f"20261010{i}" for i in range(1, 7)]:
            svc.run_batch_student(db_session, out["batch_id"], sid)

        prog = svc.progress(db_session, out["batch_id"], class_ids=_class_ids())
        assert prog["status"] == "failed"
        assert prog["completed"] == 0 and prog["failed"] == 6
        assert all(reason for reason in prog["failed_targets"].values()), "失败原因要如实回传"

    def test_partial_failure_is_distinguishable(self, db_session, students, monkeypatch, no_rag):
        calls = {"n": 0}

        def flaky(kps, diff, n, rag_context=None, question_types=None):
            # 首个学生的三次尝试（生成 + 两轮补足）全失败 → 该生无卷，其余成功
            calls["n"] += 1
            return [] if calls["n"] <= 3 else _clean(n)

        monkeypatch.setattr(svc, "_llm_generate", flaky)
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})
        monkeypatch.setattr(svc, "_enqueue_assignment", lambda batch_id, sid: None)
        out = svc.assign(db_session, [f"20261010{i}" for i in range(1, 7)],
                         {"kind": "adaptive", "question_count": 2})
        for sid in [f"20261010{i}" for i in range(1, 7)]:
            svc.run_batch_student(db_session, out["batch_id"], sid)

        prog = svc.progress(db_session, out["batch_id"], class_ids=_class_ids())
        assert prog["status"] == "partial"
        assert prog["completed"] > 0 and prog["failed"] > 0

    def test_drain_picks_unfinished_targets(self, db_session, students, monkeypatch, no_rag):
        """无 broker 部署：enqueue 只登记，兜底作业按批次逐个接手（幂等、有界）。"""
        monkeypatch.setattr(svc, "_llm_generate", lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})
        monkeypatch.setattr(svc, "_enqueue_assignment", lambda batch_id, sid: None)
        out = svc.assign(db_session, [f"20261010{i}" for i in range(1, 7)],
                         {"kind": "adaptive", "question_count": 1})
        db_session.commit()

        picked = svc.pending_batch_targets(db_session, limit=3)
        assert [b for b, _ in picked] == [out["batch_id"]] * 3
        assert len({s for _, s in picked}) == 3

        for batch_id, sid in picked:
            svc.run_batch_student(db_session, batch_id, sid)
        db_session.commit()
        again = svc.pending_batch_targets(db_session, limit=3)
        assert len(again) == 3
        assert not ({s for _, s in again} & {s for _, s in picked}), "已落卷的目标不该被重复接手"


class TestEffectiveRowReads:
    """待判定/未确认的作答不是定论 —— 不能左右下一次布置的难度与薄弱知识点。"""

    def _pending_wrong(self, db_session, aid, qid="q_kp"):
        from app.models.database import StudentAnswer
        db_session.add(StudentAnswer(
            answer_id=aid, student_id="202610101", question_id=qid,
            student_answer="x", is_correct=False, confirmed=False,
            grade_reason="PENDING_SEMANTIC"))
        db_session.commit()

    def test_zpd_ignores_pending_rows(self, db_session, students):
        for i in range(3):
            self._pending_wrong(db_session, f"pz_{i}")
        assert svc._calculate_zpd_difficulty("202610101", db_session) == "medium"

    def test_weak_kps_ignore_pending_rows(self, db_session, students):
        from app.models.database import Question, StudentAnswer, Difficulty, QuestionSource, AuditStatus
        db_session.add(Question(
            question_id="q_kp", content="题", answer="A", knowledge_points=["kp_weak"],
            difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
            audit_status=AuditStatus.PASSED))
        db_session.commit()
        self._pending_wrong(db_session, "pw_1")
        assert svc._get_weak_kps("202610101", db_session) == []

        db_session.add(StudentAnswer(
            answer_id="pw_ok", student_id="202610101", question_id="q_kp",
            student_answer="B", is_correct=False, confirmed=True))
        db_session.commit()
        assert svc._get_weak_kps("202610101", db_session) == ["kp_weak"]


class TestAuditGateIgnoresProseEquals:
    """散文里的等号（pH = 7 / V = 22.4 / Ksp = …）不是坏方程式，不能整题拦下。

    审核引擎对解析不出的输入一律 blocked —— 不先筛「像不像方程式」，
    含等号的题干会被当坏题丢掉，学生一份练习都拿不到。
    """

    @pytest.mark.parametrize("content", [
        "已知某溶液 pH = 7，下列说法正确的是",
        "标准状况下气体体积 V = 22.4 L/mol",
        "溶度积 Ksp = 1.8×10^-10 的难溶盐",
        "物质的量浓度 c = n/V",
    ])
    def test_prose_with_equals_is_not_blocked(self, content):
        q = {"content": content, "answer": "A", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [q] and blocked == []

    def test_real_unbalanced_equation_still_blocked(self):
        q = {"content": "配平：H2 + O2 = H2O", "answer": "", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [] and blocked == [q]

    def test_latex_prose_with_equals_is_not_blocked(self):
        q = {"content": r"已知 $K_{sp}$ = 1.8 $\times$ 10$^{-10}$", "answer": "A", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [q] and blocked == []


class TestAssignmentStats:
    def test_adaptive_stats_keep_knowledge_points(self, db_session, students, monkeypatch, no_rag):
        """学生任务列表/取题接口按 question_stats.knowledge_points 渲染知识点标签。"""
        from app.models.database import ExamRecord

        monkeypatch.setattr(svc, "_llm_generate",
                            lambda kps, diff, n, rag_context=None, question_types=None: _clean(n))
        monkeypatch.setattr(svc, "_audit_equation", lambda eq: {"overall_status": "passed"})

        out = svc.assign(db_session, ["202610101"],
                         {"kind": "adaptive", "knowledge_points": ["kp_a", "kp_b"],
                          "question_count": 2})
        db_session.commit()

        rec = db_session.query(ExamRecord).filter_by(
            record_id=out["results"][0]["record_id"]).one()
        assert rec.question_stats["knowledge_points"] == ["kp_a", "kp_b"]


class TestAuditGateIonEquations:
    """含负电荷/电子的离子与氧化还原式：整段进审核，且不被电荷盲引擎误杀。"""

    @pytest.mark.parametrize("content", [
        "Cu2+ + 2e- = Cu",
        "MnO4- + 8H+ + 5e- = Mn2+ + 4H2O",
        "2Fe3+ + Cu = 2Fe2+ + Cu2+",
        "SO42- + Ba2+ = BaSO4",
        r"$MnO_4^- + 8H^+ + 5e^- = Mn^{2+} + 4H_2O$",
    ])
    def test_correct_ion_equation_passes(self, content):
        q = {"content": content, "answer": "", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [q] and blocked == []

    @pytest.mark.parametrize("content", [
        "HCO3- + H+ = H2O + CO2" + _UP,
        "ClO3- + 6H+ + 6e- = Cl- + 3H2O",
        "S2- + Cu2+ = CuS" + _DOWN,
        "NH2- + H2O = NH3 + OH-",
        "AlO2- + 4H+ = Al3+ + 2H2O",
        "H2PO4- + OH- = HPO42- + H2O",
        "NO3- + 4H+ + 3e- = NO + 2H2O",
    ])
    def test_subscript_ions_are_not_eaten_as_charge(self, content):
        """含氧酸根的末位数字是下标不是电荷：剥掉会把配平正确的离子方程式误杀。"""
        q = {"content": content, "answer": "", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [q] and blocked == []

    def test_unbalanced_ion_equation_still_blocked(self):
        """电荷剥离后元素仍不配平 → 闸门照拦。"""
        q = {"content": "2H+ + 2e- = H2O", "answer": "", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert blocked == [q] and passed == []

    def test_kept_subscript_still_counts(self):
        """保留下来的下标要真的进元素计数：多一个氧仍要拦。"""
        q = {"content": "HCO3- + H+ = H2O + CO2 + O2", "answer": "", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert blocked == [q] and passed == []

    def test_charge_stripped_before_audit(self, monkeypatch):
        """送审形态已剥电荷与电子（引擎只数元素，Mn2+/MnO4- 的下标不会被当原子数）。"""
        seen = []
        monkeypatch.setattr(svc, "_audit_equation",
                            lambda eq: seen.append(eq) or {"overall_status": "passed"})
        svc._audit_gate([{"content": "MnO4- + 8H+ + 5e- = Mn2+ + 4H2O",
                          "answer": "", "analysis": ""}])
        assert seen == ["MnO4 + 8H = Mn + 4H2O"]

    def test_prose_with_hyphen_still_ignored(self):
        q = {"content": "已知 Ksp = 1.8×10^-10 的难溶盐，下列判断正确的是",
             "answer": "A", "analysis": ""}
        passed, blocked = svc._audit_gate([q])
        assert passed == [q] and blocked == []
