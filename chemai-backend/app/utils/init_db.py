"""
数据库初始化工具

上线初始化的范围：学校、年级、教师与教务账号。
学生与成绩数据经「历史数据导入」入口进入（app/services/data_import.py），
本模块不直接灌入任何学生或考试数据。
"""
import hashlib
from datetime import datetime

from app.models.database import (
    init_db, get_db, Account, Teacher,
    School, Grade,
)

SCHOOL_ID = "school_cs_001"
SCHOOL_NAME = "长沙市某中学"


def hash_password(password: str) -> str:
    """哈希密码（SHA256）"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_school(db):
    """创建学校（已存在则跳过）"""
    school = db.query(School).filter(School.school_id == SCHOOL_ID).first()
    if school:
        print(f"学校已存在: {school.name}")
        return school

    school = School(
        school_id=SCHOOL_ID,
        name=SCHOOL_NAME,
        region="湖南省长沙市",
        current_term=_current_term(),
        subjects=["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"],
    )
    db.add(school)
    db.commit()
    print(f"已创建学校: {school.name}")
    return school


def _current_grade_year() -> int:
    """当前高三年级入学年份：9 月及以后，当年入学的年级为高一"""
    today = datetime.utcnow()
    offset = 2 if today.month >= 9 else 3
    return today.year - offset


def _current_term() -> str:
    today = datetime.utcnow()
    start = today.year if today.month >= 9 else today.year - 1
    term = "第一学期" if today.month >= 9 or today.month == 1 else "第二学期"
    return f"{start}-{start + 1}学年 {term}"


def create_grade(db, school):
    """创建当前高三年级（动态对齐当前学年）"""
    year = _current_grade_year()
    grade_id = f"grade_{year}_高三"
    grade = db.query(Grade).filter(Grade.grade_id == grade_id).first()
    if grade:
        print(f"年级已存在: {grade.name}")
        return grade
    grade = Grade(
        grade_id=grade_id,
        school_id=school.school_id,
        name="高三",
        year=year,
        status=1,
    )
    db.add(grade)
    db.commit()
    print(f"已创建年级: {grade.name}（{year}级）")
    return grade


def create_teachers(db, school):
    """创建教师与教务账号（已存在则跳过）"""
    teachers_data = [
        {"teacher_id": "admin_001", "name": "系统管理员", "phone": None},
        {"teacher_id": "teacher_zhou", "name": "周老师", "phone": None},  # 化学学科组长
        {"teacher_id": "teacher_qian", "name": "钱老师", "phone": None},
        {"teacher_id": "teacher_wu", "name": "吴老师", "phone": None},
        {"teacher_id": "teacher_zheng", "name": "郑老师", "phone": None},
    ]
    for t_data in teachers_data:
        teacher = db.query(Teacher).filter(Teacher.teacher_id == t_data["teacher_id"]).first()
        if teacher:
            print(f"教师已存在: {teacher.name}")
            continue
        db.add(Teacher(
            teacher_id=t_data["teacher_id"],
            school_id=school.school_id,
            name=t_data["name"],
            phone=t_data["phone"],
            status="approved",
        ))
        db.commit()
        print(f"已创建教师: {t_data['name']}")

    accounts_data = [
        # 平台超管（ADR-0011）：**不挂 school_id、不挂 teachers 记录** ——
        # 它不是「某所学校的管理员」，是跨校的平台角色。默认数据范围为空，
        # 跨校排查要走 /api/break-glass 的限时提权。
        # （合并说明：这条是 main 侧加的，造数脚本重写时保住）
        {"account_id": "acc_super", "username": "superadmin", "password": "super123456",
         "role": "super_admin", "teacher_id": None},
        {"account_id": "acc_admin", "username": "admin", "password": "admin123",
         "role": "admin", "teacher_id": "admin_001"},
        {"account_id": "acc_zhou", "username": "zhou", "password": "zhou123456",
         "role": "subject_lead", "teacher_id": "teacher_zhou"},
        {"account_id": "acc_qian", "username": "qian", "password": "qian123456",
         "role": "teacher", "teacher_id": "teacher_qian"},
        {"account_id": "acc_wu", "username": "wu", "password": "wu123456",
         "role": "teacher", "teacher_id": "teacher_wu"},
        {"account_id": "acc_zheng", "username": "zheng", "password": "zheng123456",
         "role": "teacher", "teacher_id": "teacher_zheng"},
    ]
    for a_data in accounts_data:
        account = db.query(Account).filter(Account.username == a_data["username"]).first()
        if account:
            print(f"账号已存在: {account.username} ({account.role})")
            continue
        db.add(Account(
            account_id=a_data["account_id"],
            username=a_data["username"],
            password_hash=hash_password(a_data["password"]),
            role=a_data["role"],
            teacher_id=a_data["teacher_id"],
            status="active",
        ))
        db.commit()
        print(f"已创建账号: {a_data['username']} ({a_data['role']})")


def init_database():
    """初始化数据库：学校 / 年级 / 教师 / 教务账号

    学生、班级名册、历次成绩经导入入口进入：
      POST /api/import/roster
      POST /api/import/teaching-assignments
      POST /api/import/exam
    """
    print("=" * 60)
    print(f"ChemAI 数据库初始化 - {SCHOOL_NAME}")
    print("=" * 60)

    print("\n1. 初始化数据库表...")
    init_db()

    db = next(get_db())
    try:
        print("\n2. 创建学校...")
        school = create_school(db)

        print("\n3. 创建年级...")
        create_grade(db, school)

        print("\n4. 创建教师与账号...")
        create_teachers(db, school)

        print("\n" + "=" * 60)
        print("数据库初始化完成（学生与成绩请经数据导入入口进入）")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"\n初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
