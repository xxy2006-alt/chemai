"""数据范围 RequestScope —— ADR-0010。

每条断言都对照「关系表 → 范围」的推导，而不是照着实现复述。
关键区分点：**学科组长看全校本学科，任课教师只看自己教的班。**
"""
import pytest

from app.middleware.scope import RequestScope
from app.models.database import (
    Class, Grade, School, Student, StudentParentBinding, TeacherClassSubject,
)


@pytest.fixture
def seeded(db_session):
    """两所学校；本校三个班，其中化学班 c3 不归 T_chem 教。

      sch1/g1
        c1  化学  ← T_chem 教
        c2  数学  ← T_math 教
        c3  化学  ← T_other 教（用来验证「学科组长看全校本学科」）
      sch2/g2
        c4  化学  ← 另一所学校的化学班（用来验证不跨校）

      S1 在 c1；家长 P1 绑定 S1；S2 在 c4（别校学生）。
    """
    db_session.add_all([
        School(school_id="sch1", name="测试中学"),
        School(school_id="sch2", name="隔壁中学"),
    ])
    db_session.add_all([
        Grade(grade_id="g1", school_id="sch1", name="高一", year=2025),
        Grade(grade_id="g2", school_id="sch2", name="高一", year=2025),
    ])
    db_session.add_all([
        Class(class_id="c1", name="一班", grade="高一", grade_id="g1", subject="化学"),
        Class(class_id="c2", name="二班", grade="高一", grade_id="g1", subject="数学"),
        Class(class_id="c3", name="三班", grade="高一", grade_id="g1", subject="化学"),
        Class(class_id="c4", name="四班", grade="高一", grade_id="g2", subject="化学"),
    ])
    db_session.add_all([
        TeacherClassSubject(id="t1", teacher_id="T_chem", class_id="c1", subject="化学"),
        TeacherClassSubject(id="t2", teacher_id="T_math", class_id="c2", subject="数学"),
        TeacherClassSubject(id="t3", teacher_id="T_other", class_id="c3", subject="化学"),
    ])
    db_session.add_all([
        Student(student_id="S1", class_id="c1", name="学生一"),
        Student(student_id="S2", class_id="c4", name="学生二"),
    ])
    db_session.add(StudentParentBinding(
        binding_id="b1", student_id="S1", parent_id="P1",
        bind_code="BIND0001", status="active",
    ))
    db_session.commit()
    return db_session


def scope_ctx(db, role, user_id, school_id="sch1"):
    return RequestScope(role=role, user_id=user_id, school_id=school_id, db=db)


# ── 员工角色 ──────────────────────────────────────────────

def test_super_admin_defaults_to_empty_scope(seeded):
    """ADR-0011：平台超管默认看不到任何学校数据，跨校要走 break-glass。"""
    assert scope_ctx(seeded, "super_admin", "A1").class_ids() == set()


def test_admin_sees_whole_school(seeded):
    assert scope_ctx(seeded, "admin", "A1").class_ids() == {"c1", "c2", "c3"}


def test_academic_admin_sees_whole_school(seeded):
    assert scope_ctx(seeded, "academic_admin", "A1").class_ids() == {"c1", "c2", "c3"}


def test_teacher_sees_only_taught_classes(seeded):
    assert scope_ctx(seeded, "teacher", "T_chem").class_ids() == {"c1"}
    assert scope_ctx(seeded, "teacher", "T_math").class_ids() == {"c2"}


def test_subject_lead_sees_school_wide_within_subject(seeded):
    """ADR-0010 的核心断言：化学组长看得到 c3，哪怕 c3 不是他教的。"""
    assert scope_ctx(seeded, "subject_lead", "T_chem").class_ids() == {"c1", "c3"}


def test_subject_lead_does_not_cross_school_boundary(seeded):
    """本校 × 本学科 —— 隔壁学校的化学班 c4 不在范围内。"""
    assert "c4" not in scope_ctx(seeded, "subject_lead", "T_chem").class_ids()


def test_admin_does_not_cross_school_boundary(seeded):
    assert "c4" not in scope_ctx(seeded, "admin", "A1").class_ids()


# ── 本人角色 ──────────────────────────────────────────────

def test_student_sees_own_class(seeded):
    assert scope_ctx(seeded, "student", "S1").class_ids() == {"c1"}


def test_parent_sees_bound_child_class(seeded):
    assert scope_ctx(seeded, "parent", "P1").class_ids() == {"c1"}


def test_parent_without_binding_sees_nothing(seeded):
    assert scope_ctx(seeded, "parent", "P_nobody").class_ids() == set()


# ── fail-closed ───────────────────────────────────────────

def test_unknown_role_sees_nothing(seeded):
    assert scope_ctx(seeded, "not_a_role", "X").class_ids() == set()


def test_empty_role_sees_nothing(seeded):
    assert scope_ctx(seeded, "", "X").class_ids() == set()


def test_admin_without_school_sees_nothing(seeded):
    """超管之外的员工角色也必须有学校；没有就 fail-closed。"""
    assert scope_ctx(seeded, "admin", "A1", school_id=None).class_ids() == set()


def test_student_that_does_not_exist_sees_nothing(seeded):
    assert scope_ctx(seeded, "student", "S_nobody").class_ids() == set()


def test_scope_without_db_sees_nothing(seeded):
    assert RequestScope(role="admin", user_id="A1", school_id="sch1", db=None).class_ids() == set()


# ── 判定方法 ──────────────────────────────────────────────

def test_allows_class_matches_class_ids(seeded):
    s = scope_ctx(seeded, "teacher", "T_chem")
    assert s.allows_class("c1") is True
    assert s.allows_class("c2") is False
    assert s.allows_class("") is False


def test_allows_student_for_staff_goes_through_class(seeded):
    assert scope_ctx(seeded, "teacher", "T_chem").allows_student("S1") is True
    assert scope_ctx(seeded, "teacher", "T_math").allows_student("S1") is False
    assert scope_ctx(seeded, "teacher", "T_chem").allows_student("S_nobody") is False


def test_allows_student_for_self_roles_is_identity(seeded):
    assert scope_ctx(seeded, "student", "S1").allows_student("S1") is True
    assert scope_ctx(seeded, "student", "S1").allows_student("S2") is False

    parent = scope_ctx(seeded, "parent", "P1")
    assert parent.allows_student("S1") is True
    assert parent.allows_student("S2") is False


def test_scope_is_computed_once(seeded):
    """class_ids() 惰性计算并缓存于实例 —— 同一实例重复调用应是同一个对象。"""
    s = scope_ctx(seeded, "admin", "A1")
    assert s.class_ids() is s.class_ids()
