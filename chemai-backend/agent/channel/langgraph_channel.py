"""ChemAI LangGraph Channel — /api/agent/chat/langgraph 端点.

ReAct agent + interrupt/resume + SSE 兼容。
"""
import asyncio
import json
import logging
import os
import sys
import uuid as _uuid
from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.middleware.conversation import require_owned
from app.models.database import get_db
from agent.channel.conversation import _INTERNAL_NOTE_PREFIX

logger = logging.getLogger(__name__)
router = APIRouter()


def _log_error(tag: str):
    """把流式异常完整落盘（2026-08：异常之前只进服务窗口，无法追溯）。
    写 chemai_agent_errors.log（backend 根目录）。"""
    import traceback as _tb
    try:
        log_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "chemai_agent_errors.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n===== [{tag}] =====\n")
            _tb.print_exc(file=f)
    except Exception:
        pass

# 单轮执行超时（2026-08 卡死治理：工具/模型挂起时兜底终止，避免流永不结束）
_TURN_TIMEOUT = 180

# 超时兜底的 SSE 错误文案（chat / resume 两条流共用）
_TIMEOUT_ERROR_MSG = "处理超时，本次执行已中止，请重试或换个方式提问。"

# 批准重放后的 LLM 续接提示。重放结果已由 _replace_pending_tool_result 替换进
# 上文 ToolMessage（C 层），这里只写简短指引——不再把完整结果重复塞进 user 消息
# （2026-08 修复「用户发送端显示巨文」根因：12KB 注入消息被历史接口渲染成用户消息）。
# 注入消息统一以 _INTERNAL_NOTE_PREFIX 开头（conversation.py 历史过滤依赖该约定）。
_REPLAY_CONTINUE_MSG = (
    _INTERNAL_NOTE_PREFIX
    + "的操作已获得批准，并已自动重放完成，"
    "完整结果见上文的工具结果（工具「{name}」）。"
    "请基于该结果继续完成老师的请求，给出明确的最终答复。"
    "如果结果中包含错误，请向老师说明失败原因并给出下一步建议，不要重复调用刚才的工具。）"
)
# 兜底：ToolMessage 替换失败时保留旧行为（结果直接塞进消息），绝不丢结果
_REPLAY_CONTINUE_MSG_FALLBACK = (
    _INTERNAL_NOTE_PREFIX
    + "的操作已获得批准，并已自动重放完成。"
    "重放结果如下：\n{result}\n\n请基于这个结果继续完成老师的请求，给出明确的最终答复。"
    "如果结果中包含错误，请向老师说明失败原因并给出下一步建议，不要重复调用刚才的工具。）"
)


async def _get_app_store():
    """Get the SqliteStore singleton from app.main."""
    try:
        from app.main import get_store
        return await get_store()
    except Exception:
        return None

# ── 复用 ChatRequest / Gateway 分类器 ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent.channel.gateway import (  # noqa: E402
    ChatRequest, _classify_and_narrow
)
from agent.memory import MemoryStack  # noqa: E402
from agent.langgraph_sse_v2 import _json_safe_payload  # noqa: E402


_agent_cache: dict[str, object] = {}
_guard_state_cache: dict[str, object] = {}  # 按 conversation_id 缓存 guard_state, resume 时复用
# 线程迁移映射（ADR-0016 §4）：conversation_id → 迁移后的 checkpoint thread_id。
# 进程内存缓存即可——重启后首回合重新检测毒化并再迁移一次，代价是纯状态复制。
_THREAD_OVERRIDES: dict[str, str] = {}

# 每会话执行锁（ADR-0016 §5）：同一会话第二条流（双击批准/双标签页）→ 409，不排队
_CONV_LOCKS: dict[str, asyncio.Lock] = {}


async def acquire_conversation_lock(cid: str) -> asyncio.Lock:
    """取会话锁并真正获取；已被占用立即 409（不排队——排队会让第二次点击
    延迟生效，老师以为没点上再点一次，感知成幽灵双发）。"""
    lock = _CONV_LOCKS.setdefault(cid or "default", asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=409, detail="已有进行中的回复，请稍候再操作。")
    await lock.acquire()
    return lock


def _locked_stream(lock, gen_factory, headers=None):
    """StreamingResponse 包装：流结束（含断线取消）时释放会话锁。gen_factory
    是异步生成器函数，返回响应时才调用（与 StreamingResponse 惰性语义一致）。"""
    async def _stream():
        try:
            # ⚠ 必须 async for——gen_factory() 返回异步生成器，普通 for 会
            # TypeError: 'async_generator' object is not iterable（2026-09-20
            # 修复：该 bug 使 /stream 与 /resume 的所有流式回复一进来即 500）
            async for chunk in gen_factory():
                yield chunk
        finally:
            lock.release()
    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers=headers or {"Cache-Control": "no-cache"})


def build_config(cid: str) -> dict:
    """会话 → LangGraph config（经线程迁移映射，ADR-0016 §4）。"""
    return {"configurable": {"thread_id": _THREAD_OVERRIDES.get(cid or "default", cid or "default")},
            "recursion_limit": 24}


def _mark_run_paused_safe(cid: str) -> None:
    """断线/超时 → run 标 paused（ADR-0016 §3）。失败静默（run 不存在等）。"""
    if not cid:
        return
    try:
        from app.services.plan_run_service import plan_run_service
        from app.models.database import get_db
        plan_run_service.mark_run_paused(next(get_db()), cid)
    except Exception:
        pass


async def _migrate_thread(agent, old_config: dict, cid: str) -> dict:
    """毒化/孤儿中断线程迁移（ADR-0016 §4）：新线程复制 messages 历史，
    绝不调用模型（回归红线⑤）。旧线程原地作废。"""
    from langchain_core.messages import AIMessage
    state = await agent.aget_state(old_config)
    msgs = list((state.values or {}).get("messages", []) or [])
    # 孤儿 tool_call 一并丢弃——迁移后没有重放给它补 ToolMessage，留着必 LLM 400
    clean = [
        m for m in msgs
        if not (isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
                and not all(
                    any(getattr(n, "tool_call_id", None) == tc.get("id") for n in msgs)
                    for tc in m.tool_calls))
    ]
    new_tid = f"{cid or 'default'}-r{_uuid.uuid4().hex[:8]}"
    new_config = {"configurable": {"thread_id": new_tid}, "recursion_limit": 24}
    if clean:
        await agent.aupdate_state(new_config, {"messages": clean})
        # 迁移后计数校验（ADR-0016 §4，story 22）：复制条数必须一致
        _verify = await agent.aget_state(new_config)
        _copied = len(list((_verify.values or {}).get("messages", []) or [])) if _verify else -1
        if _copied != len(clean):
            raise RuntimeError(f"迁移校验失败：原 {len(clean)} 条，新线程 {_copied} 条")
    _THREAD_OVERRIDES[cid or "default"] = new_tid
    logger.warning("thread migrated for conversation %s: %s -> %s",
                   cid or "default", old_config.get("configurable", {}).get("thread_id"),
                   new_tid)
    return new_config


async def _repair_thread_state(agent, config, cid: str) -> tuple[bool, str, dict]:
    """线程状态清场（ADR-0016：恢复永不自动、零模型调用）。返回 (可继续, 阻断原因, config)。

    - 任务带 error（毒化，生产日志实证的 OpenAI 400 等）→ 迁移到新线程；
    - 未决中断：interrupt() 已随 ADR-0015 退役，残留中断即孤儿 → 迁移
      （2026-08 的 `ainvoke(Command(resume="cancelled"))` 偷跑完整回合、事件全丢、
      副作用照跑，且再中断会挂死流——整体删除）；
    - 无未决任务时的孤儿 tool_call：RemoveMessage 摘除（安全，无重放会引用它）。
    """
    from langchain_core.messages import AIMessage, RemoveMessage
    state = await agent.aget_state(config)
    if not state:
        return True, "", config

    # 任务已带错误 → 毒化线程 → 自动迁移（老师无感，ADR-0016 §4）
    for task in getattr(state, "tasks", ()) or ():
        if getattr(task, "error", None):
            try:
                return True, "", await _migrate_thread(agent, config, cid)
            except Exception as _e:  # noqa: BLE001
                logger.warning("thread migration failed: %s", _e)
                return False, "该对话的状态已损坏且自动修复失败，请点击「新对话」开始新的对话。", config

    msgs = list(state.values.get("messages", []) or [])
    orphans = [
        m.id for m in msgs
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
        and not all(
            any(getattr(n, "tool_call_id", None) == tc.get("id") for n in msgs)
            for tc in m.tool_calls
        )
    ]

    pending = bool(getattr(state, "next", None))

    if pending:
        # 孤儿中断（interrupt 退役前的残留 checkpoint）：纯状态迁移，零模型调用
        try:
            return True, "", await _migrate_thread(agent, config, cid)
        except Exception as _e:  # noqa: BLE001
            logger.warning("orphan-interrupt migration failed: %s", _e)
            return False, "该对话包含未完成的审批操作，状态已损坏，请点击「新对话」开始新的对话。", config
    if orphans:
        # 无未决任务：摘孤儿是安全的（不会再有重放给它配 ToolMessage）
        try:
            await agent.aupdate_state(
                config, {"messages": [RemoveMessage(id=o) for o in orphans]},
            )
            logger.warning("removed %d orphan tool_call message(s) for thread %s",
                           len(orphans), cid or "default")
        except Exception as _e:  # noqa: BLE001
            logger.warning("orphan cleanup failed: %s", _e)

    return True, "", config


async def _get_or_create_agent(persona: str = "tutor", provider: str = "deepseek",
                        student_profile=None, intent_hints="", version: str = "v1",
                        store=None, guard_state=None, teacher_id: str = ""):
    """Get or create agent. Returns (graph, guard_state, adapter_class).

    2026-08 修复「布置练习反复需要批准」：v2 必须透传 guard_state ——
    resume 时若不传，create_v2 会新建 GuardState（approved=False），
    agent 工具绑定新状态 → 用户批准后 LLM 再次 request_approval 又中断。"""
    if version == "v2":
        from agent.langgraph_agent_v2 import create_chemai_agent as create_v2
        from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
        agent, guard = await create_v2(
            persona=persona, provider=provider,
            student_profile=student_profile, intent_hints=intent_hints,
            store=store, guard_state=guard_state, teacher_id=teacher_id,
        )
        return agent, guard, LangGraphSSEAdapterV2

    # v1: multi-agent
    from agent.langgraph_agent import create_chemai_agent
    from agent.langgraph_sse import LangGraphSSEAdapter

    agent, _ = await create_chemai_agent(
        persona=persona, provider=provider,
        student_profile=student_profile, intent_hints=intent_hints,
    )
    return agent, None, LangGraphSSEAdapter


def _classify_typed_text(message: str, guard_state, is_plan_gate: bool) -> tuple[str, list[str]]:
    """门开着时打字的语义（ADR-0015 决策通道唯一化）。返回 (kind, sse_events)。

    kind:
      guidance — 确认词 → 引导老师点确认卡按钮，零副作用（打字永不构成批准：
                 「不要发送」含「发送」会被词表命中，绝不能当批准执行）；
      reject   — 其他文字 + 草稿门 → 打回+反馈（ADR-0013 防御分支，修订循环消费）；
      void     — 其他文字 + 布尔门 → 作废待批（清 pending，防幽灵批准）；
      none     — 无未决门（按普通消息流转）。

    事件只给 guidance 用（引导文案 + done）；reject/void 由调用方走各自分支。
    """
    from agent.guard import is_confirmation
    pending = getattr(guard_state, "pending_approval", None) if guard_state else None
    if not pending:
        return "none", []
    if is_confirmation(message or ""):
        text = ("请在上方确认卡上点击「批准 / 打回 / 放弃」处理这个确认请求；"
                "直接发送文字不会执行任何操作。")
        events = [
            json.dumps({"type": "text", "content": text}, ensure_ascii=False),
            json.dumps({"type": "done"}, ensure_ascii=False),
        ]
        return "guidance", [f"data: {e}\n\n" for e in events] + ["data: [DONE]\n\n"]
    if is_plan_gate:
        return "reject", []
    guard_state.pending_approval = None
    return "void", []


# 角色 → 可用 persona（服务端映射）：persona 决定 system prompt 与工具白名单
# （langgraph_agent_v2 按 persona 过滤 TOOL_META），是权限而不只是展示。
# 请求体自报的 persona 只能落在本角色允许集里，越权一律降级为角色默认——
# 否则学生一个 body 字段就能拿到教师工具（show_students 全库查学生等）。
_PERSONAS_BY_ROLE = {
    "student": ("student",),
    "parent": ("parent",),
    "teacher": ("teacher", "tutor"),
    "subject_lead": ("teacher", "tutor"),
    "academic_admin": ("teacher", "tutor"),
    "admin": ("teacher", "tutor"),
    "super_admin": ("teacher", "tutor"),
}


def _resolve_persona(request, current_user: dict) -> str:
    """对话 persona：按 token 角色收窄（三个对话端点共用，少一处就等于少一道门）。"""
    role = current_user.get("role")
    allowed = _PERSONAS_BY_ROLE.get(role)
    if not allowed:
        raise HTTPException(status_code=403, detail="当前角色不能使用对话功能")
    requested = getattr(request, "persona", None) or allowed[0]
    return requested if requested in allowed else allowed[0]


def _resolve_student_identity(request, current_user: dict, db) -> str:
    """对话里的学生身份：学生认 token（user_id 即学号），其余角色的自报 id 须在范围内。

    三个对话端点（stream / 非流式 / resume）共用——少一处就等于少一道门。
    """
    if current_user.get("role") == "student":
        return current_user.get("user_id") or ""
    student_id = request.student_id or ""
    if student_id:
        from app.middleware.scope import RequestScope
        if not RequestScope.from_user(current_user, db).allows_student(student_id):
            raise HTTPException(status_code=403, detail="无权访问该学生")
    return student_id


@router.post("/chat/langgraph/stream")
async def agent_chat_langgraph_stream(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("agent", "create", allow_self=True)),
):
    """流式对话 (SSE) — LangGraph ReAct agent + interrupt/resume.

    会话必须属于调用者（阶段 4.6 批次 E）—— `conversation_id` 由客户端自报且可枚举。
    """
    from dotenv import load_dotenv
    load_dotenv()

    from agent.deps import ChemAIDeps
    from langgraph.errors import GraphInterrupt

    # 文件访问档位 + 老师自定义工作区随请求下发（前端设置）
    from agent.tools.filesystem import set_file_access_level, set_workspace_root
    set_file_access_level(request.file_access)
    set_workspace_root(request.workspace)

    # 身份注入（ADR-0014）：直接用 PermissionChecker 已校验过的 current_user。
    # 原先这里手动再解一遍 Bearer token、而且**只取 user_id**（role / school_id 丢掉），
    # 接缝要靠它们算 Data Scope。current_user 三字段齐全、来源同一份签名 token，
    # 不必再解析一次（少一条会漂的代码路径）。
    from agent.tools.context import set_current_identity
    _teacher_id = current_user.get("user_id", "") or ""
    set_current_identity(
        _teacher_id,
        current_user.get("role", ""),
        current_user.get("school_id"),
    )

    cid = request.conversation_id

    # 会话归属（阶段 4.6 批次 E）：缺 id 或不属于调用者一律 403
    require_owned(db, cid, current_user)

    # 学生身份（P5 对话作答回流）：学生认 token 身份（user_id 即学号），
    # 客户端自报的 student_id 不采信；家长/教师自报的须落在自己的数据范围内
    student_id = _resolve_student_identity(request, current_user, db)
    persona = _resolve_persona(request, current_user)

    # Session handling — only track student_id, no message_history
    from agent.channel.gateway import _conversations
    if cid and cid in _conversations:
        if not student_id:
            student_id = _conversations[cid].get("student_id")
    elif cid:
        _conversations[cid] = {"student_id": student_id}

    # 学生身份注入（P5 对话作答回流）：服务端身份优先，工具据此落学情
    from agent.tools.context import set_current_student
    set_current_student(student_id or "")

    deps = ChemAIDeps(
        student_id=student_id,
        persona=persona,
        provider_name=request.provider,
    )

    if student_id:
        mem = MemoryStack()
        mem.load_student(student_id)
        deps.student_profile = mem.student_profile

    # Gateway classifier: 意图分类 + 工具收窄
    tool_names, intent = await _classify_and_narrow(
        request.message, persona, None
    )

    # navigate shortcut
    if intent and intent.type == "navigate" and intent.page:
        async def _nav_gen():
            yield f"data: {json.dumps({'type': 'navigate', 'page': intent.page, 'params': {}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_nav_gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    # 每会话执行锁（ADR-0016 §5）：双击批准/双标签页的第二条流立即 409
    conv_lock = await acquire_conversation_lock(cid)

    # Phase 3: extract pre-routed agent from Gateway classifier
    pre_routed_agent = None
    suggested_tools = None
    if intent and intent.target_agent and intent.confidence == "high":
        pre_routed_agent = intent.target_agent
        suggested_tools = intent.tools

    # Build hints for sub-agent (used regardless of routing)
    hints = ""
    if tool_names:
        hints = (
            f"推荐工具: {', '.join(tool_names[:5])}\n"
            f"用户消息: {request.message}\n使用推荐工具或其他工具，自行判断。"
        )

    # 门开着时打字的语义（ADR-0015 决策通道唯一化）：确认词 → 引导（零副作用）；
    # 其他文字 → 草稿门=打回+反馈 / 布尔门=作废。必须在缓存覆盖前读取上一轮 guard。
    _previous_guard = _guard_state_cache.get(cid) if cid else None
    if _previous_guard is not None and getattr(_previous_guard, "pending_approval", None):
        gate_pending_stream = getattr(_previous_guard, "pending_approval", None) or {}
        stream_is_plan_gate = gate_pending_stream.get("name") in _GATE_PLAN_TOOLS
        _kind, _guide_events = _classify_typed_text(
            request.message or "", _previous_guard, stream_is_plan_gate)
        if _kind == "guidance":
            async def _guide_gen():
                for _ev in _guide_events:
                    yield _ev
            return _locked_stream(conv_lock, _guide_gen)
        if _kind == "reject":
            # ADR-0013：草稿门开着时打字 = 打回+反馈 → 确定性修订循环
            # （旧逻辑在这里作废审批、把反馈当全新消息流转，闭环断裂）
            fb_agent, fb_guard, FBAdapter = await _get_or_create_agent(
                request.persona, request.provider, version=request.version,
                store=await _get_app_store(), guard_state=_previous_guard,
                teacher_id=_teacher_id,
            )
            fb_adapter = FBAdapter(conversation_id=cid or "")
            _restore_plan_state(fb_adapter, _previous_guard)
            fb_cfg = build_config(cid)
            fb_ok, fb_blocked, fb_cfg = await _repair_thread_state(fb_agent, fb_cfg, cid)
            if not fb_ok:
                async def fb_blocked_gen():
                    _err0 = json.dumps(
                        {'type': 'error', 'message': fb_blocked, 'recoverable': False},
                        ensure_ascii=False,
                    )
                    yield f"data: {_err0}\n\n"
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                return _locked_stream(conv_lock, fb_blocked_gen)
            from agent.context_manager import trim_context as trim_fb
            await trim_fb(fb_agent, fb_cfg)
            fb_decision = {"action": "reject", "feedback": request.message or "", "draft_id": ""}
            return _locked_stream(
                conv_lock,
                lambda: _gate_decision_stream(cid, fb_decision, _previous_guard,
                                              fb_agent, fb_adapter, fb_cfg))
        else:
            # 修改指令：旧审批作废（不重放），按新消息正常流转
            _previous_guard.pending_approval = None

    store = await _get_app_store()
    agent, guard_state, AdapterClass = await _get_or_create_agent(
        persona, request.provider,
        student_profile=deps.student_profile, intent_hints=hints,
        version=request.version, store=store,
        teacher_id=_teacher_id,
    )
    # 新的一轮用户输入：重置连续重复调用计数（2026-08 重复提醒护栏）
    if guard_state is not None:
        try:
            guard_state.begin_turn()
        except Exception:
            pass

    # Cache guard_state for resume — 避免 resume 时创建全新 GuardState 丢失 approved 状态
    if cid and guard_state:
        _guard_state_cache[cid] = guard_state
        guard_state.conversation_id = cid  # 布尔门实体登记需要（ADR-0015 阶段 2）

    adapter = AdapterClass(conversation_id=cid or "")
    full_reply = []
    config = build_config(cid)

    # 线程状态清场（毒化/孤儿中断 → 迁移，ADR-0016 §4；零模型调用）
    _ok, _blocked_reason, config = await _repair_thread_state(agent, config, cid)
    if not _ok:
        async def _blocked_gen():
            _err = json.dumps(
                {'type': 'error', 'message': _blocked_reason, 'recoverable': False},
                ensure_ascii=False,
            )
            yield f"data: {_err}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return _locked_stream(conv_lock, _blocked_gen)

    # Smart context management: TrimMessages + LLM summarization
    from agent.context_manager import trim_context
    await trim_context(agent, config)

    async def generate():
        nonlocal full_reply
        try:
            yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'}, ensure_ascii=False)}\n\n"

            # 上下文占用:收集最后一次模型调用的 provider usage(2026-08 context 环)
            from agent.context_meter import build_context_event, extract_prompt_tokens
            from app.config import config as _cfg
            _last_prompt_tokens = None

            try:
                async with asyncio.timeout(_TURN_TIMEOUT):
                    async for event in agent.astream_events(
                        {"messages": [{"role": "user", "content": request.message}],
                         "pre_routed_agent": pre_routed_agent,
                         "suggested_tools": suggested_tools or []},
                        config,
                        version="v2",
                    ):
                        if event.get("event") == "on_chat_model_end":
                            _pt = extract_prompt_tokens(event.get("data", {}).get("output"))
                            if _pt is not None:
                                _last_prompt_tokens = _pt
                        for result in adapter.feed(event):
                            try:
                                evt = json.loads(result)
                                if evt.get("type") == "text":
                                    full_reply.append(evt.get("content", ""))
                            except (json.JSONDecodeError, TypeError):
                                pass
                            yield f"data: {result}\n\n"

            except TimeoutError:
                _mark_run_paused_safe(cid)  # ADR-0016：超时即暂停，不自动重跑
                _err = json.dumps(
                    {'type': 'error', 'message': _TIMEOUT_ERROR_MSG, 'recoverable': True},
                    ensure_ascii=False,
                )
                yield f"data: {_err}\n\n"
                yield "data: [DONE]\n\n"
                return
            except asyncio.CancelledError:
                _mark_run_paused_safe(cid)  # 客户端断线：run 立刻标 paused
                raise
            except GraphInterrupt:
                # ADR-0015：interrupt 已退役——迁移间隙残留兜底：如实告知 + 标 paused
                _mark_run_paused_safe(cid)
                payload = {"type": "run_paused", "reason": "interrupted",
                           "message": "上一回合被中断，运行已暂停；重新发送消息即可继续。"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return

            # 计划状态持久化到 guard_state（批准/恢复后补发 plan_progress，2026-08）
            try:
                if guard_state is not None and getattr(adapter, "_plan_steps", None):
                    guard_state.plan_steps = adapter._plan_steps
            except Exception:
                pass

            # Finalize: use guard_state for v2, graph state for v1
            try:
                final_state = await agent.aget_state(config)
                state_values = final_state.values if final_state else {}
            except Exception:
                state_values = {}
            gs = guard_state
            result_text = state_values.get("last_result_text")
            # Fallback: use collected streaming text if state has no result_text (v2)
            if not result_text and full_reply:
                result_text = "".join(full_reply)
            # 上下文占用事件(provider usage 锚定 + 三段启发式构成)
            _ctx_event = build_context_event(
                _last_prompt_tokens, state_values.get("messages"), _cfg.CONTEXT_WINDOW,
            )
            for result in adapter.finalize(
                route=state_values.get("last_route") or (gs.last_route if gs else None),
                component=state_values.get("last_component") or (gs.last_component if gs else None),
                result_text=result_text,
            ):
                if result == "[DONE]":
                    yield f"data: {json.dumps(_ctx_event, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                else:
                    yield f"data: {result}\n\n"

        except Exception as e:
            _log_error("stream")
            import traceback
            traceback.print_exc()
            _mark_run_paused_safe(cid)  # ADR-0016：模型/系统报错 → run 如实标暂停
            err_msg = str(e)
            if 'recursion' in err_msg.lower():
                err_msg = '处理超时，Agent 重试次数用尽。请重试或换个方式提问。'
            err_payload = json.dumps(
                {'type': 'error', 'message': err_msg, 'recoverable': True},
                ensure_ascii=False,
            )
            yield f"data: {err_payload}\n\n"
            yield "data: [DONE]\n\n"

    return _locked_stream(
        conv_lock, generate,
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.post("/chat/langgraph")
async def agent_chat_langgraph(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("agent", "create", allow_self=True)),
):
    """非流式对话 — LangGraph ReAct agent。会话必须属于调用者。"""
    from dotenv import load_dotenv
    load_dotenv()

    from agent.deps import ChemAIDeps
    from langgraph.errors import GraphInterrupt

    from agent.tools.filesystem import set_file_access_level, set_workspace_root
    set_file_access_level(request.file_access)
    set_workspace_root(request.workspace)

    cid = request.conversation_id
    # 会话归属（阶段 4.6 批次 E）：缺 id 或不属于调用者一律 403
    require_owned(db, cid, current_user)

    # 身份注入（ADR-0014）：非流式端点**此前完全没有注入** —— 走这条路径时
    # 工具拿不到身份，接缝会 fail-closed 拒绝。这里补齐，三个端点行为一致。
    # （合并说明：main 侧这里原本还调 `set_current_teacher`，现在由本函数的
    #   `set_current_identity` 一并带上 user_id + role + school_id，不再重复注入。）
    from agent.tools.context import set_current_identity
    set_current_identity(
        current_user.get("user_id", ""),
        current_user.get("role", ""),
        current_user.get("school_id"),
    )

    # 学生身份：同 /stream —— token 优先，自报 id 须在数据范围内（否则可注入他人画像）
    student_id = _resolve_student_identity(request, current_user, db)
    persona = _resolve_persona(request, current_user)
    from agent.tools.context import set_current_student
    set_current_student(student_id or "")

    deps = ChemAIDeps(persona=persona, provider_name=request.provider)
    if student_id:
        mem = MemoryStack()
        mem.load_student(student_id)
        deps.student_profile = mem.student_profile

    tool_names, intent = await _classify_and_narrow(
        request.message, persona, None
    )

    if intent and intent.type == "navigate" and intent.page:
        return {"content": "", "navigate": {"page": intent.page, "params": {}}}

    hints = ""
    if tool_names:
        hints = (
            f"推荐工具: {', '.join(tool_names[:5])}\n"
            f"用户消息: {request.message}\n使用推荐工具或其他工具，自行判断。"
        )

    # Phase 3: pre-routed agent from Gateway
    pre_routed_agent2 = None
    suggested_tools2 = None
    if intent and intent.target_agent and intent.confidence == "high":
        pre_routed_agent2 = intent.target_agent
        suggested_tools2 = intent.tools

    store2 = await _get_app_store()
    agent, guard_state2, AdapterClass = await _get_or_create_agent(
        persona, request.provider,
        student_profile=deps.student_profile, intent_hints=hints,
        version=request.version, store=store2,
    )
    if guard_state2 is not None:
        try:
            guard_state2.begin_turn()  # 新的一轮用户输入：重置重复计数
        except Exception:
            pass

    config = build_config(cid)

    from agent.context_manager import trim_context
    await trim_context(agent, config)

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": request.message}],
             "pre_routed_agent": pre_routed_agent2,
             "suggested_tools": suggested_tools2 or []},
            config,
        )
    except GraphInterrupt:
        return {"content": "", "interrupt": True, "message": "Agent waiting for approval"}

    # Extract final text
    msgs = result.get("messages", [])
    text = ""
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        if content and isinstance(content, str) and content.strip():
            text = content
            break

    # Route from graph state (v1) or guard_state (v2)
    final_state = await agent.aget_state(config)
    state_values = final_state.values if final_state else {}
    response = {"content": text}
    last_route = state_values.get("last_route") if state_values else None
    last_component = state_values.get("last_component") if state_values else None
    if not last_route and guard_state2:
        last_route = guard_state2.last_route
    if not last_component and guard_state2:
        last_component = guard_state2.last_component
    if last_route and last_route.get("navigate"):
        route = last_route
        response["navigate"] = {"page": route.get("page"), "params": route.get("params", {})}
        if route.get("populate"):
            response.setdefault("populate", []).append(route["populate"])
        for act in route.get("actions", []):
            response.setdefault("actions", []).append(act)
    if last_component:
        response["component"] = last_component

    return response


async def _direct_replay_events(guard_state, approved: bool, cid: str = "") -> tuple:
    """无中断时的确定性重放（2026-08）：模型可能不调 request_approval——
    工具结果带 approval_needed 时 adapter 已直接发审批卡，批准后这里
    直接重放 guard 登记的待批调用，返回（合成 tool_result 事件, 重放信息 dict 或 None），
    供调用方恢复 LLM 继续回答——批准后不再只有一张卡而没有下文。
    重放信息含 name / raw（原始完整结果，供替换进 ToolMessage）/ result（SSE 截断版）。

    ADR-0015 阶段 2：粘性 approved 退役（不再置位——一次批准永不解锁后续工具）；
    重放后补 dedup 登记（LLM 重调同参工具命中「重复调用」，不双执行）；
    内存 pending 丢失时从 gate 实体重建（cid 非空时）。"""
    if not guard_state:
        return [], None
    pending = getattr(guard_state, "pending_approval", None)
    if not pending and cid:
        pending = _rebuild_pending_from_gate(cid)
        if pending:
            guard_state.pending_approval = pending
    if not pending:
        return [], None
    guard_state.pending_approval = None
    if not approved:
        return [], None
    from agent.tools.filesystem import set_elevate_once
    set_elevate_once()
    try:
        _replayed = await pending["fn"](**pending["kwargs"])
    except Exception as _e:  # noqa: BLE001
        _replayed = json.dumps({"error": f"重放失败: {_e}"}, ensure_ascii=False)
    try:
        guard_state.remember_call(pending["name"], pending["kwargs"])
    except Exception:
        pass
    _payload = json.loads(_replayed) if isinstance(_replayed, str) else _replayed
    if not isinstance(_payload, dict):
        _payload = {"result": _payload}
    events = [json.dumps({
        "type": "tool_result",
        "name": pending["name"],
        "tool": pending["name"],
        "success": "error" not in _payload,
        "result": _json_safe_payload(_payload),
    }, ensure_ascii=False)]
    # 重放成功后补发计划步骤完成事件（2026-08：计划卡不再永远停在"执行中"）
    _success = "error" not in _payload
    events.extend(_plan_completion_events(guard_state, pending["name"], _success))
    replay_info = {
        "name": pending["name"],
        "raw": _replayed,
        "result": _json_safe_payload(_payload, cap=12000),
        "success": _success,
    }
    return events, replay_info


def _rebuild_pending_from_gate(cid: str) -> dict | None:
    """从 gate 实体重建待批调用（进程重启后内存 pending 已失，ADR-0015 阶段 2）。"""
    try:
        from app.services.gate_service import gate_service
        from app.models.database import get_db
        target = gate_service.replay_target(next(get_db()), cid)
        if not target:
            return None
        from agent.langgraph_agent_v2 import _TOOL_BY_NAME
        fn = _TOOL_BY_NAME.get(target["tool_name"])
        if fn is None:
            return None
        return {"name": target["tool_name"], "fn": fn, "kwargs": target["kwargs"]}
    except Exception:
        return None


def _plan_completion_events(guard_state, tool_name: str, success: bool = True) -> list[str]:
    """批准重放后，用持久化的计划状态补发步骤转移事件。
    转移规则在 plan_run_service.compute_replay_transition（issue #18 阶段 1：
    approve→running（重放中）→ 重放成功才 completed 并启动下一步）。"""
    steps = getattr(guard_state, "plan_steps", None) or []
    if not steps:
        return []
    from app.services.plan_run_service import compute_replay_transition
    transitions = compute_replay_transition(steps, tool_name, success)
    events = []
    for step_no, status in transitions:
        events.append(json.dumps({
            "type": "plan_progress", "current_step": step_no, "status": status,
        }, ensure_ascii=False))
    return events


async def _replace_pending_tool_result(agent, config, tool_name: str, raw_result) -> bool:
    """C 层：把 checkpoint 里最后一条「{tool_name}」的 ToolMessage 内容替换为
    批准重放后的真实结果（保留 tool_call_id，LangGraph 配对校验不受影响）。
    成功后 LLM 续接上下文里就有完整工具结果，续接提示无需再重复塞结果。"""
    from langchain_core.messages import RemoveMessage, ToolMessage
    try:
        state = await agent.aget_state(config)
        msgs = list((state.values.get("messages", []) or []) if state else [])
        if not msgs:
            return False
        target = None
        for m in reversed(msgs):
            if getattr(m, "type", "") == "tool" and getattr(m, "name", "") == tool_name:
                target = m
                break
        if target is None or not getattr(target, "id", None) or not getattr(target, "tool_call_id", None):
            return False
        content = raw_result if isinstance(raw_result, str) else json.dumps(raw_result, ensure_ascii=False)
        new = ToolMessage(content=content, name=tool_name, tool_call_id=target.tool_call_id)
        await agent.aupdate_state(config, {"messages": [RemoveMessage(id=target.id), new]})
        return True
    except Exception as _e:  # noqa: BLE001
        logger.warning("replace pending tool result failed: %s", _e)
        return False


async def _remove_injected_replay_message(agent, config) -> None:
    """A 层：续接完成后从 checkpoint 摘除注入的续接提示（role=user 的内部消息），
    历史彻底不残留内部提示。失败静默（B 层历史过滤兜底）。"""
    from langchain_core.messages import RemoveMessage
    try:
        state = await agent.aget_state(config)
        msgs = list((state.values.get("messages", []) or []) if state else [])
        for m in reversed(msgs):
            if getattr(m, "type", "") in ("human", "user"):
                if not getattr(m, "id", None):
                    continue
                content = str(getattr(m, "content", "") or "")
                if content.lstrip().startswith(_INTERNAL_NOTE_PREFIX):
                    await agent.aupdate_state(config, {"messages": [RemoveMessage(id=m.id)]})
                    return
    except Exception as _e:  # noqa: BLE001
        logger.warning("remove injected replay message failed: %s", _e)


async def _repair_tail_toolcall_gaps(agent, config, filler: str) -> bool:
    """续接前修补「AI(tool_calls) 未紧跟其 tool 应答」的序列错位。

    机理（2026-09-20 实测 repro-zhou-0920）：门中断发生在工具应答写入之前，
    AI(assign_call) 后面没有 ToolMessage；门暂停期间 LLM 又产生新消息，
    批准后重放结果只能追加在尾部——AI 调用与其 tool 消息被隔开，
    OpenAI 校验即 400（"insufficient tool messages following tool_calls"）。

    修法：从后向前找第一条「紧随性违规」的 AIMessage（其 tool 应答没有
    紧跟在后，注意不能用全局应答集合判定——迟到消息会漏检）；
    摘除其后尾部 → 把 tail 中属于该调用的 ToolMessage 提到最前（没有则用
    filler 补位）→ 其余消息按原序跟回（RemoveMessage + 同 id 重加）。"""
    from langchain_core.messages import RemoveMessage, ToolMessage
    try:
        state = await agent.aget_state(config)
        msgs = list((state.values.get("messages", []) or []) if state else [])
        if not msgs:
            return False
        anchor_idx, anchor_ids = None, []
        for i in range(len(msgs) - 1, -1, -1):
            tcs = getattr(msgs[i], "tool_calls", None) or []
            if not tcs:
                continue
            expected = {tc.get("id") for tc in tcs if tc.get("id")}
            followed = set()
            j = i + 1
            while j < len(msgs) and type(msgs[j]).__name__ == "ToolMessage":
                followed.add(getattr(msgs[j], "tool_call_id", ""))
                j += 1
            if followed != expected:
                anchor_idx, anchor_ids = i, list(expected)
                break
        if anchor_idx is None:
            return False
        tail = msgs[anchor_idx + 1:]
        pulled, rest = [], []
        for m in tail:
            if (getattr(m, "type", "") == "tool"
                    and getattr(m, "tool_call_id", "") in anchor_ids):
                pulled.append(m)
            else:
                rest.append(m)
        for cid in anchor_ids:
            if not any(getattr(t, "tool_call_id", "") == cid for t in pulled):
                pulled.append(ToolMessage(content=filler, name="tool", tool_call_id=cid))
        ops = [RemoveMessage(id=m.id) for m in tail if getattr(m, "id", None)]
        # 重加的消息必须剥掉旧 id：LangGraph 的 add_messages 对同 id 是
        # 「原位更新」（Remove+同 id 重加=净零操作，实测），剥 id 才会
        # 作为新消息按新顺序追加到尾部
        for m in pulled + rest:
            c = m.model_copy(deep=True)
            c.id = None
            ops.append(c)
        await agent.aupdate_state(config, {"messages": ops})
        return True
    except Exception as _e:  # noqa: BLE001
        logger.warning("repair tail toolcall gaps failed: %s", _e)
        return False


async def _run_continuation(agent, adapter, config, msg: str, log_tag: str):
    """续接执行器公共骨架（2026-09-21 架构审查 D）：注入用户消息驱动 LLM 续接，
    超时/异常兜底出 error 事件（绝不静默），结束后摘除注入消息。
    note（打回/放弃）与 replay（批准）两条路径只差消息构造，执行同权。"""
    try:
        async with asyncio.timeout(_TURN_TIMEOUT):
            async for event in agent.astream_events(
                {"messages": [{"role": "user", "content": msg}]},
                config, version="v2",
            ):
                for r in adapter.feed(event):
                    yield r
    except TimeoutError:
        yield json.dumps({"type": "error",
                          "message": "处理超时，本次执行已中止，请重试或换个方式提问。",
                          "recoverable": True}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        _log_error(log_tag)
        yield json.dumps({"type": "error",
                          "message": f"恢复处理失败: {str(e)[:200]}",
                          "recoverable": True}, ensure_ascii=False)
    finally:
        await _remove_injected_replay_message(agent, config)


async def _stream_replay_continuation(agent, adapter, config, replay_info):
    """批准重放后恢复 LLM：先把重放结果替换进上文 ToolMessage（C 层），
    续接提示只写简短指引；替换失败时回退为把结果塞进消息（不丢结果）。"""
    if not replay_info:
        return
    tool_name = replay_info.get("name", "")
    replaced = await _replace_pending_tool_result(agent, config, tool_name, replay_info.get("raw"))
    if replaced:
        msg = _REPLAY_CONTINUE_MSG.format(name=tool_name)
    else:
        replaced = await _repair_tail_toolcall_gaps(
            agent, config,
            replay_info.get("raw") if isinstance(replay_info.get("raw"), str)
            else json.dumps(replay_info.get("raw"), ensure_ascii=False))
        if replaced:
            msg = _REPLAY_CONTINUE_MSG.format(name=tool_name)
        else:
            msg = _REPLAY_CONTINUE_MSG_FALLBACK.format(result=replay_info.get("result"))
    # 原位替换只改内容不改位置：若 ToolMessage 与其 assistant 调用之间已被
    # 门暂停期间的新消息隔开（2026-09-20 实测），仍会 400——续接前总是
    # 扫一遍错位（序列已合法时这是无操作）
    await _repair_tail_toolcall_gaps(agent, config, "（结果已记录）")
    async for r in _run_continuation(agent, adapter, config, msg, "replay-continuation"):
        yield r


def _restore_plan_state(adapter, guard_state) -> None:
    """把持久化的计划步骤恢复到新适配器（跨流：批准/恢复后计划卡继续推进）。"""
    try:
        steps = getattr(guard_state, "plan_steps", None) or []
        if steps:
            adapter._plan_steps = steps
            adapter._plan_active = True
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# 确认门三值决定（ADR-0013）：批准 / 打回+反馈 / 放弃
# 决定写进草稿数据（门由数据状态强制），打回路由到确定性修订，运行跨回合继续。
# ═══════════════════════════════════════════════════════════════════

# 门工具 → 草稿工件 service + 修订后前端组件（issue #12：报告为第二个工件）。
# 生成类工具（generate_*）生成即门：门登记的 name 是实际调用的工具名，
# 也必须路由到同一工件——缺键会 fallback 到学习计划服务，家长报告打回时
# 查错表报「草稿不存在」（2026-09-20 实测：7d8b… 在 parent_report_drafts）。
_GATE_DRAFT_TOOLS = {
    "send_learning_plan": ("plan_draft_service", "learning_plan", "学习计划"),
    "generate_learning_plan": ("plan_draft_service", "learning_plan", "学习计划"),
    "send_report_to_parent": ("parent_report_draft_service", "parent_report", "学习报告"),
    "generate_parent_report": ("parent_report_draft_service", "parent_report", "学习报告"),
}

# 兼容别名（/stream、/resume、conversation.py 的门判断）
_GATE_PLAN_TOOLS = set(_GATE_DRAFT_TOOLS)


def _gate_artifact(tool_name: str):
    """按门工具名取 (草稿 service 单例, 修订后前端组件名, 工件标签)。"""
    from app.services import plan_draft_service as _p
    from app.services import parent_report_draft_service as _r
    route = _GATE_DRAFT_TOOLS.get(tool_name)
    if route is None:
        route = _GATE_DRAFT_TOOLS["send_learning_plan"]
    svc, component, label = route
    singletons = {
        "plan_draft_service": _p.plan_draft_service,
        "parent_report_draft_service": _r.parent_report_draft_service,
    }
    return singletons[svc], component, label

# 打回后的 LLM 续接提示：说明修改点即可，门已确定性重开，禁止再调发送工具
_REJECT_CONTINUE_MSG = (
    _INTERNAL_NOTE_PREFIX
    + "老师打回了{artifact}（反馈：{feedback}），系统已按反馈修订出第 {version} 版"
    "并更新了下方预览卡片。请用一两句话向老师说明本次修改了什么，"
    "然后等待老师在确认卡上再次决定。不要调用{tool}——"
    "老师批准后系统会自动发送。）"
)
# 放弃后的 LLM 续接提示：本步取消、运行继续
_ABANDON_CONTINUE_MSG = (
    _INTERNAL_NOTE_PREFIX
    + "老师放弃发送{target}的{artifact}（草稿已保留，可稍后再次发送）。"
    "请继续执行计划中的剩余步骤；若没有剩余步骤，请向老师总结当前进展。）"
)


def _resolve_resume_intent(request, pending_name: str = "") -> tuple:
    """resume 请求 → (三值决定 or None, user_response)。

    草稿门（learning_plan / parent_report）保留三值决定；**布尔门**
    （`assign_adaptive_practice` 这类 requires_approval 工具）没有修订原语，
    决定要置 None 走 legacy —— 但**批准意图必须保住**：

    ⚠️ 2026-09-14 修的断链：原先写的是
        `_decision = None` 之后 `user_response = "approved" if (_decision or {}).get(...)`
    于是布尔门点「批准」会被改写成 `"cancelled"`，下游确定性重放判定为
    未批准 → 任务停在「等待确认」，批准等于没批。
    """
    decision = _normalize_decision(request)
    user_response = request.message or ""
    if decision and decision["action"] in ("approve", "reject", "abandon"):
        is_plan_gate = pending_name in _GATE_PLAN_TOOLS or bool(decision.get("draft_id"))
        approved = decision["action"] == "approve"
        if not is_plan_gate:
            decision = None          # 布尔门：非 approve 的一律按取消
        user_response = "approved" if approved else "cancelled"
    return decision, user_response


def _normalize_decision(request) -> dict | None:
    """ChatRequest → {action, feedback, draft_id} | None。

    decision 对象优先（新协议）；旧字符串只保留协议值映射
    （approved→approve、cancelled→abandon）。
    ADR-0015：中文确认词白名单（批准/确认/同意→approve）已废止——
    打字永不构成批准，批准只来自结构化决定。
    """
    d = getattr(request, "decision", None)
    if isinstance(d, dict) and d.get("action"):
        return {
            "action": str(d["action"]).strip().lower(),
            "feedback": str(d.get("feedback") or ""),
            "draft_id": str(d.get("draft_id") or ""),
            "gate_id": str(d.get("gate_id") or ""),
        }
    msg = (request.message or "").strip().lower()
    if msg == "approved":
        return {"action": "approve", "feedback": "", "draft_id": "", "gate_id": ""}
    if msg == "cancelled":
        return {"action": "abandon", "feedback": "", "draft_id": "", "gate_id": ""}
    return None


def _gate_draft_id(guard_state, decision) -> str:
    """决定要打的草稿：decision.draft_id → 待批调用 kwargs → 该生活跃草稿。"""
    if decision.get("draft_id"):
        return decision["draft_id"]
    pending = getattr(guard_state, "pending_approval", None) or {}
    kwargs = pending.get("kwargs", {}) or {}
    if kwargs.get("draft_id"):
        return kwargs["draft_id"]
    sid = kwargs.get("student_id") or ""
    if sid and pending.get("name") in _GATE_PLAN_TOOLS:
        try:
            from app.models.database import get_db
            svc, _component = _gate_artifact(pending.get("name", ""))
            active = svc.get_active_draft(next(get_db()), sid)
            return (active or {}).get("draft_id", "")
        except Exception:
            return ""
    return ""


def _decision_unlock_events(cid, guard_state, action: str) -> list[str]:
    """三值决定 → 步过渡事件（approve→running 重放中 / reject→revising /
    abandon→cancelled）。转移规则在 plan_run_service.compute_decision_transition，
    投影与持久化走 project_transitions 单一入口（2026-09-21 架构审查 B）。"""
    steps = getattr(guard_state, "plan_steps", None) or []
    if not steps:
        return []
    from app.services.plan_run_service import compute_decision_transition, project_transitions
    transitions = compute_decision_transition(steps, action)
    return project_transitions(cid, transitions)


def _gate_step_events(cid, guard_state, status: str, tool_name: str = "") -> list[str]:
    """门状态变化投影为 plan_progress 事件（等待确认/修订中/取消），并持久化到 run。"""
    steps = getattr(guard_state, "plan_steps", None) or []
    for s in steps:
        if s.get("skill") == tool_name and s.get("status") in (
                "pending", "running", "awaiting_confirmation", "revising", "failed"):
            s["status"] = status
            from app.services.plan_run_service import project_transitions
            return project_transitions(cid, [(s["step"], status)])
    return []


def _persist_send_completion(cid: str, guard_state, tool_name: str,
                             success: bool = True) -> None:
    """发送重放后把步转移落 run（转移规则 compute_replay_transition，
    投影与持久化走 project_transitions 单一入口——2026-09-21 架构审查 B）。

    注意：批准路径的 SSE 事件由 _direct_replay_events 内的
    _plan_completion_events 发出；本函数只负责 DB 侧同规则落库
    （内存态 plan_steps 与 run 实体两侧状态一致）。"""
    if not cid:
        return
    try:
        from app.services.plan_run_service import (
            plan_run_service as _prs, compute_replay_transition as _crt,
        )
        from app.models.database import get_db
        db = next(get_db())
        run = _prs.get_active_run(db, cid)
        if not run:
            return
        for step_no, status in _crt(run["steps"], tool_name, success):
            _prs.mark_step(db, cid, step_no, status)
    except Exception:
        pass


async def _stream_note_continuation(agent, adapter, config, note: str):
    """注入内部提示让 LLM 续接（打回说明/放弃续跑共用）。
    输出带 data: 前缀（调用方直接 yield；批注路径的 SSE 包装约定）。"""
    # 打回/放弃意味着被门拦住的工具不会执行——其 tool_calls 永远不会有
    # 真实结果，先补取消说明占位（含尾部重写），序列合法后再续接
    await _repair_tail_toolcall_gaps(
        agent, config, "（该操作已被老师打回或取消，未实际执行）")
    async for r in _run_continuation(agent, adapter, config, note, "gate-continuation"):
        yield f"data: {r}\n\n"


def _gate_draft_snapshot(draft_id: str):
    """按 id 取草稿快照（计划/报告两类工件都试）。"""
    try:
        from app.models.database import get_db
        from app.services.plan_draft_service import plan_draft_service
        from app.services.parent_report_draft_service import parent_report_draft_service
        db = next(get_db())
        d = plan_draft_service.get_draft(db, draft_id)
        if d:
            return d
        return parent_report_draft_service.get_draft(db, draft_id)
    except Exception:
        return None


def _teacher_in_scope(actor_id: str, student_id: str) -> bool:
    try:
        from app.models.database import get_db
        from app.services.plan_draft_service import plan_draft_service
        return plan_draft_service.teacher_teaches_student(next(get_db()), actor_id, student_id)
    except Exception:
        return False


async def _gate_decision_stream(cid, decision, guard_state, agent, adapter, config):
    """三值决定统一处理器（/resume decision 分支与 /stream 打字反馈共用）。

    approve → 草稿记批准 → 确定性重放发送 → 续接 LLM → todolist 继续
    reject  → 草稿确定性修订 → 推 v2 面板 + 重开门卡 → 续接 LLM 说明修改点
    abandon → 门步骤取消、运行继续（草稿保留）
    """
    from agent.tools.context import current_teacher

    action = decision.get("action", "")
    gate_pending = getattr(guard_state, "pending_approval", None) or {}
    tool_name = gate_pending.get("name", "send_learning_plan")
    gate_did = _gate_draft_id(guard_state, decision)
    actor_id = current_teacher() or ""

    def gate_error(message: str):
        return [
            f"data: {json.dumps({'type': 'error', 'message': message, 'recoverable': True}, ensure_ascii=False)}\n\n",
            f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n",
            "data: [DONE]\n\n",
        ]

    # ── 强绑定（ADR-0015 阶段 2，回归红线④）：决定带的 gate_id 与开着的门
    # 不一致 → 拒绝执行，重发当前门状态让 UI 对齐——批准门 A 永不执行门 B。
    _open_entity = None
    if cid:
        try:
            from app.services.gate_service import gate_service
            from app.models.database import get_db as _gdb
            _open_entity = gate_service.get_open_gate(next(_gdb()), cid)
            _binding = gate_service.check_binding(
                next(_gdb()), cid, str(decision.get("gate_id") or ""))
            if _binding:
                _og = _binding["open_gate"]
                _mismatch_evt = {
                    "type": "error",
                    "message": "确认请求已更新，请按最新确认卡重新决定。",
                    "recoverable": True,
                }
                _og_action = _og.get("action") or ""
                _gate_evt = {
                    "type": "gate_open",
                    "gate_id": _og.get("gate_id") or "",
                    "message": _og.get("message") or "请确认操作",
                    "action": _og_action,
                    "recipient": ("parent" if _og_action == "send_parent"
                                  else "student" if _og_action == "send_student"
                                  else "system"),
                    "draft_id": _og.get("draft_id") or "",
                    "version": _og.get("version") or 0,
                }
                for _ev in (
                    f"data: {json.dumps(_mismatch_evt, ensure_ascii=False)}\n\n",
                    f"data: {json.dumps(_gate_evt, ensure_ascii=False)}\n\n",
                    f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n",
                    "data: [DONE]\n\n",
                ):
                    yield _ev
                return
        except Exception as _e:  # noqa: BLE001
            # fail-closed：绑定校验本身出错 → 明确报错，绝不静默跳过（code-review 2026-09-20）
            logger.warning("gate binding check failed: %s", _e)
            for _ev in gate_error("确认门状态校验失败，请重试"):
                yield _ev
            return

    # ADR-0009 fail-closed：批准/打回是不可逆动作与门循环入口，缺身份直接拒绝；
    # 有身份则查 Data Scope（agent 路径=老师关系检查；REST 路径由 ScopeGuard 承担）
    if action in ("approve", "reject"):
        if not actor_id:
            for ev in gate_error("缺少教师身份，无法处理确认门决定"):
                yield ev
            return
        if gate_did:
            draft_snapshot = _gate_draft_snapshot(gate_did)
            if draft_snapshot and not _teacher_in_scope(actor_id, draft_snapshot["student_id"]):
                for ev in gate_error(
                    f"你没有处理学生 {draft_snapshot['student_id']} 学习计划的权限（Data Scope 不含该生）"):
                    yield ev
                return

    # ── reject：确定性修订（闭环靠契约，不靠模型自觉；按工件路由）──
    artifact_svc, component_name, artifact_label = _gate_artifact(tool_name)
    if action == "reject":
        feedback = (decision.get("feedback") or "").strip()
        if not feedback:
            for ev in gate_error("打回必须附修改意见"):
                yield ev
            return
        if not gate_did:
            for ev in gate_error("找不到待确认的学习计划草稿"):
                yield ev
            return
        try:
            from app.models.database import get_db
            v2 = artifact_svc.record_decision(
                next(get_db()), draft_id=gate_did, action="reject",
                actor_id=actor_id, feedback=feedback)
        except Exception as e:  # noqa: BLE001
            v2 = {"error": f"修订失败: {e}"}
        if "error" in v2:
            for ev in gate_error(v2["error"]):
                yield ev
            return

        guard_state.pending_approval = None
        for ev in _gate_step_events(cid, guard_state, "revising", tool_name):
            yield f"data: {ev}\n\n"
        # 推 v2 面板（component 按名替换，前端预览原地更新）
        sid = v2.get("student_id", "")
        if component_name == "parent_report":
            comp_data = {"student_id": sid, "draft_id": gate_did,
                         "report_data": v2.get("content", {})}
        else:
            comp_data = {"student_id": sid, "draft_id": gate_did,
                         "plan": v2.get("content", {})}
        comp_evt = {"type": "component", "component": component_name,
                    "params": {"student_id": sid, "draft_id": gate_did,
                               "version": v2.get("version", 0), "data": comp_data}}
        yield f"data: {json.dumps(comp_evt, ensure_ascii=False)}\n\n"
        # 重开门：重新登记待批发送（批准后 _direct_replay_events 原机制重放）
        import agent.tools.diagnosis as _diag_tools
        send_fn = getattr(_diag_tools, tool_name)
        gate_action = "send_parent" if tool_name == "send_report_to_parent" else "send_student"
        guard_state.pending_approval = {
            "name": tool_name, "fn": send_fn,
            "kwargs": {"student_id": sid, "draft_id": gate_did},
        }
        gate_evt = {"type": "gate_open",
                    "gate_id": f"g-draft-{gate_did}",
                    "message": f"修订版（第 {v2.get('version')} 版）已生成，请确认是否发送",
                    "action": gate_action,
                    "recipient": "parent" if gate_action == "send_parent" else "student",
                    "draft_id": gate_did,
                    "version": v2.get("version", 0)}
        yield f"data: {json.dumps(gate_evt, ensure_ascii=False)}\n\n"
        # 门实体重开（同 draft_id → 同 gate_id；版本/文案刷新）
        if cid:
            try:
                from app.services.gate_service import gate_service
                from app.models.database import get_db as _gdb2
                gate_service.open_gate(
                    next(_gdb2()), cid, kind="draft", tool_name=tool_name,
                    kwargs={"student_id": sid, "draft_id": gate_did},
                    draft_id=gate_did, version=int(v2.get("version") or 0),
                    action=gate_action,
                    message=f"修订版（第 {v2.get('version')} 版）已生成，请确认是否发送")
            except Exception:
                pass
        for ev in _gate_step_events(cid, guard_state, "awaiting_confirmation", tool_name):
            yield f"data: {ev}\n\n"
        # 门已重开，恢复 LLM 说明本次修改点
        guard_state.begin_turn()
        note = _REJECT_CONTINUE_MSG.format(
            artifact=artifact_label,
            tool=tool_name,
            feedback=feedback, version=v2.get("version", 0))
        async for ev in _stream_note_continuation(agent, adapter, config, note):
            yield ev
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ── abandon：本步取消，运行继续，草稿保留 ────────────────────
    if action == "abandon" and (gate_did or _open_entity):
        guard_state.pending_approval = None
        # 关真实 gate_id——布尔门没有 draft_id，必须用决定时解析的当前门实体
        _close_gid = (_open_entity or {}).get("gate_id") or f"g-draft-{gate_did}"
        if cid and _close_gid:
            try:
                from app.services.gate_service import gate_service
                from app.models.database import get_db as _gdb3
                gate_service.close_gate(next(_gdb3()), _close_gid, "cancelled")
            except Exception:
                pass
        sid = (gate_pending.get("kwargs", {}) or {}).get("student_id", "")
        for ev in _gate_step_events(cid, guard_state, "cancelled", tool_name):
            yield f"data: {ev}\n\n"
        guard_state.begin_turn()
        note = _ABANDON_CONTINUE_MSG.format(target=sid or "该学生", artifact=artifact_label)
        async for ev in _stream_note_continuation(agent, adapter, config, note):
            yield ev
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ── approve：草稿记批准 → 确定性重放（沿用既有机制）────────────
    if gate_did:
        try:
            from app.models.database import get_db
            approved = artifact_svc.record_decision(
                next(get_db()), draft_id=gate_did, action="approve", actor_id=actor_id)
            if "error" in approved:
                # 草稿已被处理（如学生管理页已确认发送）——显式告知，不盲目重放
                for ev in gate_error(approved["error"]):
                    yield ev
                return
        except Exception as e:  # noqa: BLE001
            logger.warning("gate approve record failed: %s", e)

    # 决定解锁（ADR-0015：approve → running「重放中」）——todolist 不从
    # awaiting 直接跳 completed，重放结果出来才落终态（issue #18 story 7）
    for ev in _decision_unlock_events(cid, guard_state, "approve"):
        yield f"data: {ev}\n\n"
    direct_events, replay = await _direct_replay_events(guard_state, True, cid)
    if not direct_events:
        for ev in gate_error("没有待处理的确认请求"):
            yield ev
        return
    for ev in direct_events:
        yield f"data: {ev}\n\n"
    # 关真实 gate_id——布尔门没有 draft_id，用决定时解析的当前门实体兜底
    _close_gid = (_open_entity or {}).get("gate_id") or (f"g-draft-{gate_did}" if gate_did else "")
    if cid and _close_gid:
        try:
            from app.services.gate_service import gate_service
            from app.models.database import get_db as _gdb4
            gate_service.close_gate(next(_gdb4()), _close_gid, "executed")
        except Exception:
            pass
    _persist_send_completion(cid, guard_state, replay.get("name", ""),
                             bool(replay.get("success", True)))
    # 2026-09-21：批准后续接事件必须带 data: SSE 帧——此前裸 yield，
    # 前端解析器整段丢弃（批准后无下文/"卡住"的真实面目，实测 arch4 复现）
    async for ev in _stream_replay_continuation(agent, adapter, config, replay):
        yield f"data: {ev}\n\n"
    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat/langgraph/resume")
async def agent_chat_langgraph_resume(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("agent", "create", allow_self=True)),
):
    """中断恢复 — 发送 Command(resume=...) 继续被 interrupt 暂停的 graph。会话必须属于调用者。"""
    from dotenv import load_dotenv
    load_dotenv()

    from langgraph.types import Command
    from langgraph.errors import GraphInterrupt

    from agent.tools.filesystem import set_file_access_level, set_workspace_root
    set_file_access_level(request.file_access)
    set_workspace_root(request.workspace)

    # 教师身份注入（同 /stream，2026-08）
    from agent.tools.context import set_current_identity
    _teacher_id2 = current_user.get("user_id", "") or ""
    set_current_identity(
        _teacher_id2,
        current_user.get("role", ""),
        current_user.get("school_id"),
    )

    cid = request.conversation_id
    # 会话归属（阶段 4.6 批次 E）：原来回退到共享的 "default" 线程，等于所有人共用一个会话
    require_owned(db, cid, current_user)

    # 每会话执行锁（ADR-0016 §5）
    conv_lock = await acquire_conversation_lock(cid)

    # 学生身份：批准重放也会跑工具（分步导学作答回流），身份与 /stream 同一口径
    from agent.tools.context import set_current_student
    set_current_student(_resolve_student_identity(request, current_user, db) or "")
    persona = _resolve_persona(request, current_user)

    user_response = request.message or ""

    # ADR-0013 三值决定：decision 对象优先，旧字符串向后兼容。
    # 非草稿门（assign_adaptive_practice 等布尔门）退化为 legacy approved/cancelled。
    _decision, user_response = _resolve_resume_intent(
        request,
        (getattr(_guard_state_cache.get(cid), "pending_approval", None) or {}).get("name", ""),
    )

    store3 = await _get_app_store()
    # 复用缓存的 guard_state, 避免 approved 状态丢失（须透传给 create_v2，
    # 否则新建 GuardState 导致批准后 LLM 再 request_approval 又中断）
    cached_guard = _guard_state_cache.get(cid)
    agent, guard_state, AdapterClass = await _get_or_create_agent(
        persona, request.provider, version=request.version, store=store3,
        guard_state=cached_guard, teacher_id=_teacher_id2,
    )
    if guard_state is not None:
        try:
            guard_state.begin_turn()  # 批准/恢复也是新的一轮输入：重置重复计数
        except Exception:
            pass
        guard_state.conversation_id = cid  # 布尔门实体登记需要（ADR-0015 阶段 2）
    adapter = AdapterClass(conversation_id=cid or "")
    # 恢复计划状态（2026-08：批准/恢复后计划卡继续推进，不永远停在"执行中"）
    _restore_plan_state(adapter, guard_state)
    config = build_config(cid)

    # 批准/取消前只清孤儿（ADR-0016：毒化/孤儿中断 → 迁移，零模型调用）
    _ok2, _blocked_reason2, config = await _repair_thread_state(agent, config, cid)
    if not _ok2:
        async def _blocked_gen2():
            _err2 = json.dumps(
                {'type': 'error', 'message': _blocked_reason2, 'recoverable': False},
                ensure_ascii=False,
            )
            yield f"data: {_err2}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return _locked_stream(conv_lock, _blocked_gen2)

    # ADR-0013：草稿门三值决定处理器（无图中断的常态路径——门由数据状态强制）
    if _decision:
        resume_state_gate = await agent.aget_state(config)
        if not getattr(resume_state_gate, "next", None):
            return _locked_stream(
                conv_lock,
                lambda: _gate_decision_stream(cid, _decision, guard_state, agent, adapter, config))
        # 真实中断在挂 → 退化 legacy Command 流（user_response 已映射）

    from agent.context_manager import trim_context
    await trim_context(agent, config)

    full_reply = []
    # 批准类 resume：LangGraph 恢复中断时会重放 request_approval 的 on_tool_start，
    # adapter 会重复发 awaiting_approval → 用户批准后不该再收到确认请求。
    # 过滤首个重放事件（2026-08 修复「布置练习反复需要批准」）。
    # ADR-0015：只认协议值 "approved"（_resolve_resume_intent 已归一化）。
    skip_resume_approval = (user_response or "").strip().lower() == "approved"
    # 阶段 4：过滤按 gate_id 收窄——只吞被批准那个门的旧卡事件，
    # 同一流里后续新开的门照常弹出（不再吞整条流）。
    skip_gate_id = ""
    if skip_resume_approval:
        if isinstance(_decision, dict):
            skip_gate_id = _decision.get("gate_id", "")
        if not skip_gate_id:
            try:
                from app.services.gate_service import gate_service
                from app.models.database import get_db as _gdb5
                _og5 = gate_service.get_open_gate(next(_gdb5()), cid)
                skip_gate_id = (_og5 or {}).get("gate_id", "")
            except Exception:
                skip_gate_id = ""

    # 2026-08 确定性重放：无未决中断（模型没调 request_approval）时，
    # 直接重放 guard 登记的待批调用，批准后恢复 LLM 继续回答（链路不断）
    _resume_state = await agent.aget_state(config)
    if not (getattr(_resume_state, "next", None)):
        _direct, _replay = await _direct_replay_events(
            guard_state,
            (user_response or "").strip().lower() == "approved",
            cid,
        )
        if _direct:
            async def _direct_gen():
                for _ev in _direct:
                    yield f"data: {_ev}\n\n"
                async for _ev in _stream_replay_continuation(agent, adapter, config, _replay):
                    yield f"data: {_ev}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            return _locked_stream(conv_lock, _direct_gen)

    async def generate():
        nonlocal full_reply
        try:
            # 上下文占用:收集最后一次模型调用的 provider usage(2026-08 context 环)
            from agent.context_meter import build_context_event, extract_prompt_tokens
            from app.config import config as _cfg
            _last_prompt_tokens = None

            try:
                async with asyncio.timeout(_TURN_TIMEOUT):
                    async for event in agent.astream_events(
                        Command(resume=user_response),
                        config,
                        version="v2",
                    ):
                        if event.get("event") == "on_chat_model_end":
                            _pt = extract_prompt_tokens(event.get("data", {}).get("output"))
                            if _pt is not None:
                                _last_prompt_tokens = _pt
                        for result in adapter.feed(event):
                            if skip_resume_approval:
                                try:
                                    evt = json.loads(result)
                                    _is_old_gate = (
                                        evt.get("type") == "gate_open"
                                        and skip_gate_id
                                        and evt.get("gate_id") == skip_gate_id
                                    )
                                    if _is_old_gate:
                                        continue  # 只跳过被批准门的旧卡
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            try:
                                evt = json.loads(result)
                                if evt.get("type") == "text":
                                    full_reply.append(evt.get("content", ""))
                            except (json.JSONDecodeError, TypeError):
                                pass
                            yield f"data: {result}\n\n"

            except TimeoutError:
                _mark_run_paused_safe(cid)  # ADR-0016：超时即暂停，不自动重跑
                _err = json.dumps(
                    {'type': 'error', 'message': _TIMEOUT_ERROR_MSG, 'recoverable': True},
                    ensure_ascii=False,
                )
                yield f"data: {_err}\n\n"
                yield "data: [DONE]\n\n"
                return
            except asyncio.CancelledError:
                _mark_run_paused_safe(cid)  # 客户端断线：run 立刻标 paused
                raise
            except GraphInterrupt:
                # ADR-0015：interrupt 已退役——迁移间隙残留兜底：如实告知 + 标 paused
                _mark_run_paused_safe(cid)
                payload = {"type": "run_paused", "reason": "interrupted",
                           "message": "上一回合被中断，运行已暂停；重新发送消息即可继续。"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return

            final_state = await agent.aget_state(config)
            state_values = final_state.values if final_state else {}
            gs = guard_state
            result_text2 = state_values.get("last_result_text")
            if not result_text2 and full_reply:
                result_text2 = "".join(full_reply)
            # 上下文占用事件(provider usage 锚定 + 三段启发式构成)
            _ctx_event = build_context_event(
                _last_prompt_tokens, state_values.get("messages"), _cfg.CONTEXT_WINDOW,
            )
            for result in adapter.finalize(
                route=state_values.get("last_route") or (gs.last_route if gs else None),
                component=state_values.get("last_component") or (gs.last_component if gs else None),
                result_text=result_text2,
            ):
                if result == "[DONE]":
                    yield f"data: {json.dumps(_ctx_event, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                else:
                    yield f"data: {result}\n\n"

        except Exception as e:
            _mark_run_paused_safe(cid)  # ADR-0016：模型/系统报错 → run 如实标暂停
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return _locked_stream(
        conv_lock, generate,
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@router.post("/chat/langgraph/reset")
async def agent_chat_langgraph_reset(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("agent", "delete", allow_self=True)),
):
    """重置对话(v2) — 删除该线程在 chemai_checkpoints.db 的 checkpoint/writes。

    纯 v2 实现:直接清库,不再调用 v1 的 checkpointer。
    会话必须属于调用者（阶段 4.6 批次 E）。
    """
    require_owned(db, conversation_id, current_user)

    # ADR-0015 阶段 3：重置会话顺带关闭 gate 实体（不留幽灵门）
    try:
        from app.services.gate_service import gate_service
        gate_service.close_conversation(next(get_db()), conversation_id)
        _guard_state_cache.pop(conversation_id, None)
        _THREAD_OVERRIDES.pop(conversation_id, None)
    except Exception:
        pass

    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "chemai_checkpoints.db")
    if not os.path.exists(db_path):
        return {"success": False, "message": "数据库不存在"}

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM writes WHERE thread_id = ?", (conversation_id,))
        cur.execute("DELETE FROM checkpoints WHERE thread_id = ?", (conversation_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        cur.close()
        return {"success": True, "message": "对话已重置" if deleted else "对话不存在"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# Agent 文件上传
# ═══════════════════════════════════════════════════════════════════

ALLOWED_MIMES = {
    "image/jpeg", "image/png", "image/bmp", "image/webp", "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def agent_upload(
    file: UploadFile = File(...),
    _perm: None = Depends(PermissionChecker("agent", "create")),
):
    """Agent 对话中上传文件 → 预览 → 返回操作建议

    只给员工角色（教师端 `ChatPage.tsx` / `js/agent.js` 是仅有的调用方）。
    学生端将来若要传图，改成 `allow_self=True` 即可 —— 现在是 fail-closed。
    """
    from dotenv import load_dotenv
    load_dotenv()
    mime = file.content_type or ""
    if mime not in ALLOWED_MIMES:
        if not (file.filename or "").lower().endswith(('.doc', '.docx', '.pdf', '.png', '.jpg', '.jpeg')):
            raise HTTPException(400, f"不支持的文件格式: {mime}")

    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件超过 10MB 限制")

    # Save session
    from app.models.database import get_db, UploadSession
    session_id = _uuid.uuid4().hex[:16]
    db = next(get_db())
    try:
        db.add(UploadSession(
            id=session_id,
            file_data=file_data,
            file_name=file.filename or "unknown",
            mime_type=mime,
            status="previewing",
        ))
        db.commit()
    finally:
        db.close()

    # Preview
    from app.services.ocr_service import ocr_service
    import logging as _log
    _log.getLogger(__name__).info(f'agent_upload: mime={mime}, size={len(file_data)}, fn={file.filename}')
    result = await ocr_service.recognize(file_data, mime)

    # Update session
    db = next(get_db())
    try:
        from sqlalchemy import update as sql_update
        db.execute(
            sql_update(UploadSession)
            .where(UploadSession.id == session_id)
            .values(
                status="ready",
                preview_text=result.get("preview_text", ""),
                formula_result=json.dumps(result.get("formula_result", []), ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()

    preview_text = (result.get("preview_text", "") or "")
    if not preview_text and not result.get("success"):
        err = result.get("error", "unknown")
        logger.warning("agent_upload OCR failed: %s", err)
    return {
        "upload_id": session_id,
        "file_name": file.filename or "unknown",
        "preview_text": preview_text[:500] if preview_text else "",
        "error": result.get("error") if not result.get("success") else None,
        "actions": [
            {"id": "import", "label": "导入题库"},
            {"id": "grade", "label": "批改判卷"},
            {"id": "search", "label": "搜题解析"},
        ],
    }
# reload trigger 2026-07-05T02:27:17.669215
