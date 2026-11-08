"""pytest fixtures for ChemAI tests."""
# test_smart_parse.py 是脚本式冒烟测试（依赖 OCR/MinerU 服务），模块顶层直接
# 执行 async 调用，pytest 收集会报错。从 pytest 收集中排除，保留为手动脚本。
collect_ignore = ["test_smart_parse.py"]
import sys, os, pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base
from app.models.ocr_task import OCRTask  # ensure table in metadata


@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite database, created fresh per test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_student(db_session):
    """Create a sample student in the test DB."""
    from app.models.database import Student
    s = Student(
        student_id="202610101", name="test_student", class_id="class_2025_1",
        status="approved",
        barrier_type={"concept": 0.3, "reading": 0.4, "expression": 0.3},
    )
    db_session.add(s)
    db_session.commit()
    return s


@pytest.fixture
def sample_teacher(db_session):
    """Create a sample teacher account."""
    from app.models.database import Account
    from app.utils.init_db import hash_password
    a = Account(
        account_id="acc_test_teacher",
        username="test_teacher",
        password_hash=hash_password("123456"),
        role="teacher",
        teacher_id="teacher_test",
        status="active",
    )
    db_session.add(a)
    db_session.commit()
    return a
