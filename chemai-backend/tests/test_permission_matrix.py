"""权限矩阵守卫 —— 默认拒绝（ADR-0009）。

规则：每个 /api/ 端点必须满足三者之一——

  1. **带权限声明**：依赖树里有 `PermissionChecker`（router 级或端点级均可）
  2. **是公开端点**：命中 `main.PUBLIC_PREFIXES`（登录本身、探活）
  3. **在 BACKLOG 里**：阶段 4 尚未迁移的 router

BACKLOG 是**只减不增**的迁移待办。迁移完一个 router 就把它从这里移除，
此后该 router 的任何新端点都必须带声明 —— 漏了这条测试就红。

参考实现（`REFERENCE_ROUTERS`）是已完成迁移的 router，不享受 BACKLOG 豁免，
用作阶段 4 逐个迁移时的模板。
"""
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import PUBLIC_PREFIXES, app
from app.middleware.auth import (
    ALL_ROLES, MENUS, ROLE_LABELS, ROLE_PERMISSIONS, SELF_ROLES, PermissionChecker,
    can, create_access_token, menus_for, permissions_for, role_label,
)


# 阶段 4 待迁移的 router 前缀。**只减不增。**
# 阶段 4.7 完成 —— **空集**。至此每个 /api/ 端点要么带权限声明、要么是公开端点，
# 没有任何前缀还享受豁免。此后新增端点漏声明会被守卫直接拦下。
BACKLOG: set[str] = set()

# 已完整迁移的 router —— 每个端点都必须带声明
REFERENCE_ROUTERS = (
    "/api/grades",
    "/api/school",
    "/api/teacher-applications",
    "/api/users",          # 阶段 4.2
    "/api/parent",         # 阶段 4.3（login/register 为公开端点，由 PUBLIC_PREFIXES 豁免）
    "/api/classes",        # 阶段 4.4
    "/api/analytics",      # 阶段 4.5a
    "/api/panel",          # 阶段 4.5a
    "/api/report",         # 阶段 4.5b
    "/api/diagnosis",      # 阶段 4.5b
    "/api/logs",           # 阶段 4.6
    "/api/knowledge",      # 阶段 4.6
    "/api/workspace",      # 阶段 4.6
    "/api/question",       # 阶段 4.6 批次 A
    "/api/exam",           # 阶段 4.6 批次 A
    "/api/exam-bank",      # 阶段 4.6 批次 A
    "/api/ocr",            # 阶段 4.6 批次 B（ocr.py + ocr_sheets.py 同一前缀）
    "/api/warning",        # 阶段 4.6 批次 C
    "/api/memory",         # 阶段 4.6 批次 C
    "/api/notification",   # 阶段 4.6 批次 C（parent 端点靠 get_current_parent_id 声明）
    "/api/practice",       # 阶段 4.6 批次 D（学生自助：allow_self + ScopeGuard）
    "/api/review",         # 阶段 4.6 批次 D
    "/api/auth",           # 阶段 4.6：白名单收窄，login/refresh/apply 公开、me/logout 走身份守卫
    "/api/agent",          # 阶段 4.6 批次 E（会话归属表 + allow_self）
    "/api/integration",    # 阶段 4.7（15 个限管理员 + JWKS 公开）
)


# 已校验身份、由端点自行判定数据范围的依赖（本人角色端点用）。
# 它们不走资源矩阵 —— ADR-0008 把 student/parent 划在矩阵之外，
# 但同样要求「身份取自 token 而非调用方自报」。
IDENTITY_GUARDS = ("get_current_parent_id", "get_current_user")


def _declared_permission(route: APIRoute):
    """在依赖树中查找授权声明，返回 (resource, action) 或 None。

    认两种声明：
      - `PermissionChecker(资源, 动作)` —— 员工角色走资源矩阵
      - `get_current_parent_id` / `get_current_user` —— 本人角色走身份校验

    router 级声明（include_router(dependencies=[...])）和端点级声明都会出现在
    这棵依赖树里，所以一个函数就能覆盖两种声明方式。
    """
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        call = dep.call
        if isinstance(call, PermissionChecker):
            return (call.resource, call.action)
        if getattr(call, "__name__", "") in IDENTITY_GUARDS:
            return (f"identity:{call.__name__}", "")
        stack.extend(dep.dependencies)
    return None


def _api_routes():
    return [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/")]


def _is_public(path: str) -> bool:
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


def _in_backlog(path: str) -> bool:
    return any(path.startswith(b) for b in BACKLOG)


# ─────────────────────────────────────────────────────────────
# 机制：router 级声明确实生效
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def mini_app():
    """最小应用：一个 router，权限声明只挂在 router 级，端点上没有任何装饰。"""
    router = APIRouter()

    @router.get("/ping")
    async def ping():
        return {"ok": True}

    application = FastAPI()
    application.include_router(
        router,
        prefix="/t",
        dependencies=[Depends(PermissionChecker("school", "create"))],
    )
    return application


def _signed_in(client, role):
    return client.get(
        "/t/ping",
        headers={"Authorization": f"Bearer {create_access_token('u1', role)}"},
    )


def test_router_level_check_rejects_anonymous(mini_app):
    assert TestClient(mini_app).get("/t/ping").status_code == 401


def test_router_level_check_allows_permitted_role(mini_app):
    # admin 拥有 school:create
    assert _signed_in(TestClient(mini_app), "admin").status_code == 200


def test_router_level_check_denies_unpermitted_role(mini_app):
    # teacher 只有 school:read，没有 school:create
    assert _signed_in(TestClient(mini_app), "teacher").status_code == 403


def test_router_level_check_denies_unknown_role(mini_app):
    assert _signed_in(TestClient(mini_app), "not_a_role").status_code == 403


def test_router_level_declaration_is_discoverable():
    """守卫靠反射依赖树来发现声明 —— 这条钉住那个反射确实可行。"""
    router = APIRouter()

    @router.get("/x")
    async def x():
        return {}

    application = FastAPI()
    application.include_router(
        router,
        prefix="/t",
        dependencies=[Depends(PermissionChecker("grade", "read"))],
    )
    route = next(
        r for r in application.routes
        if isinstance(r, APIRoute) and r.path == "/t/x"
    )
    assert _declared_permission(route) == ("grade", "read")


# ─────────────────────────────────────────────────────────────
# 参考实现：已迁移的 router 必须 100% 带声明
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("prefix", REFERENCE_ROUTERS)
def test_reference_router_is_fully_declared(prefix):
    routes = [r for r in _api_routes() if r.path.startswith(prefix)]
    assert routes, f"{prefix} 下没有找到任何端点"

    # 公开端点（登录/注册）天然无法声明权限 —— 它们发生在拿到 token 之前
    missing = [
        r.path for r in routes
        if _declared_permission(r) is None and not _is_public(r.path)
    ]
    assert not missing, f"{prefix} 下这些端点缺少权限声明: {missing}"


# ─────────────────────────────────────────────────────────────
# 完整性守卫：BACKLOG 之外不允许有未声明的端点
# ─────────────────────────────────────────────────────────────

def test_no_undeclared_endpoint_outside_backlog():
    offenders = [
        f"{sorted(r.methods)} {r.path}"
        for r in _api_routes()
        if _declared_permission(r) is None
        and not _is_public(r.path)
        and not _in_backlog(r.path)
    ]
    assert not offenders, (
        "以下端点既没有权限声明，也不在 BACKLOG 里：\n  "
        + "\n  ".join(sorted(offenders))
        + "\n\n新端点必须声明权限；若整个 router 尚未迁移，"
        "请把它的前缀加入 BACKLOG（并做好只减不增的打算）。"
    )


def test_backlog_only_contains_known_prefixes():
    """BACKLOG 里不该有拼错或已不存在的 router 前缀 —— 防止它悄悄失效。

    这条会在 router 被重命名/删除后变红，提醒同步清理 BACKLOG。
    """
    live = {"/".join(r.path.split("/")[:3]) for r in _api_routes() if r.path.count("/") >= 2}
    stale = {
        b for b in BACKLOG
        if not any(p.startswith(b) or b.startswith(p) for p in live)
    }
    assert not stale, f"BACKLOG 里这些前缀已不存在: {sorted(stale)}"


def test_fully_declared_routers_are_not_in_backlog():
    """已经 100% 声明的 router 不该还赖在 BACKLOG 里 —— backlog 只减不增。"""
    for b in sorted(BACKLOG):
        routes = [r for r in _api_routes() if r.path.startswith(b)]
        if not routes:
            continue
        if all(_declared_permission(r) is not None for r in routes):
            pytest.fail(
                f"{b} 下所有 {len(routes)} 个端点都已声明权限，"
                f"请把它从 BACKLOG 移除（BACKLOG 只减不增）"
            )


# ─────────────────────────────────────────────────────────────
# 迁移语义：声明必须落在预期的资源/动作上
# ─────────────────────────────────────────────────────────────
# 完整性守卫只能看到「有没有声明」，看不到「声明成了什么」——
# 把 router 基线误写成 update、把写操作漏成 read，上面那些守卫都是绿的。
# 这张表钉住每个 router 的**基线与关键端点覆盖**（不是全部端点：
# 每个 router 取基线一个 + 每个非 read 动作一个，够抓住漂移）。
EXPECTED_DECLARATIONS = [
    # 阶段 4.6 批次 A —— 内容生产：任课教师能出题建考试，删除留管理员
    ("GET", "/api/question/kps", ("question", "read")),
    ("POST", "/api/question/generate", ("question", "create")),
    ("POST", "/api/question/{question_id}/approve", ("question", "update")),
    ("GET", "/api/exam/list/{class_id}", ("exam", "read")),
    ("POST", "/api/exam/create", ("exam", "create")),
    ("PUT", "/api/exam/{exam_id}", ("exam", "update")),
    ("DELETE", "/api/exam/{exam_id}", ("exam", "delete")),
    ("GET", "/api/exam-bank/historical", ("exam_bank", "read")),
    ("POST", "/api/exam-bank/import-questions", ("exam_bank", "create")),
    ("DELETE", "/api/exam-bank/exam-sets/{set_id}", ("exam_bank", "delete")),
    # 阶段 4.6 批次 B —— OCR 答题卡（ocr.py 与 ocr_sheets.py 同一前缀）
    ("GET", "/api/ocr/tasks", ("ocr", "read")),
    ("GET", "/api/ocr/services/status", ("ocr", "read")),
    ("POST", "/api/ocr/recognize", ("ocr", "create")),
    ("POST", "/api/ocr/tasks/batch", ("ocr", "create")),
    ("POST", "/api/ocr/grading/grade", ("ocr", "create")),
    # 阶段 4.6 批次 C —— 通知 / 预警 / 学情记忆
    ("GET", "/api/warning/pending", ("warning", "read")),
    ("PUT", "/api/warning/{warning_id}/process", ("warning", "update")),
    ("GET", "/api/memory/stats", ("memory", "read")),
    ("POST", "/api/notification/send", ("notification", "create")),
    ("GET", "/api/notification/history", ("notification", "read")),
    ("DELETE", "/api/notification/{notification_id}", ("notification", "delete")),
    # 阶段 4.6 批次 D —— 学生自助入口（allow_self 在声明里体现不出来，
    # 但资源/动作要对；契约是否被遵守由 test_permission_roles.py 查）
    ("GET", "/api/practice/student/{student_id}/tasks", ("practice", "read")),
    ("POST", "/api/practice/assign", ("practice", "create")),
    ("GET", "/api/practice/wrong/list", ("practice", "read")),
    ("GET", "/api/review/student/{student_id}/due", ("review", "read")),
    ("POST", "/api/review/submit", ("review", "update")),
    # 阶段「矩阵动作扩展」—— 写端点不再借 read 把门
    ("POST", "/api/diagnosis/run-llm/{exam_record_id}", ("analysis", "create")),
    ("PUT", "/api/diagnosis/override/{student_id}", ("analysis", "update")),
    ("PUT", "/api/diagnosis/config/{teacher_id}", ("analysis", "update")),
    ("GET", "/api/diagnosis/config/{teacher_id}", ("analysis", "read")),   # 读的仍是读
    ("POST", "/api/report/send-to-students/{exam_record_id}", ("analysis", "create")),
    ("POST", "/api/memory/diagnosis-complete", ("memory", "create")),
    ("POST", "/api/warning/check", ("warning", "create")),
    ("PUT", "/api/warning/{warning_id}/process", ("warning", "update")),
    ("POST", "/api/review/create", ("review", "create")),
    ("POST", "/api/workspace/mkdir", ("workspace", "create")),
    ("GET", "/api/workspace/dirs", ("workspace", "read")),
    # 阶段 4.6 —— auth 白名单收窄后，这两个走身份守卫（不是公开端点）
    ("GET", "/api/auth/me", ("identity:get_current_user", "")),
    ("POST", "/api/auth/logout", ("identity:get_current_user", "")),
    # 阶段 4.6 批次 E —— agent 会话（归属表是真正的作用域，角色只区分能否用功能）
    ("POST", "/api/agent/chat/new", ("agent", "create")),
    ("POST", "/api/agent/chat/langgraph/stream", ("agent", "create")),
    ("GET", "/api/agent/chat/history/{thread_id}", ("agent", "read")),
    ("DELETE", "/api/agent/chat/conversations/{thread_id}", ("agent", "delete")),
    ("POST", "/api/agent/upload", ("agent", "create")),
    # 阶段 4.7 —— 集成配置：15 个限管理员，JWKS 按 LTI 规范公开
    ("GET", "/api/integration/api-keys", ("integration", "read")),
    ("DELETE", "/api/integration/api-keys/{key_id}", ("integration", "delete")),
    ("POST", "/api/integration/webhooks", ("integration", "create")),
    ("GET", "/api/integration/sftp/config", ("integration", "read")),
]


# ─────────────────────────────────────────────────────────────
# 阶段 0.1 / 0.5：角色清单与矩阵完整性
# ─────────────────────────────────────────────────────────────

def test_role_enum_is_the_single_source_of_truth():
    """7 个角色只有一份清单 —— 其它地方的角色集合都必须与 `Role` 一致。

    此前角色集合散在 ROLE_PERMISSIONS 的键、ROLE_LABELS 的键、SELF_ROLES、
    STAFF_ROLES 好几处，加一个角色要改四五处且没有东西提醒你漏了哪处。
    """
    assert len(ALL_ROLES) == 7, f"角色应当是 7 个，实际 {len(ALL_ROLES)}"
    assert len(set(ALL_ROLES)) == 7, "角色值有重复"
    assert set(ROLE_LABELS) == set(ALL_ROLES), "ROLE_LABELS 与 Role 枚举对不上"
    assert set(SELF_ROLES) <= set(ALL_ROLES), "SELF_ROLES 里有枚举之外的角色"
    assert set(ROLE_PERMISSIONS) <= set(ALL_ROLES), (
        f"矩阵里有枚举之外的角色: {set(ROLE_PERMISSIONS) - set(ALL_ROLES)}"
    )


def test_every_declared_resource_exists_in_the_matrix():
    """端点里声明的资源，矩阵里必须有人拥有 —— 否则那组端点**谁都进不去**。

    拼错一个资源名（`exam_bank` 写成 `exambank`）不会报错，只会让整组端点
    静默变成 403。这条把它变成红灯。
    """
    known = {res for perms in ROLE_PERMISSIONS.values() for res in perms}
    unknown = {}
    for route in _api_routes():
        for c in _all_checkers(route):
            if c.resource not in known:
                unknown.setdefault(c.resource, []).append(route.path)
    assert not unknown, (
        "这些资源键在矩阵里没有任何角色拥有（拼错了？）：\n  "
        + "\n  ".join(f"{res} ← {', '.join(paths[:3])}" for res, paths in unknown.items())
    )


# 「动词是写、语义确实是读」的端点 —— 显式登记，只减不增。
# 新条目出现说明有人又拿 read 给一个写端点把门（`/api/logs` 就是这么埋的洞）。
WRITE_VERBS_THAT_ARE_READS = {
    # 查询类：只是用 POST 传复杂条件，不改任何状态
    "POST /api/question/search",
    "POST /api/question/similar",
    "POST /api/question/manual/select",
    "POST /api/question/audit",           # 调 LLM 审核，只返回报告、不落库
    # 连接测试类：拨一下看通不通，不改状态
    "POST /api/integration/lms/test",
    "POST /api/integration/webhooks/test",
    "POST /api/integration/sftp/test",
}


def test_write_endpoints_are_not_gated_by_read_alone():
    """写动词（POST/PUT/PATCH/DELETE）的端点，不能只用 `read` 把关。

    这是「借读权限当写门」那一类问题的守卫 —— 它们能拦住角色，但语义是错的：
    「read 权限能触发一次全量 LLM 诊断 / 覆盖学生的诊断结果 / 写文件」。
    害处不在今天（这些端点大多零调用方），在于**后来人照着矩阵做判断会得出错误结论**。

    确实只读的写动词端点（查询用 POST 传复杂条件、连接测试）登记进
    `WRITE_VERBS_THAT_ARE_READS`，两个方向都校验（漏登记会红，条目失效也会红）。
    """
    suspects = set()
    for route in _api_routes():
        methods = {m for m in route.methods if m not in ("HEAD", "OPTIONS")}
        if not methods or methods <= {"GET"}:
            continue
        checkers = _all_checkers(route)
        if not checkers:
            continue                      # 公开端点 / 身份守卫端点，不适用
        if all(c.action == "read" for c in checkers):
            suspects.add(f"{sorted(methods)[0]} {route.path}")

    unexpected = sorted(suspects - WRITE_VERBS_THAT_ARE_READS)
    assert not unexpected, (
        "这些写动词的端点只用 `read` 把门（要么给个真写动作，要么登记进 "
        "WRITE_VERBS_THAT_ARE_READS 说明它确实只读）：\n  " + "\n  ".join(unexpected)
    )
    stale = sorted(WRITE_VERBS_THAT_ARE_READS - suspects)
    assert not stale, f"这些条目已经不成立了，请删掉: {stale}"


def test_every_declared_action_is_a_known_action():
    """动作只允许 create / read / update / delete —— 拼错的动作同样会让端点静默 403。"""
    allowed = {"create", "read", "update", "delete"}
    bad = {}
    for route in _api_routes():
        for c in _all_checkers(route):
            if c.action not in allowed:
                bad.setdefault((c.resource, c.action), []).append(route.path)
    assert not bad, f"这些 (资源, 动作) 的动作不是已知动作: {sorted(bad)}"


# 矩阵里**暂时**没有端点消费的资源键 —— 显式登记，只减不增。
# 新条目出现就说明「删了端点却忘了清矩阵」，`grading` 正是这么被抓到的
# （阶段 4.6 批次 A 删了 `/api/grading` 路由，矩阵键留了下来）。
DEAD_MATRIX_KEYS = {
    # 学生基础矩阵里的两个键，从最初的设计就存在，但没有任何端点声明它们。
    # 属**既有遗留**（不是本次引入）。留着是因为「学生自助端点将来会用」这个意图
    # 还在；真接上端点时，从这里删掉即可（本测试两个方向都会红）。
    "self_data",
    "assignment",
}


def test_matrix_resource_keys_are_all_used_somewhere():
    """矩阵里定义的资源键，必须真的有端点在用 —— 否则是**死键**。

    死键的害处：看着像「这个角色有这个资源」，实际没有任何端点消费它，
    后来人照着它做判断就会得出错误结论。
    """
    declared = {c.resource for route in _api_routes() for c in _all_checkers(route)}
    defined = {res for perms in ROLE_PERMISSIONS.values() for res in perms}
    dead = defined - declared

    unexpected = sorted(dead - DEAD_MATRIX_KEYS)
    assert not unexpected, (
        f"矩阵里这些资源键没有任何端点声明使用（多是删了端点忘了清矩阵）: {unexpected}"
    )
    stale = sorted(DEAD_MATRIX_KEYS - dead)
    assert not stale, (
        f"这些资源键已经有人用了，请从 DEAD_MATRIX_KEYS 删掉: {stale}"
    )


# ─────────────────────────────────────────────────────────────
# 阶段 7.1：7 角色 × 全部端点的决策表
# ─────────────────────────────────────────────────────────────
# 上那些守卫只看「有没有声明」。这里把它推到「**哪个角色能不能过**」：
# 对每个端点 × 7 个角色算出一个决策，再用不变量和一张显式表分别钉住。
# 决策是**结构推导**的（读依赖树里的声明 + 权限矩阵），不发请求、不需要数据库。
#
# `ALL_ROLES` / `SELF_ROLES` 从 `app.middleware.auth` 导入 —— 不在测试里另抄一份，
# 否则「角色清单有两份」又会漂移（这正是阶段 0.1 建 `Role` 枚举要解决的事）。


def _decision_for(route: APIRoute, role: str) -> str:
    """该角色调这个端点会怎样：`public` / `allow` / `deny`。

    规则（与运行时一致）：
      - 公开端点不问身份 → public
      - 树上的每个 PermissionChecker 都要放行才算过（router 基线与端点级**都要**）
      - `allow_self=True` 的检查器对本人角色直接放行 —— 之后由 ScopeGuard 收窄范围
      - 只有身份守卫（get_current_user / get_current_parent_id）的端点：登录即可
    """
    if _is_public(route.path):
        return "public"

    checkers = _all_checkers(route)
    if not checkers:
        # 没有权限声明 —— 要么是身份守卫端点，要么是漏声明（后者由守卫测试拦）
        return "allow" if _declared_permission(route) else "deny"

    for c in checkers:
        if c.allow_self and role in SELF_ROLES:
            continue
        if not can(role, c.resource, c.action):
            return "deny"
    return "allow"


# 本人角色**经由基础矩阵**（而不是 allow_self）能进的端点 —— 显式白名单，按角色登记。
# 出现新条目就说明有人给本人角色开了个资源键，必须是有意为之；条目失效了也要删掉。
SELF_ROLE_MATRIX_EXCEPTIONS: set = set()


@pytest.mark.parametrize("role", ALL_ROLES)
def test_self_roles_never_pass_a_matrix_check_without_allow_self(role):
    """**本人角色只能通过 `allow_self` / 公开 / 身份守卫三类入口**，例外须显式登记。

    student / parent 在权限矩阵里几乎没有条目，所以任何被矩阵把守的端点都该拦下他们 ——
    除非那里显式写了 `allow_self`（表示「这是本人数据，范围由 ScopeGuard 收窄」）。
    漏写一个 allow_self 会表现成「学生莫名其妙进了一个员工端点」，只靠逐端点的
    角色断言很难发现；反之，有人误给本人角色一个资源键也会被这里抓住。

    这条曾经抓到 `/api/logs`：它的门借用 `grade:read`，而学生恰好有那个键，
    于是权限层对他们是开着的 —— 真正拦住的是函数体里手写的 `role != "admin"`。
    """
    if role not in SELF_ROLES:
        pytest.skip("只查本人角色")

    offenders = set()
    for route in _api_routes():
        if _decision_for(route, role) != "allow":
            continue
        if _is_public(route.path):
            continue
        if any(c.allow_self for c in _all_checkers(route)):
            continue
        if not _all_checkers(route):
            continue  # 身份守卫端点（get_current_user / get_current_parent_id）
        offenders.add(f"{sorted(route.methods)[0]} {route.path}")

    registered = {ep for (r, ep) in SELF_ROLE_MATRIX_EXCEPTIONS if r == role}

    unexpected = offenders - registered
    assert not unexpected, (
        f"{role} 能进这些被矩阵把守、又没写 allow_self 的端点（不在白名单里）：\n  "
        + "\n  ".join(sorted(unexpected))
        + "\n\n若这是有意的（给了本人角色一个资源键），把 (角色, 端点) 加进 "
        "SELF_ROLE_MATRIX_EXCEPTIONS 并写清楚为什么；若是漏写 allow_self，补上。"
    )

    stale = registered - offenders
    assert not stale, (
        f"白名单里这些条目已经不成立了，请删掉：{sorted(stale)}　"
        f"（白名单只减不增，留着会让断言失效）"
    )


@pytest.mark.parametrize("role", ALL_ROLES)
def test_decisions_are_derived_from_the_matrix(role):
    """角色能过哪些端点，必须完全由权限矩阵决定 —— 不能有第二个真源。"""
    for route in _api_routes():
        decision = _decision_for(route, role)
        if decision == "public":
            continue
        checkers = _all_checkers(route)
        expected = all(
            (c.allow_self and role in SELF_ROLES) or can(role, c.resource, c.action)
            for c in checkers
        )
        assert (decision == "allow") == expected, f"{role} 在 {route.path} 上的决策与矩阵不符"


def test_student_cannot_list_school_grades():
    """`grade` 只管「年级管理」—— 学生不该有它。

    曾经有：`student.grade = ['read']` 让 `GET /api/grades`（返回学校年级元数据：
    grade_id / 名称 / 年份 / school_id）对学生开放。原意多半是「读自己的成绩」，
    与「年级管理」**撞名**了。

    学生读**自己**成绩走的是另一条路：`/api/report/student/{id}`（返回
    your_score / class_avg_score / rank），由 `analysis:read` + `allow_self` +
    ScopeGuard 收窄到本人 —— ADR-0008 的模型，不需要新的资源键。
    """
    route = next(r for r in _api_routes() if r.path == "/api/grades")
    assert _decision_for(route, "student") == "deny", "学生不该能列学校年级"
    assert _decision_for(route, "parent") == "deny"
    assert _decision_for(route, "teacher") == "allow", "员工照旧"


def test_integration_endpoints_are_admin_only():
    """阶段 4.7 的契约：除按 LTI 规范公开的 JWKS 外，集成端点只有管理员能过。

    这条比逐端点断言更强 —— 将来往 `integration.py` 加端点，如果忘了限管理员，
    这里会直接红。
    """
    offenders = []
    for route in _api_routes():
        if not route.path.startswith("/api/integration") or _is_public(route.path):
            continue
        for role in ALL_ROLES:
            if role in ("admin", "super_admin"):
                continue
            if _decision_for(route, role) == "allow":
                offenders.append(f"{role} → {sorted(route.methods)[0]} {route.path}")
    assert not offenders, f"这些非管理员角色能进集成端点：{offenders}"


# ── 显式决策表：每个端点族挑代表，7 个角色逐一标出预期 ──
# A=allow（通过权限层） D=deny P=public
# ⚠️ 这里只写「权限层」的结论。范围（能不能看到具体数据）由 ScopeGuard 另行把关，
#    所以 A 不代表「能拿到数据」，只代表「进了这个端点」。
DECISION_TABLE = [
    # (method, path, 预期：{角色: A/D/P})  —— 未列出的角色按 D 处理
    ("POST", "/api/auth/login",         {"*": "P"}),
    ("GET", "/api/auth/me",             {"*": "A"}),          # 身份守卫：登录即可
    ("GET", "/api/integration/api-keys", {"super_admin": "A", "admin": "A"}),
    ("GET", "/api/integration/lti/.well-known/jwks.json", {"*": "P"}),
    ("GET", "/api/question/kps",        {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    ("POST", "/api/question/generate",  {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    ("DELETE", "/api/exam/{exam_id}",   {"super_admin": "A", "admin": "A"}),
    ("POST", "/api/ocr/recognize",      {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    ("GET", "/api/warning/pending",     {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    ("GET", "/api/memory/stats",        {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    ("GET", "/api/notification/history", {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    ("GET", "/api/notification/student/{student_id}/notifications",
     {"super_admin": "A", "admin": "A", "academic_admin": "A", "subject_lead": "A",
      "teacher": "A", "student": "A", "parent": "A"}),        # allow_self：本人角色都放行，
                                                              # 具体是谁由 ScopeGuard 收窄
    ("GET", "/api/practice/student/{student_id}/tasks",
     {"super_admin": "A", "admin": "A", "academic_admin": "A", "subject_lead": "A",
      "teacher": "A", "student": "A", "parent": "A"}),        # allow_self
    ("GET", "/api/review/student/{student_id}/due",
     {"super_admin": "A", "admin": "A", "academic_admin": "A", "subject_lead": "A",
      "teacher": "A", "student": "A", "parent": "A"}),        # allow_self
    ("GET", "/api/agent/chat/history/{thread_id}",
     {"super_admin": "A", "admin": "A", "academic_admin": "A", "subject_lead": "A",
      "teacher": "A", "student": "A", "parent": "A"}),        # allow_self
    ("POST", "/api/agent/upload",       {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    ("GET", "/api/classes",             {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
    # `grade` 是「年级管理」的键，学生**没有**（2026-09-12 移除那条语义重叠的授权）
    ("GET", "/api/grades",              {"super_admin": "A", "admin": "A", "academic_admin": "A",
                                          "subject_lead": "A", "teacher": "A"}),
]


@pytest.mark.parametrize("method,path,expectations", DECISION_TABLE,
                         ids=lambda v: v if isinstance(v, str) else "")
def test_decision_table(method, path, expectations):
    """7 角色 × 代表端点的**显式**决策表 —— 一眼能看出整张矩阵长什么样。"""
    route = next((r for r in _api_routes() if r.path == path and method in r.methods), None)
    assert route is not None, f"{method} {path} 不存在（改名了？同步这张表）"

    wrong = []
    for role in ALL_ROLES:
        want = expectations.get(role, expectations.get("*", "D"))
        got = _decision_for(route, role)
        want_norm = "public" if want == "P" else ("allow" if want == "A" else "deny")
        if got != want_norm:
            wrong.append(f"{role}: 期望 {want_norm}，实际 {got}")

    assert not wrong, f"{method} {path} 决策不符：\n  " + "\n  ".join(wrong)


# ─────────────────────────────────────────────────────────────
# 前端能力清单（阶段 5）：菜单必须由矩阵派生，不能另写一套规则
# ─────────────────────────────────────────────────────────────

def test_menus_are_derived_from_the_matrix():
    """`menus_for` 的每一项都必须等价于 `can(role, 菜单声明的资源, 动作)`。

    这条钉的是「菜单与权限矩阵一致」—— 菜单写死一套、矩阵改另一套，是这类
    功能的典型腐化方式。
    """
    for role in sorted(ROLE_PERMISSIONS):
        expected = [m["key"] for m in MENUS if can(role, m["resource"], m["action"])]
        assert menus_for(role) == expected, f"{role} 的菜单与矩阵不一致"


def test_menu_keys_are_unique_and_each_is_reachable():
    keys = [m["key"] for m in MENUS]
    assert len(keys) == len(set(keys)), f"菜单 key 重复: {keys}"
    for m in MENUS:
        assert any(can(r, m["resource"], m["action"]) for r in ROLE_PERMISSIONS), (
            f"菜单 {m['key']} 声明的 {m['resource']}:{m['action']} 没有任何角色拥有 —— "
            f"这是个永远看不到的死菜单"
        )


def test_self_roles_get_no_teacher_menus():
    """学生 / 家长用 m/ 移动端；React 教师端对他们是空的，前端据此显示「无教师端权限」页。"""
    assert menus_for("student") == []
    assert menus_for("parent") == []


def test_admin_and_teacher_menus_differ():
    """阶段 5.3 的验证项：管理员与普通教师登录后侧边栏必须不同。"""
    assert "integration" in menus_for("admin")
    assert "integration" not in menus_for("teacher")


@pytest.mark.parametrize("role", [
    "super_admin", "admin", "academic_admin", "subject_lead", "teacher", "student", "parent",
])
def test_every_role_has_a_chinese_label(role):
    """阶段 0.1 要的映射表：7 个角色都要有中文显示名，且不能回落到角色值本身。"""
    label = role_label(role)
    assert label and label != role, f"{role} 没有中文显示名"


def test_unknown_role_falls_back_to_itself():
    """未知角色回落到角色值，不返回空串（免得前端显示空白）。"""
    assert role_label("not_a_role") == "not_a_role"
    assert menus_for("not_a_role") == []
    assert permissions_for("not_a_role") == []


def test_super_admin_mirrors_admin_without_aliasing():
    """超管能力 = admin **加上 break-glass**（唯一多出来的一项）。

    超管要能在跨校排查时开限时提权，所以比 admin 多这一个资源；其余每一项都必须
    与 admin 逐字相同。且**不能共享同一份 list** —— 共享的话，将来给 admin 加一个
    动作会**悄悄**改掉超管的权限，这种洞不会报错。

    数据范围是另一层：超管默认空集，提权期间才放开（ADR-0011，见 test_break_glass.py）。
    """
    from app.middleware.auth import ROLE_PERMISSIONS

    sa, ad = ROLE_PERMISSIONS["super_admin"], ROLE_PERMISSIONS["admin"]
    extra = set(sa) - set(ad)
    assert extra == {"break_glass"}, f"超管比 admin 多出的资源应只有 break_glass，实际 {extra}"
    assert not set(ad) - set(sa), "admin 有的资源超管都该有"

    for res, actions in ad.items():
        assert sa[res] == actions, f"{res} 的能力应与 admin 一致"
        assert sa[res] is not actions, f"{res} 共享了同一个 list 对象（改一边会串另一边）"


def test_lti_jwks_is_public_by_design():
    """LTI 1.3 规范要求平台**无鉴权**抓取工具的 JWKS 来验签 —— 它必须保持公开。

    这条是刻意的例外：4.7 的其余 15 个集成端点都限管理员，只有它公开。
    加的正是时候 —— 它现在只是个返回假密钥的 TODO 桩，真实现时才不会顺手锁上。
    """
    assert _is_public("/api/integration/lti/.well-known/jwks.json")
    assert _in_backlog("/api/integration/lti/.well-known/jwks.json") is False


def _all_checkers(route: APIRoute):
    """依赖树里所有 PermissionChecker 实例。"""
    out, stack = [], list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if isinstance(dep.call, PermissionChecker):
            out.append(dep.call)
        stack.extend(dep.dependencies)
    return out


@pytest.mark.parametrize(
    "route",
    [r for r in _api_routes() if any(c.allow_self for c in _all_checkers(r))],
    ids=lambda r: f"{sorted(r.methods)[0]} {r.path}",
)
def test_allow_self_endpoint_is_not_blocked_by_a_router_baseline(route):
    """`allow_self=True` 的端点不能再挂一个 `allow_self=False` 的声明。

    router 级基线（`include_router(dependencies=[...])`）**总是执行**，而且在端点
    自己的依赖之前 —— 所以给一个「学生也要用」的前缀加基线，学生会被基线挡在
    端点外，端点上写的 `allow_self=True` 根本没机会生效。
    4.5b（report/diagnosis）和 4.6 批次 D（practice/review）都在这里栽过。

    这条把「哪些前缀能加基线」钉成结构约束：self 角色在矩阵里一个资源都没有，
    所以只要树上还有 allow_self=False 的检查器，本人角色就必然进不来。
    """
    blocking = [c for c in _all_checkers(route)
                if not c.allow_self and c.resource in ("analysis", "practice",
                                                       "review", "notification")]
    assert not blocking, (
        f"{route.path} 声明了 allow_self，但依赖树里还有会挡住本人角色的检查器："
        f"{[(c.resource, c.action) for c in blocking]} —— "
        f"多半是它所在的前缀被加了 router 基线。"
    )


@pytest.mark.parametrize("method,path,expected", EXPECTED_DECLARATIONS)
def test_migrated_endpoint_declares_expected_permission(method, path, expected):
    route = next(
        (r for r in _api_routes() if r.path == path and method in r.methods),
        None,
    )
    assert route is not None, f"{method} {path} 不存在（改名了？那就同步这张表）"
    actual = _declared_permission(route)
    assert actual == expected, (
        f"{method} {path} 的声明是 {actual}，期望 {expected}"
    )
