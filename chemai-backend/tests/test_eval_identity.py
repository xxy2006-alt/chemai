"""评测身份解析的守卫（ADR-0014）。

评测此前跑在**无身份**下，而那是线上不存在的状态：agent 接缝
（`agent/guard.py`）对收身份参数的工具是 fail-closed 的 —— 没有身份就一律拒绝。
所以「每个 persona 都能解析出真实账号」必须是**会报错**的状态，不能静默降级。

这两条挡的都是已经发生过一次的事故形状：演示数据被整体换掉，写死的账号消失，
症状（场景莫名变红）离原因（没有身份 / 范围为空）很远。
"""
from evals.identity import PERSONAS, resolve


def test_eval_personas_resolve_to_real_accounts():
    """每个 persona 都要解析出真实账号，且角色对得上。"""
    for persona in PERSONAS:
        ident = resolve(persona)
        assert ident["user_id"], f"{persona} 没解析出 user_id：{ident}"
        assert ident["role"], f"{persona} 没解析出 role：{ident}"


def test_eval_identities_have_usable_scope():
    """解析出的身份必须**真的能看见数据**。

    空范围的评测身份不会报错，只会让所有身份类场景被接缝拒掉 —— 看起来像功能坏了，
    实际是评测身份选错了人（比如挑了个没有任教班级的教师）。
    """
    from app.middleware.scope import RequestScope
    from app.models.database import get_db

    session = next(get_db())
    try:
        for persona in PERSONAS:
            ident = resolve(persona)
            scope = RequestScope(ident["role"], ident["user_id"], ident["school_id"], session)
            visible = scope.student_ids()
            assert visible, f"{persona}（{ident['user_id']}）的数据范围是空的，评测量不到东西"
    finally:
        session.close()


def test_eval_student_and_parent_are_the_same_family():
    """tutor（学生）与 parent 两个 persona 要是同一家人。

    否则「家长问自己孩子的报告」这类场景里，家长看到的永远是范围外的孩子 ——
    而那正是 ADR-0014 要封的那条路的反面（范围内那一半），没人替它兜底。
    """
    student = resolve("tutor")
    parent = resolve("parent")

    from app.middleware.scope import RequestScope
    from app.models.database import get_db

    session = next(get_db())
    try:
        scope = RequestScope(parent["role"], parent["user_id"], parent["school_id"], session)
        assert scope.allows_student(student["user_id"]), (
            f"家长 {parent['user_id']} 看不到评测学生 {student['user_id']} —— "
            "两个 persona 不是同一家人，家长场景会全部落在范围外"
        )
    finally:
        session.close()
