"""
ChemAI Database Models
基于PRD v1.0完整版附录D数据字典
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, JSON, ForeignKey, Enum, create_engine, LargeBinary
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from enum import Enum as PyEnum, IntEnum

Base = declarative_base()


class BarrierType(PyEnum):
    """障碍类型枚举"""
    CONCEPT = "concept"        # 概念理解型
    READING = "reading"        # 审题障碍型
    EXPRESSION = "expression"  # 表述障碍型


class RecordType(PyEnum):
    """记录类型枚举"""
    EXAM = "exam"       # 月考
    PRACTICE = "practice"  # 练习
    ASSIGNMENT = "assignment"  # 作业


class ExamStatus(PyEnum):
    """考试生命周期状态（CONTEXT.md 六态 + cancelled；P4 做实）"""
    DRAFT = "draft"
    PUBLISHED = "published"
    IN_PROGRESS = "in_progress"
    GRADING = "grading"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class AnswerSource(PyEnum):
    """作答来源（判卷中心）：一切作答经同一落库路径，来源可辨可过滤"""
    ONLINE = "online"      # 学生线上提交
    OCR = "ocr"            # 答题卡批量识别
    MANUAL = "manual"      # 教师手动录入
    CHAT = "chat"          # 分步导学对话作答
    TRAINING = "training"  # 错题训练


class QuestionSource(PyEnum):
    """题目来源枚举"""
    AI_GENERATED = "ai_generated"
    MANUAL_SELECTED = "manual_selected"
    DAILY_PRACTICE = "daily_practice"
    OCR_IMPORT = "ocr_import"


class AuditStatus(PyEnum):
    """审核状态枚举"""
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


class Difficulty(IntEnum):
    """难度枚举 — 整数 1~5（见 CONTEXT.md：1=基础 2=中等偏易 3=中等 4=较难 5=竞赛/拔高）

    API 传输与数据库存储均使用整数值；成员名仅供代码内部引用。
    """
    EASY = 1        # 基础
    MODERATE = 2    # 中等偏易
    MEDIUM = 3      # 中等
    HARD = 4        # 较难
    COMPETITION = 5 # 竞赛/拔高

    @classmethod
    def coerce(cls, value) -> "Difficulty":
        """归一 int / 旧标签字符串 / 枚举成员 为 Difficulty"""
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            return cls.MEDIUM
        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError:
                return cls.MEDIUM
        return cls.from_label(value)

    @classmethod
    def from_label(cls, label: str) -> "Difficulty":
        """兼容旧标签字符串（easy/medium/hard/competition）"""
        labels = {
            "easy": cls.EASY, "basic": cls.EASY,
            "moderate": cls.MODERATE,
            "medium": cls.MEDIUM,
            "hard": cls.HARD,
            "competition": cls.COMPETITION,
        }
        return labels.get(str(label).lower(), cls.MEDIUM)


class Teacher(Base):
    """教师表"""
    __tablename__ = "teachers"

    teacher_id = Column(String(64), primary_key=True)
    school_id = Column(String(64), ForeignKey("schools.school_id"), nullable=True)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=True)
    status = Column(String(32), default="approved")  # pending/approved/rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    school = relationship("School", back_populates="teachers")
    teacher_subjects = relationship("TeacherClassSubject", back_populates="teacher")
    barrier_configs = relationship("BarrierConfig", back_populates="teacher")
    account = relationship("Account", back_populates="teacher", uselist=False)


class Student(Base):
    """学生表"""
    __tablename__ = "students"

    student_id = Column(String(64), primary_key=True)
    class_id = Column(String(64), ForeignKey("classes.class_id"), nullable=False)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=True)
    status = Column(String(32), default="approved")  # pending/approved/rejected
    # 障碍类型占比 (JSON: {concept: 0.3, reading: 0.5, expression: 0.2})
    barrier_type = Column(JSON, default={"concept": 0.33, "reading": 0.33, "expression": 0.34})
    barrier_last_updated = Column(DateTime, nullable=True)
    diagnosis_requested_at = Column(DateTime, nullable=True)  # 学生级诊断去抖窗口标记
    exercises_completed = Column(Integer, default=0)
    last_exercise_at = Column(DateTime, nullable=True)
    bind_code = Column(String(64), nullable=True)  # 家长绑定码
    current_plan = Column(JSON, nullable=True)  # 当前学习计划 {plan_title, daily_tasks, ...}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student_class = relationship("Class", back_populates="students")
    account = relationship("Account", back_populates="student", uselist=False)
    parent_bindings = relationship("StudentParentBinding", back_populates="student")


class Account(Base):
    """账户表（登录认证）"""
    __tablename__ = "accounts"

    account_id = Column(String(64), primary_key=True)
    role = Column(String(32), nullable=False)  # admin/teacher/student/parent
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    teacher_id = Column(String(64), ForeignKey("teachers.teacher_id"), nullable=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=True)
    parent_id = Column(String(64), ForeignKey("parents.parent_id"), nullable=True)
    status = Column(String(32), default="active")  # active/disabled
    current_token = Column(String(128), nullable=True)  # 当前登录token
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    teacher = relationship("Teacher", back_populates="account")
    student = relationship("Student", back_populates="account")
    parent = relationship("Parent", back_populates="account")


class Class(Base):
    """班级表"""
    __tablename__ = "classes"

    class_id = Column(String(64), primary_key=True)
    # 原有 `teacher_id` 列已删（阶段 6.2）：它建表时被写死 `None`、从来没有数据，
    # 却让三处代码静默失效（班主任恒 null、教师所带班级恒空）。
    # **班主任的唯一真源是 `teacher_class_subject.is_class_teacher`**；
    # 顺带删掉的 `Class.teacher` / `Teacher.classes` 两个 relationship 也依赖它
    # （留着会因推不出 join 条件而报错），且全仓库零引用。
    name = Column(String(128), nullable=False)
    student_count = Column(Integer, default=0)
    grade = Column(String(32), nullable=False)  # 年级名称，如"高一"
    subject = Column(String(32), default="化学")
    grade_id = Column(String(64), ForeignKey("grades.grade_id"), nullable=True)  # 年级外键
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    grade_rel = relationship("Grade", back_populates="classes")  # 重命名避免与grade列冲突
    students = relationship("Student", back_populates="student_class")
    exam_records = relationship("ExamRecord", back_populates="exam_class")
    teacher_subjects = relationship("TeacherClassSubject", back_populates="class_obj")


class ExamRecord(Base):
    """考试/练习记录表"""
    __tablename__ = "exam_records"

    record_id = Column(String(64), primary_key=True)
    class_id = Column(String(64), ForeignKey("classes.class_id"), nullable=False)
    type = Column(Enum(RecordType), default=RecordType.EXAM)
    name = Column(String(256), nullable=False)  # e.g. "高二上月考化学"
    question_stats = Column(JSON, nullable=True)  # 错题统计数据
    avg_score = Column(Float, nullable=True)
    total_students = Column(Integer, default=0)
    present_students = Column(Integer, default=0)  # 实际参考人数
    source = Column(Enum(QuestionSource), default=QuestionSource.AI_GENERATED)
    exam_date = Column(DateTime, nullable=True)
    status = Column(Enum(ExamStatus), nullable=True)  # 生命周期；存量经 migrate 回填
    published_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    grading_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    exam_class = relationship("Class", back_populates="exam_records")
    questions = relationship("Question", back_populates="exam_record")


class Question(Base):
    """题目表（AI生成+手动选题）"""
    __tablename__ = "questions"

    question_id = Column(String(64), primary_key=True)
    record_id = Column(String(64), ForeignKey("exam_records.record_id"), nullable=True)
    content = Column(Text, nullable=False)  # 题目正文
    options = Column(JSON, nullable=True)  # 选项列表 ["A. xxx", "B. xxx", ...]
    answer = Column(String(256), nullable=True)  # 参考答案
    analysis = Column(Text, nullable=True)  # 题目解析
    knowledge_points = Column(JSON, nullable=True)  # 知识点标签列表
    probe_dimension = Column(String(16), nullable=True)  # 考察维度: concept/reading/expression（答错时归因到该维度）
    difficulty = Column(Integer, default=Difficulty.MEDIUM.value)  # 1~5，见 Difficulty
    source = Column(Enum(QuestionSource), default=QuestionSource.AI_GENERATED)
    source_exam = Column(String(256), nullable=True)  # 手动选题来源: "2024年全国卷T15"
    audit_status = Column(Enum(AuditStatus), default=AuditStatus.PASSED)
    audit_report = Column(JSON, nullable=True)  # 三维审核报告内容
    historical_matches = Column(JSON, nullable=True)  # 历年真题关联列表
    # 审核维度 (用于F2安全审核)
    coefficient_correct = Column(Boolean, default=True)  # 系数配平
    condition_correct = Column(Boolean, default=True)  # 反应条件
    product_correct = Column(Boolean, default=True)  # 产物正确性
    structure_correct = Column(Boolean, default=True)  # 分子结构
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    exam_record = relationship("ExamRecord", back_populates="questions")
    student_answers = relationship("StudentAnswer", back_populates="question")


class BarrierConfig(Base):
    """障碍诊断配置表"""
    __tablename__ = "barrier_configs"

    config_id = Column(String(64), primary_key=True)
    teacher_id = Column(String(64), ForeignKey("teachers.teacher_id"), nullable=False)
    # 各障碍类型触发阈值
    concept_threshold = Column(Integer, default=3)  # 概念理解型：连续错误N次触发
    reading_threshold = Column(Integer, default=2)  # 审题障碍型：连续错误N次触发
    expression_threshold = Column(Integer, default=3)  # 表述障碍型：连续错误N次触发
    mastery_threshold = Column(Integer, default=3)  # 掌握标准：连续答对N次
    auto_sync_to_student = Column(Boolean, default=False)  # 诊断结论是否自动同步学生端
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    teacher = relationship("Teacher", back_populates="barrier_configs")


class StudentAnswer(Base):
    """学生作答记录表（用于障碍类型诊断）"""
    __tablename__ = "student_answers"

    answer_id = Column(String(64), primary_key=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    question_id = Column(String(64), ForeignKey("questions.question_id"), nullable=False)
    exam_record_id = Column(String(64), ForeignKey("exam_records.record_id"), nullable=True)

    student_answer = Column(String(256), nullable=True)  # 学生作答内容
    is_correct = Column(Boolean, nullable=False)
    confirmed = Column(Boolean, default=True)  # 成绩确认门：考试作答默认 False，教师确认后生效
    grade_reason = Column(String(256), nullable=True)  # 判定理由（PENDING_SEMANTIC=待语义判定）
    # 落行时真正用的标准答案键（老师粘贴的答案 > 题库）：扫描重判要拿它对齐，
    # 否则会用题库里的草稿值重判，把学生正确作答固化成语义判定错答
    answer_key = Column(String(256), nullable=True)
    source = Column(Enum(AnswerSource), nullable=True)  # 作答来源；存量经 migrate 回填
    barrier_type = Column(Enum(BarrierType), nullable=True)  # 判定障碍类型

    # 连续错误/正确计数（用于触发障碍诊断）
    consecutive_errors = Column(Integer, default=0)
    consecutive_correct = Column(Integer, default=0)

    answered_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    student = relationship("Student")
    question = relationship("Question")


class AssignmentBatch(Base):
    """练习分发布次（>SYNC_LIMIT 人异步逐生布置的清单与进度源）"""
    __tablename__ = "assignment_batches"

    batch_id = Column(String(64), primary_key=True)
    targets = Column(JSON, nullable=False)  # [student_id]
    source = Column(JSON, nullable=False)   # 取题来源 {"kind": adaptive|bank|manual, ...}
    name_hint = Column(String(128), nullable=True)
    # 终态：pending/running/done/partial/failed —— 老师据此区分「还在跑」与「已失败」
    status = Column(String(16), nullable=True)
    failed_targets = Column(JSON, nullable=True)  # {student_id: 失败原因}
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgePoint(Base):
    """知识点表（化学知识图谱）"""
    __tablename__ = "knowledge_points"

    kp_id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)  # e.g. "盐类水解"
    category = Column(String(128), nullable=True)  # e.g. "电解质溶液"
    description = Column(Text, nullable=True)
    # PubChem关联CID
    pubchem_cid = Column(String(64), nullable=True)
    # 关联题目数
    question_count = Column(Integer, default=0)
    # 错误率 (动态计算)
    error_rate = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HistoricalExam(Base):
    """历年真题表"""
    __tablename__ = "historical_exams"

    exam_id = Column(String(64), primary_key=True)
    source = Column(String(64), nullable=False)  # e.g. "全国卷2024"
    year = Column(Integer, nullable=False)
    question_number = Column(String(16), nullable=False)  # e.g. "T15"
    knowledge_points = Column(JSON, nullable=True)  # 知识点列表
    difficulty = Column(Integer, default=Difficulty.MEDIUM.value)  # 1~5，见 Difficulty
    discrimination = Column(Float, nullable=True)  # 区分度 0-1
    content = Column(Text, nullable=False)  # 题目内容
    answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionSet(Base):
    """真题集表（用户自定义收藏集）"""
    __tablename__ = "question_sets"

    set_id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)  # 真题集名称
    teacher_id = Column(String(64), nullable=True)  # 创建者教师ID
    region = Column(String(64), nullable=True)  # 来源地区，如"全国卷"
    year = Column(Integer, nullable=True)  # 年份
    source = Column(String(64), nullable=True)  # 来源说明
    description = Column(Text, nullable=True)  # 描述
    question_count = Column(Integer, default=0)  # 题目数量
    is_system = Column(Boolean, default=False)  # 是否系统预设
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    questions = relationship("QuestionSetItem", back_populates="question_set")


class QuestionSetItem(Base):
    """真题集包含的题目关联表"""
    __tablename__ = "question_set_items"

    item_id = Column(String(64), primary_key=True)
    set_id = Column(String(64), ForeignKey("question_sets.set_id"), nullable=False)
    question_id = Column(String(64), ForeignKey("questions.question_id"), nullable=False)
    sort_order = Column(Integer, default=0)  # 排序顺序
    added_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    question_set = relationship("QuestionSet", back_populates="questions")
    question = relationship("Question")


# ==================== 新增模型（Phase 1） ====================

class School(Base):
    """学校表"""
    __tablename__ = "schools"

    school_id = Column(String(64), primary_key=True)
    name = Column(String(100), nullable=False)
    region = Column(String(200), nullable=True)
    address = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    current_term = Column(String(50), nullable=True)
    subjects = Column(JSON, nullable=True)  # ["语文","数学","英语","化学",...]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    grades = relationship("Grade", back_populates="school")
    teachers = relationship("Teacher", back_populates="school")


class Grade(Base):
    """年级表"""
    __tablename__ = "grades"

    grade_id = Column(String(64), primary_key=True)
    school_id = Column(String(64), ForeignKey("schools.school_id"), nullable=True)
    name = Column(String(50), nullable=False)  # "高一"
    year = Column(Integer, nullable=False)  # 2025
    status = Column(Integer, default=1)  # 1:在读 0:已毕业
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    school = relationship("School", back_populates="grades")
    classes = relationship("Class", back_populates="grade_rel")


class TeacherClassSubject(Base):
    """教师-班级-科目关联表（多对多）"""
    __tablename__ = "teacher_class_subject"

    id = Column(String(64), primary_key=True)
    teacher_id = Column(String(64), ForeignKey("teachers.teacher_id"), nullable=False)
    class_id = Column(String(64), ForeignKey("classes.class_id"), nullable=False)
    subject = Column(String(50), nullable=False)
    is_class_teacher = Column(Boolean, default=False)  # 是否班主任
    assigned_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    teacher = relationship("Teacher", back_populates="teacher_subjects")
    class_obj = relationship("Class", back_populates="teacher_subjects")


class TeacherApplication(Base):
    """教师入驻申请表"""
    __tablename__ = "teacher_applications"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=False)
    school = Column(String(200), nullable=True)
    subject = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")  # pending/approved/rejected
    reviewer_id = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=True)
    action = Column(String(50), nullable=False)  # create/update/delete/login
    target_type = Column(String(50), nullable=True)  # student/teacher/class/grade
    target_id = Column(String(64), nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Parent(Base):
    """家长表"""
    __tablename__ = "parents"

    parent_id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=True)
    email = Column(String(128), nullable=True)
    password_hash = Column(String(256), nullable=False)
    status = Column(String(32), default="active")  # active/disabled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    bindings = relationship("StudentParentBinding", back_populates="parent")
    notifications = relationship("ParentNotification", back_populates="parent")
    account = relationship("Account", back_populates="parent", uselist=False)


class StudentParentBinding(Base):
    """亲子绑定表"""
    __tablename__ = "student_parent_bindings"

    binding_id = Column(String(64), primary_key=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    parent_id = Column(String(64), ForeignKey("parents.parent_id"), nullable=False)
    relation = Column(String(32), default="家长")  # 父亲/母亲/其他
    status = Column(String(32), default="active")  # pending/active/inactive
    bind_code = Column(String(64), nullable=False)  # 绑定验证码
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student = relationship("Student", back_populates="parent_bindings")
    parent = relationship("Parent", back_populates="bindings")


class StudentNotification(Base):
    """学生通知记录表（与 ParentNotification 对称）"""
    __tablename__ = "student_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_id = Column(String(64), nullable=False, unique=True, index=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    type = Column(String(32), nullable=False)  # practice/diagnosis/warning/weekly_report/reminder
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)

    # 关系
    student = relationship("Student")


class ParentNotification(Base):
    """家长通知记录表"""
    __tablename__ = "parent_notifications"

    notification_id = Column(String(64), primary_key=True)
    parent_id = Column(String(64), ForeignKey("parents.parent_id"), nullable=False)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    type = Column(String(32), nullable=False)  # weekly_report/score_alert/learning_plan/reminder/daily_report
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    parent = relationship("Parent", back_populates="notifications")
    student = relationship("Student")


# ⚠️ 合并说明（2026-09-14）：两支各定义过一份 StudentNotification，这里删掉了
# 「notification_id 主键 + payload / read_at / idempotency_key」那一版 —— 它和
# **真实库**对不上（三个库都是 `id` + `sent_at`，主库 2380 行），跑起来学生收件箱
# 直接 500。保留的定义在本文件下方（与库、与 feature/zcode 最新版一致）。
# 幂等不靠列：用 idempotency_key 参数派生出确定性的 notification_id。

class UploadSession(Base):
    """OCR 上传会话状态机"""
    __tablename__ = "upload_sessions"

    id = Column(String(64), primary_key=True)
    file_data = Column("file_data", LargeBinary, nullable=True)
    file_name = Column(String(512), nullable=True)
    mime_type = Column(String(128), nullable=True)
    status = Column(String(32), default="uploaded", index=True)
    preview_text = Column(Text, nullable=True)
    formula_result = Column(Text, nullable=True)
    detected_type = Column(String(32), nullable=True)
    baidu_task_id = Column(String(128), nullable=True)
    page_count = Column(Integer, default=0)
    pages_completed = Column(Integer, default=0)
    result_json = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    degraded = Column(Boolean, default=False)
    version = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentSubmission(Base):
    """学生作答记录 — 关联考试和班级"""
    __tablename__ = "student_submissions"

    submission_id = Column(String(64), primary_key=True)
    exam_id = Column(String(64), ForeignKey("exam_records.record_id"), nullable=True)
    class_id = Column(String(64), nullable=True, index=True)
    student_name = Column(String(128), nullable=True)
    original_image = Column(String(512), nullable=True)
    graded_image = Column(String(512), nullable=True)
    answers_json = Column(Text, nullable=True)
    total_score = Column(Integer, default=0)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    graded_at = Column(DateTime, nullable=True)


# 数据库初始化函数
_default_engine = None
_default_session_factory = None

# 钉死数据库路径：相对路径曾导致「从不同目录启动服务器 → 打开不同库文件 →
# 重启后数据看似全部消失」（用户反馈出现 N 次，2026-08-16 修复）。
# 无论进程从哪个目录启动，一律使用项目根目录下的 chemai.db。
# 2026-09-20 起单一真相 = settings.DATABASE_URL（config.BASE_DIR 锚定），
# 不再在此文件重复一套 __file__ 锚定口径。
import os as _os  # noqa: E402
from app.core.config import settings as _settings  # noqa: E402

_DEFAULT_DB_URL = _settings.DATABASE_URL
# 兼容：显式 DATABASE_URL 环境变量（绝对路径）仍可覆盖
# （注意 .env 里的 DATABASE_URL 只进 settings、不进 os.environ，对这里是不可见的）
_DEFAULT_DB_URL = _os.environ.get("DATABASE_URL") or _DEFAULT_DB_URL


def get_engine(database_url: str = _DEFAULT_DB_URL):
    """获取数据库引擎（单例）"""
    global _default_engine
    if _default_engine is None:
        _default_engine = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        )
        # Enable WAL mode for better concurrency
        if "sqlite" in database_url:
            from sqlalchemy import event
            @event.listens_for(_default_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()
    return _default_engine

def get_session_factory(database_url: str = _DEFAULT_DB_URL):
    """获取会话工厂（单例）"""
    global _default_session_factory
    if _default_session_factory is None:
        engine = get_engine(database_url)
        _default_session_factory = sessionmaker(bind=engine)
    return _default_session_factory

def get_db():
    """获取数据库会话（用于FastAPI依赖注入）"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LearningPlanHistory(Base):
    """学习计划历史记录"""
    __tablename__ = "learning_plan_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    plan_title = Column(String(256), nullable=False)
    plan_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class LearningPlanDraft(Base):
    """学习计划草稿 —— 确认门的实体（ADR-0013）。

    一条草稿是一条版本链：同 draft_id 追加不可变版本行（version+1，带触发它的
    老师反馈），最新一行即当前版本。状态机：
    awaiting_confirmation →（revise: 新版本行，审批归零）* → sent；
    regenerate 将旧活跃版本行标 superseded 并另开新链。
    teacher_approved 是确认门的决定记录——发送由数据状态强制，不再靠进程级布尔。
    """
    __tablename__ = "learning_plan_drafts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    draft_id = Column(String(64), nullable=False, index=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="awaiting_confirmation", index=True)
    content = Column(JSON, nullable=False)
    feedback = Column(Text, nullable=True)
    teacher_approved = Column(Boolean, nullable=False, default=False)
    approved_by = Column(String(64), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PlanRun(Base):
    """计划运行 —— todolist 的实体（ADR-0013）。

    一次多步任务的有序步骤及其状态，跨回合存活：确认门/修订循环发生时 run
    挂起持久化，刷新页面、服务重启后可重同步。每会话最多一个活跃 run，
    新 plan_task 作废旧 run（status=superseded）。
    """
    __tablename__ = "plan_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    conversation_id = Column(String(64), nullable=False, index=True)
    goal = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False, default="running", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 合并说明（2026-09-14）：这里曾出现第二份 StudentNotification（与上面同名同表），
# 已删 —— 两份列定义都与真实库一致，保留上面那份（与 feature/zcode 最新形状相同）。

class ParentReportDraft(Base):
    """家长报告草稿 —— 第二个确认门工件（ADR-0013；issue #12）。

    与 LearningPlanDraft 同构：draft_id 版本链、status 状态机、feedback 审计链、
    teacher_approved 门钥匙。不做通用工件表合并——第三种工件出现时再议。
    """
    __tablename__ = "parent_report_drafts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    draft_id = Column(String(64), nullable=False, index=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="awaiting_confirmation", index=True)
    content = Column(JSON, nullable=False)
    feedback = Column(Text, nullable=True)
    teacher_approved = Column(Boolean, nullable=False, default=False)
    approved_by = Column(String(64), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationGate(Base):
    """会话↔草稿门的持久映射（ADR-0013；#13 冒烟补丁 2）。

    门开时写入、读取时校验草稿状态自愈——服务重启后 /history 仍能重建
    待确认门卡（run 步骤路径只覆盖 todolist 内的门，裸生成门靠本表）。
    """
    __tablename__ = "conversation_gates"
    conversation_id = Column(String(64), primary_key=True)
    draft_id = Column(String(64), nullable=False, index=True)
    artifact = Column(String(32), nullable=False, default="learning_plan")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentGate(Base):
    """通用确认门实体（ADR-0015 阶段 2：门合一）。

    draft / boolean 两个 adapter 落同一 seam：kind=draft 绑定草稿
    （draft_id+version），kind=boolean 携带工具名+参数快照（重放依据）。
    每会话最多一个 status=open 的门；gate_id 是决定与重放的唯一绑定键
    ——一决定一动作，批准门 A 永不执行门 B 的动作。
    """
    __tablename__ = "agent_gates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gate_id = Column(String(80), nullable=False, unique=True, index=True)
    conversation_id = Column(String(64), nullable=False, index=True)
    kind = Column(String(16), nullable=False, default="draft")  # draft | boolean
    tool_name = Column(String(64), nullable=False, default="")
    kwargs = Column(JSON, nullable=False, default=dict)
    draft_id = Column(String(64), nullable=True, index=True)
    version = Column(Integer, nullable=True)
    action = Column(String(32), nullable=False, default="")  # send_student | send_parent | ""
    message = Column(Text, nullable=False, default="")
    status = Column(String(16), nullable=False, default="open", index=True)  # open | executed | cancelled | superseded
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)


def init_db(database_url: str = "sqlite:///./chemai.db"):
    """初始化数据库（创建所有表）"""
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    return engine

# 为了兼容旧代码，也导出默认engine
engine = get_engine()
