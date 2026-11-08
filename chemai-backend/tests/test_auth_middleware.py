"""JWT 认证中间件测试。

覆盖 base64url 编解码、token 生成/校验/过期/伪造、refresh 与 access 类型区分、
权限矩阵 can()、get_current_user、以及教师/班级数据范围函数。
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.middleware.auth import (
    SECRET_KEY, base64url_encode, base64url_decode,
    create_jwt, verify_jwt, create_access_token, create_refresh_token,
    verify_token, verify_refresh_token, can,
    get_current_user, get_teacher_classes, get_class_students,
)
from app.models.database import Class, Teacher, TeacherClassSubject, Student


# ── base64url ──

def test_base64url_roundtrip():
    for raw in [b"", b"chemai", b"\x00\xff\x01binary data\x10", "中文内容".encode("utf-8")]:
        assert base64url_decode(base64url_encode(raw)) == raw


def test_base64url_encode_is_url_safe():
    # 原标准 base64 的 '+' 与 '/' 应被替换，且无 '=' padding
    enc = base64url_encode(b"\xfb\xef\xff")
    assert "+" not in enc and "/" not in enc and "=" not in enc


# ── JWT 生成/校验 ──

def test_create_jwt_three_parts():
    token = create_jwt({"user_id": "u1"}, SECRET_KEY, expires_in=1)
    assert len(token.split(".")) == 3


def test_verify_jwt_valid_roundtrip():
    token = create_jwt({"user_id": "u1", "role": "teacher"}, SECRET_KEY, expires_in=1)
    payload = verify_jwt(token, SECRET_KEY)
    assert payload["user_id"] == "u1"
    assert payload["role"] == "teacher"
    assert "iat" in payload and "exp" in payload


def test_verify_jwt_wrong_secret_rejected():
    token = create_jwt({"user_id": "u1"}, SECRET_KEY, expires_in=1)
    assert verify_jwt(token, "other-secret") is None


def test_verify_jwt_tampered_payload_rejected():
    token = create_jwt({"user_id": "u1"}, SECRET_KEY, expires_in=1)
    parts = token.split(".")
    # 篡改 payload 而不重签 → 签名不匹配
    import json as _json
    forged = _json.dumps({"user_id": "attacker"}).encode("utf-8")
    parts[1] = base64url_encode(forged)
    assert verify_jwt(".".join(parts), SECRET_KEY) is None


def test_verify_jwt_expired_rejected():
    token = create_jwt({"user_id": "u1"}, SECRET_KEY, expires_in=-1)  # 过去 1 小时
    assert verify_jwt(token, SECRET_KEY) is None


def test_verify_jwt_malformed_rejected():
    assert verify_jwt("not.a.jwt", SECRET_KEY) is None
    assert verify_jwt("", SECRET_KEY) is None


# ── access / refresh 类型 ──

def test_access_and_refresh_type_separation():
    access = create_access_token("u1", "teacher", school_id="s1")
    refresh = create_refresh_token("u1")

    payload = verify_token(access)
    assert payload is not None
    assert payload["type"] == "access"
    assert payload["role"] == "teacher"
    assert payload["school_id"] == "s1"

    # refresh token 不能被 verify_token 接受
    assert verify_token(refresh) is None
    # access token 不能被 verify_refresh_token 接受
    assert verify_refresh_token(access) is None
    # refresh token 能被 verify_refresh_token 接受
    assert verify_refresh_token(refresh) is not None


def test_create_access_token_extra_data():
    access = create_access_token("u1", "student", extra_data={"class_id": "c1"})
    payload = verify_token(access)
    assert payload["class_id"] == "c1"


# ── 权限矩阵 can() ──

def test_can_permissions():
    assert can("admin", "school", "create") is True
    assert can("admin", "school", "delete") is True
    assert can("student", "self_data", "read") is True
    assert can("teacher", "class", "read") is True
    assert can("teacher", "class", "create") is False
    assert can("student", "school", "read") is False
    assert can("student", "analysis", "read") is False
    assert can("unknown_role", "school", "read") is False
    assert can(None, "school", "read") is False
    assert can("admin", "not_a_resource", "read") is False


# ── get_current_user ──

class _FakeRequest:
    def __init__(self, headers=None):
        self._headers = headers or {}

    @property
    def headers(self):
        return self._headers


def test_get_current_user_missing_header():
    with pytest.raises(HTTPException) as e:
        get_current_user(_FakeRequest({}))
    assert e.value.status_code == 401


def test_get_current_user_invalid_token():
    req = _FakeRequest({"Authorization": "Bearer bad.token.here"})
    with pytest.raises(HTTPException) as e:
        get_current_user(req)
    assert e.value.status_code == 401


def test_get_current_user_valid():
    token = create_access_token("t1", "teacher", school_id="s1")
    req = _FakeRequest({"Authorization": f"Bearer {token}"})
    user = get_current_user(req)
    assert user["user_id"] == "t1"
    assert user["role"] == "teacher"
    assert user["school_id"] == "s1"


def test_get_current_user_non_bearer_header():
    # 缺少 Bearer 前缀 → 401
    token = create_access_token("t1", "teacher")
    req = _FakeRequest({"Authorization": token})
    with pytest.raises(HTTPException) as e:
        get_current_user(req)
    assert e.value.status_code == 401


# ── 班级/学生数据范围 ──

def _seed_school_data(db_session):
    c1 = Class(class_id="c1", name="高一1班", grade="高一")
    c2 = Class(class_id="c2", name="高一2班", grade="高一")
    t = Teacher(teacher_id="t1", name="海老师", school_id="school1")
    db_session.add_all([c1, c2, t])
    db_session.commit()
    db_session.add(TeacherClassSubject(id="tcs1", teacher_id="t1", class_id="c1", subject="化学"))
    db_session.add(Student(student_id="s1", name="张浩宇", class_id="c1", status="approved"))
    db_session.add(Student(student_id="s2", name="李世睿", class_id="c2", status="approved"))
    db_session.commit()


def test_get_teacher_classes_admin_sees_all(db_session):
    _seed_school_data(db_session)
    classes = get_teacher_classes(db_session, "t1", role="admin")
    assert {c.class_id for c in classes} == {"c1", "c2"}


def test_get_teacher_classes_normal_teacher_only_own(db_session):
    _seed_school_data(db_session)
    classes = get_teacher_classes(db_session, "t1", role="teacher")
    assert {c.class_id for c in classes} == {"c1"}


def test_get_teacher_classes_teacher_without_tcs(db_session):
    _seed_school_data(db_session)
    classes = get_teacher_classes(db_session, "no_tcs", role="teacher")
    assert classes == []


def test_get_class_students_admin_sees_all(db_session):
    _seed_school_data(db_session)
    students = get_class_students(db_session, "c1", role="admin")
    assert {s.student_id for s in students} == {"s1"}


def test_get_class_students_teacher_unauthorized(db_session):
    _seed_school_data(db_session)
    # t1 未任教 c2 → 无权
    students = get_class_students(db_session, "c2", teacher_id="t1", role="teacher")
    assert students == []


def test_get_class_students_teacher_authorized(db_session):
    _seed_school_data(db_session)
    students = get_class_students(db_session, "c1", teacher_id="t1", role="teacher")
    assert {s.student_id for s in students} == {"s1"}
