"""
chemistry-memory Skill Handler
ChemAI 学情历史记忆管理系统
"""
import sys
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills._templates.base_handler import BaseSkillHandler  # noqa: E402

# 记忆存储根目录
MEMORY_ROOT = Path(__file__).parent / "memory_data"
STUDENTS_DIR = MEMORY_ROOT / "students"
CLASSES_DIR = MEMORY_ROOT / "classes"
TEACHERS_DIR = MEMORY_ROOT / "teachers"
SESSIONS_DIR = MEMORY_ROOT / "sessions"

# 确保目录存在
MEMORY_ROOT.mkdir(exist_ok=True)
STUDENTS_DIR.mkdir(exist_ok=True)
CLASSES_DIR.mkdir(exist_ok=True)
TEACHERS_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("chemistry-memory")


class MemoryStorage:
    """记忆存储管理器"""

    @staticmethod
    def _get_student_dir(student_id: str) -> Path:
        """获取学生记忆目录"""
        student_dir = STUDENTS_DIR / student_id
        student_dir.mkdir(exist_ok=True)
        return student_dir

    @staticmethod
    def _get_class_dir(class_id: str) -> Path:
        """获取班级记忆目录"""
        class_dir = CLASSES_DIR / class_id
        class_dir.mkdir(exist_ok=True)
        return class_dir

    @staticmethod
    def _get_teacher_dir(teacher_id: str) -> Path:
        """获取教师记忆目录"""
        teacher_dir = TEACHERS_DIR / teacher_id
        teacher_dir.mkdir(exist_ok=True)
        return teacher_dir

    @staticmethod
    def read_memory(entity_type: str, entity_id: str, memory_type: str) -> Optional[str]:
        """读取记忆内容"""
        try:
            if entity_type == "student":
                dir_path = MemoryStorage._get_student_dir(entity_id)
            elif entity_type == "class":
                dir_path = MemoryStorage._get_class_dir(entity_id)
            elif entity_type == "teacher":
                dir_path = MemoryStorage._get_teacher_dir(entity_id)
            else:
                return None

            file_path = dir_path / f"{memory_type}.md"
            if file_path.exists():
                return file_path.read_text(encoding="utf-8")
            return None
        except Exception as e:
            logger.error(f"读取记忆失败: {e}")
            return None

    @staticmethod
    def write_memory(
        entity_type: str, entity_id: str, memory_type: str, content: str, append: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """写入记忆内容。

        append=True 且提供 idempotency_key 时，若该键已存在于现有内容中则跳过追加（幂等），
        避免同一事件重复投递记两条。
        """
        try:
            if entity_type == "student":
                dir_path = MemoryStorage._get_student_dir(entity_id)
            elif entity_type == "class":
                dir_path = MemoryStorage._get_class_dir(entity_id)
            elif entity_type == "teacher":
                dir_path = MemoryStorage._get_teacher_dir(entity_id)
            else:
                return {"success": False, "error": "未知实体类型"}

            file_path = dir_path / f"{memory_type}.md"

            if append and file_path.exists():
                existing_content = file_path.read_text(encoding="utf-8")
                if idempotency_key is not None and idempotency_key in existing_content:
                    return {
                        "success": True,
                        "skipped": True,
                        "reason": "idempotent_duplicate",
                        "updated_at": datetime.now().isoformat(),
                    }
                content = existing_content + "\n" + content

            file_path.write_text(content, encoding="utf-8")

            # 更新 FTS 索引
            MemoryStorage._update_fts_index(entity_type, entity_id, memory_type, content)

            return {"success": True, "updated_at": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"写入记忆失败: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _update_fts_index(entity_type: str, entity_id: str, memory_type: str, content: str) -> None:
        """更新 FTS 索引"""
        try:
            db_path = SESSIONS_DIR / "search.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # 创建 FTS 表（如果不存在）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_fts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT,
                    entity_id TEXT,
                    memory_type TEXT,
                    content TEXT,
                    updated_at TEXT,
                    UNIQUE(entity_type, entity_id, memory_type)
                )
            """
            )

            # 使用 FTS5 虚拟表
            cursor.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts_content USING fts5(
                    entity_type, entity_id, memory_type, content,
                    content='memory_fts',
                    content_rowid='id'
                )
            """
            )

            # 插入或替换
            cursor.execute(
                """
                INSERT OR REPLACE INTO memory_fts (entity_type, entity_id, memory_type, content, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (entity_type, entity_id, memory_type, content, datetime.now().isoformat()),
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"更新FTS索引失败: {e}")

    @staticmethod
    def search_memory(
        query: str, search_type: str = "all", student_id: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索记忆"""
        try:
            db_path = SESSIONS_DIR / "search.db"
            if not db_path.exists():
                return []

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            sql = """
                SELECT entity_type, entity_id, memory_type, content, updated_at
                FROM memory_fts
                WHERE content LIKE ?
            """
            params = [f"%{query}%"]

            if search_type != "all":
                sql += " AND entity_type = ?"
                params.append(search_type.rstrip("s"))  # student -> studen

            if student_id:
                sql += " AND entity_id = ?"
                params.append(student_id)

            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                results.append(
                    {
                        "entity_type": row[0],
                        "entity_id": row[1],
                        "memory_type": row[2],
                        "snippet": row[3][:200] + "..." if len(row[3]) > 200 else row[3],
                        "updated_at": row[4],
                    }
                )

            return results
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """获取记忆统计"""
        try:
            total_students = len(list(STUDENTS_DIR.glob("*")))
            total_classes = len(list(CLASSES_DIR.glob("*")))
            total_teachers = len(list(TEACHERS_DIR.glob("*")))

            # 计算存储大小
            total_size = 0
            for path in MEMORY_ROOT.rglob("*"):
                if path.is_file():
                    total_size += path.stat().st_size

            # 最新和最早的记录（以 float mtime 追踪最值，循环外再转 ISO——
            # 首轮赋 ISO 字符串会导致第二轮 float<str 比较抛 TypeError）
            newest_mtime = None
            oldest_mtime = None
            for path in MEMORY_ROOT.rglob("*.md"):
                mtime = path.stat().st_mtime
                if oldest_mtime is None or mtime < oldest_mtime:
                    oldest_mtime = mtime
                if newest_mtime is None or mtime > newest_mtime:
                    newest_mtime = mtime

            oldest = datetime.fromtimestamp(oldest_mtime).isoformat() if oldest_mtime is not None else None
            newest = datetime.fromtimestamp(newest_mtime).isoformat() if newest_mtime is not None else None

            return {
                "total_students": total_students,
                "total_classes": total_classes,
                "total_teachers": total_teachers,
                "storage_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_memory": oldest,
                "newest_memory": newest,
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"error": str(e)}


class MemoryHandler(BaseSkillHandler):
    """chemistry-memory Skill Handler"""

    # ===== 学生记忆 =====

    def memory_student_get(self, student_id: str, memory_type: str = "all") -> Dict[str, Any]:
        """获取学生的学情记忆"""
        if memory_type == "all":
            # 返回所有类型的记忆
            memory_types = ["profile", "barrier_history", "weak_kps", "practice_history", "preferences"]
            result = {"student_id": student_id, "memories": {}}
            for mtype in memory_types:
                content = MemoryStorage.read_memory("student", student_id, mtype)
                if content:
                    result["memories"][mtype] = content
            return result
        else:
            content = MemoryStorage.read_memory("student", student_id, memory_type)
            return {"student_id": student_id, "memory_type": memory_type, "content": content}

    def memory_student_update(
        self, student_id: str, memory_type: str, content: str, append: bool = False
    ) -> Dict[str, Any]:
        """更新学生的学情记忆"""
        return MemoryStorage.write_memory("student", student_id, memory_type, content, append)

    # ===== 班级记忆 =====

    def memory_class_get(self, class_id: str, memory_type: str = "all") -> Dict[str, Any]:
        """获取班级的学情记忆"""
        if memory_type == "all":
            memory_types = ["summary", "common_barriers", "trends"]
            result = {"class_id": class_id, "memories": {}}
            for mtype in memory_types:
                content = MemoryStorage.read_memory("class", class_id, mtype)
                if content:
                    result["memories"][mtype] = content
            return result
        else:
            content = MemoryStorage.read_memory("class", class_id, memory_type)
            return {"class_id": class_id, "memory_type": memory_type, "content": content}

    def memory_class_update(
        self, class_id: str, memory_type: str, content: str, append: bool = False
    ) -> Dict[str, Any]:
        """更新班级的学情记忆"""
        return MemoryStorage.write_memory("class", class_id, memory_type, content, append)

    # ===== 教师记忆 =====

    def memory_teacher_get(self, teacher_id: str, memory_type: str = "all") -> Dict[str, Any]:
        """获取教师的个性化配置"""
        if memory_type == "all":
            memory_types = ["config", "teaching_style"]
            result = {"teacher_id": teacher_id, "memories": {}}
            for mtype in memory_types:
                content = MemoryStorage.read_memory("teacher", teacher_id, mtype)
                if content:
                    result["memories"][mtype] = content
            return result
        else:
            content = MemoryStorage.read_memory("teacher", teacher_id, memory_type)
            return {"teacher_id": teacher_id, "memory_type": memory_type, "content": content}

    def memory_teacher_update(self, teacher_id: str, memory_type: str, content: str) -> Dict[str, Any]:
        """更新教师的个性化配置"""
        return MemoryStorage.write_memory("teacher", teacher_id, memory_type, content, False)

    # ===== 搜索 =====

    def memory_search(
        self, query: str, search_type: str = "all", student_id: Optional[str] = None, limit: int = 10
    ) -> Dict[str, Any]:
        """跨会话搜索学情历史"""
        results = MemoryStorage.search_memory(query, search_type, student_id, limit)
        return {"query": query, "results": results, "count": len(results)}

    # ===== LLM 摘要 =====

    def memory_summarize(self, student_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """对学生的历史数据进行 LLM 摘要"""
        # 读取所有记忆
        profile = MemoryStorage.read_memory("student", student_id, "profile")
        barrier_history = MemoryStorage.read_memory("student", student_id, "barrier_history")
        weak_kps = MemoryStorage.read_memory("student", student_id, "weak_kps")
        practice_history = MemoryStorage.read_memory("student", student_id, "practice_history")

        # 检查是否需要刷新
        if not force_refresh and profile:
            # 提取最后更新时间
            if "最后更新时间" in profile:
                return {"success": True, "student_id": student_id, "message": "画像未过期"}

        # 生成新摘要
        summary = self._generate_profile_summary(
            student_id, barrier_history, weak_kps, practice_history
        )

        # 更新画像
        MemoryStorage.write_memory("student", student_id, "profile", summary)

        return {"success": True, "student_id": student_id, "summary_generated": summary}

    def _generate_profile_summary(
        self, student_id: str, barrier_history: Optional[str], weak_kps: Optional[str], practice_history: Optional[str]
    ) -> str:
        """生成学生画像摘要"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        summary = f"""# 学生画像: {student_id}

## 学习概况
- 障碍类型: 待诊断
- 整体掌握度: 待评估
- 最近活跃: {now}

## 历史诊断记录
{barrier_history or "暂无诊断记录"}

## 薄弱知识点
{weak_kps or "暂无薄弱知识点记录"}

## 练习历史
{practice_history or "暂无练习记录"}

## 最近更新时间
{now}
"""
        return summary

    # ===== 统计 =====

    def memory_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计"""
        return MemoryStorage.get_stats()

    # ===== 事件触发 =====

    def memory_on_exam_completed(
        self, student_id: str, exam_record_id: str, score: float, correct_count: int, total_count: int
    ) -> Dict[str, Any]:
        """考试完成事件"""
        now = datetime.now().strftime("%Y-%m-%d")
        entry = f"""
### {now} - 考试 {exam_record_id}
- **得分率**: {score}%
- **正确率**: {correct_count}/{total_count}
- **考试ID**: {exam_record_id}
"""

        MemoryStorage.write_memory(
            "student", student_id, "practice_history", entry, append=True,
            idempotency_key=f"考试 {exam_record_id}\n",
        )

        return {"success": True, "event": "exam_completed", "student_id": student_id}

    def memory_on_diagnosis_completed(
        self, student_id: str, barrier_type: Dict[str, float], dominant_barrier: str, weak_kps: List[str],
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """诊断完成事件（event_id 用于幂等去重，避免同一诊断重复记入 barrier_history）。"""
        now = datetime.now().strftime("%Y-%m-%d")

        # 更新障碍历史
        barrier_entry = f"""
### {now} - 诊断记录{f" {event_id}" if event_id else ""}
- **障碍类型**: {dominant_barrier}
- **障碍占比**: 概念 {barrier_type.get('concept', 0) * 100:.0f}% | 审题 {barrier_type.get('reading', 0) * 100:.0f}% | 表述 {barrier_type.get('expression', 0) * 100:.0f}%
- **薄弱知识点**: {', '.join(weak_kps)}
"""
        MemoryStorage.write_memory(
            "student", student_id, "barrier_history", barrier_entry, append=True,
            idempotency_key=(f"诊断记录 {event_id}\n" if event_id else None),
        )

        # 更新薄弱知识点
        kp_entry = "# 薄弱知识点追踪\n\n## 当前薄弱知识点\n"
        for i, kp in enumerate(weak_kps, 1):
            kp_entry += f"{i}. **{kp}** - 待跟踪\n"
        kp_entry += f"\n最后更新: {now}\n"
        MemoryStorage.write_memory("student", student_id, "weak_kps", kp_entry)

        return {"success": True, "event": "diagnosis_completed", "student_id": student_id}

    def memory_on_practice_completed(
        self, student_id: str, practice_id: str, score: float, completed_count: int, total_count: int
    ) -> Dict[str, Any]:
        """练习完成事件"""
        now = datetime.now().strftime("%Y-%m-%d")
        entry = f"""
### {now} - 练习 {practice_id}
- **得分率**: {score}%
- **完成率**: {completed_count}/{total_count}
- **练习ID**: {practice_id}
"""
        MemoryStorage.write_memory(
            "student", student_id, "practice_history", entry, append=True,
            idempotency_key=f"练习 {practice_id}\n",
        )

        return {"success": True, "event": "practice_completed", "student_id": student_id}


# ==================== Tool 入口函数 ====================


def memory_student_get(student_id: str, memory_type: str = "all") -> Dict:
    """Tool: 获取学生的学情记忆"""
    handler = MemoryHandler()
    return handler.memory_student_get(student_id, memory_type)


def memory_student_update(student_id: str, memory_type: str, content: str, append: bool = False) -> Dict:
    """Tool: 更新学生的学情记忆"""
    handler = MemoryHandler()
    return handler.memory_student_update(student_id, memory_type, content, append)


def memory_class_get(class_id: str, memory_type: str = "all") -> Dict:
    """Tool: 获取班级的学情记忆"""
    handler = MemoryHandler()
    return handler.memory_class_get(class_id, memory_type)


def memory_class_update(class_id: str, memory_type: str, content: str, append: bool = False) -> Dict:
    """Tool: 更新班级的学情记忆"""
    handler = MemoryHandler()
    return handler.memory_class_update(class_id, memory_type, content, append)


def memory_teacher_get(teacher_id: str, memory_type: str = "all") -> Dict:
    """Tool: 获取教师的个性化配置"""
    handler = MemoryHandler()
    return handler.memory_teacher_get(teacher_id, memory_type)


def memory_teacher_update(teacher_id: str, memory_type: str, content: str) -> Dict:
    """Tool: 更新教师的个性化配置"""
    handler = MemoryHandler()
    return handler.memory_teacher_update(teacher_id, memory_type, content)


def memory_search(query: str, search_type: str = "all", student_id: Optional[str] = None, limit: int = 10) -> Dict:
    """Tool: 跨会话搜索学情历史"""
    handler = MemoryHandler()
    return handler.memory_search(query, search_type, student_id, limit)


def memory_summarize(student_id: str, force_refresh: bool = False) -> Dict:
    """Tool: 对学生的历史数据进行 LLM 摘要"""
    handler = MemoryHandler()
    return handler.memory_summarize(student_id, force_refresh)


def memory_stats() -> Dict:
    """Tool: 获取记忆系统的统计信息"""
    handler = MemoryHandler()
    return handler.memory_stats()


def memory_on_exam_completed(
    student_id: str, exam_record_id: str, score: float, correct_count: int, total_count: int
) -> Dict:
    """Tool: 考试完成事件"""
    handler = MemoryHandler()
    return handler.memory_on_exam_completed(student_id, exam_record_id, score, correct_count, total_count)


def memory_on_diagnosis_completed(
    student_id: str, barrier_type: Dict[str, float], dominant_barrier: str, weak_kps: List[str],
    event_id: Optional[str] = None,
) -> Dict:
    """Tool: 诊断完成事件"""
    handler = MemoryHandler()
    return handler.memory_on_diagnosis_completed(student_id, barrier_type, dominant_barrier, weak_kps, event_id)


def memory_on_practice_completed(
    student_id: str, practice_id: str, score: float, completed_count: int, total_count: int
) -> Dict:
    """Tool: 练习完成事件"""
    handler = MemoryHandler()
    return handler.memory_on_practice_completed(student_id, practice_id, score, completed_count, total_count)


# ==================== 主入口 ====================

if __name__ == "__main__":

    def test():
        handler = MemoryHandler()

        # 测试统计
        stats = handler.memory_stats()
        print(f"记忆统计: {stats}")

        # 测试写入学生记忆
        result = handler.memory_student_update(
            "test_student_001",
            "profile",
            "# 学生画像: test_student_001\n\n测试内容",
        )
        print(f"写入记忆: {result}")

        # 测试读取学生记忆
        result = handler.memory_student_get("test_student_001", "profile")
        print(f"读取记忆: {result}")

        # 测试考试完成事件
        result = handler.memory_on_exam_completed("test_student_001", "exam_001", 85.5, 17, 20)
        print(f"考试完成事件: {result}")

        # 测试诊断完成事件
        result = handler.memory_on_diagnosis_completed(
            "test_student_001", {"concept": 0.3, "reading": 0.5, "expression": 0.2}, "reading", ["盐类水解", "电离"]
        )
        print(f"诊断完成事件: {result}")

    test()
