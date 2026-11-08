"""
MemoryStack — 分层对话记忆
- working: 最近 N 轮对话（滑动窗口）
- episodic: 关键事件（诊断结果、考试记录）
- student_profile: 学生画像
"""
import json
from collections import deque


class MemoryStack:
    def __init__(self, max_working: int = 20):
        self.working = deque(maxlen=max_working)
        self.episodic: dict = {}
        self.student_profile: dict = {}
        self._max_working = max_working

    def add_turn(self, role: str, content: str):
        """添加一轮对话"""
        self.working.append({"role": role, "content": content})

    def add_episode(self, key: str, data: dict):
        """记录关键事件"""
        self.episodic[key] = data

    def load_student(self, student_id: str):
        """从数据库加载学生画像"""
        try:
            import sys
            import os

            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from app.models.database import get_db
            from sqlalchemy import text

            session = next(get_db())
            row = session.execute(
                text(
                    "SELECT name, barrier_type, exercises_completed FROM students WHERE student_id = :sid"
                ),
                {"sid": student_id},
            ).fetchone()
            session.close()

            if row:
                self.student_profile = {
                    "student_id": student_id,
                    "name": row[0],
                    "barrier": json.loads(row[1]) if isinstance(row[1], str) else row[1],
                    "exercises_completed": row[2],
                }
            else:
                self.student_profile = {"student_id": student_id, "name": "未知"}
        except Exception:
            self.student_profile = {"student_id": student_id, "name": "未知"}

    def build_context(self, user_input: str) -> list[dict]:
        """构建发送给 LLM 的完整消息列表"""
        messages = []

        # 学生画像
        if self.student_profile:
            profile_text = f"当前学生: {json.dumps(self.student_profile, ensure_ascii=False)}"
            messages.append({"role": "system", "content": profile_text})

        # 情景记忆
        if self.episodic:
            ep_text = f"历史关键事件: {json.dumps(self.episodic, ensure_ascii=False)}"
            messages.append({"role": "system", "content": ep_text})

        # 工作记忆（对话历史）
        for turn in self.working:
            messages.append(turn)

        # 当前输入
        messages.append({"role": "user", "content": user_input})

        return messages

    def clear_working(self):
        """清空工作记忆（新对话）"""
        self.working.clear()

    def get_summary(self) -> str:
        """获取记忆摘要"""
        return json.dumps(
            {
                "turns": len(self.working),
                "episodes": list(self.episodic.keys()),
                "profile": self.student_profile.get("name", "未知"),
            },
            ensure_ascii=False,
        )

    def to_dict(self) -> dict:
        """序列化为可持久化字典"""
        return {
            "working": list(self.working),
            "episodic": self.episodic,
            "student_profile": self.student_profile,
        }

    @classmethod
    def from_dict(cls, data: dict, max_working: int = 20) -> "MemoryStack":
        """从字典恢复记忆"""
        stack = cls(max_working=max_working)
        for turn in data.get("working", []):
            stack.working.append(turn)
        stack.episodic = data.get("episodic", {})
        stack.student_profile = data.get("student_profile", {})
        return stack
