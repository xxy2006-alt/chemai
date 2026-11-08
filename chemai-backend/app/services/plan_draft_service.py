"""计划草稿 service —— 学习计划「生成 → 修订 → 确认 → 发送」生命周期的唯一家园
（ADR-0012 业务逻辑住 service；ADR-0013 确认门实体化）。

interface 即测试面：
    create_draft(...)      regenerate 语义：作废该生旧活跃草稿，另开版本链
    revise_draft(...)      同链追加版本（记录老师反馈），审批归零（修订须再确认）
    record_decision(...)   确认门三值决定：approve / reject(=revise) / abandon(不改状态)
    send_draft(...)        发送由数据状态强制：未 teacher_approved 一律 approval_needed
    get_active_draft / get_draft / list_versions
    teacher_teaches_student  Data Scope 关系检查（老师—班级—学生）

agent 工具与 REST 端点皆是本 service 之上的薄 adapter，不承载业务逻辑。
db 会话可选注入（测试用内存库），缺省走 get_db()。
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

STATUS_AWAITING = "awaiting_confirmation"
STATUS_SENT = "sent"
STATUS_SUPERSEDED = "superseded"

# 学生端计划读缓存（TTL 24h）——GET /learning-plan/{sid} 读-through，
# 归 service 所有（ADR-0012：API 不持有业务状态）
_plan_cache = {}


def _new_db():
    from app.models.database import get_db
    return next(get_db())


def _draft_payload(row) -> Dict:
    return {
        "draft_id": row.draft_id,
        "student_id": row.student_id,
        "version": row.version,
        "status": row.status,
        "content": row.content,
        "feedback": row.feedback,
        "teacher_approved": bool(row.teacher_approved),
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "",
    }


def _notification_id(draft_id: str, version: int, student_id: str) -> str:
    """由幂等键（draft_id+version）派生确定性通知 ID——重复投递得到同一 ID。"""
    digest = hashlib.sha1(f"plan_draft:{draft_id}:v{version}:{student_id}".encode()).hexdigest()[:12]
    return f"plan_{digest}"


class PlanDraftService:
    """学习计划草稿生命周期。所有流转住在这一处；门由草稿状态强制。"""

    # ── Data Scope（老师—班级—学生关系）─────────────────────────

    @staticmethod
    def teacher_teaches_student(db: Session, teacher_id: str, student_id: str) -> bool:
        """fail-closed：任一关系缺失即 False。员工管理角色的范围检查在 REST
        adapter 层由 ScopeGuard 承担（沿用 ADR-0008/0009 分层）。"""
        if not teacher_id or not student_id:
            return False
        row = db.execute(
            text("SELECT class_id FROM students WHERE student_id = :s"),
            {"s": student_id},
        ).fetchone()
        if not row or not row[0]:
            return False
        hit = db.execute(
            text("SELECT 1 FROM teacher_class_subject WHERE teacher_id = :t "
                 "AND class_id = :c LIMIT 1"),
            {"t": teacher_id, "c": row[0]},
        ).fetchone()
        return hit is not None

    # ── 查询 ────────────────────────────────────────────────

    @staticmethod
    def get_draft(db: Session, draft_id: str) -> Optional[Dict]:
        """版本链当前版本（最新一行）。"""
        row = (db.query(_Draft)
               .filter(_Draft.draft_id == draft_id)
               .order_by(_Draft.version.desc())
               .first())
        return _draft_payload(row) if row else None

    @staticmethod
    def get_active_draft(db: Session, student_id: str) -> Optional[Dict]:
        """该生当前待确认草稿（最新活跃链的最新版本）。"""
        row = (db.query(_Draft)
               .filter(_Draft.student_id == student_id,
                       _Draft.status == STATUS_AWAITING)
               .order_by(_Draft.id.desc())
               .first())
        return _draft_payload(row) if row else None

    @staticmethod
    def list_versions(db: Session, draft_id: str) -> List[Dict]:
        rows = (db.query(_Draft)
                .filter(_Draft.draft_id == draft_id)
                .order_by(_Draft.version.asc())
                .all())
        return [_draft_payload(r) for r in rows]

    # ── 生成（regenerate 语义内建）────────────────────────────

    @staticmethod
    def create_draft(db: Session, student_id: str, created_by: str = "",
                     student_name: str = "") -> Dict:
        """生成草稿 v1。已有活跃草稿 → 全部标 superseded（推翻重来）。"""
        student, err = _resolve_student(db, student_id, student_name)
        if err:
            return err
        student_id, student_name = student

        ctx, err = _collect_student_context(db, student_id)
        if err:
            return err

        from app.services.llm_service import llm_service
        result = llm_service.generate_learning_plan(
            student_name=student_name,
            barrier_type=ctx["barrier_type"],
            weak_knowledge_points=ctx["weak_kps"],
            recent_performance=ctx["recent_performance"],
        )
        plan_data, err = _parse_plan(result)
        if err:
            return err

        # regenerate：作废该生全部活跃版本（每生最多一份活跃草稿）
        db.query(_Draft).filter(
            _Draft.student_id == student_id, _Draft.status == STATUS_AWAITING,
        ).update({"status": STATUS_SUPERSEDED}, synchronize_session=False)

        draft_id = uuid.uuid4().hex[:16]
        row = _Draft(
            draft_id=draft_id, student_id=student_id, version=1,
            status=STATUS_AWAITING, content=plan_data,
            created_by=created_by or "",
        )
        db.add(row)
        db.commit()
        return {**_draft_payload(row), "student_name": student_name}

    # ── 修订（revise 同链）───────────────────────────────────

    @staticmethod
    def revise_draft(db: Session, draft_id: str, feedback: str,
                     revised_by: str = "") -> Dict:
        """按老师反馈修订：同链追加版本行，teacher_approved 归零（修订须再确认）。"""
        if not (feedback or "").strip():
            return {"error": "缺少修订意见：请说明要修改的地方"}
        latest_row = _latest_row(db, draft_id)
        if not latest_row:
            return {"error": "该草稿不存在或已被处理，请刷新后重试；若反复出现请重新生成一份"}
        if latest_row.status != STATUS_AWAITING:
            return {"error": f"草稿当前状态为 {latest_row.status}，不能修订"}

        latest = _draft_payload(latest_row)
        student = db.execute(
            text("SELECT name FROM students WHERE student_id = :s"),
            {"s": latest["student_id"]},
        ).fetchone()
        student_name = student[0] if student else latest["student_id"]
        ctx, _ = _collect_student_context(db, latest["student_id"])

        from app.services.llm_service import llm_service
        result = llm_service.revise_learning_plan(
            student_name=student_name,
            previous_plan=latest["content"],
            feedback=feedback.strip(),
            barrier_type=ctx["barrier_type"] if ctx else "concept",
        )
        plan_data, err = _parse_plan(result)
        if err:
            return err

        row = _Draft(
            draft_id=draft_id, student_id=latest["student_id"],
            version=latest["version"] + 1, status=STATUS_AWAITING,
            content=plan_data, feedback=feedback.strip(),
            created_by=revised_by or latest_row.created_by or "",
        )
        db.add(row)
        db.commit()
        return _draft_payload(row)

    # ── 确认门三值决定 ────────────────────────────────────────

    @staticmethod
    def record_decision(db: Session, draft_id: str, action: str,
                        actor_id: str = "", feedback: str = "") -> Dict:
        """把老师的决定写进草稿数据（门由数据强制，不靠进程态）。

        approve → teacher_approved=True（发送放行的唯一钥匙；ADR-0009 fail-closed：
                  缺教师身份一律拒绝——不可逆动作必须有人对身份负责）
        reject  → 必带反馈 → revise_draft（新版本、审批归零）
        abandon → 不改草稿（本步可弃，草稿保留待以后再发）

        Data Scope 由 adapter 层强制（REST=ScopeGuard，agent=channel 的
        teacher_teaches_student 关系检查）；本方法管身份与状态。
        """
        latest_row = _latest_row(db, draft_id)
        if not latest_row:
            return {"error": "该草稿不存在或已被处理，请刷新后重试；若反复出现请重新生成一份"}
        if latest_row.status != STATUS_AWAITING:
            return {"error": ("该学习计划已确认发送给学生，无需重复处理" if latest_row.status == "sent" else f"该草稿当前状态（{latest_row.status}）不支持此操作，请刷新后查看最新状态")}

        action = (action or "").strip().lower()
        if action == "approve" and not (actor_id or "").strip():
            return {"error": "缺少教师身份，无法记录批准（fail-closed）"}
        if action == "approve":
            latest_row.teacher_approved = True
            latest_row.approved_by = actor_id or ""
            db.commit()
            return _draft_payload(latest_row)
        if action == "reject":
            return PlanDraftService.revise_draft(db, draft_id, feedback, actor_id)
        if action == "abandon":
            return _draft_payload(latest_row)
        return {"error": f"未知的确认门决定: {action}"}

    # ── 发送（确认门在这里强制）───────────────────────────────

    @staticmethod
    def send_draft(db: Session, student_id: str, draft_id: str = "",
                   sender_id: str = "") -> Dict:
        """发送草稿给学生。门由数据状态强制：

        - 未确认（teacher_approved=False）→ approval_needed 载荷（含 draft_id），
          门卡由前端/channel 呈现；这是唯一的门，不再有进程级提权布尔。
        - 已确认 → 执行发送效果并置 sent。
        """
        # 有身份即早查 Data Scope（不给学生外的人看门卡）；缺身份的强制检查
        # 放在批准之后（那时才真正不可逆）
        if (sender_id or "").strip() and not PlanDraftService.teacher_teaches_student(
                db, sender_id, student_id):
            return {"error": f"你没有向学生 {student_id} 发送学习计划的权限（Data Scope 不含该生）"}

        payload = (PlanDraftService.get_draft(db, draft_id) if draft_id
                   else PlanDraftService.get_active_draft(db, student_id))
        if not payload:
            latest_any = (db.query(_Draft)
                          .filter(_Draft.student_id == student_id)
                          .order_by(_Draft.id.desc()).first())
            hint = f"（该生最近一份草稿状态为 {latest_any.status}）" if latest_any else "（该生从未生成过草稿）"
            return {
                "approval_needed": True,
                "message": f"即将把学习计划发送给学生 {student_id}，但没有可发送的待确认草稿{hint}",
                "target": student_id,
                "action": "send_student",
                "student_id": student_id,
            }
        if payload["status"] != STATUS_AWAITING or not payload["teacher_approved"]:
            return {
                "approval_needed": True,
                "message": f"学习计划（第 {payload['version']} 版）尚未经老师确认，请先确认再发送",
                "target": student_id,
                "action": "send_student",
                "draft_id": payload["draft_id"],
                "version": payload["version"],
                "student_id": student_id,
            }
        # 即将不可逆发送（ADR-0009 fail-closed）：缺身份 = 无人可对发送负责 = 拒绝
        if not (sender_id or "").strip():
            return {"error": "缺少教师身份，无法发送（fail-closed）"}
        if not PlanDraftService.teacher_teaches_student(db, sender_id, student_id):
            return {"error": f"你没有向学生 {student_id} 发送学习计划的权限（Data Scope 不含该生）"}

        student = db.query(_Student).filter(
            _Student.student_id == student_id).first()
        if not student:
            return {"error": f"学生 {student_id} 不存在"}

        content = payload["content"]
        student.current_plan = content
        db.add(_History(
            student_id=student_id,
            plan_title=content.get("plan_title", "学习计划"),
            plan_data=content,
        ))
        # 学生收件箱投递（幂等键 draft_id+version，重复投递不重复插入）
        nid = _notification_id(payload["draft_id"], payload["version"], student_id)
        exists = db.query(_StudentNotification).filter(
            _StudentNotification.notification_id == nid).first()
        if not exists:
            db.add(_StudentNotification(
                notification_id=nid,
                student_id=student_id,
                type="learning_plan",
                title="📋 你有一份新的学习计划",
                content=content.get("plan_title", "学习计划"),
            ))
        row = db.query(_Draft).filter(
            _Draft.draft_id == payload["draft_id"],
            _Draft.version == payload["version"],
        ).first()
        row.status = STATUS_SENT
        db.commit()

        # 内存缓存同步（学生端即刻可见；缓存归 service 所有，API 读-through）
        _plan_cache[student_id] = {"plan": content, "expires_at": datetime.utcnow().timestamp() + 86400}

        return {
            "result": f"学习计划已确认发送，{student.name} 可在学生端查看",
            "student_id": student_id,
            "student_name": student.name,
            "draft_id": payload["draft_id"],
            "version": payload["version"],
        }


# ── 内部：模型别名与帮助函数（implementation, not interface）────

from app.models.database import (  # noqa: E402
    LearningPlanDraft as _Draft,
    LearningPlanHistory as _History,
    Student as _Student,
    StudentNotification as _StudentNotification,
)


def _latest_row(db: Session, draft_id: str):
    return (db.query(_Draft)
            .filter(_Draft.draft_id == draft_id)
            .order_by(_Draft.version.desc())
            .first())


def _resolve_student(db: Session, student_id: str, student_name: str):
    """名字/学号二选一解析出唯一学生。返回 ((student_id, name), None) 或 (None, err)。"""
    if student_name and not student_id:
        rows = db.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        if not rows:
            return None, {"error": f"未找到名为 '{student_name}' 的学生"}
        if len(rows) > 1:
            return None, {
                "multiple_matches": [{"student_id": r[0], "name": r[1]} for r in rows],
                "hint": "找到多个匹配学生，请指定学号",
            }
        return (rows[0][0], rows[0][1]), None
    if not student_id:
        return None, {"error": "请提供 student_id 或 student_name"}
    row = db.execute(
        text("SELECT student_id, name FROM students WHERE student_id = :s"),
        {"s": student_id},
    ).fetchone()
    if not row:
        return None, {"error": f"学生 {student_id} 不存在"}
    return (row[0], row[1]), None


def _collect_student_context(db: Session, student_id: str) -> tuple:
    """障碍类型（主导）+ 薄弱知识点 + 近期正确率 —— LLM 生成/修订共用上下文。"""
    try:
        student = db.query(_Student).filter(_Student.student_id == student_id).first()
        barrier_raw = student.barrier_type if student else {}
        if isinstance(barrier_raw, str):
            try:
                barrier_raw = json.loads(barrier_raw)
            except (json.JSONDecodeError, TypeError):
                barrier_raw = {}
        dominant = "concept"
        if isinstance(barrier_raw, dict) and barrier_raw:
            dominant = max(barrier_raw, key=barrier_raw.get)
    except Exception:
        dominant = "concept"

    weak_kps: List[str] = []
    try:
        wk_rows = db.execute(text(
            "SELECT q.knowledge_points FROM student_answers sa "
            "JOIN questions q ON sa.question_id = q.question_id "
            "WHERE sa.student_id = :s AND sa.is_correct = 0 "
            "ORDER BY sa.answered_at DESC LIMIT 20"
        ), {"s": student_id}).fetchall()
        kp_count: Dict[str, int] = {}
        for r in wk_rows:
            kps = r[0] or []
            if isinstance(kps, str):
                try:
                    kps = json.loads(kps)
                except (json.JSONDecodeError, TypeError):
                    kps = [kps]
            for kp in kps:
                kp_count[kp] = kp_count.get(kp, 0) + 1
        weak_kps = [kp for kp, _ in sorted(kp_count.items(), key=lambda x: -x[1])[:5]]
    except Exception:
        weak_kps = []

    recent_performance = None
    try:
        agg = db.execute(text(
            "SELECT COUNT(*) total, SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) "
            "FROM student_answers WHERE student_id = :s"
        ), {"s": student_id}).fetchone()
        if agg and agg[0]:
            total, correct = agg[0], agg[1] or 0
            recent_performance = {"total_answers": total, "correct_answers": correct,
                                  "accuracy": round(correct / total, 3)}
    except Exception:
        recent_performance = None

    return {"barrier_type": dominant, "weak_kps": weak_kps,
            "recent_performance": recent_performance}, None


def _parse_plan(result: Dict) -> tuple:
    if not result.get("success") or not result.get("content", "").strip():
        return None, {"error": "学习计划生成失败，请重试"}
    try:
        plan_data = json.loads(result["content"])
    except (json.JSONDecodeError, TypeError):
        return None, {"error": "学习计划解析失败，请重试"}
    if not isinstance(plan_data, dict) or not plan_data.get("plan_title"):
        return None, {"error": "LLM 返回的计划内容不完整，请重试"}
    return plan_data, None


plan_draft_service = PlanDraftService()
