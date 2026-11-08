"""记忆追加幂等测试：同一事件 ID 重复投递只记录一次。

对应 spec「记忆追加去重」——practice_history / barrier_history 追加前按事件 ID 去重。
测试打在「作业调度边界」的处理器面（MemoryHandler 的事件方法），不测队列/线程。
"""
from pathlib import Path

import chem_skills.chemistry_memory.handler as mem_mod


def _isolate_memory_dirs(monkeypatch, tmp_path):
    """把模块级记忆目录重定向到临时目录，避免污染真实 memory_data/。"""
    students = tmp_path / "students"
    sessions = tmp_path / "sessions"
    students.mkdir(parents=True, exist_ok=True)
    sessions.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mem_mod, "STUDENTS_DIR", students)
    monkeypatch.setattr(mem_mod, "SESSIONS_DIR", sessions)


def test_exam_completed_is_idempotent(monkeypatch, tmp_path):
    """同一场考试完成事件投递两次，practice_history 只记录一次。"""
    _isolate_memory_dirs(monkeypatch, tmp_path)
    handler = mem_mod.MemoryHandler()

    handler.memory_on_exam_completed("s1", "exam_1", 85.5, 17, 20)
    handler.memory_on_exam_completed("s1", "exam_1", 85.5, 17, 20)

    content = mem_mod.MemoryStorage.read_memory("student", "s1", "practice_history")
    assert content is not None
    assert content.count("**考试ID**: exam_1") == 1


def test_practice_completed_is_idempotent(monkeypatch, tmp_path):
    """同一练习完成事件投递两次，practice_history 只记录一次。"""
    _isolate_memory_dirs(monkeypatch, tmp_path)
    handler = mem_mod.MemoryHandler()

    handler.memory_on_practice_completed("s1", "practice_1", 90.0, 18, 20)
    handler.memory_on_practice_completed("s1", "practice_1", 90.0, 18, 20)

    content = mem_mod.MemoryStorage.read_memory("student", "s1", "practice_history")
    assert content is not None
    assert content.count("**练习ID**: practice_1") == 1


def test_diagnosis_completed_is_idempotent(monkeypatch, tmp_path):
    """同一诊断事件（event_id）投递两次，barrier_history 只记录一次。"""
    _isolate_memory_dirs(monkeypatch, tmp_path)
    handler = mem_mod.MemoryHandler()
    barrier = {"concept": 0.3, "reading": 0.5, "expression": 0.2}

    handler.memory_on_diagnosis_completed("s1", barrier, "reading", ["盐类水解", "电离"], event_id="exam_1")
    handler.memory_on_diagnosis_completed("s1", barrier, "reading", ["盐类水解", "电离"], event_id="exam_1")

    content = mem_mod.MemoryStorage.read_memory("student", "s1", "barrier_history")
    assert content is not None
    assert content.count("诊断记录 exam_1") == 1
