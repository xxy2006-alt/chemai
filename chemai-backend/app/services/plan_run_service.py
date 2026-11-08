"""计划运行 service —— todolist（Plan Run）状态流转的唯一家园（ADR-0013）。

interface 即测试面：
    start_run(conversation_id, goal, steps)   新 run 作废该会话旧活跃 run
    mark_step(conversation_id, step, status)  步状态推进（无活跃 run 时静默 no-op）
    get_active_run(conversation_id)           刷新页面/重启后的重同步查询

channel / SSE 适配器按 conversation_id 调用，无需携带 run_id。
步状态机：pending / running / awaiting_confirmation / revising /
completed / failed / cancelled。全部步骤到终态 → run 置 completed。
"""
import uuid
from typing import Dict, List, Optional

_STEP_TERMINAL = {"completed", "failed", "cancelled"}

# ── 步进转移规则（issue #18 阶段 1：状态机的唯一家园，ADR-0015 §4）────
# 门工具 → 门应挂住的步骤 skill。生成即门（generate_*）的门挂在对应的
# 「发送」步骤上；其余门（含布尔门）挂工具自身。
_GATE_STEP_SKILL = {
    "send_learning_plan": "send_learning_plan",
    "send_report_to_parent": "send_report_to_parent",
    "generate_learning_plan": "send_learning_plan",
    "generate_parent_report": "send_report_to_parent",
    "assign_adaptive_practice": "assign_adaptive_practice",
    "delete_bank": "delete_bank",
}

# 生成即门的生成工具（ADR-0013）：成功即自带门卡——生成步打勾、门挂发送步
_GATE_GENERATORS = {"generate_learning_plan", "generate_parent_report"}


def _find_step(steps: List[Dict], tool_name: str):
    """按 skill 找可转移的步骤；找不到时认当前 running/failed 步
    （2026-09-14 语义保留：门不只挂在同名步骤上）。"""
    matched = next((s for s in steps
                    if s.get("skill") == tool_name
                    and s.get("status") in ("pending", "running", "failed",
                                            "awaiting_confirmation")), None)
    if matched is None:
        matched = next((s for s in steps
                        if s.get("status") in ("running", "failed")), None)
    return matched


def compute_tool_transition(steps: List[Dict], tool_name: str,
                            result) -> List[tuple]:
    """工具结果 → 步转移列表 [(step_no, status)]（纯函数，原地更新 steps）。

    approval_needed = 被门拦下 → awaiting_confirmation，**阻塞**：不标完成、
    不启动下一步（曾被 adapter 当 success 标成 completed——「没确认就往下推」
    的根因）。error → failed（不自动推进）。成功 → completed 并启动下一步。
    """
    if tool_name == "plan_task" or not steps:
        return []
    transitions: List[tuple] = []
    if isinstance(result, dict) and result.get("approval_needed") \
            and tool_name in _GATE_STEP_SKILL:
        gate_skill = _GATE_STEP_SKILL[tool_name]
        # 生成即门：生成步确实成功了（草稿已落库）→ 打勾；门挂在对应发送步
        if tool_name in _GATE_GENERATORS:
            gen_step = next((s for s in steps
                             if s.get("skill") == tool_name
                             and s.get("status") in ("pending", "running", "failed")), None)
            if gen_step is not None:
                gen_step["status"] = "completed"
                transitions.append((gen_step["step"], "completed"))
        target = _find_step(steps, gate_skill)
        if target is not None and target.get("status") != "awaiting_confirmation":
            target["status"] = "awaiting_confirmation"
            transitions.append((target["step"], "awaiting_confirmation"))
        return transitions
    if isinstance(result, dict) and result.get("approval_needed"):
        return []  # 工作区外访问等按次审批：不属计划门，不动 todolist
    step = _find_step(steps, tool_name)
    if step is None:
        return []
    # gate_open_blocked = 该工具被**已打开的确认门**拦下（2026-09-20 实测：
    # 门等待期间 LLM 多调的发送类工具返回此错误）——语义是「暂停等待确认」
    # 而非失败，此前被标成 failed，计划卡给老师看红色失败态（误导）。
    if isinstance(result, dict) and result.get("gate_open_blocked"):
        if step.get("status") in ("pending", "running", "failed"):
            step["status"] = "awaiting_confirmation"
            transitions.append((step["step"], "awaiting_confirmation"))
        return transitions
    failed = isinstance(result, dict) and "error" in result
    if failed:
        if step.get("status") in ("pending", "running", "failed"):
            step["status"] = "failed"
            transitions.append((step["step"], "failed"))
        return transitions
    if step.get("status") in ("pending", "running", "failed",
                              "awaiting_confirmation"):
        step["status"] = "completed"
        transitions.append((step["step"], "completed"))
        nxt = next((x for x in steps if x.get("status") == "pending"), None)
        if nxt is not None:
            nxt["status"] = "running"
            transitions.append((nxt["step"], "running"))
    return transitions


def compute_decision_transition(steps: List[Dict], action: str) -> List[tuple]:
    """三值决定 → 步转移（纯函数）。approve 解锁门步骤进入重放中；
    重放结果由 compute_replay_transition 落终态——「未批准」与「重放完成」
    从此是两个状态。"""
    target = next((s for s in steps
                   if s.get("status") == "awaiting_confirmation"), None)
    if target is None:
        return []
    new_status = {"approve": "running", "reject": "revising",
                  "abandon": "cancelled"}.get(action)
    if not new_status:
        return []
    target["status"] = new_status
    return [(target["step"], new_status)]


def compute_replay_transition(steps: List[Dict], tool_name: str,
                              success: bool) -> List[tuple]:
    """批准后重放结果 → 步转移（纯函数）。成功 → completed 并启动下一步；
    失败 → failed（不自动推进，由 agent 向老师说明）。"""
    target = next((s for s in steps
                   if s.get("skill") == tool_name
                   and s.get("status") in ("running", "awaiting_confirmation")),
                  None)
    if target is None:
        return []
    if success:
        target["status"] = "completed"
        transitions = [(target["step"], "completed")]
        nxt = next((x for x in steps if x.get("status") == "pending"), None)
        if nxt is not None:
            nxt["status"] = "running"
            transitions.append((nxt["step"], "running"))
        return transitions
    target["status"] = "failed"
    return [(target["step"], "failed")]


class PlanRunService:
    @staticmethod
    def start_run(db, conversation_id: str, goal: str, steps: List[Dict]) -> Dict:
        if not conversation_id:
            return {}
        from app.models.database import PlanRun as _Run
        db.query(_Run).filter(
            _Run.conversation_id == conversation_id, _Run.status != "completed",
        ).update({"status": "superseded"}, synchronize_session=False)
        run = _Run(
            run_id=uuid.uuid4().hex[:16],
            conversation_id=conversation_id,
            goal=goal or "",
            steps=[dict(s, status=s.get("status", "pending")) for s in steps],
        )
        db.add(run)
        db.commit()
        return {"run_id": run.run_id, "goal": run.goal, "steps": run.steps}

    @staticmethod
    def get_active_run(db, conversation_id: str) -> Optional[Dict]:
        if not conversation_id:
            return None
        from app.models.database import PlanRun as _Run
        run = (db.query(_Run)
               .filter(_Run.conversation_id == conversation_id,
                       _Run.status.in_(("running", "paused")))
               .order_by(_Run.id.desc())
               .first())
        if not run:
            return None
        return {"run_id": run.run_id, "goal": run.goal,
                "steps": run.steps, "status": run.status}

    # ── Paused Run（ADR-0016）：断线/超时/孤儿中断 → paused；显式决定/消息 → running ──

    @staticmethod
    def mark_run_paused(db, conversation_id: str) -> None:
        if not conversation_id:
            return
        from app.models.database import PlanRun as _Run
        db.query(_Run).filter(
            _Run.conversation_id == conversation_id, _Run.status == "running",
        ).update({"status": "paused"}, synchronize_session=False)
        db.commit()

    @staticmethod
    def mark_run_resumed(db, conversation_id: str) -> None:
        if not conversation_id:
            return
        from app.models.database import PlanRun as _Run
        db.query(_Run).filter(
            _Run.conversation_id == conversation_id, _Run.status == "paused",
        ).update({"status": "running"}, synchronize_session=False)
        db.commit()

    @staticmethod
    def mark_step(db, conversation_id: str, step: int, status: str,
                  gate_draft_id: Optional[str] = None) -> Optional[Dict]:
        """推进一步的状态并返回最新 run（无活跃 run 静默 no-op）。
        gate_draft_id：该步挂起的确认门草稿（ADR-0013 重同步依据——
        写进 run 步骤 JSON，服务重启后门卡可从 DB 重建）。
        全部步骤到终态时 run 置 completed。"""
        if not conversation_id:
            return None
        from app.models.database import PlanRun as _Run
        run = (db.query(_Run)
               .filter(_Run.conversation_id == conversation_id,
                       _Run.status.in_(("running", "paused")))
               .order_by(_Run.id.desc())
               .first())
        if not run:
            return None
        # JSON 列必须整体重新赋值——原地 mutate 不会被 SQLAlchemy 检测，
        # 且 commit 后过期重载会直接丢弃变更
        new_steps = []
        for s in (run.steps or []):
            if s.get("step") == step:
                s = dict(s, status=status)
                if gate_draft_id:
                    s["gate_draft_id"] = gate_draft_id
            new_steps.append(dict(s))
        run.steps = new_steps
        if all(s.get("status") in _STEP_TERMINAL for s in new_steps):
            run.status = "completed"
        elif run.status == "paused":
            # 决定/工具驱动的转移 = 老师的显式动作（ADR-0016 §2）→ 运行回到 running
            run.status = "running"
        db.commit()
        return {"run_id": run.run_id, "goal": run.goal,
                "steps": new_steps, "status": run.status}




    # ── 会话门映射（#13 冒烟补丁 2：裸生成门的 DB 重同步）─────────

    @staticmethod
    def record_gate(db, conversation_id: str, draft_id: str, artifact: str) -> None:
        """门开启时记录 会话→草稿 映射（幂等 upsert）。"""
        if not conversation_id or not draft_id:
            return
        from app.models.database import ConversationGate as _Gate
        row = db.get(_Gate, conversation_id)
        if row:
            row.draft_id = draft_id
            row.artifact = artifact
        else:
            db.add(_Gate(conversation_id=conversation_id,
                         draft_id=draft_id, artifact=artifact))
        db.commit()

    @staticmethod
    def get_gate(db, conversation_id: str) -> Optional[Dict]:
        """读取会话待确认门；草稿已不在待确认态则视为陈旧，惰性清除并返回 None。"""
        if not conversation_id:
            return None
        from app.models.database import ConversationGate as _Gate
        row = db.get(_Gate, conversation_id)
        if not row:
            return None
        from app.services.plan_draft_service import plan_draft_service
        from app.services.parent_report_draft_service import parent_report_draft_service
        svc = (parent_report_draft_service if row.artifact == "parent_report"
               else plan_draft_service)
        d = svc.get_draft(db, row.draft_id)
        if not d or d.get("status") != "awaiting_confirmation":
            db.delete(row)
            db.commit()
            return None
        if row.artifact == "parent_report":
            action, label = "send_parent", "学习报告"
        else:
            action, label = "send_student", "学习计划"
        return {"draft_id": d["draft_id"], "student_id": d["student_id"],
                "version": d["version"], "action": action,
                "message": f"{label}（第 {d['version']} 版）等待确认"}


plan_run_service = PlanRunService()


# ── 转移投影引擎（2026-09-21 架构审查 B）───────────────────────────────
# 「转移 → SSE 事件 + DB 落库」此前在四个调用面各自手搓循环（adapter /
# _decision_unlock_events / _gate_step_events / _persist_send_completion），
# 每加一种路径就要记得再抄一遍——打回无后续、不收尾类 bug 的固定来源。
# 收权：所有调用面只算转移（纯函数），投影与持久化走这一个入口。

def project_transitions(cid: str, transitions: List[tuple],
                        gate_draft_id: str = "") -> List[str]:
    """把 [(step_no, status)] 投影为 plan_progress SSE 事件串并落库。

    - 事件格式与历史完全一致（前端契约不变）
    - gate_draft_id 仅随 awaiting_confirmation 状态写入（ADR-0013 重同步）
    - 无 cid（单测/内存态）时只产事件不落库
    - 返回值兼容各调用面原有的 list[str] 形状
    """
    import json as _json
    events = []
    for step_no, status in transitions:
        events.append(_json.dumps({
            "type": "plan_progress", "current_step": step_no, "status": status,
        }, ensure_ascii=False))
    if not cid:
        return events
    try:
        from app.models.database import get_db as _get_db
        db = next(_get_db())
        try:
            for step_no, status in transitions:
                plan_run_service.mark_step(
                    db, cid, step_no, status,
                    gate_draft_id=gate_draft_id if status == "awaiting_confirmation" else "")
        finally:
            db.close()
    except Exception:
        pass  # 落库失败不阻断 SSE 投影（与各调用面原行为一致）
    return events
