"""
chemistry-notification Skill Tests
测试消息通知网关
"""
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills.chemistry_notification.handler import (
    NotificationHandler,
    DiscordGateway,
    SlackGateway,
    TelegramGateway,
    EmailGateway,
    NotificationTemplates,
)


class TestNotificationTemplates:
    """测试通知模板"""

    def test_format_assignment_discord(self):
        """测试作业通知 Discord 格式"""
        data = {
            "class_name": "高三一班",
            "exam_name": "化学反应速率练习",
            "knowledge_points": ["反应速率计算", "碰撞理论"],
            "question_count": 10,
            "deadline": "2026-04-20",
        }
        result = NotificationTemplates.format_assignment("discord", data)
        assert "高三一班" in result["description"]
        assert result["title"] == "📝 新作业布置"

    def test_format_assignment_telegram(self):
        """测试作业通知 Telegram 格式"""
        data = {
            "class_name": "高三一班",
            "exam_name": "化学反应速率练习",
            "knowledge_points": ["反应速率计算", "碰撞理论"],
            "question_count": 10,
            "deadline": "2026-04-20",
        }
        result = NotificationTemplates.format_assignment("telegram", data)
        assert "高三一班" in result
        assert "化学反应速率练习" in result

    def test_format_error_report_email(self):
        """测试错题报告 Email 格式"""
        data = {
            "student_name": "张三",
            "exam_name": "期中考试",
            "score": 72.5,
            "class_avg": 78.0,
            "weak_kps": [{"name": "盐类水解", "count": 3}, {"name": "电离", "count": 2}],
        }
        result = NotificationTemplates.format_error_report("email", data)
        assert "张三" in result["html"]
        assert "72.5" in result["html"]

    def test_format_score_alert_email(self):
        """测试成绩预警 Email 格式"""
        data = {
            "student_name": "李四",
            "exam_name": "月考",
            "score": 55.0,
            "threshold": 60.0,
        }
        result = NotificationTemplates.format_score_alert("email", data)
        assert "李四" in result["html"]
        assert "55" in result["html"]
        assert "⚠️" in result["html"] or "alert" in result["html"].lower()

    def test_format_encouragement_telegram(self):
        """测试鼓励消息 Telegram 格式"""
        data = {
            "student_name": "王五",
            "message": "今天的计算题做得很好，继续保持！",
        }
        result = NotificationTemplates.format_encouragement("telegram", data)
        assert "王五" in result
        assert "计算题" in result


class TestDiscordGateway:
    """测试 Discord 网关"""

    def test_format_embed(self):
        """测试 Discord embed 格式化"""
        content = "Test message"
        embed = {
            "title": "Test Title",
            "description": "Test description",
            "color": 5814783,
        }
        formatted = DiscordGateway.format_message(content, embed)
        assert formatted["content"] == content
        assert formatted["embeds"][0]["title"] == "Test Title"


class TestSlackGateway:
    """测试 Slack 网关"""

    def test_format_blocks(self):
        """测试 Slack blocks 格式化"""
        content = "Test message"
        blocks = SlackGateway.format_message(content)
        assert isinstance(blocks, list)
        assert any("Test message" in str(b) for b in blocks)


class TestTelegramGateway:
    """测试 Telegram 网关"""

    def test_format_markdown(self):
        """测试 Telegram Markdown 格式化"""
        text = "Test message"
        formatted = TelegramGateway.format_message(text)
        assert "Test message" in formatted


class TestEmailGateway:
    """测试 Email 网关"""

    def test_format_html(self):
        """测试 Email HTML 格式化"""
        subject = "Test Subject"
        body = "Test body content"
        html = EmailGateway.format_email(subject, body)
        assert "Test Subject" in html
        assert "Test body content" in html


class TestNotificationHandler:
    """测试通知处理器"""

    def test_init(self):
        """测试处理器初始化"""
        handler = NotificationHandler()
        assert handler is not None

    def test_send_assignment_discord(self):
        """测试发送作业通知到 Discord"""
        handler = NotificationHandler()
        data = {
            "class_id": "class_001",
            "class_name": "高三一班",
            "exam_name": "测试作业",
            "knowledge_points": ["原子结构"],
            "question_count": 5,
            "deadline": "2026-04-20",
            "channel": "discord",
        }
        # 测试格式化和验证（不实际发送）
        formatted = NotificationTemplates.format_assignment("discord", data)
        assert formatted["title"] == "📝 新作业布置"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
