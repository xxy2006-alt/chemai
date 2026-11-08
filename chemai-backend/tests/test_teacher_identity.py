"""身份注入 + 数据范围校验回归（2026-08 起；2026-09-14 ADR-0014 扩为完整身份）。

身份经 contextvars 注入 guard 包装器；接缝据此**校验**工具收到的身份类参数
是否落在调用者的 Data Scope 内（`agent/tools/data_scope.py`）。

⚠️ **2026-09-14 行为变更**：此前只有「回退」没有「校验」——
模型显式传 `teacher_id` 会被原样采用，所以本文件原先那句
「不能靠传参冒充其他教师」是**不实的**（有测试钉着"能冒充"）。
ADR-0014 落地后，传别人的 `teacher_id` **会被拒绝**。

⚠️ **本文件不写死账号名**：2026-09-14 踩过 —— 演示数据被整体换过，
写死的 `teacher_hai` 消失，整个文件连带烂掉。改成运行时从库里挑真实教师。
"""
import asyncio
import contextlib
import json

from agent.guard import GuardState, _make_guarded_tool
from agent.tools.context import current_teacher, set_current_identity, set_current_teacher


def _real_teachers(n: int = 1):
    """从库里取 n 个真实存在的教师 (teacher_id, school_id) —— 不写死账号。"""
    from sqlalchemy import text

    from app.models.database import get_db

    session = next(get_db())
    try:
        rows = session.execute(
            text("SELECT teacher_id, school_id FROM teachers ORDER BY teacher_id LIMIT :n"),
            {"n": n},
        ).fetchall()
    finally:
        session.close()
    assert len(rows) >= n, f"库里至少需要 {n} 个教师才能跑这个文件，实际 {len(rows)} 个"
    return [(r[0], r[1]) for r in rows]


def _run(coro):
    async def go():
        return await coro

    return asyncio.run(go())


@contextlib.contextmanager
def _registered(fn, scope: dict):
    """把临时工具登记进 TOOL_META —— 接缝的范围规则**只认这一处声明**。

    旧实现按 `args_schema` 有没有 `teacher_id` 字段来判断，不需要登记；
    ADR-0014 改成「声明驱动」：没声明 = 不校验 = 不回填。生产里所有真工具都在
    TOOL_META 里（`agent/tools/__init__.py` 有断言兜着），所以这个差异只影响测试。
    """
    from agent.tools import TOOL_META

    TOOL_META[fn] = {"personas": [], "call_limit": 99, "scope": scope}
    try:
        yield
    finally:
        TOOL_META.pop(fn, None)


def test_contextvar_roundtrip():
    assert current_teacher() == ""
    _run(_set_and_check())


async def _set_and_check():
    set_current_identity("teacher_hai")
    assert current_teacher() == "teacher_hai"
    set_current_identity("")
    assert current_teacher() == ""


def test_guard_injects_teacher_id_when_tool_omits_it():
    """工具声明 teacher_id 参数但模型未传 → guard 注入服务端身份。"""
    captured = {}

    async def fake(teacher_id: str = "", name: str = ""):
        """Fake tool needing teacher identity."""
        captured["teacher_id"] = teacher_id
        return json.dumps({"ok": True})

    tid, school = _real_teachers()[0]
    gs = GuardState()
    set_current_identity(tid, "teacher", school)
    try:
        with _registered(fake, {"teacher_id": "teacher"}):
            guarded = _make_guarded_tool(fake, gs)
            out = _run(guarded.ainvoke({"name": "x"}))
        assert json.loads(out)["ok"] is True
        assert captured["teacher_id"] == tid
    finally:
        set_current_identity("")


def test_guard_rejects_impersonating_another_teacher():
    """**模型传别人的 teacher_id → 拒绝**（ADR-0014 把"回退"变成了"校验"）。

    这条此前叫 `test_guard_respects_explicit_teacher_id`，断言的是
    「传了就用传的」—— 即**能冒充**。ADR-0014 落地后期望翻转。
    """
    captured = {}
    me, school = _real_teachers(2)[0]
    other = _real_teachers(2)[1][0]

    async def fake(teacher_id: str = ""):
        """Fake tool needing teacher identity."""
        captured["teacher_id"] = teacher_id
        return json.dumps({"ok": True})

    gs = GuardState()
    set_current_identity(me, "teacher", school)
    try:
        with _registered(fake, {"teacher_id": "teacher"}):
            guarded = _make_guarded_tool(fake, gs)
            out = _run(guarded.ainvoke({"teacher_id": other}))
    finally:
        set_current_identity("")

    assert captured == {}, "工具不该被调用 —— 冒充他人身份必须在接缝处就被拒"
    assert json.loads(out).get("scope_denied") is True, out[:200]


def _probe_name_outside_scope(allowed_ids: set):
    """找一个姓名片段：全校能匹配到 ≥2 个学生，但**一个都不在** allowed_ids 里。

    动态找而不是写死「周」—— 演示数据已经整体换过一次，写死的数据早晚会失效，
    而失效的守卫比没有守卫更糟（看起来还在挡）。
    """
    from sqlalchemy import text

    from app.models.database import get_db

    session = next(get_db())
    try:
        names = [r[0] for r in session.execute(text("SELECT name FROM students")).fetchall() if r[0]]
        for ch in dict.fromkeys(n[0] for n in names):
            ids = {
                r[0] for r in session.execute(
                    text("SELECT student_id FROM students WHERE name LIKE :n"), {"n": f"%{ch}%"}
                ).fetchall()
            }
            if len(ids) >= 2 and not (ids & allowed_ids):
                return ch
    finally:
        session.close()
    return None


def test_guard_does_not_leak_out_of_scope_candidates():
    """按姓名匹配到多个学生时，候选**只列范围内的**（ADR-0014）。

    踩到过的真实形状：范围过滤原先放在匹配**之后**，于是 `many` 那条分支把全库
    LIKE 的结果原样当候选返回 —— 家长搜一个常见姓氏，拿到全校学生的姓名 + 学号。
    这就是「不泄漏存在性」要挡的东西，所以判定必须在**搜的时候**做。
    """
    from evals.identity import resolve

    parent = resolve("parent")
    parent_id = parent["user_id"]

    from app.middleware.scope import RequestScope
    from app.models.database import get_db

    session = next(get_db())
    try:
        allowed = RequestScope(
            parent["role"], parent_id, parent["school_id"], session
        ).student_ids()
    finally:
        session.close()
    probe = _probe_name_outside_scope(allowed)
    assert probe, "库里找不到「匹配多人且全在范围外」的姓名片段，这条守卫没法构造探针"

    captured = {}

    async def fake(student_name: str = ""):
        """Fake tool needing student scope."""
        captured["student_name"] = student_name
        return json.dumps({"ok": True})

    gs = GuardState()
    set_current_identity(parent_id, parent["role"], parent["school_id"])
    try:
        with _registered(fake, {"student_name": "student"}):
            guarded = _make_guarded_tool(fake, gs)
            out = _run(guarded.ainvoke({"student_name": probe}))
    finally:
        set_current_identity("")

    data = json.loads(out)
    assert "multiple_matches" not in data, f"候选泄漏了范围外的学生：{out[:300]}"
    assert captured == {}, "范围外的姓名不该进到工具里"


def test_list_teacher_exams_uses_context_teacher(monkeypatch):
    """真实工具经 guard 包装（agent 实际路径）：无参数调用时回退到
    上下文教师（服务端身份反查账户），列出其任教班级的考试。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models.database as db_mod
    from app.models.database import (
        Account, Base, Class, Grade, School, TeacherClassSubject,
    )
    from agent.tools.ocr_grading import list_teacher_exams

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(School(school_id="sch_hai", name="海中"))
    session.add(Grade(grade_id="g_hai", school_id="sch_hai", name="高一", year=2026))
    session.add(Class(class_id="c_hai", name="一班", grade="高一",
                      grade_id="g_hai", subject="化学"))
    session.add(TeacherClassSubject(id="tcs_hai", teacher_id="teacher_hai",
                                    class_id="c_hai", subject="化学"))
    session.add(Account(account_id="acc_hai", username="hai", role="teacher",
                        teacher_id="teacher_hai", password_hash="x"))
    session.commit()
    monkeypatch.setattr(db_mod, "get_db", lambda: iter([session]))

    gs = GuardState()
    guarded = _make_guarded_tool(list_teacher_exams, gs)
    set_current_teacher("teacher_hai")
    try:
        out = _run(guarded.ainvoke({}))
    finally:
        set_current_teacher("")
    data = json.loads(out)
    assert "error" not in data, f"不应报缺少教师身份: {out[:200]}"
    assert [c["class_id"] for c in data["classes"]] == ["c_hai"]
    session.close()
