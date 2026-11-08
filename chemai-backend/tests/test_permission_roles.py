"""角色行为断言 —— 「角色 A 能 / 角色 B 不能」（阶段 4.6）。

`test_permission_matrix.py` 是**结构守卫**：它只看「端点有没有权限声明」。
本文件是**行为断言**：真的发请求，看授权层放不放行。

约定：
  - 每个断言都是「同一端点，换 token」——同一条路径上角色 A 放行、角色 B 拒绝。
  - 「能」断言的是**授权层放行**（非 401/403），不保证业务成功：调用 LLM 的端点
    在测试里不该被真调，所以取状态码 ≠ 403 作为证据，而不是 == 200。
  - 镜像 app 的 router 基线必须与 `main.py` 一致（见 `_client`）。
    基线漂移由 `test_permission_matrix.py` 的 EXPECTED_DECLARATIONS 兜底。

数据图（照搬 test_request_scope.py 的构造，两校四班）：

    sch1/g1
      c1 化学 ← T_chem 教（也是 S1 所在班）
      c2 数学 ← T_math 教
      c3 化学 ← T_other 教
    sch2/g2
      c4 化学   ← 别校，用来验证不跨校
"""
import pytest
from datetime import date
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import analytics as analytics_mod
from app.api import class_api as class_api_mod
from app.api import diagnosis as diagnosis_mod
from app.api import exam_bank as exam_bank_mod
from app.api import exam as exam_mod
from app.api import class_api as class_api_mod
from app.api import integration as integration_mod
from app.api import memory as memory_mod
from app.api import notification as notification_mod
from app.api import ocr as ocr_mod
from app.api import ocr_sheets as ocr_sheets_mod
from app.api import question as question_mod
from app.api import review as review_mod
from app.api import panel as panel_mod
from app.api import report as report_mod
from app.api import practice as practice_mod
from app.api import user as user_mod
from app.api import practice_wrong as practice_wrong_mod
from app.api.practice_api import wrong_topic as wrong_topic_mod
from app.api import warning as warning_mod
from app.middleware.auth import PermissionChecker, create_access_token
from app.models.database import (
    Base, Class, ExamRecord, Grade, Parent, Question, RecordType, School,
    Student, StudentAnswer, StudentParentBinding, Teacher, TeacherClassSubject, get_db,
)
from app.models.ocr_task import OCRTask


@pytest.fixture
def db_session():
    # TestClient 在独立线程执行端点，内存库必须用 StaticPool 共享同一连接
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
def seeded(db_session):
    db_session.add_all([
        School(school_id="sch1", name="测试中学"),
        School(school_id="sch2", name="隔壁中学"),
        Grade(grade_id="g1", school_id="sch1", name="高一", year=2025),
        Grade(grade_id="g2", school_id="sch2", name="高一", year=2025),
    ])
    db_session.add_all([
        Class(class_id="c1", name="一班", grade="高一", grade_id="g1", subject="化学"),
        Class(class_id="c2", name="二班", grade="高一", grade_id="g1", subject="数学"),
        Class(class_id="c4", name="四班", grade="高一", grade_id="g2", subject="化学"),
    ])
    db_session.add_all([
        # 教师本人 —— class_api 取班主任姓名时要 join 这张表
        Teacher(teacher_id="T_chem", name="化学老师", school_id="sch1", status="approved"),
        Teacher(teacher_id="T_math", name="数学老师", school_id="sch1", status="approved"),
    ])
    db_session.add_all([
        # is_class_teacher 标出班主任 —— 它是班主任的唯一真源（阶段 6.2）
        TeacherClassSubject(id="t1", teacher_id="T_chem", class_id="c1", subject="化学",
                            is_class_teacher=True),
        TeacherClassSubject(id="t2", teacher_id="T_math", class_id="c2", subject="数学"),
    ])
    db_session.add_all([
        Student(student_id="S1", class_id="c1", name="学生一"),
        Student(student_id="S2", class_id="c4", name="学生二"),   # 别校，验证不跨校
    ])
    db_session.add(Parent(parent_id="P1", name="家长一", password_hash="x"))
    db_session.add(StudentParentBinding(
        binding_id="b1", student_id="S1", parent_id="P1",
        bind_code="BIND0001", status="active",
    ))
    # 两人各一条错题 —— 验证「不传 student_id 的全局查询」被收窄到本人
    db_session.add(Question(question_id="q1", content="题一", answer="A"))
    db_session.add_all([
        StudentAnswer(answer_id="a_s1", student_id="S1", question_id="q1", is_correct=False),
        StudentAnswer(answer_id="a_s2", student_id="S2", question_id="q1", is_correct=False),
    ])
    # 两个教师各上传过答题卡 —— 用来验证 /api/ocr/tasks 的身份取自 token
    db_session.add_all([
        OCRTask(task_id="k_chem", teacher_id="T_chem", batch_id="b_chem",
                image_path="/tmp/a.jpg", title="化学答题卡"),
        OCRTask(task_id="k_math", teacher_id="T_math", batch_id="b_math",
                image_path="/tmp/b.jpg", title="数学答题卡"),
    ])
    # c1 的一场考试：用来区分「有 exam:delete 的人」和「没有的人」
    db_session.add(ExamRecord(
        record_id="e1", class_id="c1", name="期中化学",
        type=RecordType.EXAM, exam_date=date(2026, 4, 1),
    ))
    db_session.commit()
    return db_session


@pytest.fixture
def client(db_session):
    """镜像 main.py 的三个 router 基线。改 main.py 的基线时这里要同步。"""
    app = FastAPI()
    app.include_router(
        question_mod.router, prefix="/api/question",
        dependencies=[Depends(PermissionChecker("question", "read"))],
    )
    app.include_router(
        exam_mod.router, prefix="/api/exam",
        dependencies=[Depends(PermissionChecker("exam", "read"))],
    )
    app.include_router(
        exam_bank_mod.router, prefix="/api/exam-bank",
        dependencies=[Depends(PermissionChecker("exam_bank", "read"))],
    )
    # diagnosis.py 在 main.py 里没有 router 基线（逐端点声明）
    app.include_router(diagnosis_mod.router, prefix="/api/diagnosis")
    app.include_router(
        ocr_mod.router, prefix="/api/ocr",
        dependencies=[Depends(PermissionChecker("ocr", "read"))],
    )
    app.include_router(
        ocr_sheets_mod.router, prefix="/api/ocr",
        dependencies=[Depends(PermissionChecker("ocr", "read"))],
    )
    app.include_router(
        warning_mod.router, prefix="/api/warning",
        dependencies=[Depends(PermissionChecker("warning", "read"))],
    )
    app.include_router(
        memory_mod.router, prefix="/api/memory",
        dependencies=[Depends(PermissionChecker("memory", "read"))],
    )
    # notification.py 没有 router 基线 —— 家长端点 get_parent_notifications
    # 走 get_current_parent_id 身份校验，加基线会把家长自己的通知挡掉
    app.include_router(notification_mod.router, prefix="/api/notification")
    # analytics / practice / review 没有 router 基线 —— 前缀下有学生/家长自助端点，
    # 基线会在 allow_self 之前把本人角色挡掉（main.py 里同一处理）。
    app.include_router(analytics_mod.router, prefix="/api/analytics")
    app.include_router(practice_mod.router, prefix="/api/practice")
    app.include_router(practice_wrong_mod.router, prefix="/api/practice")
    app.include_router(wrong_topic_mod.router, prefix="/api/practice/wrong-topic")
    app.include_router(review_mod.router, prefix="/api/review")
    app.include_router(
        class_api_mod.router, prefix="/api/classes",
        dependencies=[Depends(PermissionChecker("class", "read"))],
    )
    # integration.py 没有 router 基线 —— 前缀下有个按 LTI 规范必须公开的 JWKS 端点
    app.include_router(integration_mod.router, prefix="/api/integration")
    # report.py 没有 router 基线（逐端点声明）；users 挂 student:read 基线
    app.include_router(report_mod.router, prefix="/api/report")
    app.include_router(
        user_mod.router, prefix="/api/users",
        dependencies=[Depends(PermissionChecker("student", "read"))],
    )
    app.include_router(
        class_api_mod.router, prefix="/api/classes",
        dependencies=[Depends(PermissionChecker("class", "read"))],
    )
    app.include_router(
        panel_mod.router, prefix="/api/panel",
        dependencies=[Depends(PermissionChecker("analysis", "read"))],
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


def hdr(role, user_id, school_id="sch1"):
    return {"Authorization": f"Bearer {create_access_token(user_id, role, school_id=school_id)}"}


TEACHER = ("teacher", "T_chem")     # 任教 c1
ADMIN = ("admin", "A1")             # 本校全部班级
STUDENT = ("student", "S1")         # 本人
PARENT = ("parent", "P1")           # 本人角色


# ─────────────────────────────────────────────────────────────
# 匿名 / 本人角色：内容生产 router 一律进不来
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/question/kps",
    "/api/exam-bank/historical",
])
def test_content_routers_reject_anonymous(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("role_ctx", [STUDENT, PARENT], ids=["student", "parent"])
@pytest.mark.parametrize("path", [
    "/api/question/kps",
    "/api/exam-bank/historical",
])
def test_content_routers_reject_self_roles(client, role_ctx, path):
    """学生/家长在矩阵里没有任何内容资源键 —— 不是 403 就是被 deny。"""
    r = client.get(path, headers=hdr(*role_ctx))
    assert r.status_code == 403, f"{path} 对 {role_ctx[0]} 返回 {r.status_code}"


def test_teacher_can_read_questions(client, seeded):
    r = client.get("/api/question/kps", headers=hdr(*TEACHER))
    assert r.status_code != 403, "任课教师应当能读题目资源"


# ─────────────────────────────────────────────────────────────
# 数据范围：同一个端点，教师只看得到自己教的班
# ─────────────────────────────────────────────────────────────

def test_admin_can_list_exams_of_any_class_in_school(client, seeded):
    r = client.get("/api/exam/list/c1", headers=hdr(*ADMIN))
    assert r.status_code == 200


def test_teacher_can_list_exams_of_own_class(client, seeded):
    r = client.get("/api/exam/list/c1", headers=hdr(*TEACHER))
    assert r.status_code == 200, "T_chem 教 c1，应当放行"


def test_teacher_cannot_list_exams_of_other_school_class(client, seeded):
    """c4 在 sch2 —— 教师范围只含本校自己教的班。"""
    r = client.get("/api/exam/list/c4", headers=hdr(*TEACHER))
    assert r.status_code == 403


def test_student_cannot_list_exams(client, seeded):
    r = client.get("/api/exam/list/c1", headers=hdr(*STUDENT))
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# 删除留管理员：教师能建能改不能删
# ─────────────────────────────────────────────────────────────

def test_admin_can_delete_exam(client, seeded):
    r = client.delete("/api/exam/e1", headers=hdr(*ADMIN))
    assert r.status_code == 200, "admin 有 exam:delete 且 e1 在范围内"


def test_teacher_cannot_delete_exam(client, seeded):
    r = client.delete("/api/exam/e1", headers=hdr(*TEACHER))
    assert r.status_code == 403, "teacher 的 exam 只有 _CRU —— 删除留管理员"


def test_teacher_cannot_delete_exam_bank_set(client, seeded):
    r = client.delete("/api/exam-bank/exam-sets/set1", headers=hdr(*TEACHER))
    assert r.status_code == 403, "删除题库是 delete 动作，教师没有"


# ─────────────────────────────────────────────────────────────
# 真题库：教师能建能导入（矩阵 2026-09-12 从 _R 提到 _CRU）
# ─────────────────────────────────────────────────────────────

def test_teacher_can_create_exam_bank_set(client, seeded):
    """教师端 ExamPage 建题库走的正是这条 —— 给 _R 会把整页废掉。"""
    r = client.post(
        "/api/exam-bank/exam-sets",
        json={"name": "我的题库"},
        headers=hdr(*TEACHER),
    )
    assert r.status_code != 403, "教师应当能建题库"


def test_student_cannot_create_exam_bank_set(client, seeded):
    r = client.post(
        "/api/exam-bank/exam-sets",
        json={"name": "偷偷建一个"},
        headers=hdr(*STUDENT),
    )
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# 答题卡：任务列表的身份取自 token，不是调用方自报的 teacher_id
# ─────────────────────────────────────────────────────────────

def test_student_cannot_list_ocr_tasks(client, seeded):
    r = client.get("/api/ocr/tasks", headers=hdr(*STUDENT))
    assert r.status_code == 403


def test_teacher_only_sees_own_ocr_tasks(client, seeded):
    r = client.get("/api/ocr/tasks", headers=hdr(*TEACHER))
    assert r.status_code == 200
    assert set(r.json()["batches"]) == {"b_chem"}


def test_teacher_cannot_widen_ocr_tasks_via_query_param(client, seeded):
    """反模式已死：T_chem 传 ?teacher_id=T_math 仍只拿到自己的批次。

    此前该参数留空则返回**所有教师**的任务，是本批次修掉的泄漏。
    """
    r = client.get("/api/ocr/tasks?teacher_id=T_math", headers=hdr(*TEACHER))
    assert r.status_code == 200
    assert set(r.json()["batches"]) == {"b_chem"}, "身份必须取自 token，不看查询参数"


def test_admin_can_filter_ocr_tasks_by_teacher(client, seeded):
    r = client.get("/api/ocr/tasks?teacher_id=T_math", headers=hdr(*ADMIN))
    assert r.status_code == 200
    assert set(r.json()["batches"]) == {"b_math"}


def test_student_cannot_trigger_ocr_recognize(client, seeded):
    """学生没有 ocr:create —— 哪怕文件为空也不该走到端点体里。"""
    r = client.post("/api/ocr/recognize", headers=hdr(*STUDENT))
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# 预警 / 学情记忆 / 通知（阶段 4.6 批次 C）
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/warning/pending",
    "/api/memory/stats",
    "/api/notification/history",
])
def test_batch_c_routers_reject_student(client, seeded, path):
    r = client.get(path, headers=hdr(*STUDENT))
    assert r.status_code == 403


def test_teacher_can_read_warnings(client, seeded):
    r = client.get("/api/warning/pending", headers=hdr(*TEACHER))
    assert r.status_code != 403


def test_teacher_can_read_warnings_of_own_student(client, seeded):
    r = client.get("/api/warning/student/S1", headers=hdr(*TEACHER))
    assert r.status_code == 200, "S1 在 T_chem 教的 c1"


def test_teacher_cannot_read_warnings_of_other_school_student(client, seeded):
    r = client.get("/api/warning/student/S2", headers=hdr(*TEACHER))
    assert r.status_code == 403, "S2 在别校的 c4"


def test_student_cannot_read_warnings_of_own_classmate(client, seeded):
    """S1 是学生 —— 本人角色连 warning:read 都没有。"""
    r = client.get("/api/warning/student/S1", headers=hdr(*STUDENT))
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# 家长通知：用身份守卫而不是矩阵 —— 加基线会把家长自己挡掉
# ─────────────────────────────────────────────────────────────

def test_parent_can_read_own_notifications(client, seeded):
    r = client.get("/api/notification/parent/P1/notifications", headers=hdr(*PARENT))
    assert r.status_code == 200, "家长端点必须保持可达（身份取自 token）"


def test_parent_cannot_read_others_notifications(client, seeded):
    r = client.get("/api/notification/parent/P_other/notifications", headers=hdr(*PARENT))
    assert r.status_code == 403, "路径里的 parent_id 不能伪造"


def test_student_cannot_use_parent_notification_endpoint(client, seeded):
    r = client.get("/api/notification/parent/P1/notifications", headers=hdr(*STUDENT))
    assert r.status_code == 403, "仅家长可访问"


def test_student_can_read_own_notifications(client, seeded):
    """allow_self 放行 + ScopeGuard 收窄到本人 —— 家长端点有对称能力。"""
    r = client.get("/api/notification/student/S1/notifications", headers=hdr(*STUDENT))
    assert r.status_code == 200


def test_student_cannot_read_classmate_notifications(client, seeded):
    """⚠️ allow_self 的契约：守卫测试只看得到「声明存在」，
    这条断言才是在查「契约有没有被遵守」——S1 读 S2 的通知必须被 ScopeGuard 挡下。
    """
    r = client.get("/api/notification/student/S2/notifications", headers=hdr(*STUDENT))
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# 练习 / 复习：学生自助入口（阶段 4.6 批次 D）
# ─────────────────────────────────────────────────────────────

def test_student_can_read_own_practice_tasks(client, seeded):
    r = client.get("/api/practice/student/S1/tasks", headers=hdr(*STUDENT))
    assert r.status_code == 200, "allow_self 放行 + ScopeGuard 收窄到本人"


def test_student_cannot_read_classmate_practice_tasks(client, seeded):
    r = client.get("/api/practice/student/S2/tasks", headers=hdr(*STUDENT))
    assert r.status_code == 403


def test_teacher_cannot_read_other_school_student_practice(client, seeded):
    """S2 在 sch2 的 c4 —— 不在 T_chem 的 c1 范围内。"""
    r = client.get("/api/practice/student/S2/tasks", headers=hdr(*TEACHER))
    assert r.status_code == 403


def test_student_wrong_list_without_param_is_narrowed_to_self(client, seeded):
    """泄漏点：student_id 留空时，这个端点此前返回**所有学生**的错题。"""
    r = client.get("/api/practice/wrong/list", headers=hdr(*STUDENT))
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1, f"只该看到自己的 1 条错题，实际 {body['count']}"


def test_student_wrong_list_rejects_classmate_filter(client, seeded):
    r = client.get("/api/practice/wrong/list?student_id=S2", headers=hdr(*STUDENT))
    assert r.status_code == 403, "不能靠查询参数看同学的错题"


def test_teacher_wrong_list_only_covers_own_scope(client, seeded):
    """T_chem 范围是 c1（含 S1），不含别校的 S2。"""
    r = client.get("/api/practice/wrong/list", headers=hdr(*TEACHER))
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_teacher_can_read_own_scope_wrong_list_by_id(client, seeded):
    r = client.get("/api/practice/wrong/list?student_id=S1", headers=hdr(*TEACHER))
    assert r.status_code == 200


def test_teacher_cannot_read_other_school_wrong_list_by_id(client, seeded):
    r = client.get("/api/practice/wrong/list?student_id=S2", headers=hdr(*TEACHER))
    assert r.status_code == 403


def test_student_can_read_own_review_due(client, seeded):
    r = client.get("/api/review/student/S1/due", headers=hdr(*STUDENT))
    assert r.status_code == 200


def test_student_cannot_read_classmate_review_due(client, seeded):
    r = client.get("/api/review/student/S2/due", headers=hdr(*STUDENT))
    assert r.status_code == 403


def test_parent_can_read_bound_child_practice(client, seeded):
    """家长读绑定学生（S1 已通过 StudentParentBinding 绑到 P1）。"""
    r = client.get("/api/practice/student/S1/tasks", headers=hdr(*PARENT))
    assert r.status_code == 200


def test_parent_cannot_read_unbound_student_practice(client, seeded):
    r = client.get("/api/practice/student/S2/tasks", headers=hdr(*PARENT))
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# 集成配置：仅学校管理员（阶段 4.7）
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("role_ctx", [TEACHER, STUDENT, PARENT], ids=["teacher", "student", "parent"])
def test_non_admin_cannot_read_integration_api_keys(client, seeded, role_ctx):
    """tasks.md 4.7 的验证项：教师 token 调 /api/integration/api-keys → 403。"""
    r = client.get("/api/integration/api-keys", headers=hdr(*role_ctx))
    assert r.status_code == 403


def test_subject_lead_cannot_read_integration_api_keys(client, seeded):
    """学科组长也不行 —— 集成配置是校级管理，不是学科级。"""
    r = client.get("/api/integration/api-keys", headers=hdr("subject_lead", "T_hai"))
    assert r.status_code == 403


def test_admin_can_read_integration_api_keys(client, seeded):
    r = client.get("/api/integration/api-keys", headers=hdr(*ADMIN))
    assert r.status_code != 403


def test_integration_rejects_anonymous(client, seeded):
    assert client.get("/api/integration/api-keys").status_code == 401


# ─────────────────────────────────────────────────────────────
# 班级列表的班主任（阶段 6.2）
# ─────────────────────────────────────────────────────────────

def test_class_list_returns_real_head_teacher(client, seeded):
    """班主任取自 `teacher_class_subject.is_class_teacher`，不是 `classes.teacher_id`。

    那个字段建表时写死 `None`（init_db），所以原实现**班主任恒返回 null、
    `is_class_teacher` 恒为 False**。这条钉住修复后的行为。
    """
    r = client.get("/api/classes", headers=hdr(*ADMIN))
    assert r.status_code == 200
    by_id = {c["class_id"]: c for c in r.json()["classes"]}

    assert by_id["c1"]["teacher_id"] == "T_chem", "c1 的班主任应是 T_chem"
    assert by_id["c1"]["teacher_name"] == "化学老师"
    assert by_id["c1"]["teachers"][0]["is_class_teacher"] is True

    # c2 没有班主任 —— 不能瞎认领
    assert by_id["c2"]["teacher_id"] is None
    assert by_id["c2"]["teachers"][0]["is_class_teacher"] is False


def test_lti_jwks_needs_no_token(client, seeded):
    """LTI 1.3 规范要求平台无鉴权抓取 JWKS —— 不能给它加声明。

    其余 15 个集成端点都限管理员，只有这个例外；真实现 LTI 时别顺手锁上。
    """
    r = client.get("/api/integration/lti/.well-known/jwks.json")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# 数据范围收窄：自报参数不等于「随便填」（round-3 残留）
# ─────────────────────────────────────────────────────────────

def test_warning_pending_is_narrowed_to_own_classes(client, seeded):
    """T_chem 教 c1：待处理预警里只能出现 c1 的学生，别校的 S2 不出现。"""
    from app.models.warning_log import WarningLog
    seeded.add_all([
        WarningLog(warning_id="w_s1", student_id="S1", warning_type="score_drop",
                   level="medium", title="S1 预警", status="pending", content="x"),
        WarningLog(warning_id="w_s2", student_id="S2", warning_type="score_drop",
                   level="medium", title="S2 预警（别校）", status="pending", content="y"),
    ])
    seeded.commit()

    r = client.get("/api/warning/pending", headers=hdr(*TEACHER))
    assert r.status_code == 200
    assert [w["student_id"] for w in r.json()["warnings"]] == ["S1"]


def test_warning_pending_rejects_out_of_scope_class(client, seeded):
    r = client.get("/api/warning/pending?class_id=c4", headers=hdr(*TEACHER))
    assert r.status_code == 403, "c4 是别校的班"


def test_memory_diagnosis_complete_rejects_out_of_scope_student(client, seeded):
    """写学情记忆的 student_id 在请求体里 —— 跨校写必须 403（此前无范围校验）。"""
    r = client.post("/api/memory/diagnosis-complete", headers=hdr(*TEACHER), json={
        "student_id": "S2", "barrier_type": {"concept": 0.5},
        "dominant_barrier": "concept", "weak_kps": ["kp_x"],
    })
    assert r.status_code == 403


def test_learning_plan_generate_rejects_other_student(client, seeded):
    """allow_self 放行学生后端点必须自己收窄 —— 不能生成他人的学习计划。"""
    r = client.post("/api/diagnosis/learning-plan/generate", headers=hdr(*STUDENT), json={
        "student_id": "S2", "barrier_type": "concept",
        "weak_knowledge_points": ["kp_x"],
    })
    assert r.status_code == 403


def test_student_can_list_own_wrong_topic_knowledge_points(client, seeded, monkeypatch):
    """学生端筛薄弱知识点的接口：allow_self 放行 + require_student 收窄到本人。"""
    # 该端点经 wrong_question_trainer 自开会话取错题 —— 收到测试库上
    monkeypatch.setattr("app.services.wrong_question_trainer.get_db", lambda: iter([seeded]))
    r = client.get("/api/practice/wrong-topic/knowledge-points?student_id=S1",
                   headers=hdr(*STUDENT))
    assert r.status_code == 200


def test_student_cannot_list_classmate_wrong_topic_knowledge_points(client, seeded):
    r = client.get("/api/practice/wrong-topic/knowledge-points?student_id=S2",
                   headers=hdr(*STUDENT))
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# 判卷中心的改判/成绩浏览：按考试所属班级收窄
# ─────────────────────────────────────────────────────────────

def test_teacher_can_browse_own_class_submissions(client, seeded):
    r = client.get("/api/ocr/grading/submissions?exam_id=e1", headers=hdr(*TEACHER))
    assert r.status_code == 200, "e1 在 T_chem 教的 c1"


def test_teacher_cannot_browse_other_school_submissions(client, seeded):
    from app.models.database import ExamRecord, RecordType
    seeded.add(ExamRecord(record_id="e4", class_id="c4", name="别校考试", type=RecordType.EXAM))
    seeded.commit()

    r = client.get("/api/ocr/grading/submissions?exam_id=e4", headers=hdr(*TEACHER))
    assert r.status_code == 403, "e4 在别校的 c4"


def test_teacher_can_override_own_class_answer(client, seeded):
    r = client.post("/api/ocr/grading/override", headers=hdr(*TEACHER),
                    json={"answer_id": "a_s1", "is_correct": True, "reason": "改判"})
    assert r.status_code == 200


def test_teacher_cannot_override_other_school_answer(client, seeded):
    r = client.post("/api/ocr/grading/override", headers=hdr(*TEACHER),
                    json={"answer_id": "a_s2", "is_correct": True, "reason": "改判"})
    assert r.status_code == 404, "S2 在别校 —— 不泄漏该作答是否存在"


# ─────────────────────────────────────────────────────────────
# 答题卡判分/保存：批次归属 + 考试班级（自报 id 不算数）
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def ocr_scope_env(seeded, monkeypatch):
    """端点自开会话取批次的库 —— 收到测试库上（与 wrong_topic 同一约定）。"""
    monkeypatch.setattr("app.models.database.get_db", lambda: iter([seeded]))
    return seeded


def test_teacher_cannot_save_to_other_school_exam(client, ocr_scope_env):
    from app.models.database import ExamRecord, RecordType
    ocr_scope_env.add(ExamRecord(record_id="e4", class_id="c4", name="别校考试",
                                 type=RecordType.EXAM))
    ocr_scope_env.commit()

    r = client.post("/api/ocr/grading/save", headers=hdr(*TEACHER),
                    json={"batch_id": "b_chem", "exam_id": "e4"})
    assert r.status_code == 403, "e4 在别校的 c4"


def test_teacher_cannot_save_other_teachers_batch(client, ocr_scope_env):
    r = client.post("/api/ocr/grading/save", headers=hdr(*TEACHER),
                    json={"batch_id": "b_math", "exam_id": "e1"})
    assert r.status_code == 403, "b_math 是 T_math 上传的批次"


def test_teacher_cannot_grade_other_teachers_batch(client, ocr_scope_env):
    r = client.post("/api/ocr/grading/grade", headers=hdr(*TEACHER),
                    json={"batch_id": "b_math", "correct_answers": "1.A"})
    assert r.status_code == 403


def test_teacher_can_save_own_batch_to_own_class_exam(client, ocr_scope_env):
    from app.models.database import Difficulty, Question, QuestionSource, AuditStatus
    from app.models.ocr_task import OCRTask
    ocr_scope_env.add(Question(
        question_id="e1_1", record_id="e1", content="题1", answer="A", options=["A", "B"],
        analysis="", knowledge_points=[], difficulty=Difficulty.MEDIUM,
        source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED))
    ocr_scope_env.add(OCRTask(
        task_id="k_ok", teacher_id="T_chem", batch_id="b_ok", title="我的卡",
        image_path="/tmp/ok.jpg", student_id="S1", student_name="学生一", status="done",
        grading_result={"questions": [{"q_number": 1, "student_answer": "A", "is_correct": True}]},
    ))
    ocr_scope_env.commit()

    r = client.post("/api/ocr/grading/save", headers=hdr(*TEACHER),
                    json={"batch_id": "b_ok", "exam_id": "e1"})
    assert r.status_code == 200, r.text
    assert r.json()["saved"] == 1


def _add_graded_batches(seeded):
    from app.models.database import Teacher
    from app.models.ocr_task import OCRTask
    seeded.add(Teacher(teacher_id="T_away", name="别校老师", school_id="sch2"))
    seeded.add_all([
        OCRTask(task_id="k_chem2", teacher_id="T_chem", batch_id="b_chem",
                image_path="/tmp/c.jpg", status="done",
                grading_result={"questions": [{"q_number": 1, "is_correct": True}]}),
        OCRTask(task_id="k_math2", teacher_id="T_math", batch_id="b_math",
                image_path="/tmp/m.jpg", status="done",
                grading_result={"questions": [{"q_number": 1, "is_correct": True}]}),
        OCRTask(task_id="k_away", teacher_id="T_away", batch_id="b_away",
                image_path="/tmp/a.jpg", status="done",
                grading_result={"questions": [{"q_number": 1, "is_correct": True}]}),
        # 无归属批（上传时自报空 teacher_id）：谁都不该看到
        OCRTask(task_id="k_orphan", teacher_id="", batch_id="b_orphan",
                image_path="/tmp/o.jpg", status="done",
                grading_result={"questions": [{"q_number": 1, "is_correct": True}]}),
    ])
    seeded.commit()


def test_grading_queue_shows_only_own_batches(client, seeded):
    """待确认队列读侧按 token 身份收窄：任课教师只看得到自己上传的批。"""
    _add_graded_batches(seeded)

    r = client.get("/api/ocr/grading/queue", headers=hdr(*TEACHER))
    assert r.status_code == 200
    assert [b["batch_id"] for b in r.json()["pending_confirm"]] == ["b_chem"]


def test_grading_queue_admin_sees_only_own_school_batches(client, seeded):
    """校级管理员限本校：别校教师的批与无归属批都不出现。"""
    _add_graded_batches(seeded)

    r = client.get("/api/ocr/grading/queue", headers=hdr(*ADMIN))
    assert r.status_code == 200
    assert sorted(b["batch_id"] for b in r.json()["pending_confirm"]) == ["b_chem", "b_math"]


# ─────────────────────────────────────────────────────────────
# 报告 / 排课 / 答题卡：新守卫按参数真实语义收窄
# ─────────────────────────────────────────────────────────────

def test_report_exam_mode_allows_own_class_teacher(client, seeded):
    """教师报告端点的路径参数是 exam_record_id 时，按该考试班级收窄（不是按教师 id）。"""
    r = client.get("/api/report/teacher/e1", headers=hdr(*TEACHER))
    assert r.status_code == 200, "e1 在 T_chem 教的 c1"


def test_report_exam_mode_rejects_other_school_exam(client, seeded):
    from app.models.database import ExamRecord, RecordType
    seeded.add(ExamRecord(record_id="e4", class_id="c4", name="别校考试",
                          type=RecordType.EXAM))
    seeded.commit()

    r = client.get("/api/report/teacher/e4", headers=hdr(*TEACHER))
    assert r.status_code == 403, "e4 在别校的 c4"


def test_report_teacher_mode_rejects_other_school_teacher(client, seeded):
    """教师总览模式：A 校管理员不能看 B 校教师（ScopeGuard(kind=teacher) 补了学校维度）。"""
    from app.models.database import Teacher
    seeded.add(Teacher(teacher_id="T_away", name="别校老师", school_id="sch2"))
    seeded.commit()

    assert client.get("/api/report/teacher/T_away", headers=hdr(*ADMIN)).status_code == 403
    assert client.get("/api/report/teacher/T_chem", headers=hdr(*ADMIN)).status_code == 200


def _has_class_row(session, teacher_id, class_id):
    from app.models.database import TeacherClassSubject
    return session.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id,
        TeacherClassSubject.class_id == class_id).count() > 0


def test_assign_classes_rejects_foreign_class_ids(client, seeded):
    """排课不能把外校班级挂给本校教师（TeacherClassSubject 就是范围推导的真源）。"""
    r = client.post("/api/users/teacher/T_chem/assign-classes", headers=hdr(*ADMIN),
                    json=[{"class_id": "c4", "subject": "化学"}])
    assert r.status_code == 403
    assert _has_class_row(seeded, "T_chem", "c4") is False


def test_assign_classes_allows_own_school_class(client, seeded):
    r = client.post("/api/users/teacher/T_chem/assign-classes", headers=hdr(*ADMIN),
                    json=[{"class_id": "c1", "subject": "化学"}])
    assert r.status_code == 200 and _has_class_row(seeded, "T_chem", "c1") is True


def test_teacher_classes_rejects_other_school_teacher(client, seeded):
    from app.models.database import Teacher
    seeded.add(Teacher(teacher_id="T_away", name="别校老师", school_id="sch2"))
    seeded.commit()

    assert client.get("/api/users/teacher/T_away/classes",
                      headers=hdr(*TEACHER)).status_code == 403


def test_ocr_batch_status_rejects_other_teachers_batch(client, seeded):
    r = client.get("/api/ocr/tasks/batch/b_math", headers=hdr(*TEACHER))
    assert r.status_code == 404, "b_math 是 T_math 上传的批次"


def test_ocr_retry_rejects_other_teachers_task(client, seeded):
    r = client.post("/api/ocr/tasks/k_math/retry", headers=hdr(*TEACHER))
    assert r.status_code == 404


def test_ocr_tasks_admin_sees_only_own_school(client, seeded):
    """校级管理员的任务列表限本校（不是「所有学校」）。"""
    from app.models.database import Teacher
    from app.models.ocr_task import OCRTask
    seeded.add(Teacher(teacher_id="T_away", name="别校老师", school_id="sch2"))
    seeded.add(OCRTask(task_id="k_away", teacher_id="T_away", batch_id="b_away",
                       image_path="/tmp/x.jpg", title="别校卡"))
    seeded.commit()

    r = client.get("/api/ocr/tasks", headers=hdr(*ADMIN))
    assert r.status_code == 200
    assert sorted(r.json()["batches"]) == ["b_chem", "b_math"]


def _add_practice_records(seeded):
    """两场练习：p_c1（c1，本校）/ p_c4（c4，别校），各带一道题。"""
    from app.models.database import Difficulty, ExamRecord, Question, QuestionSource, AuditStatus
    seeded.add_all([
        ExamRecord(record_id="p_c1", class_id="c1", name="本校练习",
                   type=RecordType.PRACTICE, exam_date=date(2026, 4, 2)),
        # docx 导出把文件名写进 latin-1 响应头：控制用例用 ASCII 名避开编码限制
        ExamRecord(record_id="p_ascii", class_id="c1", name="practice_ascii",
                   type=RecordType.PRACTICE, exam_date=date(2026, 4, 2)),
        ExamRecord(record_id="p_c4", class_id="c4", name="别校练习",
                   type=RecordType.PRACTICE, exam_date=date(2026, 4, 2)),
    ])
    for qid, rec in (("p_c1_1", "p_c1"), ("p_c4_1", "p_c4"), ("p_ascii_1", "p_ascii")):
        seeded.add(Question(
            question_id=qid, record_id=rec, content="题", answer="A", options=["A", "B"],
            analysis="", knowledge_points=[], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED))
    seeded.commit()
    return seeded


def test_finalize_persists_completed_status(client, seeded, db_session):
    """finalize 的 completed 迁移必须落库（transition 的事务边界归调用方）。"""
    from app.models.database import ExamRecord, ExamStatus, Question, StudentAnswer
    seeded.add(Question(question_id="e1_1", record_id="e1", content="题",
                        answer="A", options=["A", "B"]))
    seeded.add(StudentAnswer(answer_id="a_fin", student_id="S1", question_id="e1_1",
                             exam_record_id="e1", student_answer="A", is_correct=True,
                             confirmed=True))
    exam = seeded.query(ExamRecord).filter_by(record_id="e1").one()
    exam.status = ExamStatus.GRADING
    seeded.commit()

    r = client.post("/api/exam/e1/finalize", headers=hdr(*TEACHER))
    assert r.status_code == 200 and r.json()["status"] == "completed"

    db_session.rollback()          # 模拟请求结束时的未提交回滚：没 commit 就丢
    fresh = db_session.query(ExamRecord).filter_by(record_id="e1").one()
    assert fresh.status == ExamStatus.COMPLETED
    assert fresh.completed_at is not None


def test_practice_submit_rejects_foreign_record(client, seeded):
    seeded = _add_practice_records(seeded)
    r = client.post("/api/practice/submit", headers=hdr(*STUDENT), json={
        "practice_id": "p_c4", "student_id": "S1",
        "answers": [{"question_id": "p_c4_1", "answer": "A"}]})
    assert r.status_code == 403


def test_practice_submit_accepts_own_record(client, seeded):
    seeded = _add_practice_records(seeded)
    r = client.post("/api/practice/submit", headers=hdr(*STUDENT), json={
        "practice_id": "p_c1", "student_id": "S1",
        "answers": [{"question_id": "p_c1_1", "answer": "A"}]})
    assert r.status_code == 200


def test_practice_content_rejects_foreign_record(client, seeded):
    seeded = _add_practice_records(seeded)
    r = client.get("/api/practice/student/S1/practice/p_c4", headers=hdr(*STUDENT))
    assert r.status_code == 404


def test_practice_questions_rejects_foreign_record(client, seeded):
    seeded = _add_practice_records(seeded)
    assert client.get("/api/practice/p_c4/questions", headers=hdr(*TEACHER)).status_code == 403
    assert client.get("/api/practice/p_c1/questions", headers=hdr(*TEACHER)).status_code == 200


def test_question_export_rejects_foreign_record(client, seeded):
    """导出别校试卷/答案被范围守卫挡下（放行路径本身受 docx 响应头编码限制，不在此断言）。"""
    seeded = _add_practice_records(seeded)
    assert client.get("/api/question/export/p_c4", headers=hdr(*TEACHER)).status_code == 403


def test_student_report_rejects_foreign_exam(client, seeded):
    seeded = _add_practice_records(seeded)
    assert client.get("/api/report/student/p_c4/S1", headers=hdr(*TEACHER)).status_code == 403
    assert client.get("/api/report/student/p_c1/S1", headers=hdr(*TEACHER)).status_code == 200


def test_warning_process_is_scoped(client, seeded):
    from app.models.warning_log import WarningLog
    seeded.add_all([
        WarningLog(warning_id="w_s1", student_id="S1", warning_type="score_drop",
                   level="medium", title="本校预警", status="pending", content="x"),
        WarningLog(warning_id="w_s2", student_id="S2", warning_type="score_drop",
                   level="medium", title="别校预警", status="pending", content="y"),
    ])
    seeded.commit()

    r = client.put("/api/warning/w_s2/process", headers=hdr(*TEACHER),
                   json={"action": "ignored"})
    assert r.status_code == 404
    assert seeded.query(WarningLog).filter_by(warning_id="w_s2").one().status == "pending"

    ok = client.put("/api/warning/w_s1/process", headers=hdr(*TEACHER),
                    json={"action": "processed"})
    assert ok.status_code == 200


def test_panel_dashboard_aggregates_are_scoped(client, seeded):
    """教师首页聚合只看自己的班（此前是全库口径）。"""
    from datetime import datetime as _dt
    from app.models.database import Class, Question, Student, StudentAnswer

    seeded.add(Class(class_id="c_own", name="自己的班", grade="高一",
                     grade_id="g1", subject="化学"))
    # 阶段 6.2：`classes.teacher_id` 已删，任课/班主任关系的唯一真源是这张表
    seeded.add(TeacherClassSubject(id="tcs_own", teacher_id="T_chem",
                                   class_id="c_own", subject="化学"))
    seeded.add_all([
        Student(student_id="S_own", class_id="c_own", name="自己的学生"),
        Question(question_id="q_panel", content="题", answer="A"),
    ])
    for aid, sid in (("a_own", "S_own"), ("a_other", "S2")):
        seeded.add(StudentAnswer(answer_id=aid, student_id=sid, question_id="q_panel",
                                 is_correct=False, answered_at=_dt.utcnow()))
    seeded.add_all([
        # 未生效行：判定中 / 待教师确认 —— 既不算成绩也不进待诊断
        StudentAnswer(answer_id="a_own_pending", student_id="S_own", question_id="q_panel",
                      is_correct=False, answered_at=_dt.utcnow(),
                      grade_reason="PENDING_SEMANTIC"),
        StudentAnswer(answer_id="a_own_unconf", student_id="S_own", question_id="q_panel",
                      is_correct=False, answered_at=_dt.utcnow(), confirmed=False),
    ])
    seeded.commit()

    r = client.get("/api/panel/dashboard/T_chem", headers=hdr(*TEACHER))
    assert r.status_code == 200
    data = r.json()["data"]
    # 2 = c1 的 S1 + c_own 的 S_own（两条各 1 份，且都是生效行）。
    # 合并说明：这数原先是 1 —— 旧口径只认 `classes.teacher_id`，看不到 c1；
    # 阶段 6.2 改用 teacher_class_subject 后 T_chem 的可见班是 c1 ∪ c_own，两者都在范围内。
    # 别校 S2（c4）与未生效的两行（判定中 / 待确认）仍然都不计入。
    assert data["weekly_practice"] == 2
    assert data["completion_rate"] == 10         # 2 份 /（2 学生 × 10）


def test_student_detail_stats_count_only_effective_rows(client, seeded):
    """学情详情只认生效行：判定中/待确认的作答不进练习数、正确率与薄弱点。"""
    from app.models.database import (
        Difficulty, Question, QuestionSource, StudentAnswer, AuditStatus,
    )
    seeded.add_all([
        Question(question_id="q_eff", content="题", answer="A", options=None, analysis="",
                 knowledge_points=["kp_eff"], difficulty=Difficulty.MEDIUM,
                 source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED),
        Question(question_id="q_pend", content="题", answer="A", options=None, analysis="",
                 knowledge_points=["kp_pend"], difficulty=Difficulty.MEDIUM,
                 source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED),
    ])
    seeded.add_all([
        StudentAnswer(answer_id="a_eff", student_id="S1", question_id="q_eff",
                      student_answer="B", is_correct=False, confirmed=True),
        StudentAnswer(answer_id="a_pend", student_id="S1", question_id="q_pend",
                      student_answer="B", is_correct=False, confirmed=True,
                      grade_reason="PENDING_SEMANTIC"),
        StudentAnswer(answer_id="a_unconf", student_id="S1", question_id="q_pend",
                      student_answer="B", is_correct=False, confirmed=False),
    ])
    seeded.commit()

    r = client.get("/api/panel/class/c1/student/S1", headers=hdr(*TEACHER))
    assert r.status_code == 200
    body = r.json()
    assert body["total_exercises"] == 2          # seeded 里 S1 的生效错答 + 本条 q_eff
    assert body["weak_knowledge_points"] == ["kp_eff"]
    assert "kp_pend" not in body["weak_knowledge_points"]


def test_class_create_rejects_foreign_grade(client, seeded):
    r = client.post("/api/classes", headers=hdr(*ADMIN),
                    json={"name": "越界班", "grade_id": "g2"})
    assert r.status_code == 403


def test_class_create_allows_own_grade(client, seeded):
    r = client.post("/api/classes", headers=hdr(*ADMIN),
                    json={"name": "本校班", "grade_id": "g1"})
    assert r.status_code == 200


def test_class_update_rejects_foreign_grade(client, seeded):
    r = client.put("/api/classes/c1", headers=hdr(*ADMIN), json={"grade_id": "g2"})
    assert r.status_code == 403


def test_ocr_stats_rejects_foreign_class(client, seeded):
    """整卷粘贴统计是跨租户写路径：class_id / student_id 都得在范围内。"""
    r = client.post("/api/ocr/stats", headers=hdr(*TEACHER), json={
        "class_id": "c4", "exam_name": "越界卷", "exam_date": "2026-04-02",
        "questions": [{"number": 1, "content": "题", "correct_answer": "A",
                       "knowledge_points": []}],
        "ocr_results": [{"student_id": "S2", "answers": {"1": "A"}}],
    })
    assert r.status_code == 403


def test_ocr_stats_rejects_foreign_students(client, seeded):
    r = client.post("/api/ocr/stats", headers=hdr(*TEACHER), json={
        "class_id": "c1", "exam_name": "本校卷", "exam_date": "2026-04-02",
        "questions": [{"number": 1, "content": "题", "correct_answer": "A",
                       "knowledge_points": []}],
        "ocr_results": [{"student_id": "S2", "answers": {"1": "A"}}],
    })
    assert r.status_code == 403


def test_ocr_stats_keeps_unjudged_subjective_pending(client, seeded, db_session):
    """整卷粘贴：当场判不出的主观题落待判定行、不算答错，交扫描作业重判（ADR-0013）。"""
    from app.models.database import StudentAnswer
    from app.services.grading_center import PENDING_REASON

    r = client.post("/api/ocr/stats", headers=hdr(*TEACHER), json={
        "class_id": "c1", "exam_name": "粘贴卷", "exam_date": "2026-04-02",
        "questions": [{"number": 1, "content": "简答", "correct_answer": "增大",
                       "knowledge_points": ["kp1"], "max_score": 6}],
        "ocr_results": [{"student_id": "S1", "answers": {"1": "变大"}}],
    })
    assert r.status_code == 200
    assert r.json()["question_stats"][0]["error_count"] == 0   # 判定中不是答错

    row = db_session.query(StudentAnswer).filter(
        StudentAnswer.student_id == "S1",
        StudentAnswer.exam_record_id.like("exam_%"),
    ).one()
    assert row.grade_reason == PENDING_REASON
    assert row.is_correct is False


def test_ocr_stats_does_not_count_missing_key_as_wrong(client, seeded, db_session):
    """缺标准答案（未判）与判定中同口径：不记错、不进错误名单、不进知识点错误。"""
    r = client.post("/api/ocr/stats", headers=hdr(*TEACHER), json={
        "class_id": "c1", "exam_name": "无答案卷", "exam_date": "2026-04-02",
        "questions": [{"number": 1, "content": "简答", "correct_answer": "",
                       "knowledge_points": ["kp_nokey"], "max_score": 6}],
        "ocr_results": [{"student_id": "S1", "answers": {"1": "变大"}}],
    })
    assert r.status_code == 200
    stat = r.json()["question_stats"][0]
    assert stat["error_count"] == 0            # 未判的题不是每个学生都答错
    assert stat["error_rate"] == 0
    assert stat["wrong_students"] == []


def test_practice_tasks_hide_other_students_personal_record(client, seeded, db_session):
    """逐生布置的练习（question_stats.student_id 标归属）只对本人可见/可答。"""
    from app.models.database import ExamRecord, RecordType
    db_session.add(ExamRecord(
        record_id="p_s2", class_id="c1", name="自适应练习-学生二",
        type=RecordType.PRACTICE, question_stats={"student_id": "S2"}, present_students=1,
    ))
    db_session.commit()

    tasks = client.get("/api/practice/student/S1/tasks", headers=hdr(*STUDENT))
    assert tasks.status_code == 200
    assert "p_s2" not in [t["practice_id"] for t in tasks.json()["tasks"]]

    # 也别想绕开列表直接提交到别人的卷子
    submitted = client.post("/api/practice/submit", headers=hdr(*STUDENT), json={
        "practice_id": "p_s2", "student_id": "S1",
        "answers": [{"question_id": "q1", "answer": "A"}]})
    assert submitted.status_code == 403

    assert client.get("/api/practice/student/S1/practice/p_s2",
                      headers=hdr(*STUDENT)).status_code == 404


def test_student_and_parent_self_dashboards_stay_reachable(client, seeded):
    """analytics 逐端点声明权限：本人自助看板不被员工基线挡在端点之前（回归）。"""
    assert client.get("/api/analytics/dashboard/student/S1",
                      headers=hdr(*STUDENT)).status_code == 200
    assert client.get("/api/analytics/dashboard/parent/S1",
                      headers=hdr(*PARENT)).status_code == 200
    assert client.get("/api/analytics/student/S1/personal-stats",
                      headers=hdr(*STUDENT)).status_code == 200
    # 班级级端点仍走员工权限矩阵
    assert client.get("/api/analytics/class/c1/overview",
                      headers=hdr(*STUDENT)).status_code == 403
    # 他人看板仍被 ScopeGuard 挡住
    assert client.get("/api/analytics/dashboard/student/S2",
                      headers=hdr(*STUDENT)).status_code == 403


def test_warning_check_scoped_to_caller_classes(client, seeded, db_session, monkeypatch):
    """手动触发预警检查只作用于调用者范围内的学生（不替别校学生建预警、发家长通知）。"""
    from datetime import datetime, timedelta
    import app.services.early_warning as ew
    import app.services.notification_service as nsvc
    from app.models.warning_log import WarningLog

    monkeypatch.setattr(ew, "get_db", lambda: iter([db_session]))
    monkeypatch.setattr(nsvc.notification_service, "send_warning_notification",
                        lambda **kw: 0)      # 家长外发不是本用例的面

    old = datetime.utcnow() - timedelta(days=10)
    for sid in ("S1", "S2"):
        row = db_session.query(Student).filter_by(student_id=sid).one()
        row.created_at = old
        row.last_exercise_at = None
    db_session.commit()

    r = client.post("/api/warning/check", headers=hdr(*TEACHER))
    assert r.status_code == 200
    assert [w.student_id for w in db_session.query(WarningLog).all()] == ["S1"]


def test_diagnosis_plan_ignores_pending_answers(client, seeded, db_session):
    """学情读侧只认生效行：判定中的行不进正确率分母、不进薄弱知识点。"""
    from app.models.database import Question, StudentAnswer
    from app.services.grading_center import PENDING_REASON
    db_session.add(Question(question_id="q_pending", content="待判定题", answer="增大",
                            knowledge_points=["kp_pending"]))
    db_session.add(StudentAnswer(
        answer_id="a_s1_pending", student_id="S1", question_id="q_pending",
        student_answer="变大", is_correct=False, confirmed=True,
        grade_reason=PENDING_REASON,
    ))
    db_session.commit()

    r = client.get("/api/diagnosis/plan/S1", headers=hdr(*STUDENT))
    assert r.status_code == 200
    data = r.json()["data"]
    # seeded 只有 a_s1 一条生效行；待判定行不计入分母
    assert data["total_answers"] == 1
    assert "kp_pending" not in data["weak_knowledge_points"]


def test_ocr_upload_owner_comes_from_token(client, seeded, db_session, monkeypatch, tmp_path):
    """上传批次的归属取 token 身份，不采信表单里自报的 teacher_id。"""
    from app.api import ocr_sheets as ocr_sheets_mod
    monkeypatch.setattr(ocr_sheets_mod, "UPLOAD_DIR", str(tmp_path))
    from app.models.ocr_task import OCRTask

    r = client.post("/api/ocr/tasks/batch", headers=hdr(*ADMIN),
                    data={"teacher_id": "T_away"},
                    files={"files": ("card.jpg", b"fake-image", "image/jpeg")})
    assert r.status_code == 200
    task = db_session.query(OCRTask).filter_by(batch_id=r.json()["batch_id"]).one()
    assert task.teacher_id == "A1"          # token 身份，不是表单里的 T_away


def test_student_report_marks_pending_as_pending(client, seeded):
    """判定中/待确认的作答不算答错：不拉低分数、不回显标准答案（ADR-0013）。"""
    from app.models.database import Difficulty, Question, QuestionSource, StudentAnswer, AuditStatus
    for qid, content in (("e1_1", "选择"), ("e1_2", "主观"), ("e1_3", "待确认")):
        seeded.add(Question(
            question_id=qid, record_id="e1", content=content, answer="A", options=["A", "B"],
            analysis="", knowledge_points=[], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED))
    seeded.add_all([
        StudentAnswer(answer_id="a_r_ok", student_id="S1", question_id="e1_1",
                      exam_record_id="e1", student_answer="A", is_correct=True, confirmed=True),
        StudentAnswer(answer_id="a_r_pending", student_id="S1", question_id="e1_2",
                      exam_record_id="e1", student_answer="x", is_correct=False,
                      confirmed=True, grade_reason="PENDING_SEMANTIC"),
        StudentAnswer(answer_id="a_r_unconf", student_id="S1", question_id="e1_3",
                      exam_record_id="e1", student_answer="y", is_correct=False,
                      confirmed=False),
    ])
    seeded.commit()

    r = client.get("/api/report/student/e1/S1", headers=hdr(*STUDENT))
    assert r.status_code == 200
    body = r.json()
    assert body["pending_count"] == 2
    assert body["your_score"] == 100.0           # 只算已生效的那一道（对了）

    by_q = {q["question_number"]: q for q in body["questions"]}
    assert by_q["2"]["pending"] is True
    assert by_q["2"]["correct_answer"] == ""     # 判定中不回显标准答案
    assert "判定中" in by_q["2"]["encouragement"]
    assert by_q["3"]["pending"] is True
    assert by_q["1"]["pending"] is False


def test_student_report_all_pending_shows_no_score(client, seeded):
    """整卷都判定中：不给 0 分成绩、不给「答错」评价（与逐题 pending 自洽）。"""
    from app.models.database import Difficulty, Question, QuestionSource, StudentAnswer, AuditStatus
    seeded.add(Question(question_id="e1_p1", record_id="e1", content="主观", answer="A",
                        options=None, analysis="", knowledge_points=[],
                        difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
                        audit_status=AuditStatus.PASSED))
    seeded.add(StudentAnswer(answer_id="a_r_all_pending", student_id="S1", question_id="e1_p1",
                             exam_record_id="e1", student_answer="x", is_correct=False,
                             confirmed=False))
    seeded.commit()

    r = client.get("/api/report/student/e1/S1", headers=hdr(*STUDENT))
    assert r.status_code == 200
    body = r.json()
    assert body["pending_count"] == 1
    assert body["your_score"] is None            # 0 分是误导：没有成绩可呈现
    assert "判定中" in body["summary"]
    assert "不要气馁" not in body["summary"]


def test_practice_history_excludes_pending_rows(client, seeded):
    """练习历史正确率只算生效行，待判定单独计数。"""
    from app.models.database import StudentAnswer
    seeded = _add_practice_records(seeded)
    seeded.add_all([
        StudentAnswer(answer_id="a_h_ok", student_id="S1", question_id="p_c1_1",
                      exam_record_id="p_c1", student_answer="A", is_correct=True,
                      confirmed=True),
        StudentAnswer(answer_id="a_h_pending", student_id="S1", question_id="p_c1_1",
                      exam_record_id="p_c1", student_answer="x", is_correct=False,
                      grade_reason="缺少标准答案（未判）"),
    ])
    seeded.commit()

    r = client.get("/api/practice/history/S1", headers=hdr(*STUDENT))
    assert r.status_code == 200
    entry = next(h for h in r.json()["history"] if h["practice_id"] == "p_c1")
    assert entry["total_questions"] == 1      # 未判的不算
    assert entry["correct_count"] == 1
    assert entry["accuracy"] == 1.0
    assert entry["pending_count"] == 1
