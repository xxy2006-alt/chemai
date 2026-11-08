"""
数据库迁移脚本
处理新增表和表结构变更

使用方式:
    python -m app.utils.migrate
"""
import os
import sys
from datetime import datetime

from sqlalchemy import text, inspect

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app.models.database import get_engine, get_session_factory  # noqa: E402


def get_existing_tables(engine):
    """获取现有表列表（兼容不同SQLAlchemy版本）"""
    inspector = inspect(engine)
    return inspector.get_table_names()


def migrate():
    """执行数据库迁移"""
    engine = get_engine()
    session_factory = get_session_factory()
    session = session_factory()

    print("=" * 50)
    print("ChemAI Database Migration")
    print("=" * 50)

    try:
        # 获取现有表列表
        existing_tables = get_existing_tables(engine)
        print(f"\nExisting tables: {existing_tables}")

        # 检查是否需要迁移
        if 'schools' in existing_tables:
            print("\n[OK] schools table exists, skip")
        else:
            create_schools_table(engine)
            print("[OK] schools table created")

        if 'grades' in existing_tables:
            print("[OK] grades table exists, skip")
        else:
            create_grades_table(engine)
            print("[OK] grades table created")

        if 'teacher_class_subject' in existing_tables:
            print("[OK] teacher_class_subject table exists, skip")
        else:
            create_teacher_class_subject_table(engine)
            print("[OK] teacher_class_subject table created")

        if 'teacher_applications' in existing_tables:
            print("[OK] teacher_applications table exists, skip")
        else:
            create_teacher_applications_table(engine)
            print("[OK] teacher_applications table created")

        if 'operation_logs' in existing_tables:
            print("[OK] operation_logs table exists, skip")
        else:
            create_operation_logs_table(engine)
            print("[OK] operation_logs table created")

        # 处理现有表的结构变更
        migrate_classes_table(engine)
        migrate_classes_teacher_id(engine)
        migrate_teachers_table(engine)
        migrate_role_values(engine)
        backfill_legacy_conversations(engine)
        migrate_student_answers_source(engine)
        create_assignment_batches_table(engine)
        create_student_notifications_table(engine)
        migrate_exam_records_status(engine)
        migrate_loop_remediation(engine)
        migrate_questions_difficulty_enum(engine)

        print("\n" + "=" * 50)
        print("Migration completed!")
        print("=" * 50)

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def create_schools_table(engine):
    """创建学校表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS schools (
            school_id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            region VARCHAR(200),
            address VARCHAR(255),
            phone VARCHAR(20),
            current_term VARCHAR(50),
            subjects JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_grades_table(engine):
    """创建年级表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS grades (
            grade_id VARCHAR(64) PRIMARY KEY,
            school_id VARCHAR(64),
            name VARCHAR(50) NOT NULL,
            year INTEGER NOT NULL,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (school_id) REFERENCES schools(school_id)
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_teacher_class_subject_table(engine):
    """创建教师-班级-科目关联表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS teacher_class_subject (
            id VARCHAR(64) PRIMARY KEY,
            teacher_id VARCHAR(64) NOT NULL,
            class_id VARCHAR(64) NOT NULL,
            subject VARCHAR(50) NOT NULL,
            is_class_teacher BOOLEAN DEFAULT 0,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id),
            FOREIGN KEY (class_id) REFERENCES classes(class_id),
            UNIQUE (teacher_id, class_id, subject)
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_teacher_applications_table(engine):
    """创建教师入驻申请表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS teacher_applications (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(128) NOT NULL,
            phone VARCHAR(32) NOT NULL,
            school VARCHAR(200),
            subject VARCHAR(50),
            status VARCHAR(20) DEFAULT 'pending',
            reviewer_id VARCHAR(64),
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_operation_logs_table(engine):
    """创建操作日志表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(64),
            action VARCHAR(50) NOT NULL,
            target_type VARCHAR(50),
            target_id VARCHAR(64),
            detail JSON,
            ip_address VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def migrate_classes_table(engine):
    """迁移classes表：添加grade_id列"""
    with engine.connect() as conn:
        # 检查grade_id列是否存在
        result = conn.execute(text("PRAGMA table_info(classes)"))
        columns = [row[1] for row in result.fetchall()]

        if 'grade_id' not in columns:
            # SQLite不支持直接ADD FOREIGN KEY，需要分步
            # 1. 添加grade_id列
            conn.execute(text("ALTER TABLE classes ADD COLUMN grade_id VARCHAR(64)"))
            conn.commit()
            print("[OK] classes.grade_id column added")
        else:
            print("[OK] classes.grade_id column exists, skip")

        # 检查grade列是否需要保留（保留作为年级名称）
        if 'grade' not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN grade VARCHAR(32) DEFAULT '高一'"))
            conn.commit()
            print("[OK] classes.grade column added")
        else:
            print("[OK] classes.grade column exists, skip")


def migrate_classes_teacher_id(engine):
    """删除 `classes.teacher_id` 列（阶段 6.2）。幂等。

    那一列建表时被写死 `None`、从来没有数据，却让三处代码静默失效：
    班主任恒为 null、`panel` 的「教师管理的班级」恒空、`report` 的教师总览恒空。
    **班主任的唯一真源是 `teacher_class_subject.is_class_teacher`**（6.2 上半已改过去）。

    ⚠️ **不能直接 `ALTER TABLE ... DROP COLUMN`** —— 实测报
    `error in table classes after drop column: unknown column "teacher_id" in
    foreign key definition`：该列出现在 `classes` **自己的表级外键**里
    （`FOREIGN KEY(teacher_id) REFERENCES teachers(teacher_id)`），而 SQLite
    不允许删被表级 FK 引用的列，也没有 `DROP CONSTRAINT`。（`teachers.role` 能直接删，
    是因为它没有外键 —— 别照着那个先例想当然。）

    故走 SQLite 标准的**整表重建**：建新表 → 拷数据 → 删旧表 → 改名。

    两个必须用底层 DBAPI 连接的理由（踩过两次）：
      1. `PRAGMA foreign_keys` 是**逐连接**的 —— 用另一个连接设它，对这次重建无效
      2. 它**在事务里是空操作** —— 而 SQLAlchemy 一执行语句就 autobegin，
         所以 `conn.execute(text("PRAGMA foreign_keys=off")); conn.begin()` 那样写
         既设不上、还会报 "already initialized a Transaction"
    重建期间必须关外键：`students.class_id → classes.class_id` 有 66 行子记录，
    开着外键 `DROP TABLE classes` 会被隐式 DELETE 的外键检查拦下。
    """
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        columns = [r[1] for r in cur.execute("PRAGMA table_info(classes)").fetchall()]

        if 'teacher_id' not in columns:
            print("[OK] classes.teacher_id column already absent, skip")
            return

        keep = [c for c in columns if c != 'teacher_id']
        cols = ", ".join(keep)

        cur.execute("PRAGMA foreign_keys=off")
        cur.execute("BEGIN")
        try:
            cur.execute("""
                CREATE TABLE classes_new (
                    class_id VARCHAR(64) NOT NULL,
                    name VARCHAR(128) NOT NULL,
                    student_count INTEGER,
                    grade VARCHAR(32) NOT NULL,
                    subject VARCHAR(32),
                    grade_id VARCHAR(64),
                    created_at DATETIME,
                    updated_at DATETIME,
                    PRIMARY KEY (class_id),
                    FOREIGN KEY(grade_id) REFERENCES grades (grade_id)
                )
            """)
            cur.execute(f"INSERT INTO classes_new ({cols}) SELECT {cols} FROM classes")
            cur.execute("DROP TABLE classes")
            cur.execute("ALTER TABLE classes_new RENAME TO classes")

            broken = cur.execute("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"重建后外键校验失败: {broken}")
            raw.commit()
            print(f"[OK] classes.teacher_id column dropped（整表重建，保留 {len(keep)} 列）")
        except Exception:
            raw.rollback()
            raise
        cur.execute("PRAGMA foreign_keys=on")
    finally:
        raw.close()


def migrate_teachers_table(engine):
    """迁移teachers表：删除已弃用的 role 列（角色唯一真源是 accounts.role，见 ADR-0008）"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(teachers)"))
        columns = [row[1] for row in result.fetchall()]

        if 'role' in columns:
            conn.execute(text("ALTER TABLE teachers DROP COLUMN role"))
            conn.commit()
            print("[OK] teachers.role column dropped")
        else:
            print("[OK] teachers.role column already absent, skip")


def migrate_questions_difficulty_enum(engine):
    """questions.difficulty 旧版存整数 1-5（CONTEXT.md 旧约定），新模型是
    Enum(Difficulty) 按 NAME 存——把遗留整数值归一化为枚举名，否则 ORM 读即炸。"""
    mapping = {"1": "EASY", "2": "MEDIUM", "3": "MEDIUM", "4": "HARD", "5": "COMPETITION"}
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT difficulty FROM questions"))
        legacy = [str(r[0]) for r in result.fetchall()
                  if str(r[0]) in mapping]
        for v in legacy:
            conn.execute(text("UPDATE questions SET difficulty = :nv WHERE difficulty = :ov"),
                         {"nv": mapping[v], "ov": v})
        if legacy:
            conn.commit()
            print(f"[OK] questions.difficulty normalized from legacy ints: {legacy}")
        else:
            print("[OK] questions.difficulty already enum names, skip")


def migrate_loop_remediation(engine):
    """整改批次列：student_answers.confirmed（存量 True 保持历史成绩生效）、
    students.diagnosis_requested_at（诊断去抖）、student_answers.answer_key
    （落行时用的标准答案键，供待判定行扫描重判对齐；存量留空回退题库答案）。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(student_answers)"))
        cols = [row[1] for row in result.fetchall()]
        if 'confirmed' not in cols:
            conn.execute(text("ALTER TABLE student_answers ADD COLUMN confirmed BOOLEAN DEFAULT 1"))
            conn.commit()
            print("[OK] student_answers.confirmed added")
        else:
            print("[OK] student_answers.confirmed exists, skip")
        conn.execute(text("UPDATE student_answers SET confirmed = 1 WHERE confirmed IS NULL"))
        conn.commit()

        if 'answer_key' not in cols:
            conn.execute(text("ALTER TABLE student_answers ADD COLUMN answer_key VARCHAR(256)"))
            conn.commit()
            print("[OK] student_answers.answer_key added")
        else:
            print("[OK] student_answers.answer_key exists, skip")

        result = conn.execute(text("PRAGMA table_info(students)"))
        cols = [row[1] for row in result.fetchall()]
        if 'diagnosis_requested_at' not in cols:
            conn.execute(text("ALTER TABLE students ADD COLUMN diagnosis_requested_at DATETIME"))
            conn.commit()
            print("[OK] students.diagnosis_requested_at added")
        else:
            print("[OK] students.diagnosis_requested_at exists, skip")


def migrate_exam_records_status(engine):
    """迁移exam_records表：加 status/时间戳列并回填（P4 考试生命周期）。

    回填规则：考试 + question_stats 含 published:true → published；其余 → draft。
    练习/作业记录状态列置 draft（生命周期语义仅考试使用，统一非空便于查询）。
    """
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(exam_records)"))
        columns = [row[1] for row in result.fetchall()]

        for col in ("status", "published_at", "started_at", "grading_at",
                    "completed_at", "cancelled_at"):
            if col not in columns:
                conn.execute(text(f"ALTER TABLE exam_records ADD COLUMN {col} VARCHAR(32)"))
                conn.commit()
                print(f"[OK] exam_records.{col} column added")
            else:
                print(f"[OK] exam_records.{col} column exists, skip")

        result = conn.execute(text(
            "SELECT record_id, question_stats, type FROM exam_records WHERE status IS NULL"
        ))
        rows = result.fetchall()
        for record_id, stats, rtype in rows:
            stats_obj = None
            if isinstance(stats, str):
                import json as _json
                try:
                    stats_obj = _json.loads(stats)
                except (ValueError, TypeError):
                    stats_obj = None
            published = isinstance(stats_obj, dict) and stats_obj.get("published")
            # Enum 列按成员 NAME 存储校验（ORM 契约）——写小写会让 ORM 读取 LookupError
            target = "PUBLISHED" if (str(rtype).lower() == "exam" and published) else "DRAFT"
            conn.execute(text(
                "UPDATE exam_records SET status = :st WHERE record_id = :rid"),
                {"st": target, "rid": record_id})
        if rows:
            conn.commit()
        print(f"[OK] exam_records.status backfilled for {len(rows)} rows")


def create_student_notifications_table(engine):
    """创建学生站内通知表（P3 notification-dispatch；create_all 之外为存量库补建）"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS student_notifications (
            notification_id VARCHAR(64) PRIMARY KEY,
            student_id VARCHAR(64) NOT NULL,
            type VARCHAR(32) NOT NULL,
            title VARCHAR(256) NOT NULL,
            content TEXT,
            payload JSON,
            is_read BOOLEAN,
            read_at DATETIME,
            idempotency_key VARCHAR(128) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()
        print("[OK] student_notifications table ready")


def create_assignment_batches_table(engine):
    """创建练习分发布次表（P2 assignment-service；create_all 之外为存量库补建）"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS assignment_batches (
            batch_id VARCHAR(64) PRIMARY KEY,
            targets JSON NOT NULL,
            source JSON NOT NULL,
            name_hint VARCHAR(128),
            status VARCHAR(16),
            failed_targets JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()

        # 存量表补列（幂等可重跑）：旧库没有 status/failed_targets，批次无终态可查
        result = conn.execute(text("PRAGMA table_info(assignment_batches)"))
        columns = [row[1] for row in result.fetchall()]
        for col, ddl in (("status", "status VARCHAR(16)"),
                         ("failed_targets", "failed_targets JSON")):
            if col not in columns:
                conn.execute(text(f"ALTER TABLE assignment_batches ADD COLUMN {ddl}"))
                conn.commit()
                print(f"[OK] assignment_batches.{col} column added")
            else:
                print(f"[OK] assignment_batches.{col} column exists, skip")
        print("[OK] assignment_batches table ready")


def migrate_student_answers_source(engine):
    """迁移student_answers表：加 source / grade_reason 列并回填来源（判卷中心，ADR-0012）。

    回填规则：ocr_ 前缀 answer_id 来自答题卡批量管线 → ocr；其余按 online。
    """
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(student_answers)"))
        columns = [row[1] for row in result.fetchall()]

        if 'source' not in columns:
            conn.execute(text("ALTER TABLE student_answers ADD COLUMN source VARCHAR(32)"))
            conn.commit()
            print("[OK] student_answers.source column added")
        else:
            print("[OK] student_answers.source column exists, skip")

        if 'grade_reason' not in columns:
            conn.execute(text("ALTER TABLE student_answers ADD COLUMN grade_reason VARCHAR(256)"))
            conn.commit()
            print("[OK] student_answers.grade_reason column added")
        else:
            print("[OK] student_answers.grade_reason column exists, skip")

        result = conn.execute(text(
            "SELECT COUNT(*) FROM student_answers WHERE source IS NULL"
        ))
        null_count = result.scalar() or 0
        if null_count:
            # Enum 列按成员 NAME 存储校验（ORM 契约）——写小写 value 会让 ORM 读取 LookupError
            conn.execute(text(
                "UPDATE student_answers SET source = CASE "
                "WHEN answer_id LIKE 'ocr_%' THEN 'OCR' ELSE 'ONLINE' END "
                "WHERE source IS NULL"
            ))
            conn.commit()
            print(f"[OK] student_answers.source backfilled for {null_count} rows")
        else:
            print("[OK] student_answers.source already backfilled, skip")

        # 重跑修复：早期迁移写过小写 value，这些行 ORM 一读就崩，等值过滤也会静默漏掉
        result = conn.execute(text(
            "SELECT COUNT(*) FROM student_answers "
            "WHERE source IN ('online','ocr','manual','chat','training')"
        ))
        lower_count = result.scalar() or 0
        if lower_count:
            conn.execute(text(
                "UPDATE student_answers SET source = UPPER(source) "
                "WHERE source IN ('online','ocr','manual','chat','training')"
            ))
            conn.commit()
            print(f"[OK] student_answers.source normalized to enum NAME for {lower_count} rows")
        else:
            print("[OK] student_answers.source enum names, skip")


# 角色值中英统一（ADR-0008）：旧中文值 → 英文 snake_case
ROLE_RENAME = {
    '学科组长': 'subject_lead',
    '教务管理员': 'academic_admin',
}


def migrate_role_values(engine):
    """角色值迁移：中文 → 英文 snake_case。幂等——已是新值的库不受影响。

    只处理 accounts.role —— 它是角色唯一真源。teachers.role 已弃用并在
    migrate_teachers_table 中被删除，故不在此处迁移。
    """
    with engine.connect() as conn:
        total = 0
        for old, new in ROLE_RENAME.items():
            result = conn.execute(
                text("UPDATE accounts SET role = :new WHERE role = :old"),
                {"new": new, "old": old},
            )
            if result.rowcount:
                print(f"[OK] accounts.role: {old} -> {new} ({result.rowcount} 行)")
                total += result.rowcount
        conn.commit()
        print(f"[OK] 角色值迁移完成，共 {total} 行")


# ── 会话归属回填（阶段 4.6 批次 E）─────────────────────────────
# 存量老会话（归属表上线前的）在 checkpoint 数据里**没有任何身份线索** ——
# msgpack 里只有 messages / 路由信息，ChatRequest 的 student_id 没有落进图状态。
# 所以只能按「这个部署是谁在用」显式回填，不做任何猜测。
#
# 本部署的演示家庭是「家长 lgh(parent_demo_001) + 学生 202610201(李雨萱)」，
# 存量自助端会话只有这两个账号产生的。`t-*` 不回填 —— 员工角色本来就按前缀
# 认领老会话（见 app/middleware/conversation.py）。
LEGACY_CONVERSATION_OWNERS = {
    "p-": ("parent", "parent_demo_001"),   # lgh
    "m-": ("student", "202610201"),        # 李雨萱
}


def backfill_legacy_conversations(engine):
    """把存量老会话的归属**显式**回填给演示账号。幂等、可重跑。

    - 只处理本表里还没有归属记录的 thread（已有的不动，不会覆盖）
    - 账号不存在就整条跳过（换部署 / 清了演示数据时不会误认）
    - checkpoint 库不存在就跳过（还没跑过对话的环境）
    """
    import sqlite3

    from app.middleware.conversation import checkpoints_db_path
    from app.models.conversation_owner import ConversationOwner

    ConversationOwner.__table__.create(engine, checkfirst=True)

    db_path = checkpoints_db_path()
    if not os.path.exists(db_path):
        print("[SKIP] 会话归属回填：checkpoint 库不存在")
        return

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT thread_id FROM checkpoints").fetchall()
    finally:
        conn.close()
    thread_ids = [r[0] for r in rows if r[0]]

    with engine.connect() as db:
        existing = {
            r[0] for r in db.execute(
                text("SELECT thread_id FROM conversation_owners")
            ).fetchall()
        }
        total = 0
        for prefix, (role, user_id) in LEGACY_CONVERSATION_OWNERS.items():
            account = db.execute(
                text("SELECT 1 FROM accounts WHERE role = :role AND "
                     "COALESCE(parent_id, student_id) = :uid AND status = 'active'"),
                {"role": role, "uid": user_id},
            ).fetchone()
            if not account:
                print(f"[SKIP] {prefix}* 回填：账号 {user_id}({role}) 不存在")
                continue
            targets = [
                t for t in thread_ids
                if t.startswith(prefix) and t not in existing
            ]
            for t in targets:
                db.execute(
                    text("INSERT INTO conversation_owners (thread_id, user_id, role, created_at) "
                         "VALUES (:t, :u, :r, :c)"),
                    {"t": t, "u": user_id, "r": role, "c": datetime.utcnow()},
                )
            db.commit()
            total += len(targets)
            print(f"[OK] {prefix}* -> {user_id}({role})：回填 {len(targets)} 条")
        print(f"[OK] 会话归属回填完成，共 {total} 条")


if __name__ == "__main__":
    migrate()
