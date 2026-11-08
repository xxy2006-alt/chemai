"""确认门 service —— Confirmation Gate 的唯一家园（ADR-0015 阶段 2：门合一）。

draft / boolean 两个 adapter 落在同一 seam 后。interface 即测试面：

    open_gate(db, conversation_id, kind, tool_name, kwargs, ...) → gate_id
    get_open_gate(db, conversation_id) → 门卡载荷 dict | None
    check_binding(db, conversation_id, gate_id) → None | {gate_mismatch, open_gate}
    close_gate(db, gate_id, status) → None
    replay_target(db, conversation_id) → (tool_name, kwargs) | None   重放依据（重启后仍可重建）

gate_id 身份：草稿门 g-draft-{draft_id}（跨版本稳定）；布尔门 g-tool-{tool}-{hash8}。
一决定一动作：决定必带 gate_id（旧客户端空 gate_id + 单门开着时放行），
不一致拒绝执行并让调用方重发当前门状态——批准门 A 永不执行门 B 的动作。
"""
import hashlib
import json
from datetime import datetime
from typing import Dict, Optional


def draft_gate_id(draft_id: str) -> str:
    return f"g-draft-{draft_id}"


def boolean_gate_id(tool_name: str, kwargs: Dict) -> str:
    raw = f"{tool_name}:{json.dumps(kwargs or {}, sort_keys=True, ensure_ascii=False, default=str)}"
    return f"g-tool-{tool_name}-{hashlib.sha1(raw.encode()).hexdigest()[:8]}"


class GateService:
    @staticmethod
    def open_gate(db, conversation_id: str, kind: str, tool_name: str,
                  kwargs: Dict, draft_id: str = "", version: int = 0,
                  action: str = "", message: str = "") -> str:
        """开门（幂等 upsert）：同会话旧开着的门置 superseded（互斥），返回 gate_id。"""
        if not conversation_id:
            return ""
        from app.models.database import AgentGate as _Gate
        gid = draft_gate_id(draft_id) if kind == "draft" and draft_id \
            else boolean_gate_id(tool_name, kwargs or {})
        db.query(_Gate).filter(
            _Gate.conversation_id == conversation_id, _Gate.status == "open",
            _Gate.gate_id != gid,
        ).update({"status": "superseded"}, synchronize_session=False)
        # ⚠ 按列查询而非 db.get（PK 是自增 id，不是 gate_id）——原实现
        # upsert 分支永不命中，重开门 UNIQUE 冲突被吞（code-review 2026-09-20）
        row = db.query(_Gate).filter(_Gate.gate_id == gid).first()
        if row:
            row.status = "open"
            row.kind = kind
            row.tool_name = tool_name
            row.kwargs = kwargs or {}
            row.version = version
            row.action = action
            row.message = message
            row.decided_at = None
        else:
            row = _Gate(
                gate_id=gid, conversation_id=conversation_id, kind=kind,
                tool_name=tool_name, kwargs=kwargs or {},
                draft_id=draft_id or None, version=version or None,
                action=action, message=message, status="open",
            )
            db.add(row)
        db.commit()
        return gid

    @staticmethod
    def get_open_gate(db, conversation_id: str) -> Optional[Dict]:
        if not conversation_id:
            return None
        from app.models.database import AgentGate as _Gate
        row = (db.query(_Gate)
               .filter(_Gate.conversation_id == conversation_id,
                       _Gate.status == "open")
               .order_by(_Gate.id.desc())
               .first())
        if not row:
            return None
        # 读时自愈（2026-09-21 架构审查 A）：同会话多余的开门行一律 superseded——
        # 修复前的双登记（guard 布尔门 + adapter 草稿门）留下的存量，读到即收敛，
        # 僵尸门不再挡死批准后的后续工具
        try:
            dup = (db.query(_Gate)
                   .filter(_Gate.conversation_id == conversation_id,
                           _Gate.status == "open",
                           _Gate.id != row.id)
                   .update({"status": "superseded"}, synchronize_session=False))
            if dup:
                db.commit()
        except Exception:
            db.rollback()
        # 草稿门自愈：草稿已不在待确认态（面板点了发送等）→ 门自动关
        if row.kind == "draft" and row.draft_id:
            from app.services.plan_draft_service import plan_draft_service
            from app.services.parent_report_draft_service import parent_report_draft_service
            d = plan_draft_service.get_draft(db, row.draft_id) \
                or parent_report_draft_service.get_draft(db, row.draft_id)
            if not d or d.get("status") != "awaiting_confirmation":
                row.status = "superseded"
                db.commit()
                return None
        return {
            "gate_id": row.gate_id, "kind": row.kind,
            "tool_name": row.tool_name, "kwargs": row.kwargs or {},
            "draft_id": row.draft_id or "", "version": row.version or 0,
            "action": row.action, "message": row.message,
        }

    @staticmethod
    def check_binding(db, conversation_id: str, gate_id: str) -> Optional[Dict]:
        """决定 ↔ 门的强绑定校验。None=放行；dict=拒绝（含当前门状态供重发）。"""
        open_gate = GateService.get_open_gate(db, conversation_id)
        if open_gate is None:
            return None
        if not gate_id:
            return None  # 旧客户端未带 gate_id + 单门开着 → 放行
        if gate_id == open_gate["gate_id"]:
            return None
        return {"gate_mismatch": True, "open_gate": open_gate}

    @staticmethod
    def close_gate(db, gate_id: str, status: str) -> None:
        from app.models.database import AgentGate as _Gate
        row = db.query(_Gate).filter(_Gate.gate_id == gate_id).first()
        if row:
            row.status = status
            row.decided_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def replay_target(db, conversation_id: str) -> Optional[Dict]:
        """重放依据（gate 实体携带 tool+kwargs，重启后仍可重建）。"""
        open_gate = GateService.get_open_gate(db, conversation_id)
        if not open_gate:
            return None
        return {"tool_name": open_gate["tool_name"],
                "kwargs": open_gate["kwargs"], "gate": open_gate}


    @staticmethod
    def close_conversation(db, conversation_id: str) -> None:
        """会话重置/删除 → 该会话所有门关闭（不留幽灵门，issue #18 阶段 3）。"""
        if not conversation_id:
            return
        from app.models.database import AgentGate as _Gate
        db.query(_Gate).filter(
            _Gate.conversation_id == conversation_id, _Gate.status == "open",
        ).update({"status": "superseded"}, synchronize_session=False)
        db.commit()


gate_service = GateService()
