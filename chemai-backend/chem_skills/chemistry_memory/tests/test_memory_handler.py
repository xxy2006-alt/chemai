"""
chemistry-memory Skill Tests
测试学情记忆系统
"""
import sys
import os
from pathlib import Path
import tempfile
import shutil

# 添加项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest

from chem_skills.chemistry_memory import handler as memory_handler_module
from chem_skills.chemistry_memory.handler import (
    MemoryHandler,
    MemoryStorage,
    STUDENTS_DIR,
    CLASSES_DIR,
    TEACHERS_DIR,
    SESSIONS_DIR,
)


class TestMemoryStorage:
    """测试记忆存储"""

    @pytest.fixture(autouse=True)
    def _isolated_memory_dirs(self, monkeypatch, tmp_path):
        """把模块目录常量指到临时目录：测试不读写仓库共享的 memory_data/"""
        self.test_root = tmp_path
        # 目录常量统一指到同一隔离根之下，与 get_stats 的 MEMORY_ROOT.rglob 一致
        memory_root = tmp_path / "memory_data"
        self.students_dir = memory_root / "students"
        self.classes_dir = memory_root / "classes"
        self.teachers_dir = memory_root / "teachers"
        self.sessions_dir = memory_root / "sessions"
        for d in (self.students_dir, self.classes_dir, self.teachers_dir, self.sessions_dir):
            d.mkdir(parents=True)

        monkeypatch.setattr(memory_handler_module, "MEMORY_ROOT", memory_root)
        monkeypatch.setattr(memory_handler_module, "STUDENTS_DIR", self.students_dir)
        monkeypatch.setattr(memory_handler_module, "CLASSES_DIR", self.classes_dir)
        monkeypatch.setattr(memory_handler_module, "TEACHERS_DIR", self.teachers_dir)
        monkeypatch.setattr(memory_handler_module, "SESSIONS_DIR", self.sessions_dir)

    def test_write_and_read_student_memory(self):
        """测试写入和读取学生记忆"""
        student_id = "test_001"
        memory_type = "profile"
        content = "# Test Profile\n\nTest content"

        result = MemoryStorage.write_memory(
            "student", student_id, memory_type, content
        )
        assert result["success"] is True

        read_content = MemoryStorage.read_memory("student", student_id, memory_type)
        assert read_content == content

    def test_write_and_read_class_memory(self):
        """测试写入和读取班级记忆"""
        class_id = "class_001"
        memory_type = "summary"
        content = "# Class Summary\n\nTest summary"

        result = MemoryStorage.write_memory("class", class_id, memory_type, content)
        assert result["success"] is True

        read_content = MemoryStorage.read_memory("class", class_id, memory_type)
        assert read_content == content

    def test_write_and_read_teacher_memory(self):
        """测试写入和读取教师记忆"""
        teacher_id = "teacher_001"
        memory_type = "config"
        content = "# Teacher Config\n\nTest config"

        result = MemoryStorage.write_memory("teacher", teacher_id, memory_type, content)
        assert result["success"] is True

        read_content = MemoryStorage.read_memory("teacher", teacher_id, memory_type)
        assert read_content == content

    def test_append_mode(self):
        """测试追加模式"""
        student_id = "test_002"
        memory_type = "barrier_history"

        MemoryStorage.write_memory("student", student_id, memory_type, "First entry")
        MemoryStorage.write_memory(
            "student", student_id, memory_type, "Second entry", append=True
        )

        content = MemoryStorage.read_memory("student", student_id, memory_type)
        assert "First entry" in content
        assert "Second entry" in content

    def test_get_stats(self):
        """测试统计功能"""
        MemoryStorage.write_memory("student", "s1", "profile", "Content 1")
        MemoryStorage.write_memory("student", "s2", "profile", "Content 2")
        MemoryStorage.write_memory("class", "c1", "summary", "Summary 1")
        MemoryStorage.write_memory("teacher", "t1", "config", "Config 1")

        stats = MemoryStorage.get_stats()
        assert stats["total_students"] == 2
        assert stats["total_classes"] == 1
        assert stats["total_teachers"] == 1


class TestMemoryHandler:
    """测试记忆处理器"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        self.test_root = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """每个测试后清理"""
        shutil.rmtree(self.test_root, ignore_errors=True)

    def test_memory_student_get(self):
        """测试获取学生记忆"""
        handler = MemoryHandler()
        result = handler.memory_student_get("nonexistent", "profile")
        assert result["student_id"] == "nonexistent"
        assert result["memory_type"] == "profile"

    def test_memory_student_update(self):
        """测试更新学生记忆"""
        handler = MemoryHandler()
        result = handler.memory_student_update(
            "student_test", "profile", "# Test Profile"
        )
        assert result["success"] is True

    def test_memory_on_exam_completed(self):
        """测试考试完成事件"""
        handler = MemoryHandler()
        result = handler.memory_on_exam_completed(
            "student_001", "exam_001", 85.5, 17, 20
        )
        assert result["success"] is True
        assert result["event"] == "exam_completed"
        assert result["student_id"] == "student_001"

    def test_memory_on_diagnosis_completed(self):
        """测试诊断完成事件"""
        handler = MemoryHandler()
        result = handler.memory_on_diagnosis_completed(
            "student_001",
            {"concept": 0.3, "reading": 0.5, "expression": 0.2},
            "reading",
            ["盐类水解", "电离"],
        )
        assert result["success"] is True
        assert result["event"] == "diagnosis_completed"
        assert result["student_id"] == "student_001"

    def test_memory_on_practice_completed(self):
        """测试练习完成事件"""
        handler = MemoryHandler()
        result = handler.memory_on_practice_completed(
            "student_001", "practice_001", 90.0, 18, 20
        )
        assert result["success"] is True
        assert result["event"] == "practice_completed"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
