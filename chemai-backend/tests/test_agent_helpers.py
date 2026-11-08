"""Agent 层纯辅助测试：MemoryStack 分层记忆 + conversation 渠道抽取辅助函数。

MemoryStack 的 load_student 在函数内部 import get_db，测试 patch app.models.database.get_db。
conversation 的 _extract_messages / _extract_msg_role_content 处理 dict 与 LangChain 对象。
"""
from agent.memory import MemoryStack
from agent.channel.conversation import (
    _extract_msg_role_content, _extract_messages, new_conversation,
)


# ── MemoryStack：工作记忆 / 情景记忆 / 画像 ──

def test_add_turn_and_build_context_ordering():
    ms = MemoryStack()
    ms.student_profile = {"student_id": "s1", "name": "张浩宇"}
    ms.add_episode("diag", {"barrier": "concept"})
    ms.add_turn("human", "你好")
    ms.add_turn("ai", "你好！有什么化学问题？")

    ctx = ms.build_context("今天的题")
    roles = [m["role"] for m in ctx]
    # 画像 + 情景记忆在前，然后历史，最后当前输入
    assert roles == ["system", "system", "human", "ai", "user"]
    assert ctx[0]["content"].startswith("当前学生:")
    assert ctx[1]["content"].startswith("历史关键事件:")
    assert ctx[-1] == {"role": "user", "content": "今天的题"}


def test_build_context_no_profile():
    ms = MemoryStack()
    ctx = ms.build_context("hi")
    assert ctx == [{"role": "user", "content": "hi"}]


def test_working_memory_sliding_window():
    ms = MemoryStack(max_working=20)
    for i in range(25):
        ms.add_turn("human", f"第{i}轮")
    assert len(ms.working) == 20
    # 最旧的 5 条被丢弃，保留第 5..24 轮
    assert ms.working[0] == {"role": "human", "content": "第5轮"}
    assert ms.working[-1] == {"role": "human", "content": "第24轮"}


def test_clear_working():
    ms = MemoryStack()
    ms.add_turn("human", "x")
    ms.add_episode("k", {"v": 1})
    ms.clear_working()
    assert len(ms.working) == 0
    assert ms.episodic == {"k": {"v": 1}}  # 情景记忆保留


def test_add_episode_overwrites_same_key():
    ms = MemoryStack()
    ms.add_episode("k", {"v": 1})
    ms.add_episode("k", {"v": 2})
    assert ms.episodic == {"k": {"v": 2}}


def test_get_summary():
    ms = MemoryStack()
    ms.add_turn("human", "x")
    ms.add_turn("ai", "y")
    ms.add_episode("diag", {})
    ms.student_profile = {"student_id": "s1", "name": "李世睿"}
    s = ms.get_summary()
    assert '"turns": 2' in s
    assert '"diag"' in s
    assert "李世睿" in s


# ── to_dict / from_dict ──

def test_roundtrip_preserves_all():
    ms = MemoryStack(max_working=10)
    ms.add_turn("human", "q")
    ms.add_episode("e1", {"x": 1})
    ms.student_profile = {"student_id": "s1", "name": "王"}

    restored = MemoryStack.from_dict(ms.to_dict(), max_working=10)
    assert list(restored.working) == list(ms.working)
    assert restored.episodic == ms.episodic
    assert restored.student_profile == ms.student_profile


# ── load_student ──

class _FakeRow:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, i):
        return self._values[i]


class _FakeSession:
    def __init__(self, row):
        self._row = row
        self.closed = False

    def execute(self, *a, **k):
        return self

    def fetchone(self):
        return self._row

    def close(self):
        self.closed = True


def test_load_student_found(monkeypatch):
    row = _FakeRow(["张浩宇", '["概念薄弱"]', 12])
    sess = _FakeSession(row)
    monkeypatch.setattr("app.models.database.get_db", lambda: iter([sess]))

    ms = MemoryStack()
    ms.load_student("s1")
    assert ms.student_profile["student_id"] == "s1"
    assert ms.student_profile["name"] == "张浩宇"
    assert ms.student_profile["barrier"] == ["概念薄弱"]
    assert ms.student_profile["exercises_completed"] == 12
    assert sess.closed is True


def test_load_student_not_found(monkeypatch):
    sess = _FakeSession(None)
    monkeypatch.setattr("app.models.database.get_db", lambda: iter([sess]))

    ms = MemoryStack()
    ms.load_student("ghost")
    assert ms.student_profile == {"student_id": "ghost", "name": "未知"}


def test_load_student_exception_falls_back(monkeypatch):
    def boom():
        raise RuntimeError("db down")
        yield

    monkeypatch.setattr("app.models.database.get_db", boom)
    ms = MemoryStack()
    ms.load_student("s1")
    assert ms.student_profile == {"student_id": "s1", "name": "未知"}


# ── conversation 抽取辅助 ──

def test_extract_msg_role_content_dict():
    assert _extract_msg_role_content({"role": "human", "content": "hi"}) == ("human", "hi")
    # 缺 content → 空串
    assert _extract_msg_role_content({"role": "ai"}) == ("ai", "")
    # dict 风格用 type 兜底
    assert _extract_msg_role_content({"type": "ai", "content": "ok"}) == ("ai", "ok")


def test_extract_msg_role_content_langchain_object():
    class M:
        type = "human"
        content = "你好"

    assert _extract_msg_role_content(M()) == ("human", "你好")


def test_extract_messages_from_messages_channel():
    ckpt = {"channel_values": {"messages": [{"role": "human", "content": "a"}]}}
    assert _extract_messages(ckpt) == [{"role": "human", "content": "a"}]


def test_extract_messages_start_channel_fallback():
    ckpt = {"channel_values": {"__start__": {"messages": [{"role": "ai", "content": "b"}]}}}
    assert _extract_messages(ckpt) == [{"role": "ai", "content": "b"}]


def test_extract_messages_empty_and_invalid():
    assert _extract_messages({}) == []
    assert _extract_messages({"channel_values": {}}) == []
    assert _extract_messages(None) == []
    assert _extract_messages([]) == []
    assert _extract_messages({"channel_values": []}) == []


# ── new_conversation ──

import asyncio


def _new_conv(db, prefix=None, user=None):
    """直接调端点函数（不经 FastAPI）—— db / current_user 要自己传。

    阶段 4.6 批次 E 起 new_conversation 会登记会话归属，所以这两个依赖
    不再是可省略的默认参数。
    """
    user = user or {"user_id": "T1", "role": "teacher"}
    kwargs = {"db": db, "current_user": user}
    if prefix is not None:
        kwargs["prefix"] = prefix
    return asyncio.run(new_conversation(**kwargs))


def test_new_conversation_default_prefix(db_session):
    r = _new_conv(db_session)
    tid = r["thread_id"]
    assert tid.startswith("m-")
    assert tid.split("-", 1)[1].isdigit()


def test_new_conversation_custom_prefix(db_session):
    for prefix in ("t-", "p-", "c-"):
        r = _new_conv(db_session, prefix)
        assert r["thread_id"].startswith(prefix)
        assert r["thread_id"].split("-", 1)[1].isdigit()


def test_new_conversation_unique(db_session):
    import time
    a = _new_conv(db_session)["thread_id"]
    time.sleep(0.005)  # thread_id 基于毫秒时间戳，避免同毫秒碰撞
    b = _new_conv(db_session)["thread_id"]
    assert a != b
