"""
ChemAI Main Application
基于FastAPI的高中化学AI辅助教学工具后端服务
"""
import asyncio
import os

# 禁用 ChromaDB posthog telemetry (修复版本兼容性问题)
try:
    import posthog
    _original_capture = posthog.capture
    posthog.capture = lambda *args, **kwargs: None
except ImportError:
    pass

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from app.core.config import settings

# LangGraph SqliteStore (long-term memory)
_store = None
_store_ctx = None  # async context manager holder


async def get_store():
    """Get the SqliteStore singleton (lazily initialized via async context manager)."""
    global _store, _store_ctx
    if _store is None:
        from langgraph.store.sqlite.aio import AsyncSqliteStore
        import os
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chemai_store.db")
        _store_ctx = AsyncSqliteStore.from_conn_string(db_path)
        _store = await _store_ctx.__aenter__()
        await _store.setup()
    return _store

# ── 化学式渲染中间件 — 所有 JSON 响应中的化学式自动转 Unicode 下标/上标 ──
from app.middleware.chem_render import ChemRenderMiddleware  # noqa: E402
from app.middleware.auth import PermissionChecker  # noqa: E402

# API路由
from app.api import (  # noqa: E402
    ocr,
    exam,
    question,
    diagnosis,
    report,
    practice,
    panel,
    auth,
    user,
    class_api,
    exam_bank,
    memory,
    school,
    grade,
    teacher_application,
    log,
    parent,
    review,
    warning,
    analytics,
    integration,
    notification,
    knowledge,
    workspace_api,
    break_glass,
)
from app.api.practice_api import wrong_topic  # noqa: E402

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="高中化学AI辅助教学工具 - 教师端+学生端API服务"
)

# 获取前端文件目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# CORS配置（生产环境通过 CHEMAI_CORS_ORIGINS 环境变量设置白名单）
ALLOWED_ORIGINS = os.getenv("CHEMAI_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS.split(",") if ALLOWED_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 化学式 Unicode 渲染 — 所有 JSON 响应中自动转换下标/上标
app.add_middleware(ChemRenderMiddleware)

# 无需认证的路径
# 仅保留「登录本身」与「探活」。其余全部要求有效 token（ADR-0009）。
PUBLIC_PREFIXES = [
    # ⚠️ 逐条列出，不再整段放行 /api/auth/ —— 原来整段白名单让 logout/me 也免鉴权，
    # 而它们本来就在拿到 token 之后调用。只有「发生在拿到 token 之前」的才留在这里。
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/apply",     # 教师入驻申请（含 GET /apply/{app_id} 查状态）
    # 家长登录/注册发生在拿到 token 之前，必须放行。
    # 注意：/api/parent/ 的其余端点（children/bind/report/send-bind-code…）一律要求认证。
    "/api/parent/login",
    "/api/parent/register",
    # LTI 1.3 规范要求**平台无鉴权**抓取工具的 JWKS 来验签 —— 这个端点
    # 设计上就该公开（装的本来就是公钥）。4.7 的其余 15 个端点都限管理员。
    "/api/integration/lti/.well-known/jwks.json",
    "/health",
]

# API 文档会把全部端点结构暴露给任何人 —— 仅开发环境开放
if settings.DEBUG:
    PUBLIC_PREFIXES += ["/docs", "/redoc", "/openapi.json"]
PUBLIC_EXTENSIONS = {".html", ".js", ".css", ".png", ".ico", ".svg", ".woff2"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # 非 API 路径跳过
    if not path.startswith("/api/"):
        return await call_next(request)
    # 白名单前缀跳过（如 /api/auth/、/api/agent/ 及其子路径）
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    # 静态文件跳过
    if any(path.endswith(ext) for ext in PUBLIC_EXTENSIONS):
        return await call_next(request)

    from app.middleware.auth import verify_token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "未携带认证token"})
    token = auth_header.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "token无效或已过期"})
    return await call_next(request)

# 注册API路由（优先级最高）
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(
    user.router, prefix="/api/users", tags=["用户管理"],
    # 基线：员工角色都能读学生；本人角色（student/parent）无 student:read → 403
    dependencies=[Depends(PermissionChecker("student", "read"))],
)
app.include_router(
    class_api.router, prefix="/api/classes", tags=["班级管理"],
    # 基线：员工角色都能读班级（含 subject_lead / teacher）；本人角色 403
    dependencies=[Depends(PermissionChecker("class", "read"))],
)
app.include_router(
    ocr.router, prefix="/api/ocr", tags=["OCR识别"],
    # 基线：员工角色可读 OCR（学生/家长无 ocr:read → 403）
    dependencies=[Depends(PermissionChecker("ocr", "read"))],
)
app.include_router(
    exam.router, prefix="/api/exam", tags=["考试管理"],
    # 基线：员工角色可读考试（学生/家长无 exam:read → 403）
    dependencies=[Depends(PermissionChecker("exam", "read"))],
)
app.include_router(
    question.router, prefix="/api/question", tags=["题目管理"],
    # 基线：员工角色可读题目（学生/家长无 question:read → 403）
    dependencies=[Depends(PermissionChecker("question", "read"))],
)
app.include_router(diagnosis.router, prefix="/api/diagnosis", tags=["障碍诊断"])
app.include_router(report.router, prefix="/api/report", tags=["报告生成"])
# ⚠️ 这里**不能**用 router 基线：/api/practice 下有学生自助端点，
# 基线总是执行，会把 allow_self 里的学生挡在端点之前（4.5b 踩过同一个坑）。
# 故全部逐端点声明。
app.include_router(practice.router, prefix="/api/practice", tags=["自适应练习"])
from app.api import practice_wrong  # noqa: E402
app.include_router(practice_wrong.router, prefix="/api/practice", tags=["错题复习"])
app.include_router(
    panel.router, prefix="/api/panel", tags=["学情面板"],
    # 基线：员工角色可读学情；学生/家长无 analysis:read → 403
    dependencies=[Depends(PermissionChecker("analysis", "read"))],
)
app.include_router(
    exam_bank.router, prefix="/api/exam-bank", tags=["真题库管理"],
    # 基线：员工角色可读真题库（学生/家长无 exam_bank:read → 403）
    dependencies=[Depends(PermissionChecker("exam_bank", "read"))],
)
app.include_router(
    memory.router, prefix="/api/memory", tags=["学情记忆"],
    # 基线：员工角色可读学情记忆；学生/家长无 memory:read → 403
    # ⚠️ POST /diagnosis-complete 是写操作，但矩阵里 memory 只有 read
    #    （见 auth.py 的 CONTENT_PERMISSIONS 与 tasks.md 的语义偏松记录）
    dependencies=[Depends(PermissionChecker("memory", "read"))],
)
app.include_router(school.router, prefix="/api/school", tags=["学校设置"])
app.include_router(grade.router, prefix="/api/grades", tags=["年级管理"])
app.include_router(teacher_application.router, prefix="/api/teacher-applications", tags=["教师入驻"])
app.include_router(log.router, prefix="/api/logs", tags=["操作日志"])
app.include_router(parent.router, prefix="/api/parent", tags=["家长端"])
# 同上：/api/review 是学生自助入口，逐端点声明
app.include_router(review.router, prefix="/api/review", tags=["间隔复习"])
app.include_router(
    warning.router, prefix="/api/warning", tags=["学情预警"],
    # 基线：员工角色可读预警（学生/家长无 warning:read → 403）
    dependencies=[Depends(PermissionChecker("warning", "read"))],
)
# ⚠️ 同 /api/practice：analytics 下有学生/家长自助看板（dashboard/student|parent、
# student/{id}/personal-stats，靠 allow_self + ScopeGuard 收窄），router 基线总是执行，
# 会把本人角色挡在端点之前（他们是矩阵外的角色，没有 analysis:read）。故逐端点声明。
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据可视化"])
app.include_router(
    break_glass.router, prefix="/api/break-glass", tags=["平台提权"],
    # ADR-0011：只有 super_admin 能开提权（admin 也没有这个资源键）
)
app.include_router(integration.router, prefix="/api/integration", tags=["LMS集成"])
from app.api import data_import  # noqa: E402
app.include_router(data_import.router)
app.include_router(notification.router, prefix="/api/notification", tags=["通知推送"])
app.include_router(wrong_topic.router, prefix="/api/practice/wrong-topic", tags=["错题强化"])
app.include_router(
    knowledge.router, prefix="/api/knowledge", tags=["知识卡片"],
    # 知识点卡片是纯读内容；学生/家长无 knowledge:read → 403
    dependencies=[Depends(PermissionChecker("knowledge", "read"))],
)

# 文档解析
app.include_router(
    workspace_api.router,  # 工作区目录浏览器（前缀在 router 内）
    dependencies=[Depends(PermissionChecker("workspace", "read"))],
)

# Answer sheet OCR + grading
from app.api import ocr_sheets  # noqa: E402
app.include_router(
    ocr_sheets.router, prefix="/api/ocr", tags=["答题卡批改"],
    dependencies=[Depends(PermissionChecker("ocr", "read"))],
)

# ChemAgent (LangGraph ReAct agent)
from agent.channel.langgraph_channel import router as langgraph_router  # noqa: E402
app.include_router(langgraph_router, prefix="/api/agent", tags=["AI Agent (LangGraph)"])

# ── Conversation management routes (registered directly on app) ──
from agent.channel.conversation import (  # noqa: E402
    list_conversations,
    get_conversation_history,
    new_conversation,
    delete_conversation,
)
app.get("/api/agent/chat/conversations", tags=["对话管理"])(list_conversations)
app.get("/api/agent/chat/history/{thread_id}", tags=["对话管理"])(get_conversation_history)
app.post("/api/agent/chat/new", tags=["对话管理"])(new_conversation)
app.delete("/api/agent/chat/conversations/{thread_id}", tags=["对话管理"])(delete_conversation)


def _nocache_file(path, **kw):
    """返回文件并禁用缓存"""
    from starlette.responses import FileResponse as _FR
    resp = _FR(path, **kw)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.get("/")
async def root():
    # 优先提供 React 教师端构建产物（dist），回退源码 index.html
    dist_html = os.path.join(FRONTEND_DIR, "dist", "index.html")
    if os.path.exists(dist_html):
        return _nocache_file(dist_html)
    html_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(html_file):
        return _nocache_file(html_file)
    return RedirectResponse(url="/login.html")

@app.get("/favicon.png")
async def serve_favicon():
    dist_favicon = os.path.join(FRONTEND_DIR, "dist", "favicon.png")
    if os.path.exists(dist_favicon):
        return FileResponse(dist_favicon, media_type="image/png")
    return RedirectResponse(url="/")

@app.get("/m")
async def mobile_root():
    # ADR-0001：移动端并入 React SPA，旧 /m 重定向到 SPA hash 路由
    return RedirectResponse(url="/#/m")


# 旧静态移动页 → SPA 路由 映射（ADR-0001 URL 兼容；e2e 与收藏链接不断链）
_MOBILE_SPA_MAP = {
    "index.html": "/#/m",
    "practice.html": "/#/m/practice",
    "wrong.html": "/#/m/wrong",
    "review.html": "/#/m/review",
    "report.html": "/#/m/me",
    "login.html": "/#/m/login",
    "parent.html": "/#/m/parent",
    "parent-login.html": "/#/m/parent-login",
    "design-v1.html": "/#/m",
}


# 真题题库图片静态文件（兼容目录名带数字前缀：01_全国卷 ↔ 全国卷，
# 与 exam_bank.py 的 region 归一化 re.sub(r"^\d+_", "", entry) 保持一致）
import os as _os  # noqa: E402
import re as _re  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
_figures_dir = _os.path.join(_os.path.dirname(__file__), "..", "data", "exam_questions")

@app.get("/static/figures/{path:path}")
async def serve_exam_figure(path: str):
    if not path or ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400)
    base = _Path(_figures_dir)
    direct = base / path
    if direct.is_file():
        return FileResponse(direct)
    # 兜底：目录名与 URL 地区名带数字前缀错位（URL 用归一化名 全国卷，目录为 01_全国卷）
    parts = path.split("/")
    if parts and parts[0]:
        stripped = _re.sub(r"^\d+_", "", parts[0])
        if stripped != parts[0]:
            # URL 带前缀（01_全国卷）→ 目录不带前缀（全国卷）
            alt = base / stripped / "/".join(parts[1:])
            if alt.is_file():
                return FileResponse(alt)
        # URL 不带前缀（全国卷）→ 目录带前缀（01_全国卷）
        for entry in _os.listdir(base) if base.is_dir() else []:
            if _re.sub(r"^\d+_", "", entry) == parts[0]:
                alt = base / entry / "/".join(parts[1:])
                if alt.is_file():
                    return FileResponse(alt)
                break
    raise HTTPException(status_code=404)

# 复杂结构图（RDKit 渲染，ADR-0005 H1）
from app.services.structure_render import IMG_DIR as _qimg_dir  # noqa: E402
_os.makedirs(_qimg_dir, exist_ok=True)
app.mount("/static/question_images", StaticFiles(directory=_qimg_dir), name="question_images")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# 静态文件路由（精确匹配，避免被动态路由捕获）
@app.get("/app.js")
async def serve_app_js():
    js_file = os.path.join(FRONTEND_DIR, "app.js")
    if os.path.exists(js_file):
        return FileResponse(js_file, media_type="application/javascript")
    return RedirectResponse(url="/")


@app.get("/components/{file}")
async def serve_component(file: str):
    """前端组件静态文件"""
    file_path = os.path.join(FRONTEND_DIR, "components", file)
    if os.path.exists(file_path):
        ext = file.rsplit(".", 1)[-1] if "." in file else ""
        media_types = {"js": "application/javascript", "css": "text/css"}
        return FileResponse(file_path, media_type=media_types.get(ext))
    return RedirectResponse(url="/")

@app.get("/styles.css")
async def serve_css():
    css_file = os.path.join(FRONTEND_DIR, "styles.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    return RedirectResponse(url="/")


@app.get("/common.css")
async def serve_common_css():
    css_file = os.path.join(FRONTEND_DIR, "common.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    return RedirectResponse(url="/")


@app.get("/login.html")
async def serve_login_html():
    html_file = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.exists(html_file):
        return _nocache_file(html_file)
    return RedirectResponse(url="/")


@app.get("/index.html")
async def serve_index_html():
    html_file = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(html_file):
        html_file = os.path.join(FRONTEND_DIR, "login.html")
    return FileResponse(html_file)


# 前端静态资源精确路由（必须在兜底 /{page} 之前）
@app.get("/design-system.css")
async def serve_design_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "design-system.css"))

@app.get("/js/{filename}")
async def serve_js(filename: str):
    fp = os.path.join(FRONTEND_DIR, "js", filename)
    if os.path.isfile(fp):
        return FileResponse(fp)
    raise HTTPException(status_code=404)

@app.get("/pages/{filename}")
async def serve_pages(filename: str):
    fp = os.path.join(FRONTEND_DIR, "pages", filename)
    if os.path.isfile(fp):
        return FileResponse(fp)

@app.get("/m/{filename}")
async def serve_mobile(filename: str):
    # ADR-0001：旧静态移动页已退役，按映射表重定向到 SPA hash 路由
    target = _MOBILE_SPA_MAP.get(filename)
    if target:
        return RedirectResponse(url=target)
    return RedirectResponse(url="/#/m")

# React 教师端构建产物静态资源（方向 A 现代学术蓝；纯增量，不影响现有路由）
_dist_assets = os.path.join(FRONTEND_DIR, "dist", "assets")
if os.path.isdir(_dist_assets):
    app.mount("/assets", StaticFiles(directory=_dist_assets), name="assets")

# 旧教师端归档只读访问（2026 归档到 frontend/legacy/teacher/，供对照/回滚）
_legacy_dir = os.path.join(FRONTEND_DIR, "legacy")
if os.path.isdir(_legacy_dir):
    app.mount("/legacy", StaticFiles(directory=_legacy_dir), name="legacy")

# HTML页面路由（兜底 — 必须放在所有精确路由之后）
@app.get("/{page}")
async def serve_page(page: str):
    if ".." in page or page.startswith("/"):
        return RedirectResponse(url="/")
    # 如果已经是完整文件名（如 teacher.html），直接用
    if page.endswith(".html"):
        candidates = [
            os.path.join(FRONTEND_DIR, page),
            os.path.join(FRONTEND_DIR, "pages", page),
        ]
    else:
        candidates = [
            os.path.join(FRONTEND_DIR, f"{page}.html"),
            os.path.join(FRONTEND_DIR, "pages", f"{page}.html"),
        ]
    for html_file in candidates:
        if os.path.exists(html_file):
            return _nocache_file(html_file)
    return RedirectResponse(url="/")


@app.on_event("startup")
async def startup_event():
    # Initialize SqliteStore (long-term memory)
    global _store
    _store = await get_store()
    print("SqliteStore initialized (chemai_store.db)")
    from app.models.database import engine, Base
    Base.metadata.create_all(bind=engine)
    print("数据库表已创建/验证")

    # Debug: print all agent routes
    print("=== Registered agent routes ===")
    for route in app.routes:
        if hasattr(route, 'routes'):
            for sr in route.routes:
                sp = getattr(sr, 'path', None)
                sm = getattr(sr, 'methods', None)
                if sp and '/agent/' in sp:
                    print(f"  {sm} {sp}")
    print("=== End agent routes ===")

    from app.utils.init_db import init_database
    init_database()

    # 真题库全量写入 historical_exams（幂等 upsert，检索/导入入口的数据源）
    try:
        from app.services.exam_bank import exam_bank_service
        synced = exam_bank_service.sync_all_to_db()
        print(f"[ExamBank] historical_exams 同步完成: {synced} 条")
    except Exception as e:
        print(f"[ExamBank] historical_exams 同步失败: {e}")

    # 注册 Agent Skills
    try:
        from agent.skills_init import register_all_skills
        register_all_skills()
    except Exception as e:
        print(f"Skills 注册失败: {e}")

    # 构建向量索引 —— 后台线程（2026-08 修复：启动被 chroma 嵌入重建阻塞 40+ 秒，
    # 期间 uvicorn 不接客，浏览器打开 localhost 显示"无法访问"）。
    # 必须用 to_thread：_get_embedding 是同步 dashscope HTTP 调用，
    # 直接 create_task 会阻塞事件循环，服务器同样无法响应。
    try:
        from app.services.vector_search import vector_search_service

        async def _build_index_background():
            try:
                count = await asyncio.to_thread(
                    vector_search_service.build_index_from_exam_bank)
                print(f"Vector index built (background): {count} questions")
            except Exception as e:  # noqa: BLE001
                print(f"Vector index build skipped: {e}")

        asyncio.create_task(_build_index_background())
    except Exception as e:  # noqa: BLE001
        print(f"Vector index task create failed: {e}")

    # 启动调度器
    try:
        from app.scheduler import init_scheduler
        init_scheduler(app)
    except ImportError as e:
        print(f"调度器启动失败 (APScheduler可能未安装): {e}")


@app.on_event("shutdown")
async def shutdown_event():
    # Close SqliteStore
    global _store, _store_ctx
    if _store_ctx is not None:
        try:
            await _store_ctx.__aexit__(None, None, None)
            _store = None
            _store_ctx = None
            print("SqliteStore closed")
        except Exception as e:
            print(f"SqliteStore close failed: {e}")

    # 关闭调度器
    try:
        from app.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception as e:
        print(f"调度器关闭失败: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
