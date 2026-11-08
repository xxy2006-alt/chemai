"""ChemAI Agent Guard Infrastructure — shared by v1 and v2 agent architectures.

GuardState provides per-invocation safety: deduplication, call limits,
prerequisite checks, and approval gating for destructive tools.

Extracted from langgraph_agent.py (v1 multi-agent) so both v1 and v2 can
import from a neutral module without circular dependencies.
"""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

# ── Tool call limits (lazy-loaded from TOOL_META to avoid circular imports) ──
TOOL_CALL_LIMITS: dict[str, int] = {}
_LIMITS_INITIALIZED = False

def _ensure_call_limits():
    global TOOL_CALL_LIMITS, _LIMITS_INITIALIZED
    if _LIMITS_INITIALIZED:
        return
    try:
        from agent.tools import TOOL_META
        TOOL_CALL_LIMITS = {t.__name__: m["call_limit"] for t, m in TOOL_META.items()}
    except ImportError:
        pass
    _LIMITS_INITIALIZED = True


# ── Approval gating ──
# 破坏性工具：assign_adaptive_practice / delete_bank 需要先 request_approval。
# write/edit/bash 不在其列——它们自带工作区判定（区内直接执行、区外按次审批，
# bash 另有白名单+危险命令过滤），一刀切前置审批会让"工作区内写文件"也要
# 弹卡（2026-08 全工具链路验收实测：写 test.txt 被 requires_approval 拦截，
# 与 DSH 工作区语义冲突）。
TOOL_APPROVAL_REQUIRED = {"assign_adaptive_practice", "delete_bank"}

# 生成即门（ADR-0013/#13 冒烟补丁）：这些工具成功即自带门卡（返回 approval_needed
# + draft_id），guard 登记对应「发送」调用而非工具自身——生成不可重放。
_GATE_OPEN_TOOLS = {"generate_learning_plan", "generate_parent_report"}

# ── 连续重复调用护栏（2026-08，DSH repeat-tool-reminder 同款）──
_REPEAT_THRESHOLDS = (3, 5, 8)


def _get_db():
    """轻量 DB session（布尔门实体登记用，ADR-0015 阶段 2）。
    失败由调用方 try/except 兜底——门实体登记失败不阻断工具拦截本身。"""
    from app.models.database import get_db
    return next(get_db())


def _repeat_reminder(name: str, count: int) -> str:
    """生成重复调用提醒文案：第 3 次温和，第 5/8 次严厉（只提醒不阻断）。"""
    if count == 3:
        return (
            f"提醒：你正在连续第 {count} 次用完全相同的参数调用 {name}。"
            "如果它没有按预期工作，请换一种思路——修正参数、换其他工具、"
            "或直接向老师说明情况，不要盲目重复。"
        )
    return (
        f"警告：已连续 {count} 次用完全相同参数调用 {name}，继续重复大概率不会成功。"
        "请立即停止重复：分析失败原因、改用其他工具或参数，"
        "或直接向老师说明情况并请求指导。"
    )

# ── Recursion limits ──
RECURSION_LIMIT_V1 = 8
RECURSION_LIMIT_V2 = 12

_CONFIRMATION_WORDS = {
    "同意", "可以", "好的", "好", "行", "确认", "发送", "发吧", "发",
    "批准", "ok", "okay", "yes", "approve", "approved", "没问题", "就这样",
    "发送给学生", "同步给家长", "可以发送", "请发送", "发过去",
}


def is_confirmation(text: str) -> bool:
    """自然语言确认判断（2026-08 发送确认门）：老师打字"同意/发吧"等
    即视为批准；修改指令等其他内容不视为确认。"""
    normalized = (text or "").strip().lower().replace("，", "").replace("。", "")
    if normalized in _CONFIRMATION_WORDS:
        return True
    # 短句且含确认性动词（如"同意发送""那就发吧"）
    if len(normalized) <= 12 and any(w in normalized for w in ("同意", "批准", "发吧", "发送")):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# GuardState
# ═══════════════════════════════════════════════════════════════════════

class GuardState:
    """Per-invocation safety state shared across all tool calls within one request.

    Tracks: dedup (same tool+args within 5s = skip), call limits (per-tool max),
    prerequisite checks (required args present), and approval gating (destructive
    tools must first call request_approval).
    """

    def __init__(self):
        self.seen_calls: set[str] = set()
        self.call_counts: dict[str, int] = {}
        self.approved: bool = False
        self.last_route: dict | None = None
        self.last_component: dict | None = None
        self.panel_opened: bool = False
        # 2026-08 确定性审批重放：approval_needed 的调用被拦截时登记
        # （fn/kwargs），request_approval 获批后自动重放，不再依赖 LLM 自觉重试
        self.pending_approval: dict | None = None
        # 2026-08 计划状态持久化：plan_task 生成的步骤跨流保存（批准/恢复后
        # 由 channel 补发 plan_progress，避免计划卡永远停在"执行中"）
        self.plan_steps: list = []
        # 2026-08 连续重复调用护栏（DSH repeat-tool-reminder 同款）：
        # 同工具+同参数连续调用计数，阈值 [3,5,8] 时注入提醒（只提醒不阻断）
        self.last_call_key: str | None = None
        self.consecutive_repeats: int = 0
        # 2026-09-21 门类工具串行锁：并行 tool_calls（同一条 AI 消息多个调用，
        # ToolNode 并发执行）时，「pending 检查 → 登记门」之间存在整个工具执行的
        # await 窗口，两个门类工具可同时通过检查 → 双门齐开（实测）。门类工具的
        # 检查+登记必须持锁串行，拿锁后重验 pending。
        self._gate_lock: "asyncio.Lock | None" = None

    def gate_lock(self) -> "asyncio.Lock":
        if self._gate_lock is None:
            self._gate_lock = asyncio.Lock()
        return self._gate_lock

    def begin_turn(self) -> None:
        """新一轮用户输入开始：重置连续重复计数（跨轮不累计，DSH 同语义）。"""
        self.last_call_key = None
        self.consecutive_repeats = 0

    def track_repeat(self, name: str, kwargs: dict) -> int:
        """登记一次工具调用，返回连续重复次数（1 = 首次或换了个调用）。"""
        key = f"{name}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False)}"
        if key == self.last_call_key:
            self.consecutive_repeats += 1
        else:
            self.last_call_key = key
            self.consecutive_repeats = 1
        return self.consecutive_repeats

    def check_dedup(self, name: str, kwargs: dict) -> bool:
        """Return True if this exact call was already made (dedup hit)."""
        key = f"{name}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False)}"
        if key in self.seen_calls:
            return True
        self.seen_calls.add(key)
        return False

    def forget_call(self, name: str, kwargs: dict) -> None:
        """撤销一次调用登记——调用未实际执行时（如返回 approval_needed）调用，
        批准后重试不会被「检测到重复调用」拦截。"""
        key = f"{name}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False)}"
        self.seen_calls.discard(key)

    def remember_call(self, name: str, kwargs: dict) -> None:
        """补一次调用登记——批准重放绕过 _guarded 直接执行裸 fn，登记 dedup 键，
        LLM 重调同参工具时命中「重复调用」拦截（issue #18 阶段 2：不再双执行）。"""
        key = f"{name}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False)}"
        self.seen_calls.add(key)

    def check_limit(self, name: str) -> str | None:
        """Return error message if call limit exceeded, else None."""
        _ensure_call_limits()
        limit = TOOL_CALL_LIMITS.get(name)
        if limit is None:
            return None
        count = self.call_counts.get(name, 0) + 1
        self.call_counts[name] = count
        if count > limit:
            return f"已调用 {name} {count} 次（上限 {limit} 次），请基于已有结果继续。"
        return None

    def check_prerequisites(self, name: str, kwargs: dict) -> str | None:
        """Return error message if required params are missing, else None."""
        # 自动出题双路径（用户决策，2026-08）：generate_questions 不再强制先开面板——
        # 对话里给全 知识点+题型+数量 可直接生成；面板路径仍可先 show_exam_workbench。
        # show_exam_workbench 不设前置：面板的意义就是让用户在面板内补数据。
        prereqs = {
            "search_exam_bank": ["keyword"],
            "diagnose_barrier": ["student_id_or_class_id"],
            "weekly_report": ["student_id_or_class_id"],
            "assign_adaptive_practice": ["student_id_or_class_id"],
        }
        for field in prereqs.get(name, []):
            if field == "student_id_or_class_id":
                if not any((kwargs.get(k, "") or "").strip() for k in
                           ("student_id", "student_name", "class_id", "class_name")):
                    return "缺少必要信息：请先向用户确认学生姓名/学号或班级。"
                continue
            if field == "keyword":
                val = (kwargs.get("keyword", "") or "").strip()
                if not val or len(val) <= 2:
                    return "搜索关键词太宽泛。请先向用户确认：需要哪个具体知识点的真题？"
                continue
            if field == "knowledge_points":
                val = kwargs.get("knowledge_points", "") or ""
                if isinstance(val, list):
                    empty = not any(str(x).strip() for x in val)
                else:
                    empty = not str(val).strip()
                if empty:
                    return (
                        "缺少必要信息：知识点为空。请先向用户确认本次要考察哪些知识点"
                        "（例如：物质的量、氧化还原反应）。"
                    )
                continue
            if not (kwargs.get(field, "") or "").strip():
                return f"缺少必要信息: {field}。请先向用户确认。"
        return None


# ═══════════════════════════════════════════════════════════════════════
# Tool Wrappers
# ═══════════════════════════════════════════════════════════════════════

def _make_guarded_tool(fn, guard_state: GuardState, requires_approval: bool = False):
    """Wrap a tool function with GuardState safety checks.

    Applies: prerequisite check → call limit → dedup → approval gating.
    Strips _route and _component fields from result before returning.
    """
    from langchain_core.tools import tool as lc_tool, StructuredTool

    base_tool = lc_tool(fn)

    async def _guarded(**kwargs) -> str:
        name = fn.__name__
        # 2026-08 连续重复调用护栏：登记并生成提醒（只提醒不阻断，DSH 同款）。
        # 必须放在 dedup 之前——被去重拦截的重复尝试也算连续重复，第 3/5/8 次附提醒
        _reminder = None
        try:
            _rep = guard_state.track_repeat(name, kwargs)
            if _rep in _REPEAT_THRESHOLDS:
                _reminder = _repeat_reminder(name, _rep)
        except Exception:
            pass

        def _out(payload: dict) -> str:
            if _reminder:
                payload = dict(payload)
                payload["_reminder"] = _reminder
            return json.dumps(payload, ensure_ascii=False)

        # 数据范围校验（ADR-0014）：接缝统一执行 TOOL_META 里声明的范围规则。
        #
        # 取代原先那段「只做默认填充」的身份回退 —— 它挡不住模型自报身份
        # （`teacher_id` 传了就用传的），也完全没覆盖 `student_id` / `class_id`。
        # 现在：ID 直接判范围、姓名在范围内搜、`teacher_id` 以服务端身份为准。
        # 无身份则 fail-closed（评测之外的路径不会有这情况）。
        from agent.tools.data_scope import check_tool_scope
        if (denied := check_tool_scope(fn, kwargs)) is not None:
            return _out(denied)
        if (msg := guard_state.check_prerequisites(name, kwargs)):
            return _out({"error": msg, "missing_prerequisites": True})
        if (msg := guard_state.check_limit(name)):
            return _out({"error": msg, "limit_exceeded": True})
        if guard_state.check_dedup(name, kwargs):
            return _out({"error": "检测到重复调用，已跳过", "dedup_skipped": True})
        # C1-Q3 全拦（issue #18 阶段 1）：确认门开着（有未决门）时，agent 的一切
        # 工具调用都被拒——LLM 自然转为文字说明。根治「第二个门覆盖第一个 pending」
        # 与「门没批就推进后续步骤」。重放路径走 pending["fn"] 裸函数，不经过本包装。
        # 2026-09-21 文案契约分离（架构审查 C）：llm_brief 是给模型的中性事实
        # （第三人称，无祈使句——祈使句会被 LLM 鹦鹉学舌念给用户）；ui_label 是
        # 给前端工具卡的展示字段。error 保留为机器判定用，不再是用户可见文案。
        if getattr(guard_state, "pending_approval", None) is not None:
            return _out({
                "error": "waiting_for_gate",
                "llm_brief": "当前有一张确认卡等待老师决定，此操作已暂缓。"
                             "老师处理完确认卡后，任务会自动继续。",
                "ui_label": "等待确认",
                "gate_open_blocked": True,
            })
        if requires_approval:  # ADR-0015：粘性 approved 已退役——首次调用一律拦下登记门
            # 与 approval_needed 同待遇：登记待重放 —— 老师批准后由
            # request_approval 自动补跑本次调用。
            # （2026-09-14 修：原先只有 approval_needed 那条路登记，而
            #  assign_adaptive_practice 这类工具是被**护栏直接拦下**的，
            #  结果批准后没有东西可重放 → 任务断在"等待确认"那一步。）
            # ADR-0015 阶段 2：布尔门实体化——拦下即登记 gate 实体（重启可重建）
            # 并返回 approval_needed 门卡载荷（与草稿门同构，adapter 据此发卡，
            # 不再依赖 request_approval / interrupt）。
            guard_state.forget_call(name, kwargs)
            guard_state.pending_approval = {"name": name, "fn": fn, "kwargs": kwargs}
            from app.services.gate_service import boolean_gate_id, gate_service
            gate_id = boolean_gate_id(name, kwargs)
            try:
                if getattr(guard_state, "conversation_id", ""):
                    gate_service.open_gate(
                        _get_db(), guard_state.conversation_id,
                        kind="boolean", tool_name=name, kwargs=kwargs,
                        action="", message="此操作需要老师确认后执行")
            except Exception:
                pass  # 实体登记失败不阻断拦截本身（内存 pending 仍在）
            return _out({
                "approval_needed": True,
                "message": "此操作需要老师确认，请在确认卡上批准/打回/放弃。",
                "message_gate": "此操作需要老师确认：请确认是否执行。",
                "gate_id": gate_id,
                "action": "",
                "awaiting_gate": True,
            })
        result = await fn(**kwargs)
        if name == "show_exam_workbench":
            guard_state.panel_opened = True
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if isinstance(data, dict):
                    # 按次审批（工作区外访问，pi 式权限门）：批准是 guard 层的事，
                    # 不是 LLM 的事——工具返回 approval_needed 时：
                    #   - 已批准 → set_elevate_once 单次放行，立即重放工具
                    #   - 未批准 → 原样返回给 LLM，由 LLM 按工具 docstring 调 request_approval
                    #     （2026-08 修复「read 卡死」：不再在工具内直接 interrupt()——
                    #     langgraph 1.x 的 astream_events 会静默吞掉工具内 interrupt，
                    #     既没有审批卡、又会在带旧中断状态的线程上永久挂死流）
                    #
                    # 例外（ADR-0013 生成即门，2026-09 真实冒烟发现）：草稿生成工具
                    # 返回 approval_needed 时草稿已落库、无破坏性副作用，任何情况下
                    # 都不得重放生成（会 regenerate 自身）；登记的是对应的「发送」调用
                    # ——老师批准 → 确定性重放发送；打回 → channel 确定性修订。
                    # 这保证「生成后停等确认」不依赖模型自觉调发送工具。
                    if data.get("approval_needed") and name in _GATE_OPEN_TOOLS:
                        import agent.tools.diagnosis as _diag_tools
                        pending_name = ("send_report_to_parent"
                                        if name == "generate_parent_report"
                                        else "send_learning_plan")
                        send_args = {"student_id": data.get("student_id", ""),
                                     "draft_id": data.get("draft_id", "")}
                        if send_args["draft_id"]:
                            # 重验（2026-09-21）：并行 tool_calls 时本工具执行的
                            # await 窗口内，另一个门类工具可能已登记 pending——
                            # 不得覆盖（否则双门齐开，实测 repro-zhou-0920）
                            if guard_state.pending_approval is not None:
                                return _out({
                                    "error": "waiting_for_gate",
                                    "llm_brief": "当前有一张确认卡等待老师决定，本次操作已暂缓；"
                                                 "草稿已生成不会丢失，老师处理完确认卡后可再次发起。",
                                    "ui_label": "等待确认（草稿已生成，当前门处理完可再发起）",
                                    "gate_open_blocked": True,
                                })
                            guard_state.forget_call(name, kwargs)
                            guard_state.pending_approval = {
                                "name": pending_name,
                                "fn": getattr(_diag_tools, pending_name),
                                "kwargs": send_args,
                            }
                            # 2026-09-21 门实体登记收权（架构审查 A）：草稿门实体
                            # 由 guard 统一落库（此前 adapter 也开一扇 → 双实体双
                            # gate_id，前端两张卡、批准后僵尸门）。adapter 只发卡。
                            try:
                                if getattr(guard_state, "conversation_id", ""):
                                    from app.services.gate_service import gate_service
                                    gate_service.open_gate(
                                        _get_db(), guard_state.conversation_id,
                                        kind="draft", tool_name=pending_name,
                                        kwargs=send_args,
                                        draft_id=str(send_args["draft_id"]),
                                        version=int(data.get("version") or 0),
                                        action=str(data.get("action") or ""),
                                        message=str(data.get("message_gate")
                                                    or data.get("message") or "请确认操作"),
                                    )
                            except Exception:
                                pass  # 实体登记失败不阻断拦截（内存 pending 仍在）
                        # 无 draft_id（生成失败等）→ 原样返回，不弹门
                    elif data.get("approval_needed"):
                        # 按次审批（工作区外访问等）。ADR-0015 阶段 2：粘性
                        # approved 的「已批准→自动放行重跑」退役（H4：一次批准
                        # 解锁同轮后续一切按次审批）——一律登记待重放 + 门实体，
                        # 批准后由 channel 确定性重放（set_elevate_once 真单次消费）。
                        from app.services.gate_service import boolean_gate_id, gate_service
                        _gid = boolean_gate_id(name, kwargs)
                        try:
                            if getattr(guard_state, "conversation_id", ""):
                                gate_service.open_gate(
                                    _get_db(), guard_state.conversation_id,
                                    kind="boolean", tool_name=name, kwargs=kwargs,
                                    action="", message=str(data.get("message") or "此操作需要老师确认"))
                        except Exception:
                            pass
                        guard_state.forget_call(name, kwargs)
                        guard_state.pending_approval = {
                            "name": name, "fn": fn, "kwargs": kwargs,
                        }
                        data["gate_id"] = _gid
                        data.setdefault("message_gate", data.get("message") or "此操作需要老师确认")
                        data["awaiting_gate"] = True
                    if "_route" in data:
                        guard_state.last_route = data.pop("_route")
                    if "_component" in data:
                        guard_state.last_component = data.pop("_component")
                    if _reminder:
                        data["_reminder"] = _reminder
                    return json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(result, dict):
            if "_route" in result:
                guard_state.last_route = result.pop("_route")
            if "_component" in result:
                guard_state.last_component = result.pop("_component")
            if _reminder:
                result["_reminder"] = _reminder
            return result
        if _reminder and isinstance(result, str):
            return json.dumps({"_reminder": _reminder, "result": result[:2000]}, ensure_ascii=False)
        return result

    return StructuredTool(name=base_tool.name, description=base_tool.description,
                          args_schema=base_tool.args_schema, coroutine=_guarded)


def _make_request_approval_tool(guard_state: GuardState):
    """Create a request_approval tool that triggers LangGraph interrupt().

    2026-08 修复「布置练习反复需要批准」：同一调用内已批准过（guard_state.approved）
    后，LLM 再次调用 request_approval 不再中断 —— 直接返回，避免跨回合重复审批卡。
    """
    from langchain_core.tools import tool as lc_tool
    from langgraph.types import interrupt

    @lc_tool
    async def request_approval(message: str, context: str = "") -> str:
        """向老师请求确认。"""
        if guard_state.approved:
            return "already approved"  # 已批准过，不再中断（防 LLM 重复请求）
        # 尊重 resume 返回值：只有明确批准才置位 approved——取消不得留下
        # 已批准状态（7a3ae89 安全语义；2026-08 read 卡死修复配套：
        # 预置位会配合 channel 的「未决中断自动清场」把取消变成静默批准）
        answer = interrupt({"type": "approval", "message": message, "context": context})
        if str(answer or "").strip().lower() in ("approved", "批准", "确认", "同意"):
            guard_state.approved = True
            # 2026-08 确定性重放：获批后自动重跑被拦截的调用（不再依赖 LLM 自觉重试——
            # 实测批准后模型可能直接收尾，链路断掉）
            pending = guard_state.pending_approval
            guard_state.pending_approval = None
            if pending is not None:
                from agent.tools.filesystem import set_elevate_once
                set_elevate_once()
                try:
                    _replayed = await pending["fn"](**pending["kwargs"])
                    _payload = json.loads(_replayed) if isinstance(_replayed, str) else _replayed
                    if not isinstance(_payload, dict):
                        _payload = {"result": _payload}
                    return json.dumps({
                        "__replayed_tool": pending["name"],
                        "result": _payload,
                        "note": (
                            "这是刚才被批准的「读取文件」操作的实际结果，"
                            "请直接向用户展示其中的内容，不要再请求批准。"
                        ),
                    }, ensure_ascii=False)
                except Exception as _e:  # noqa: BLE001
                    return json.dumps({
                        "__replayed_tool": pending["name"],
                        "result": {"error": f"重放失败: {_e}"},
                    }, ensure_ascii=False)
            return str(answer)
        # 取消：给模型的工具结果必须明确终止，否则模型会反复再发起审批
        # （每次都会产生新 interrupt → 新孤儿 tool_call，2026-08 实测）
        # ADR-0015：pending 必须一并清空——否则后一句「好的」命中确认分支
        # 幽灵批准已取消的动作（2026-09-20 阶段 0 回归红线）。
        guard_state.pending_approval = None
        return "该操作已按老师的决定取消，不会执行。任务在此分支结束，请用一句话向老师确认即可。"
    return request_approval


# ═══════════════════════════════════════════════════════════════════════
# Checkpointer (shared SqliteSaver singleton)
# ═══════════════════════════════════════════════════════════════════════

import aiosqlite as _aiosqlite  # noqa: E402
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa: E402

_checkpointer = None


async def _get_checkpointer():
    """Return the shared AsyncSqliteSaver singleton for agent conversation persistence."""
    global _checkpointer
    if _checkpointer is None:
        # 钉死绝对路径（2026-08-16）：相对路径随进程 cwd 漂移，曾导致重启后
        # 历史对话"消失"（写库与 conversation.py 读库指向不同文件）。
        import os as _os
        _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        conn = await _aiosqlite.connect(_os.path.join(_proj, "chemai_checkpoints.db"))
        _checkpointer = AsyncSqliteSaver(conn)
        await _checkpointer.setup()
    return _checkpointer


# ═══════════════════════════════════════════════════════════════════════
# LLM Model Factory
# ═══════════════════════════════════════════════════════════════════════

def get_langchain_model(provider: str):
    """Return a ChatOpenAI model for the given provider (deepseek/mimo/zhipu/dashscope)."""
    from langchain_openai import ChatOpenAI
    from app.config import config as _cfg

    api_keys = _cfg.provider_keys
    configs = {
        "deepseek": {"model": _cfg.DEEPSEEK_MODEL, "base_url": _cfg.DEEPSEEK_BASE_URL},
        "mimo": {"model": _cfg.MIMO_MODEL, "base_url": _cfg.MIMO_BASE_URL},
        "zhipu": {"model": _cfg.ZHIPU_MODEL, "base_url": "https://open.bigmodel.cn/api/paas/v4"},
        "dashscope": {"model": _cfg.DASHSCOPE_MODEL, "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    }
    cfg = configs.get(provider, configs["deepseek"])
    # stream_usage=True: 流式响应末尾携带 usage(DeepSeek 等 OpenAI 兼容端点支持),
    # 供 context_meter 计算上下文占用;不支持 include_usage 的端点自动忽略
    # max_retries=2 + request_timeout=60: 模型请求级指数退避重试（DSH llm-retry 同款，
    # 2026-08：接口抖动/限流不再导致整轮白跑）
    return ChatOpenAI(model=cfg["model"], api_key=api_keys.get(provider, ""),
                      base_url=cfg["base_url"], temperature=0.3, max_tokens=4096,
                      stream_usage=True, max_retries=2, request_timeout=60.0)
