"""数据范围（第二层权限）—— ADR-0010。

角色只决定**用哪几个维度收窄**，范围本身从关系表算出来：

    teacher → teacher_class_subject → class → grade → school

`class_ids()` 是唯一的计算点，其余方法都从它派生。规则：

    super_admin      空集 —— 跨校要走 break-glass，不是常驻权限（ADR-0011）
    admin            本校全部班级
    academic_admin   本校全部班级
    subject_lead     本校 × 本学科（ADR-0010）
    teacher          仅自己任教的班
    student          自己所在班
    parent           自己绑定学生所在班
    未知 / 身份缺失    空集（fail-closed）

设计约束：
  - **fail-closed**：身份缺失、角色未知、查不到数据 —— 一律空范围，不放行。
  - 若将来加缓存，**key 必须含 school_id**，否则会把「本校管理员」变成「所有学校管理员」。
"""
from typing import Optional, Set

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models.database import (
    Class, ExamRecord, Grade, Student, StudentParentBinding, Teacher,
    TeacherClassSubject, get_db,
)

# 在本校范围内不受班级维度收窄的员工角色
_SCHOOL_WIDE = ("admin", "academic_admin")

# 员工角色（学生/家长是「本人角色」，走身份即范围，ADR-0008）
STAFF_ROLES = ("teacher", "subject_lead", "academic_admin", "admin")


def resolve_identity(db: Session, user_id: str) -> dict:
    """按 token 里的 user_id 反查账户 → {"user_id","role","school_id"}。

    给「身份不在请求里」（如 Agent 工具上下文）的调用方用；查不到返回空角色，
    调用方按 fail-closed 处理。绝不能用模型/前端自报的 id 当身份。
    """
    from sqlalchemy import or_
    from app.models.database import Account

    if not user_id:
        return {"user_id": "", "role": "", "school_id": None}
    account = db.query(Account).filter(or_(
        Account.account_id == user_id, Account.teacher_id == user_id,
        Account.student_id == user_id, Account.parent_id == user_id,
    )).first()
    if account is None:
        return {"user_id": user_id, "role": "", "school_id": None}
    from app.api.auth import get_user_info
    info = get_user_info(account, db)
    return {"user_id": user_id, "role": account.role, "school_id": info.get("school_id")}


class RequestScope:
    """一个登录身份能触达的数据范围。"""

    def __init__(self, role: str, user_id: str, school_id: Optional[str] = None,
                 db: Optional[Session] = None):
        self.role = role or ""
        self.user_id = user_id or ""
        self.school_id = school_id
        self.db = db
        self._class_ids: Optional[Set[str]] = None

    @classmethod
    def from_user(cls, user: dict, db: Session) -> "RequestScope":
        """从 PermissionChecker / get_current_user 返回的身份字典构造。"""
        user = user or {}
        return cls(user.get("role"), user.get("user_id"), user.get("school_id"), db)

    # ── 唯一的范围计算点 ────────────────────────────────────────

    def class_ids(self) -> Set[str]:
        """该身份可触达的 class_id 集合。惰性计算并缓存于实例上。"""
        if self._class_ids is None:
            self._class_ids = self._compute_class_ids()
        return self._class_ids

    def _compute_class_ids(self) -> Set[str]:
        if not self.db or not self.role:
            return set()
        if self.role == "super_admin":
            return self._all_classes_if_elevated()         # ADR-0011：默认空，提权期间放开
        if self.role in _SCHOOL_WIDE:
            return self._classes_in_school()
        if self.role == "subject_lead":
            return self._classes_for_subject_lead()
        if self.role == "teacher":
            return self._classes_taught()
        if self.role == "student":
            return self._class_of_student(self.user_id)
        if self.role == "parent":
            return self._classes_of_bound_children()
        return set()                                       # 未知角色 fail-closed

    # ── 各角色的取数 ───────────────────────────────────────────

    def _all_classes_if_elevated(self) -> Set[str]:
        """ADR-0011：超管默认空范围，**只有 break-glass 生效期间**才放开到全部学校。

        提权是否生效由读时判定（`expires_at` 到点即失效），所以不需要任何清理任务；
        没有生效中的提权 → 空集，与其他角色的 fail-closed 一致。
        """
        from app.middleware.break_glass import active_session

        if not active_session(self.db, self.user_id):
            return set()
        rows = self.db.query(Class.class_id).all()
        return {r[0] for r in rows if r[0]}

    def _classes_in_school(self) -> Set[str]:
        if not self.school_id:
            return set()
        rows = (
            self.db.query(Class.class_id)
            .join(Grade, Class.grade_id == Grade.grade_id)
            .filter(Grade.school_id == self.school_id)
            .all()
        )
        return {r[0] for r in rows if r[0]}

    def _classes_taught(self) -> Set[str]:
        if not self.user_id:
            return set()
        rows = (
            self.db.query(TeacherClassSubject.class_id)
            .filter(TeacherClassSubject.teacher_id == self.user_id)
            .all()
        )
        return {r[0] for r in rows if r[0]}

    def _classes_for_subject_lead(self) -> Set[str]:
        """本校 × 本学科。学科来自 teacher_class_subject，不在角色上（ADR-0010）。"""
        if not self.user_id:
            return set()
        subjects = {
            r[0] for r in self.db.query(TeacherClassSubject.subject)
            .filter(TeacherClassSubject.teacher_id == self.user_id).all()
            if r[0]
        }
        in_school = self._classes_in_school()
        if not subjects or not in_school:
            return set()
        rows = (
            self.db.query(Class.class_id)
            .filter(Class.class_id.in_(in_school), Class.subject.in_(subjects))
            .all()
        )
        return {r[0] for r in rows if r[0]}

    def _class_of_student(self, student_id: str) -> Set[str]:
        if not student_id:
            return set()
        row = (
            self.db.query(Student.class_id)
            .filter(Student.student_id == student_id)
            .first()
        )
        return {row[0]} if row and row[0] else set()

    def _classes_of_bound_children(self) -> Set[str]:
        if not self.user_id:
            return set()
        rows = (
            self.db.query(Student.class_id)
            .join(StudentParentBinding,
                  Student.student_id == StudentParentBinding.student_id)
            .filter(StudentParentBinding.parent_id == self.user_id,
                    StudentParentBinding.status == "active")
            .all()
        )
        return {r[0] for r in rows if r[0]}

    # ── 判定 ──────────────────────────────────────────────────

    def student_ids(self) -> Set[str]:
        """范围内可见的**学生个体**集合。

        与 `allows_student` 的区别：本人角色只含自己（学生）或绑定子女（家长），
        **不含同班同学** —— 给「不传 student_id 就返回全部」这类聚合查询收窄用。
        """
        if not self.db:
            return set()
        if self.role == "student":
            return {self.user_id} if self.user_id else set()
        if self.role == "parent":
            if not self.user_id:
                return set()
            rows = (
                self.db.query(StudentParentBinding.student_id)
                .filter(StudentParentBinding.parent_id == self.user_id,
                        StudentParentBinding.status == "active")
                .all()
            )
            return {r[0] for r in rows if r[0]}
        classes = self.class_ids()
        if not classes:
            return set()
        rows = (
            self.db.query(Student.student_id)
            .filter(Student.class_id.in_(classes))
            .all()
        )
        return {r[0] for r in rows if r[0]}

    def allows_class(self, class_id: str) -> bool:
        return bool(class_id) and class_id in self.class_ids()

    def allows_teacher(self, teacher_id: str) -> bool:
        """员工维度：本人；校级管理员限**本校**教师（查不到学校一律拒绝）。"""
        if not teacher_id:
            return False
        if teacher_id == self.user_id:
            return True
        if self.role not in _SCHOOL_WIDE or not self.school_id or not self.db:
            return False
        row = self.db.query(Teacher.school_id).filter(
            Teacher.teacher_id == teacher_id).first()
        return bool(row and row[0] and row[0] == self.school_id)

    def allows_student(self, student_id: str) -> bool:
        """本人角色直接比身份；员工角色落到「该生所在班是否在范围内」。"""
        if not student_id or not self.db:
            return False
        if self.role == "student":
            return student_id == self.user_id
        if self.role == "parent":
            row = (
                self.db.query(StudentParentBinding.student_id)
                .filter(StudentParentBinding.parent_id == self.user_id,
                        StudentParentBinding.student_id == student_id,
                        StudentParentBinding.status == "active")
                .first()
            )
            return row is not None
        row = (
            self.db.query(Student.class_id)
            .filter(Student.student_id == student_id)
            .first()
        )
        if not row or not row[0]:
            return False
        return self.allows_class(row[0])


def require_student(user: dict, db: Session, student_id: str) -> None:
    """就地校验 student_id 落在调用者范围内 —— 给 student_id **不在路径上**
    （在请求体 / 查询参数里）的端点用；路径参数请用 `ScopeGuard`。

    本人角色由 `RequestScope.allows_student` 直接比身份，员工角色落到班级范围。
    """
    if not student_id or not RequestScope.from_user(user, db).allows_student(student_id):
        raise HTTPException(status_code=403, detail="无权访问该学生")


class ScopeGuard:
    """依赖：校验路径参数里的 class_id / student_id 落在调用者的数据范围内。

    身份取自 token（由全局中间件与 router 级 `PermissionChecker` 校验），
    范围由 `RequestScope` 从关系表推导。不在范围内 → 403。

    用法 —— 每个端点只多一行：

        @router.get("/class/{class_id}/overview")
        async def get_overview(
            class_id: str,
            _: None = Depends(ScopeGuard("class_id")),
            db: Session = Depends(get_db),
        ):
    """

    def __init__(self, param: str, kind: str = "class"):
        assert kind in ("class", "student", "teacher", "exam_record"), kind
        self.param = param
        self.kind = kind

    def __call__(
        self,
        request: Request,
        db: Session = Depends(get_db),
    ) -> None:
        value = request.path_params.get(self.param)
        if not value:
            return                      # 路径没这个参数就不管（由端点自己兜底）

        from app.middleware.auth import get_current_user
        user = get_current_user(request)

        if self.kind == "teacher":
            # 教师数据只对本人与校级管理员开放，且校级管理员限本校教师
            if RequestScope.from_user(user, db).allows_teacher(value):
                return
            raise HTTPException(status_code=403, detail="无权访问该教师的数据")

        if self.kind == "exam_record":
            # 考试记录 → 它所属的班级 → 范围。查不到一律拒绝，不泄漏"这条记录存在"
            row = (
                db.query(ExamRecord.class_id)
                .filter(ExamRecord.record_id == value)
                .first()
            )
            if not row or not row[0]:
                raise HTTPException(status_code=403, detail="无权访问该考试记录")
            scope = RequestScope.from_user(user, db)
            if not scope.allows_class(row[0]):
                raise HTTPException(status_code=403, detail="无权访问该考试记录")
            return

        scope = RequestScope.from_user(user, db)
        if self.kind == "class":
            allowed, what = scope.allows_class(value), "班级"
        else:
            allowed, what = scope.allows_student(value), "学生"

        if not allowed:
            raise HTTPException(status_code=403, detail=f"无权访问该{what}")
