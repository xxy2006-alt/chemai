"""通知分发（notification-dispatch）测试。

服务层：dispatch 幂等 / 网关开关 / 未读读写（测试面 = service interface）。
端点层：学生本人可见 / 越权 403 / 已读标记（TestClient 最小 app）。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.database as db_mod
from app.models.database import (
    Base, Student, StudentParentBinding, StudentNotification,
)
from app.middleware.auth import create_access_token
from app.api import notification as notif_mod
from app.services import notification_service as nsvc
from app.services import grading_center


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def patched_db(db_session, monkeypatch):
    """service 自开会话的路径指向测试库（对齐 test_notification_service 的 ns_mod 约定）。"""
    monkeypatch.setattr(nsvc, "get_db", lambda: iter([db_session]))
    return db_session


@pytest.fixture
def seeded(db_session):
    from app.models.database import School, Grade, Class
    db_session.add(School(school_id="school1", name="测试中学"))
    db_session.add(Grade(grade_id="g1", school_id="school1", name="高一", year=2026))
    db_session.add(Class(class_id="class_2025_1", name="一班", grade="高一",
                         grade_id="g1", subject="化学"))
    db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
    db_session.add(Student(student_id="202610102", name="张浩宇", class_id="class_2025_1"))
    db_session.commit()
    return db_session


def _student_hdr():
    """学生 token：user_id 即 student_id（对齐既有鉴权测试）。"""
    return {"Authorization": f"Bearer {create_access_token('202610101', 'student')}"}


def _admin_hdr():
    """发送类路由是教师/管理员动作（notification:create 不授予学生）。"""
    return {"Authorization": f"Bearer {create_access_token('admin1', 'admin', school_id='school1')}"}


@pytest.fixture
def client(seeded, patched_db):
    app = FastAPI()
    app.include_router(notif_mod.router, prefix="/api/notification")

    def override_get_db():
        yield seeded

    app.dependency_overrides[db_mod.get_db] = override_get_db
    with TestClient(app) as c:
        yield c


# ═══════════ 服务层 ═══════════

class TestDispatch:
    def test_dispatch_student_writes_inbox(self, patched_db):
        out = nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610101"},
            event={"type": "assignment", "title": "新练习已送达",
                   "content": "自适应练习-李雨萱", "payload": {"record_id": "asg_1"}},
            idempotency_key="asg_asg_1",
        )
        assert out["channel"] == "in_app"
        rows = patched_db.query(StudentNotification).all()
        assert len(rows) == 1
        assert rows[0].type == "assignment" and rows[0].is_read is False

    def test_dispatch_idempotent_on_replay(self, patched_db):
        for _ in range(2):
            nsvc.notification_service.dispatch(
                recipient={"role": "student", "id": "202610101"},
                event={"type": "assignment", "title": "新练习已送达", "content": ""},
                idempotency_key="asg_same",
            )
        assert patched_db.query(StudentNotification).count() == 1

    def test_dispatch_no_key_allows_repeat(self, patched_db):
        """无幂等键的显式发送（教师手动）允许重复。"""
        for _ in range(2):
            nsvc.notification_service.dispatch(
                recipient={"role": "student", "id": "202610101"},
                event={"type": "warning", "title": "提醒", "content": ""},
            )
        assert patched_db.query(StudentNotification).count() == 2

    def test_gateway_off_by_default(self, patched_db, monkeypatch):
        """开关默认关：只落站内，不触网关（seam 被触碰即失败）。"""
        def _bomb(ev, recipient=None):
            raise AssertionError("gateway seam should not be called when off")
        monkeypatch.setattr(nsvc, "_gateway_send", _bomb)
        nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610101"},
            event={"type": "assignment", "title": "t", "content": ""},
        )
        assert patched_db.query(StudentNotification).count() == 1

    def test_gateway_on_sends_and_still_writes_inbox(self, patched_db, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "NOTIFY_EXTERNAL_GATEWAYS", True)
        called = []
        monkeypatch.setattr(nsvc, "_gateway_send",
                            lambda ev, recipient=None: called.append(ev["type"]) or True)
        out = nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610101"},
            event={"type": "assignment", "title": "t", "content": ""},
        )
        assert out["external"] is True
        assert called == ["assignment"]
        assert patched_db.query(StudentNotification).count() == 1

    def test_gateway_never_broadcasts_without_recipient_route(self, patched_db, monkeypatch):
        """规范：网关开启但无 per-收件人投递配置时仅站内，绝不把学生数据发进共享频道。"""
        from app.core.config import settings
        import chem_skills.chemistry_notification.handler as gw

        monkeypatch.setattr(settings, "NOTIFY_EXTERNAL_GATEWAYS", True)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "bot-token")
        monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "shared-channel")

        sent = []

        class _FakeGateway:
            def __init__(self, bot_token=""):
                self.bot_token = bot_token

            def send(self, chat_id, text):
                sent.append((chat_id, text))
                return type("R", (), {"success": True})()

        monkeypatch.setattr(gw, "TelegramGateway", _FakeGateway)

        out = nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610101"},
            event={"type": "grading", "title": "判卷完成", "content": "正确率 80%"},
        )
        assert out["external"] is False and sent == []      # 没有收件人路由 → 不外发
        assert patched_db.query(StudentNotification).count() == 1

        # 收件人自带投递配置时才外发，且只发到那个会话
        routed = nsvc.notification_service.dispatch(
            recipient={"role": "parent", "id": "P1", "chat_id": "parent-chat"},
            event={"type": "grading", "title": "判卷完成", "content": "正确率 80%"},
        )
        assert routed["external"] is True
        assert [c for c, _ in sent] == ["parent-chat"]

    def test_dispatch_parent_role(self, patched_db):
        patched_db.add(StudentParentBinding(
            binding_id="b1", parent_id="P1", student_id="202610101",
            status="active", bind_code="BC1"))
        patched_db.commit()
        out = nsvc.notification_service.dispatch(
            recipient={"role": "parent", "id": "P1", "student_id": "202610101"},
            event={"type": "weekly", "title": "周报已生成", "content": ""},
            idempotency_key="week_1",
        )
        assert out["channel"] == "in_app"
        from app.models.database import ParentNotification
        assert patched_db.query(ParentNotification).count() == 1

        # 重放：家长事件同样幂等（dedup 走 ParentNotification，不重复插入）
        out2 = nsvc.notification_service.dispatch(
            recipient={"role": "parent", "id": "P1", "student_id": "202610101"},
            event={"type": "weekly", "title": "周报已生成", "content": ""},
            idempotency_key="week_1",
        )
        assert out2["duplicate"] is True
        assert patched_db.query(ParentNotification).count() == 1


class TestUnread:
    def test_unread_count_and_mark_read(self, patched_db):
        svc = nsvc.notification_service
        for i in range(3):
            svc.dispatch(recipient={"role": "student", "id": "202610101"},
                         event={"type": "assignment", "title": f"n{i}", "content": ""},
                         idempotency_key=f"k{i}")
        assert svc.unread_count("202610101") == 3

        rows = svc.student_notifications("202610101")
        first_id = rows[0]["notification_id"]
        assert svc.mark_read("202610101", [first_id]) == 1
        assert svc.unread_count("202610101") == 2

        assert svc.mark_read("202610101") == 2      # 全部已读
        assert svc.unread_count("202610101") == 0

    def test_mark_read_other_student_noop(self, patched_db):
        svc = nsvc.notification_service
        svc.dispatch(recipient={"role": "student", "id": "202610101"},
                     event={"type": "assignment", "title": "n", "content": ""})
        assert svc.mark_read("202610102") == 0      # 他人的通知不可动


# ═══════════ 端点层 ═══════════

class TestStudentEndpoints:
    def test_list_own_notifications_with_unread(self, client, patched_db):
        nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610101"},
            event={"type": "assignment", "title": "新练习", "content": "x"},
            idempotency_key="k1")
        r = client.get("/api/notification/student/202610101/notifications",
                       headers=_student_hdr())
        body = r.json()
        assert r.status_code == 200
        assert body["unread_count"] == 1
        assert body["notifications"][0]["title"] == "新练习"

    def test_read_endpoint_marks(self, client, patched_db):
        nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610101"},
            event={"type": "assignment", "title": "新练习", "content": ""},
            idempotency_key="k1")
        nid = patched_db.query(StudentNotification).first().notification_id
        r = client.put(f"/api/notification/{nid}/read?user_id=202610101&user_type=student",
                       headers=_student_hdr())
        assert r.status_code == 200
        assert patched_db.query(StudentNotification).first().is_read is True

    def test_read_endpoint_rejects_other_owner(self, client, patched_db):
        nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610102"},
            event={"type": "assignment", "title": "别人的", "content": ""})
        nid = patched_db.query(StudentNotification).first().notification_id
        r = client.put(f"/api/notification/{nid}/read?user_id=202610101&user_type=student",
                       headers=_student_hdr())
        # 404 而非 403：不向调用者泄漏「该通知存在但属于别人」
        assert r.status_code == 404

    def test_send_to_student_route_dispatches(self, client, patched_db):
        r = client.post(
            "/api/notification/send-to-student/202610101"
            "?notification_type=assignment&title=老师提醒&content=完成练习",
            headers=_admin_hdr(),
        )
        assert r.status_code == 200
        rows = patched_db.query(StudentNotification).all()
        assert len(rows) == 1 and rows[0].title == "老师提醒"

    def test_send_to_class_route_dispatches(self, client, patched_db):
        r = client.post(
            "/api/notification/send-to-class/class_2025_1"
            "?notification_type=assignment&title=班级通知&content=今晚交",
            headers=_admin_hdr(),
        )
        assert r.status_code == 200
        assert patched_db.query(StudentNotification).count() == 2   # 班里两个学生

    def test_send_route_honours_idempotency_key(self, client, patched_db):
        """显式发送可带幂等键：同键重放不重复落库。"""
        body = {"type": "reminder", "title": "交作业", "content": "今晚交",
                "target_type": "student", "target_ids": ["202610101"],
                "idempotency_key": "evt_send_1"}
        first = client.post("/api/notification/send", json=body, headers=_admin_hdr())
        assert first.status_code == 200 and first.json()["sent_count"] == 1

        replay = client.post("/api/notification/send", json=body, headers=_admin_hdr())
        assert replay.status_code == 200 and replay.json()["sent_count"] == 0
        assert patched_db.query(StudentNotification).count() == 1

    def test_send_route_rejects_empty_targets(self, client):
        """没有收件人 → 400（原先是 200 + sent_count:0 的静默空操作）。"""
        r = client.post("/api/notification/send", headers=_admin_hdr(),
                        json={"type": "reminder", "title": "交作业", "content": "今晚交",
                              "target_type": "student"})
        assert r.status_code == 400

    def test_student_read_route_marks_selected_ids(self, client, patched_db):
        """notification_ids 从 JSON body 读（原先被当成 multipart File，永远收不到）。"""
        ids = []
        for i in (1, 2):
            out = nsvc.notification_service.dispatch(
                recipient={"role": "student", "id": "202610101"},
                event={"type": "assignment", "title": f"通知{i}", "content": ""})
            ids.append(out["notification_id"])
        r = client.post("/api/notification/student/202610101/read",
                        json={"notification_ids": [ids[0]]},
                        headers=_student_hdr())
        assert r.status_code == 200 and r.json()["marked"] == 1
        # mark_read 走批量 UPDATE（synchronize_session=False），重查前先丢弃身份图缓存
        patched_db.expire_all()
        state = {n.notification_id: n.is_read for n in
                 patched_db.query(StudentNotification).all()}
        assert state[ids[0]] is True
        assert state[ids[1]] is False   # 未选中的不动

    def test_student_read_route_empty_body_marks_all(self, client, patched_db):
        """缺省 body（{}）= 全部已读，移动端既有调用形态。"""
        for i in (1, 2):
            nsvc.notification_service.dispatch(
                recipient={"role": "student", "id": "202610101"},
                event={"type": "assignment", "title": f"通知{i}", "content": ""})
        r = client.post("/api/notification/student/202610101/read",
                        json={}, headers=_student_hdr())
        assert r.status_code == 200 and r.json()["marked"] == 2


# ═══════════ 触发点端到端 ═══════════

@pytest.fixture
def exam_record(db_session):
    """最小 PRACTICE 记录 + 1 题（对齐 test_grading_center 的形态）。"""
    from app.models.database import ExamRecord, Question, RecordType, Difficulty, QuestionSource, AuditStatus
    from datetime import datetime as _dt
    rec = ExamRecord(record_id="gc_exam_001", class_id="class_2025_1",
                     name="触发测试卷", type=RecordType.PRACTICE,
                     total_students=1, present_students=1, exam_date=_dt.utcnow())
    db_session.add(rec)
    db_session.add(Question(
        question_id="gc_q_1", record_id="gc_exam_001", content="题1",
        options=["A", "B", "C", "D"], answer="B", analysis="",
        knowledge_points=["kp"], difficulty=Difficulty.MEDIUM,
        source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED))
    db_session.commit()
    return rec

class TestTriggers:
    def test_assignment_notifies_student(self, db_session, monkeypatch):
        """布置完成 → 学生收件箱出现「新练习已送达」。"""
        from app.models.database import Student
        for i in (1, 2):
            db_session.add(Student(student_id=f"20261010{i}", name=f"学生{i}",
                                   class_id="class_2025_1"))
        db_session.commit()
        monkeypatch.setattr(db_mod, "get_db", lambda: iter([db_session]))
        monkeypatch.setattr(nsvc, "get_db", lambda: iter([db_session]))
        monkeypatch.setattr(nsvc, "_gateway_send", lambda ev, recipient=None: False)

        from app.services import assignment_service as asvc
        monkeypatch.setattr(asvc, "_llm_generate",
                            lambda kps, diff, n, rag_context=None, question_types=None: [])
        # 让 compose 走通：直接假生成
        def fake_gen(kps, diff, n, rag_context=None, question_types=None):
            return [{"content": f"题{i}", "options": ["A", "B"], "answer": "A",
                     "analysis": "", "knowledge_points": ["kp"]} for i in range(n)]
        monkeypatch.setattr(asvc, "_llm_generate", fake_gen)
        monkeypatch.setattr(asvc, "_audit_equation", lambda eq: {"overall_status": "passed"})

        out = asvc.assign(db_session, ["202610101"],
                          {"kind": "adaptive", "question_count": 2})
        db_session.commit()
        assert out["results"][0]["status"] == "assigned"

        rows = db_session.query(StudentNotification).filter_by(student_id="202610101").all()
        assert len(rows) == 1 and rows[0].type == "assignment"

    def test_grading_notifies_student(self, db_session, exam_record, sample_student, monkeypatch):
        """练习判卷落库 → 学生收件箱出现「判卷完成」。"""
        monkeypatch.setattr(db_mod, "get_db", lambda: iter([db_session]))
        monkeypatch.setattr(nsvc, "get_db", lambda: iter([db_session]))
        monkeypatch.setattr(nsvc, "_gateway_send", lambda ev, recipient=None: False)
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)

        from app.services import grading_center
        grading_center.save(db_session, [
            {"question_id": "gc_q_1", "student_answer": "B", "is_correct": True},
        ], "202610101", "gc_exam_001", "online")
        db_session.commit()

        rows = db_session.query(StudentNotification).filter_by(student_id="202610101").all()
        assert len(rows) == 1 and rows[0].type == "grading"

    def test_grading_notify_failure_does_not_break_save(self, db_session, exam_record,
                                                        sample_student, monkeypatch):
        """通知抛异常不影响判卷落库（防御语义）。"""
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)

        def _boom(**kw):
            raise RuntimeError("dispatch down")
        monkeypatch.setattr(nsvc.notification_service, "dispatch", _boom)

        out = grading_center.save(db_session, [
            {"question_id": "gc_q_1", "student_answer": "B", "is_correct": True},
        ], "202610101", "gc_exam_001", "online")
        db_session.commit()
        assert out["saved"] == 1


class TestSendScopeNarrowing:
    """/send 的收件人必须落在调用者数据范围内（此前任课教师可给外校学生落通知）。"""

    @pytest.fixture
    def second_class(self, seeded):
        from app.models.database import Class, Grade, TeacherClassSubject
        seeded.add(Grade(grade_id="g2", school_id="school1", name="高二", year=2026))
        seeded.add(Class(class_id="class_2025_2", name="二班", grade="高二",
                         grade_id="g2", subject="化学"))
        seeded.add(Student(student_id="202610103", name="王小明", class_id="class_2025_2"))
        seeded.add(TeacherClassSubject(id="t_sort", teacher_id="T_chem",
                                       class_id="class_2025_1", subject="化学"))
        seeded.commit()
        return seeded

    def _teacher_hdr(self):
        return {"Authorization": f"Bearer {create_access_token('T_chem', 'teacher', school_id='school1')}"}

    def _body(self, rid):
        return {"type": "reminder", "title": "提醒", "content": "交作业",
                "target_type": "student", "target_ids": [rid]}

    def test_teacher_can_send_within_own_class(self, client, second_class):
        r = client.post("/api/notification/send", json=self._body("202610101"),
                        headers=self._teacher_hdr())
        assert r.status_code == 200 and r.json()["sent_count"] == 1

    def test_teacher_cannot_send_outside_own_class(self, client, second_class, patched_db):
        r = client.post("/api/notification/send", json=self._body("202610103"),
                        headers=self._teacher_hdr())
        assert r.status_code == 403
        assert patched_db.query(StudentNotification).count() == 0, "越界收件人一条都不该落"


class TestSendAndReadScope:
    def test_send_route_parent_targets_carry_student_id(self, client, patched_db):
        """家长分支必须把通知挂到具体学生（student_id 是 NOT NULL 外键）。"""
        from app.models.database import ParentNotification, StudentParentBinding
        patched_db.add(StudentParentBinding(binding_id="b1", parent_id="P1",
                                            student_id="202610101", status="active",
                                            bind_code="BC1"))
        patched_db.commit()

        r = client.post("/api/notification/send", headers=_admin_hdr(), json={
            "type": "reminder", "title": "交作业", "content": "今晚交",
            "target_type": "parent", "target_ids": ["P1"]})
        assert r.status_code == 200 and r.json()["sent_count"] == 1
        row = patched_db.query(ParentNotification).one()
        assert row.student_id == "202610101"

    def test_send_route_rejects_parent_out_of_scope(self, client, patched_db):
        from app.models.database import Class, Grade, Parent, School, Student, StudentParentBinding
        patched_db.add_all([
            School(school_id="school2", name="别校"),
            Grade(grade_id="g9", school_id="school2", name="高一", year=2026),
            Class(class_id="class_other", name="外校班", grade="高一",
                  grade_id="g9", subject="化学"),
            Student(student_id="202699999", name="外校生", class_id="class_other"),
            Parent(parent_id="P9", name="外校家长", password_hash="x"),
            StudentParentBinding(binding_id="b9", parent_id="P9",
                                 student_id="202699999", status="active", bind_code="BC9"),
        ])
        patched_db.commit()

        r = client.post("/api/notification/send", headers=_admin_hdr(), json={
            "type": "reminder", "title": "t", "content": "c",
            "target_type": "parent", "target_ids": ["P9"]})
        assert r.status_code == 403

    def test_staff_read_path_is_scoped(self, client, patched_db):
        """员工标记已读同样按数据范围收窄，不采信自报的 user_id。"""
        from app.models.database import Class, Grade, School, Student
        patched_db.add_all([
            School(school_id="school2", name="别校"),
            Grade(grade_id="g9", school_id="school2", name="高一", year=2026),
            Class(class_id="class_other", name="外校班", grade="高一",
                  grade_id="g9", subject="化学"),
            Student(student_id="202699999", name="外校生", class_id="class_other"),
        ])
        patched_db.commit()
        nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202699999"},
            event={"type": "assignment", "title": "外校通知", "content": ""})
        nid = patched_db.query(StudentNotification).one().notification_id

        r = client.put(f"/api/notification/{nid}/read"
                       "?user_id=202699999&user_type=student", headers=_admin_hdr())
        assert r.status_code == 404
        assert patched_db.query(StudentNotification).one().is_read is False

    def test_staff_read_path_allows_own_school(self, client, patched_db):
        nsvc.notification_service.dispatch(
            recipient={"role": "student", "id": "202610101"},
            event={"type": "assignment", "title": "校内通知", "content": ""})
        nid = patched_db.query(StudentNotification).one().notification_id

        r = client.put(f"/api/notification/{nid}/read"
                       "?user_id=202610101&user_type=student", headers=_admin_hdr())
        assert r.status_code == 200
        assert patched_db.query(StudentNotification).one().is_read is True


class TestIdempotencyKeyLength:
    def test_long_key_keeps_recipients_apart(self, patched_db):
        """超长幂等键不能把收件人截掉：两个收件人各落一条、各自可重放去重。"""
        key = "k" * 120
        for rid in ("202610101", "202610102"):
            nsvc.notification_service.dispatch(
                recipient={"role": "student", "id": rid},
                event={"type": "assignment", "title": "t", "content": ""},
                idempotency_key=key)
        rows = patched_db.query(StudentNotification).all()
        assert {r.student_id for r in rows} == {"202610101", "202610102"}

        # 重放仍幂等：同键同收件人不新增
        for rid in ("202610101", "202610102"):
            nsvc.notification_service.dispatch(
                recipient={"role": "student", "id": rid},
                event={"type": "assignment", "title": "t", "content": ""},
                idempotency_key=key)
        assert patched_db.query(StudentNotification).count() == 2
