"""LangGraph SSE Adapter v2 — astream_events → ChemAI SSE 事件格式.

Single-path adapter for single-agent mode. No sub_agent_depth tracking,
no route cards, no sub-agent panels. Tools and text flow directly.
"""

import json
import re


def _tool_category(name: str) -> str:
    return name.split("_")[0] if "_" in name else name


# S3 工件类工具（2026-08）：结果以图表/面板/题目卡内联渲染，文本不得复述数据
_SUPPRESS_TEXT_TOOLS = {
    "show_diagnosis", "diagnose_barrier", "generate_learning_plan",
    "weekly_report", "generate_parent_report", "generate_questions",
    "search_exam_bank", "balance_equation",
    "list_banks", "list_teacher_exams", "query_batch_grades",
    # 批次/任务类：结果含内部标识（batch_id/task_id），文本复述即泄漏（2026-08）
    "query_ocr_progress", "grade_answer_sheets", "save_grading_results",
    "query_grading_queue", "confirm_exam_grades", "query_assignment_progress",
}

# 压制后替代模型文本的标准过渡文案（避免空 AI 气泡 + 保持"最多一句"体验）
_TEXT_TRANSITIONS = {
    "diagnose_barrier": "诊断报告已生成，见下方图表",
    "show_diagnosis": "诊断报告已生成，见下方图表",
    "generate_learning_plan": "学习计划已生成，请在下方预览",
    "weekly_report": "周报已生成，请查看下方卡片",
    "generate_parent_report": "家长报告预览已生成，请查看下方卡片",
    "generate_questions": "题目已生成，请查看下方卡片",
    "search_exam_bank": "真题已找到，请查看下方卡片",
    "balance_equation": "配平结果见下方卡片",
    "plan_task": "任务计划已生成，请查看下方计划卡",
    "list_banks": "题库列表如下方卡片",
    "list_teacher_exams": "考试列表如下方卡片",
    "query_batch_grades": "成绩如下方卡片",
    "query_ocr_progress": "识别进度如下方卡片",
    "grade_answer_sheets": "批改结果如下方卡片",
    "save_grading_results": "保存结果如下方卡片",
    "query_grading_queue": "待确认队列如下方卡片",
    "confirm_exam_grades": "成绩确认结果如下方卡片",
    "query_assignment_progress": "布置进度如下方卡片",
}


def _serialize_args(tool_input: dict) -> dict:
    return tool_input


def _json_safe_payload(parsed, cap: int = 8000) -> str:
    """工具结果 → SSE 载荷。大结果优先截断 content/result/text 字段（保持 JSON
    合法），而不是整体切片——否则 25KB 的 read 结果截到 8000 变成非法 JSON，
    前端解析失败会把大文件显示成「（空文件）」（2026-08 read 卡死根因）。"""
    if isinstance(parsed, dict):
        out = dict(parsed)
        budget = max(256, cap - 600)  # 给其他字段与 JSON 结构预留空间
        for key in ("content", "result", "text"):
            val = out.get(key)
            if isinstance(val, str) and len(val) > budget:
                out[key] = val[:budget] + "\n…[内容过长已截断，可要求分页/limit 读取]"
                out["truncated"] = True
        payload = json.dumps(out, ensure_ascii=False)
    else:
        payload = json.dumps(parsed, ensure_ascii=False)
    if len(payload) > cap:
        payload = payload[:cap].rstrip("\\")
    return payload


class LangGraphSSEAdapterV2:
    """Simplified SSE adapter for single ReAct agent.

    Emits: tool_call, tool_result, phase, text, component, navigate, done.
    No sub_agent_start / sub_agent_end / subagent_text / route events.
    """

    def __init__(self, conversation_id: str = ""):
        self._phase = "thinking"
        self._tool_results = []
        self._did_stream_text = False
        self._last_tool_text = ""       # last tool's text output (for dedup)
        self._reply_prefix = ""         # accumulate first chars of new reply
        self._skip_dedup = False        # dedup already decided for this reply
        self._tool_complete = False     # tool already gave a complete answer — skip LLM text
        # 2026-08 S3：工件类工具（图表/面板/题目/报告/计划已内联渲染）出结果后，
        # 压制本轮模型后续文本——文本不得复述面板内容
        self.suppress_text = False
        self._pending_transition = ""   # 压制后替代文本（一句话过渡）
        self._transition_sent = False   # 每轮只发一次
        # Spec 06: planner state — plan_task 结果驱动 plan_summary/plan_progress
        self._plan_steps = []
        self._plan_active = False
        # ADR-0013：Plan Run 持久化——conversation_id 由 channel 注入，
        # 步状态变更同步 plan_run_service（刷新/重启后 todolist 可重同步）
        self._conversation_id = conversation_id

    def feed(self, event: dict) -> list[str]:
        event_type = event.get("event", "")
        name = event.get("name", "")
        data = event.get("data", {})

        # ── Tool start ──
        if event_type == "on_tool_start":
            if name == "request_approval":
                # ADR-0015：request_approval 已退役——此分支只兜底旧 checkpoint
                # 迁移间隙的重放事件。按 pause 语义呈现，不出确认按钮。
                return [json.dumps({
                    "type": "run_paused", "reason": "interrupted",
                    "message": data.get("input", {}).get("message", "运行已暂停"),
                }, ensure_ascii=False)]
            return [json.dumps({
                "type": "tool_call", "name": name,
                "tool": _tool_category(name),
                "args": _serialize_args(data.get("input", {})),
            }, ensure_ascii=False)]

        # ── Tool end ──
        if event_type == "on_tool_end":
            if name == "request_approval":
                # 2026-08 确定性重放：获批后 request_approval 自动重跑被拦截的调用，
                # 结果带 __replayed_tool 标记 → 合成原工具（如 read）的 tool_result，
                # 前端渲染真实内容卡（批准后不再断链）
                try:
                    _raw = str(data.get("output", ""))
                    _m = re.match(r"^content=(['\"])(.*?)\1(?:\s+(?:additional_kwargs|name|tool_call_id|id|type)=.*)?$",
                                  _raw, re.S)
                    if _m:
                        _raw = _m.group(2).replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
                    _parsed = json.loads(_raw)
                    if isinstance(_parsed, dict) and "__replayed_tool" in _parsed:
                        _inner = _parsed.get("result")
                        _evs = [json.dumps({
                            "type": "tool_result",
                            "name": _parsed["__replayed_tool"],
                            "tool": _tool_category(_parsed["__replayed_tool"]),
                            "success": not (isinstance(_inner, dict) and "error" in _inner),
                            "result": _json_safe_payload(_inner),
                        }, ensure_ascii=False)]
                        # 重放工具也推进计划卡（2026-08：批准后步骤不再永远"执行中"）
                        if self._plan_active:
                            _pl = self._advance_plan(
                                _parsed["__replayed_tool"],
                                not (isinstance(_inner, dict) and "error" in _inner),
                                _inner if isinstance(_inner, dict) else None)
                            _evs.extend(_pl)
                        return _evs
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
                return []
            output = data.get("output", "")
            result_str = str(output) if not isinstance(output, str) else output
            success = True

            # Unwrap LangGraph ToolMessage repr:
            #   content='...JSON...' name='tool_name' tool_call_id='call_xxx'
            #   content='...JSON...' additional_kwargs={...}
            # （非贪婪匹配到 content 值结束的引号，兼容带 name/tool_call_id/additional_kwargs 后缀）
            m = re.match(r"^content=(['\"])(.*?)\1(?:\s+(?:additional_kwargs|name|tool_call_id|id|type)=.*)?$",
                         result_str, re.S)
            if m:
                inner = m.group(2).replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
                result_str = inner

            # Extract structured images (raw_decode handles trailing content)
            image_events = []
            parsed = None
            try:
                decoder = json.JSONDecoder()
                parsed, _ = decoder.raw_decode(result_str) if isinstance(result_str, str) else (result_str, 0)
                if isinstance(parsed, dict) and "images" in parsed:
                    # Replace result_str with just the text (LLM sees clean text)
                    result_str = parsed.get("text", result_str)
                    for img_entry in parsed.get("images", []):
                        if img_entry.get("urls"):
                            image_events.append(json.dumps({
                                "type": "exam_images",
                                "q_index": img_entry.get("q_index", 0),
                                "title": img_entry.get("title", ""),
                                "urls": img_entry.get("urls", []),
                            }, ensure_ascii=False))
                    # Store only text in _tool_results
                    self._tool_results.append({"tool_name": name, "result": {"text": result_str}})
                    # Store for text dedup (LLM should not echo tool guidance verbatim)
                    self._last_tool_text = result_str
                    # If tool returned structured tutoring response, skip LLM text after it
                    if "guidance" in parsed or "step" in parsed:
                        self._tool_complete = True
                elif isinstance(parsed, dict) and "error" in parsed:
                    success = False
                    self._tool_results.append({"tool_name": name, "result": parsed})
                else:
                    self._tool_results.append({"tool_name": name, "result": parsed})
            except Exception as exc:
                self._tool_results.append({
                    "tool_name": name,
                    "result": {"error": str(exc), "raw": str(result_str)[:500]},
                })
                success = False

            # 下发干净的 JSON（解析成功时重新序列化，避免 repr 残留/截断导致前端拿不到结构化数据）
            if parsed is not None and not (isinstance(parsed, dict) and "images" in parsed):
                result_payload = _json_safe_payload(parsed)
            else:
                result_payload = _json_safe_payload(
                    result_str if isinstance(result_str, str) else str(result_str))

            events = [json.dumps({
                "type": "tool_result", "name": name,
                "tool": _tool_category(name), "success": success,
                "result": result_payload,
            }, ensure_ascii=False)]
            events.extend(image_events)

            # 2026-08 审批卡不再依赖模型调 request_approval：工具结果带
            # approval_needed 时直接发门卡。ADR-0015 阶段 4：事件契约类型化——
            # gate_open{gate_id, action, recipient, draft_id?, version?}，
            # 「等待人工」与「系统暂停」(run_paused) 在 wire 上是两个事件。
            if isinstance(parsed, dict) and parsed.get("approval_needed"):
                gate_did = str(parsed.get("draft_id") or "")
                gate_action = str(parsed.get("action") or "")
                recipient = ("parent" if gate_action == "send_parent"
                             else "student" if gate_action == "send_student" else "system")
                gate_gid = str(parsed.get("gate_id") or (f"g-draft-{gate_did}" if gate_did else ""))
                gate_evt = {
                    "type": "gate_open",
                    "gate_id": gate_gid,
                    # 生成即门：门卡文案用 message_gate（message 是生成成功文案）
                    "message": parsed.get("message_gate") or parsed.get("message", "请确认操作"),
                    "action": gate_action,
                    "recipient": recipient,
                }
                if gate_did:
                    gate_evt["draft_id"] = gate_did
                if parsed.get("version") is not None:
                    gate_evt["version"] = parsed["version"]
                events.append(json.dumps(gate_evt, ensure_ascii=False))
                # 2026-09-21 门实体登记收权（架构审查 A）：adapter 只发卡不落库。
                # 实体由 guard 统一登记（生成即门/直接发送/按次审批三条路径都
                # 在 guard）。此前 adapter 对带 draft_id 的结果再开一扇 draft 门
                # → 与 guard 的门双实体双 gate_id：前端两张确认卡、批准后僵尸门
                # 挡死后续工具（实测 2026-09-21）。重启重建门卡走 guard 登记的实体。
                gate_draft_id = str(parsed.get("draft_id") or "")
                self._last_gate_draft_id = gate_draft_id

            # S3：工件类工具结果已内联渲染 → 压制本轮后续文本复述
            if success and name in _SUPPRESS_TEXT_TOOLS:
                self.suppress_text = True
                self._pending_transition = _TEXT_TRANSITIONS.get(name, "")

            # ── Spec 06: plan_summary / plan_progress 事件（前端已有步骤卡 UI）──
            if name == "plan_task" and isinstance(parsed, dict) and parsed.get("steps"):
                # S3：计划卡已内联渲染，压制后续文本复述
                self.suppress_text = True
                self._pending_transition = _TEXT_TRANSITIONS.get("plan_task", "")
                self._plan_steps = [dict(s, status="pending") for s in parsed["steps"]]
                self._plan_active = True
                # ADR-0013：run 实体落库（每会话一个活跃 run，新 run 作废旧 run）
                if self._conversation_id:
                    try:
                        from app.services.plan_run_service import plan_run_service
                        from app.models.database import get_db
                        plan_run_service.start_run(
                            next(get_db()), self._conversation_id,
                            parsed.get("goal", ""), self._plan_steps)
                    except Exception:
                        pass
                events.append(json.dumps({
                    "type": "plan_summary",
                    "goal": parsed.get("goal", ""),
                    "total_steps": parsed.get("total_steps", len(self._plan_steps)),
                    "steps": [
                        {"step": s["step"], "skill": s.get("skill", ""),
                         "description": s.get("description", ""), "status": "pending"}
                        for s in self._plan_steps
                    ],
                }, ensure_ascii=False))
                if self._plan_steps:
                    events.append(json.dumps({
                        "type": "plan_progress",
                        "current_step": self._plan_steps[0]["step"], "status": "running",
                    }, ensure_ascii=False))
            elif self._plan_active and name != "plan_task":
                events.extend(self._advance_plan(name, success, parsed))

            return events

        # ── Text streaming ──
        if event_type == "on_chat_model_stream":
            # If tool already gave a complete answer, skip all LLM text
            # S3：工件类工具已内联渲染 → 文本零复述，发一句标准过渡（防空气泡）
            if self._tool_complete or self.suppress_text:
                if not self._transition_sent and self._pending_transition:
                    self._transition_sent = True
                    results = []
                    if self._phase != "reply":
                        self._phase = "reply"
                        results.append(json.dumps(
                            {"type": "phase", "phase": "reply"}, ensure_ascii=False
                        ))
                    results.append(json.dumps(
                        {"type": "text", "content": self._pending_transition},
                        ensure_ascii=False,
                    ))
                    return results
                return []
            chunk = data.get("chunk", None)
            if chunk is None:
                return []
            content = getattr(chunk, "content", None)
            if not content:
                return []
            results = []
            if self._phase != "reply":
                self._phase = "reply"
                self._did_stream_text = False
                self._reply_prefix = ""
                self._skip_dedup = False
                results.append(json.dumps(
                    {"type": "phase", "phase": "reply"}, ensure_ascii=False
                ))
            # Dedup: check if new reply is just echoing the last tool output
            if not self._skip_dedup and self._last_tool_text:
                self._reply_prefix += content
                if len(self._reply_prefix) >= 50 or (not content.strip()):
                    self._skip_dedup = True  # decide once
                    prefix = self._reply_prefix.strip()
                    tool_prefix = self._last_tool_text.strip()[:len(prefix)]
                    # Heuristic: if first 50 chars overlap >70%, skip entire reply
                    if prefix and tool_prefix and self._text_similarity(prefix, tool_prefix) > 0.7:
                        return []  # skip — LLM echoing tool guidance
            self._did_stream_text = True
            results.append(json.dumps(
                {"type": "text", "content": content}, ensure_ascii=False
            ))
            return results

        return []

    def _apply_transitions(self, transitions: list, gate_draft_id: str = "") -> list[str]:
        """步转移投影（事件 + 落库）。转移规则在 plan_run_service 纯函数，
        投影与持久化收权到 project_transitions 单一入口（2026-09-21 架构审查 B）；
        adapter 只保留内存态收尾（全终态 → 恢复文本流）。"""
        from app.services.plan_run_service import project_transitions
        events = project_transitions(self._conversation_id, transitions, gate_draft_id)
        if transitions and all(
                s.get("status") in ("completed", "failed", "cancelled")
                for s in self._plan_steps):
            # 全部步骤到终态 → 恢复文本流：agent 执行完必须给用户最终回复
            self.suppress_text = False
            self._plan_active = False
        return events

    def _advance_plan(self, tool_name: str, success: bool, parsed=None) -> list[str]:
        """工具结束 → 步转移（规则在 plan_run_service.compute_tool_transition）。
        approval_needed = 被门拦下 → awaiting（阻塞，不推进下一步）。"""
        from app.services.plan_run_service import compute_tool_transition
        if not self._plan_active or tool_name == "plan_task":
            return []
        if isinstance(parsed, dict):
            result = parsed
        else:
            result = {"ok": True} if success else {"error": "failed"}
        transitions = compute_tool_transition(self._plan_steps, tool_name, result)
        gate_draft_id = getattr(self, "_last_gate_draft_id", "") or ""
        return self._apply_transitions(transitions, gate_draft_id)

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Simple character-level similarity (Jaccard-like on char sets)."""
        if not a or not b:
            return 0.0
        set_a, set_b = set(a), set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def finalize(self, route: dict = None, component: dict = None,
                 result_text: str = None) -> list[str]:
        events = []

        # ── Component (inline panel) ──
        if component and component.get("component"):
            events.append(json.dumps({
                "type": "component",
                "component": component["component"],
                "params": component.get("params", {}),
            }, ensure_ascii=False))
        # ── Text result: only emit if NOT already streamed chunk-by-chunk ──
        elif result_text and not self._did_stream_text:
            events.append(json.dumps({
                "type": "text", "content": result_text,
            }, ensure_ascii=False))

        # ── Route ──
        if route and route.get("navigate"):
            events.append(json.dumps({
                "type": "navigate", "page": route.get("page"),
                "params": route.get("params", {}),
            }, ensure_ascii=False))
            pop = route.get("populate")
            if pop:
                events.append(json.dumps({
                    "type": "populate", "target": pop.get("target", ""),
                    "data": pop.get("data", {}),
                }, ensure_ascii=False))
            for act in route.get("actions", []):
                events.append(json.dumps({
                    "type": "action", "action": act.get("action", ""),
                    "payload": act.get("payload", ""),
                }, ensure_ascii=False))
        elif not route:
            # Fallback: check tool results for _route signals
            for tr in self._tool_results:
                r = tr.get("result", {}).get("_route")
                if r and r.get("navigate"):
                    events.append(json.dumps({
                        "type": "navigate", "page": r.get("page"),
                        "params": r.get("params", {}),
                    }, ensure_ascii=False))
                    pop = r.get("populate")
                    if pop:
                        events.append(json.dumps({
                            "type": "populate", "target": pop.get("target", ""),
                            "data": pop.get("data", {}),
                        }, ensure_ascii=False))
                    for act in r.get("actions", []):
                        events.append(json.dumps({
                            "type": "action", "action": act.get("action", ""),
                            "payload": act.get("payload", ""),
                        }, ensure_ascii=False))
                    break

        events.append(json.dumps({"type": "done"}, ensure_ascii=False))
        events.append("[DONE]")
        return events
