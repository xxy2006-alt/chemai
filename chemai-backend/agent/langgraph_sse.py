"""LangGraph SSE Adapter — astream_events → ChemAI SSE 事件格式.

Emit route / sub_agent_start / subagent_text / sub_agent_end events
for frontend to render: 路由卡 → 工具卡 → 子Agent面板流式 → 主对话框流式.
"""
import json
import re
import time


def _tool_category(name: str) -> str:
    return name.split("_")[0] if "_" in name else name


def _unwrap_tool_message(result_str: str) -> str:
    """解包 LangGraph ToolMessage repr：content='...JSON...' name=... tool_call_id=...
    （2026-08 修复：repr 带后缀时旧逻辑解包失败 → 前端卡片拿到 raw 乱码/空图表）"""
    m = re.match(r"^content=(['\"])(.*?)\1(?:\s+(?:additional_kwargs|name|tool_call_id|id|type)=.*)?$",
                 result_str, re.S)
    if m:
        inner = m.group(2).replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
        return inner
    return result_str


def _serialize_args(tool_input: dict) -> dict:
    return tool_input


def _json_safe_payload(parsed, cap: int = 8000) -> str:
    """工具结果 → SSE 载荷。大结果优先截断 content/result/text 字段（保持 JSON
    合法），而不是整体切片——否则大文件读取结果被截成非法 JSON，前端会显示成
    「（空文件）」。与 langgraph_sse_v2 同款。"""
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


_SUB_AGENT_DISPLAY = {
    "search_expert": "搜索专家",
    "exam_expert": "出题专家",
    "diagnosis_expert": "诊断专家",
    "tutor_expert": "辅导专家",
    "bank_manager": "题库管理",
    "browser_expert": "浏览器专家",
}

_ROUTE_TOOL_DISPLAY = {
    "route_to_search_expert": "搜索专家",
    "route_to_exam_expert": "出题专家",
    "route_to_diagnosis_expert": "诊断专家",
    "route_to_tutor_expert": "辅导专家",
    "route_to_bank_manager": "题库管理",
    "route_to_browser_expert": "浏览器专家",
}


class LangGraphSSEAdapter:
    _SUB_AGENT_NODES = {
        "search_expert", "exam_expert", "diagnosis_expert",
        "tutor_expert", "bank_manager", "browser_expert",
    }

    def __init__(self):
        self._phase = "thinking"
        self._tool_results = []
        self._sub_agent_depth = 0
        self._sub_agent_start = 0
        self._current_sub_agent = ""

    def feed(self, event: dict) -> list[str]:
        event_type = event.get("event", "")
        name = event.get("name", "")
        data = event.get("data", {})

        # ── Sub-agent chain tracking: sub_agent_start / sub_agent_end ──
        if event_type == "on_chain_start" and name in self._SUB_AGENT_NODES:
            if self._sub_agent_depth == 0:
                self._sub_agent_depth = 1
                self._sub_agent_start = time.time()
                self._current_sub_agent = name
                return [json.dumps({
                    "type": "sub_agent_start",
                    "agent": name,
                    "display": _SUB_AGENT_DISPLAY.get(name, name),
                }, ensure_ascii=False)]
            self._sub_agent_depth += 1

        if event_type == "on_chain_end" and name in self._SUB_AGENT_NODES:
            self._sub_agent_depth = max(0, self._sub_agent_depth - 1)
            if self._sub_agent_depth == 0:
                return [json.dumps({
                    "type": "sub_agent_end",
                    "agent": self._current_sub_agent,
                    "display": _SUB_AGENT_DISPLAY.get(self._current_sub_agent, self._current_sub_agent),
                }, ensure_ascii=False)]

        # ── Inside sub-agent: emit tools + stream subagent_text ──
        if self._sub_agent_depth > 0:
            if event_type == "on_tool_start":
                if name == "request_approval":
                    return [json.dumps({
                        "type": "phase", "phase": "awaiting_approval",
                        "message": data.get("input", {}).get("message", "请确认"),
                    }, ensure_ascii=False)]
                return [json.dumps({
                    "type": "tool_call", "name": name,
                    "tool": _tool_category(name),
                    "args": _serialize_args(data.get("input", {})),
                }, ensure_ascii=False)]

            if event_type == "on_tool_end":
                if name == "request_approval":
                    return []
                output = data.get("output", "")
                result_str = str(output) if not isinstance(output, str) else output
                result_str = _unwrap_tool_message(result_str)
                success = True
                parsed = None
                try:
                    parsed = json.loads(result_str) if isinstance(result_str, str) else result_str
                    if isinstance(parsed, dict) and "error" in parsed:
                        success = False
                    self._tool_results.append({"tool_name": name, "result": parsed})
                except (json.JSONDecodeError, TypeError):
                    self._tool_results.append({"tool_name": name, "result": {"raw": str(result_str)[:500]}})
                # 解析成功时下发干净 JSON（避免 repr 残留/截断）；大结果截字段不截整体
                payload = _json_safe_payload(parsed) if parsed is not None else _json_safe_payload(
                    result_str if isinstance(result_str, str) else str(result_str))
                return [json.dumps({
                    "type": "tool_result", "name": name,
                    "tool": _tool_category(name), "success": success,
                    "result": payload,
                }, ensure_ascii=False)]

            if event_type == "on_chat_model_stream":
                chunk = data.get("chunk", None)
                if chunk and getattr(chunk, "content", None):
                    return [json.dumps({
                        "type": "subagent_text",
                        "content": chunk.content,
                    }, ensure_ascii=False)]
                return []
            return []

        # ── Outside sub-agent: route events + normal event processing ──

        if event_type == "on_tool_start":
            if name.startswith("route_to_"):
                agent_name = name[len("route_to_"):]
                return [json.dumps({
                    "type": "route",
                    "agent": agent_name,
                    "display": _ROUTE_TOOL_DISPLAY.get(name, agent_name),
                }, ensure_ascii=False)]
            if name == "request_approval":
                return [json.dumps({
                    "type": "phase", "phase": "awaiting_approval",
                    "message": data.get("input", {}).get("message", "请确认"),
                }, ensure_ascii=False)]
            return [json.dumps({
                "type": "tool_call", "name": name,
                "tool": _tool_category(name),
                "args": _serialize_args(data.get("input", {})),
            }, ensure_ascii=False)]

        if event_type == "on_tool_end":
            if name.startswith("route_to_"):
                return []  # route completion handled by sub_agent_start
            if name == "request_approval":
                return []
            output = data.get("output", "")
            result_str = str(output) if not isinstance(output, str) else output
            result_str = _unwrap_tool_message(result_str)
            success = True
            parsed = None
            try:
                parsed = json.loads(result_str) if isinstance(result_str, str) else result_str
                if isinstance(parsed, dict) and "error" in parsed:
                    success = False
                self._tool_results.append({"tool_name": name, "result": parsed})
            except (json.JSONDecodeError, TypeError):
                self._tool_results.append({"tool_name": name, "result": {"raw": str(result_str)[:500]}})
            payload = _json_safe_payload(parsed) if parsed is not None else _json_safe_payload(
                result_str if isinstance(result_str, str) else str(result_str))
            return [json.dumps({
                "type": "tool_result", "name": name,
                "tool": _tool_category(name), "success": success,
                "result": payload,
            }, ensure_ascii=False)]

        if event_type == "on_chat_model_stream":
            chunk = data.get("chunk", None)
            if chunk is None:
                return []
            content = getattr(chunk, "content", None)
            if not content:
                return []
            results = []
            if self._phase != "reply":
                self._phase = "reply"
                results.append(json.dumps(
                    {"type": "phase", "phase": "reply"}, ensure_ascii=False
                ))
            results.append(json.dumps(
                {"type": "text", "content": content}, ensure_ascii=False
            ))
            return results

        return []

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
        # ── Text result (when no component, emit sub-agent's answer directly) ──
        elif result_text:
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
