"""
chemistry-notification Skill Handler
ChemAI 消息通知网关 - 支持 Discord/Slack/Telegram/Email
"""
import sys
import os
import smtplib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
import logging

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills._templates.base_handler import BaseSkillHandler  # noqa: E402

logger = logging.getLogger("chemistry-notification")

# 配置存储路径
CONFIG_DIR = Path(__file__).parent / "configs"


@dataclass
class NotificationResult:
    """通知发送结果"""
    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class DiscordGateway:
    """Discord 消息网关"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    def send(self, content: str, embed: Dict = None) -> NotificationResult:
        """发送 Discord 消息"""
        if not self.webhook_url:
            return NotificationResult(success=False, channel="discord", error="Discord webhook 未配置")

        try:
            import requests

            payload = {"content": content}
            if embed:
                payload["embeds"] = [embed]

            response = requests.post(self.webhook_url, json=payload, timeout=30)
            if response.status_code in [200, 204]:
                return NotificationResult(success=True, channel="discord", message_id=response.text)
            else:
                return NotificationResult(success=False, channel="discord", error=f"发送失败: {response.status_code}")
        except Exception as e:
            return NotificationResult(success=False, channel="discord", error=str(e))

    @staticmethod
    def format_message(content: str, embed: Dict = None) -> Dict:
        """格式化 Discord 消息（不发送）"""
        return {"content": content, "embeds": [embed] if embed else []}


class SlackGateway:
    """Slack 消息网关"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    def send(self, blocks: List[Dict]) -> NotificationResult:
        """发送 Slack 消息"""
        if not self.webhook_url:
            return NotificationResult(success=False, channel="slack", error="Slack webhook 未配置")

        try:
            import requests

            payload = {"blocks": blocks}
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            if response.status_code in [200, 204]:
                return NotificationResult(success=True, channel="slack", message_id=response.text)
            else:
                return NotificationResult(success=False, channel="slack", error=f"发送失败: {response.status_code}")
        except Exception as e:
            return NotificationResult(success=False, channel="slack", error=str(e))

    @staticmethod
    def format_message(content: str) -> List[Dict]:
        """格式化 Slack 消息为 blocks（不发送）"""
        return [{"type": "section", "text": {"type": "mrkdwn", "text": content}}]


class TelegramGateway:
    """Telegram 消息网关"""

    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    def send(self, chat_id: str, text: str, parse_mode: str = "Markdown") -> NotificationResult:
        """发送 Telegram 消息"""
        if not self.api_url:
            return NotificationResult(success=False, channel="telegram", error="Telegram bot token 未配置")

        try:
            import requests

            payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
            response = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=30)
            result = response.json()

            if result.get("ok"):
                return NotificationResult(
                    success=True, channel="telegram", message_id=str(result["result"]["message_id"])
                )
            else:
                return NotificationResult(success=False, channel="telegram", error=result.get("description"))
        except Exception as e:
            return NotificationResult(success=False, channel="telegram", error=str(e))

    @staticmethod
    def format_message(text: str) -> str:
        """格式化 Telegram Markdown 文本（不发送）"""
        return text


class EmailGateway:
    """Email 消息网关"""

    def __init__(self, smtp_host: str = None, smtp_port: int = 587, username: str = None, password: str = None):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.username = username or os.getenv("SMTP_USERNAME")
        self.password = password or os.getenv("SMTP_PASSWORD")

    def send(self, to_email: str, subject: str, body: str, html: bool = False) -> NotificationResult:
        """发送 Email"""
        if not all([self.smtp_host, self.username, self.password]):
            return NotificationResult(success=False, channel="email", error="Email 配置不完整")

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.username
            msg["To"] = to_email

            if html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.username, [to_email], msg.as_string())

            return NotificationResult(success=True, channel="email", message_id=to_email)
        except Exception as e:
            return NotificationResult(success=False, channel="email", error=str(e))

    @staticmethod
    def format_email(subject: str, body: str) -> str:
        """格式化邮件为 HTML（不发送）"""
        return (
            f"<html><head><title>{subject}</title></head>"
            f"<body><h3>{subject}</h3><p>{body}</p></body></html>"
        )


class NotificationTemplates:
    """通知模板"""

    @staticmethod
    def assignment_discord(class_name: str, exam_name: str, knowledge_points: List[str], question_count: int, deadline: str, practice_link: str = None) -> Dict:
        """作业通知 - Discord"""
        kp_text = ", ".join(knowledge_points[:3])
        if len(knowledge_points) > 3:
            kp_text += f" 等{len(knowledge_points)}个"

        embed = {
            "title": "📝 新作业布置",
            "description": f"**班级**: {class_name}\n**作业**: {exam_name}",
            "fields": [
                {"name": "知识点", "value": kp_text, "inline": True},
                {"name": "题量", "value": f"{question_count} 道", "inline": True},
                {"name": "截止", "value": deadline, "inline": True},
            ],
            "color": 5814783,  # 绿色
        }

        if practice_link:
            embed["url"] = practice_link

        return {"content": "📝 **新作业布置**", "embed": embed}

    @staticmethod
    def assignment_slack(class_name: str, exam_name: str, knowledge_points: List[str], question_count: int, deadline: str) -> List[Dict]:
        """作业通知 - Slack"""
        kp_text = ", ".join(knowledge_points[:3])
        return [
            {"type": "header", "text": {"type": "plain_text", "text": "📝 新作业布置", "emoji": True}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"**班级**: {class_name}"},
                {"type": "mrkdwn", "text": f"**作业**: {exam_name}"},
                {"type": "mrkdwn", "text": f"**知识点**: {kp_text}"},
                {"type": "mrkdwn", "text": f"**题量**: {question_count} 道"},
                {"type": "mrkdwn", "text": f"**截止**: {deadline}"},
            ]},
        ]

    @staticmethod
    def assignment_telegram(class_name: str, exam_name: str, knowledge_points: List[str], question_count: int, deadline: str, practice_link: str = None) -> str:
        """作业通知 - Telegram"""
        kp_text = ", ".join(knowledge_points[:3])
        if len(knowledge_points) > 3:
            kp_text += f" 等{len(knowledge_points)}个"

        text = (
            f"📝 新作业布置\n\n"
            f"班级: {class_name}\n"
            f"作业: {exam_name}\n"
            f"知识点: {kp_text}\n"
            f"题量: {question_count} 道\n"
            f"截止: {deadline}"
        )

        if practice_link:
            text += f"\n\n{practice_link}"

        return text

    @staticmethod
    def error_report_telegram(student_name: str, exam_name: str, score: float, class_avg: float, weak_kps: List[Dict], report_link: str = None) -> str:
        """错题报告 - Telegram"""
        kp_text = "\n".join([f"  {i+1}. {kp['name']} (错误{kp['count']}次)" for i, kp in enumerate(weak_kps[:5])])

        text = f"""📋 **{student_name}** 错题报告

考试: {exam_name}
得分率: {score}%
班级平均: {class_avg}%

薄弱知识点:
{kp_text}"""

        if report_link:
            text += f"\n\n[查看完整报告]({report_link})"

        return text

    @staticmethod
    def error_report_email(student_name: str, exam_name: str, score: float, class_avg: float, weak_kps: List[Dict], report_link: str = None) -> Dict:
        """错题报告 - Email"""
        kp_html = "<br>".join([f"{i+1}. {kp['name']} (错误{kp['count']}次)" for i, kp in enumerate(weak_kps[:5])])

        subject = f"{student_name} - {exam_name} 错题报告"
        body = f"""
家长您好，

{student_name} 的 {exam_name} 错题报告已生成。

得分率: {score}%
班级平均: {class_avg}%

薄弱知识点:
{kp_html}

查看完整报告: {report_link or '请登录系统查看'}

ChemAI 智能教学助手
"""
        html = (
            f"<html><head><title>{subject}</title></head>"
            f"<body><h3>{student_name} - {exam_name} 错题报告</h3>"
            f"<p>得分率: {score}%（班级平均: {class_avg}%）</p>"
            f"<p>薄弱知识点:</p><p>{kp_html}</p>"
            f"</body></html>"
        )
        return {"subject": subject, "body": body, "html": html}

    @staticmethod
    def learning_plan_telegram(student_name: str, barrier_type: str, weak_kps: List[str], plan_period: str, daily_tasks: List[str], plan_link: str = None) -> str:
        """学习计划 - Telegram"""
        kp_text = ", ".join(weak_kps[:3])
        tasks_text = "\n".join([f"  Day {i+1}: {task}" for i, task in enumerate(daily_tasks[:7])])

        text = f"""📖 **{student_name}** 个性化学习计划

周期: {plan_period}
主要障碍: {barrier_type}
薄弱知识点: {kp_text}

每日学习任务:
{tasks_text}"""

        if plan_link:
            text += f"\n\n[查看完整计划]({plan_link})"

        return text

    @staticmethod
    def encouragement_telegram(student_name: str, message: str) -> str:
        """鼓励消息 - Telegram"""
        return f"🌟 {student_name}，你有一条新的鼓励：\n\n{message}"

    @staticmethod
    def score_alert_email(student_name: str, exam_name: str, score: float, threshold: float, parent_email: str = None) -> Dict:
        """成绩预警 - Email"""
        subject = f"【成绩预警】{student_name} - {exam_name}"
        body = f"""
家长您好，

{student_name} 在最近的{exam_name}中得分率为{score}%，低于预警阈值{threshold}%。

建议：
1. 与孩子沟通了解原因
2. 及时查看错题报告，分析问题所在
3. 配合学习计划进行针对性练习

ChemAI 智能教学助手
"""
        html = (
            f"<html><head><title>{subject}</title></head>"
            f"<body><h3>⚠️ {subject}</h3>"
            f"<p>{student_name} 在最近的{exam_name}中得分率为{score}%，低于预警阈值{threshold}%。</p>"
            f"</body></html>"
        )
        return {"subject": subject, "body": body, "to": parent_email, "html": html}

    # ===== 统一分发入口（按平台路由到具体模板；平台不支持该类型时抛 ValueError）=====

    @staticmethod
    def format_assignment(platform: str, data: Dict) -> Any:
        """作业通知统一分发：platform ∈ {discord, slack, telegram}"""
        if platform == "discord":
            payload = NotificationTemplates.assignment_discord(
                class_name=data["class_name"], exam_name=data["exam_name"],
                knowledge_points=data["knowledge_points"], question_count=data["question_count"],
                deadline=data["deadline"], practice_link=data.get("practice_link"),
            )
            embed = payload["embed"]
            result = {
                "title": embed["title"],
                "description": embed["description"],
                "fields": embed.get("fields", []),
            }
            if "url" in embed:
                result["url"] = embed["url"]
            return result
        if platform == "telegram":
            return NotificationTemplates.assignment_telegram(
                class_name=data["class_name"], exam_name=data["exam_name"],
                knowledge_points=data["knowledge_points"], question_count=data["question_count"],
                deadline=data["deadline"], practice_link=data.get("practice_link"),
            )
        if platform == "slack":
            return NotificationTemplates.assignment_slack(
                class_name=data["class_name"], exam_name=data["exam_name"],
                knowledge_points=data["knowledge_points"], question_count=data["question_count"],
                deadline=data["deadline"],
            )
        raise ValueError(f"平台 {platform} 不支持作业通知")

    @staticmethod
    def format_error_report(platform: str, data: Dict) -> Any:
        """错题报告统一分发：platform ∈ {email, telegram}"""
        if platform == "email":
            return NotificationTemplates.error_report_email(
                student_name=data["student_name"], exam_name=data["exam_name"],
                score=data["score"], class_avg=data["class_avg"],
                weak_kps=data["weak_kps"], report_link=data.get("report_link"),
            )
        if platform == "telegram":
            return NotificationTemplates.error_report_telegram(
                student_name=data["student_name"], exam_name=data["exam_name"],
                score=data["score"], class_avg=data["class_avg"],
                weak_kps=data["weak_kps"], report_link=data.get("report_link"),
            )
        raise ValueError(f"平台 {platform} 不支持错题报告")

    @staticmethod
    def format_score_alert(platform: str, data: Dict) -> Any:
        """成绩预警统一分发：platform ∈ {email}"""
        if platform == "email":
            return NotificationTemplates.score_alert_email(
                student_name=data["student_name"], exam_name=data["exam_name"],
                score=data["score"], threshold=data["threshold"],
                parent_email=data.get("parent_email"),
            )
        raise ValueError(f"平台 {platform} 不支持成绩预警")

    @staticmethod
    def format_encouragement(platform: str, data: Dict) -> Any:
        """鼓励消息统一分发：platform ∈ {telegram}"""
        if platform == "telegram":
            return NotificationTemplates.encouragement_telegram(
                student_name=data["student_name"], message=data["message"],
            )
        raise ValueError(f"平台 {platform} 不支持鼓励消息")


class NotificationHandler(BaseSkillHandler):
    """chemistry-notification Skill Handler"""

    def __init__(self):
        super().__init__()
        self.templates = NotificationTemplates()
        self._load_configs()

    def _load_configs(self):
        """加载配置"""
        CONFIG_DIR.mkdir(exist_ok=True)
        self.config_path = CONFIG_DIR / "gateways.json"
        if self.config_path.exists():
            try:
                self.configs = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                self.configs = {}
        else:
            self.configs = {}

    def _save_config(self):
        """保存配置"""
        self.config_path.write_text(json.dumps(self.configs, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_gateway_config(self, teacher_id: str) -> Dict:
        """获取教师的网关配置"""
        return self.configs.get(teacher_id, {})

    # ===== 作业通知 =====

    def notify_assignment(
        self,
        class_id: str,
        class_name: str,
        exam_name: str,
        knowledge_points: List[str],
        question_count: int,
        deadline: str,
        channel: str = "all",
        practice_link: str = None,
    ) -> Dict[str, Any]:
        """发送作业布置通知"""
        results = []

        if channel in ["discord", "all"]:
            gateway = DiscordGateway()
            template = self.templates.assignment_discord(class_name, exam_name, knowledge_points, question_count, deadline, practice_link)
            result = gateway.send(template["content"], template.get("embed"))
            results.append({"channel": "discord", **result.__dict__})

        if channel in ["slack", "all"]:
            gateway = SlackGateway()
            template = self.templates.assignment_slack(class_name, exam_name, knowledge_points, question_count, deadline)
            result = gateway.send(template)
            results.append({"channel": "slack", **result.__dict__})

        return {"success": any(r["success"] for r in results), "results": results}

    # ===== 错题报告 =====

    def notify_error_report(
        self,
        student_id: str,
        student_name: str,
        exam_name: str,
        score: float,
        class_avg: float,
        weak_kps: List[Dict],
        channel: str = "telegram",
        report_link: str = None,
        parent_telegram_id: str = None,
        parent_email: str = None,
    ) -> Dict[str, Any]:
        """发送错题报告通知"""
        results = []

        if channel in ["telegram", "all"] and parent_telegram_id:
            gateway = TelegramGateway()
            text = self.templates.error_report_telegram(student_name, exam_name, score, class_avg, weak_kps, report_link)
            result = gateway.send(parent_telegram_id, text)
            results.append({"channel": "telegram", **result.__dict__})

        if channel in ["email", "all"] and parent_email:
            gateway = EmailGateway()
            template = self.templates.error_report_email(student_name, exam_name, score, class_avg, weak_kps, report_link)
            result = gateway.send(parent_email, template["subject"], template["body"])
            results.append({"channel": "email", **result.__dict__})

        return {"success": any(r["success"] for r in results), "results": results}

    # ===== 学习计划 =====

    def notify_learning_plan(
        self,
        student_id: str,
        student_name: str,
        barrier_type: str,
        weak_kps: List[str],
        plan_period: str,
        daily_tasks: List[str],
        channel: str = "telegram",
        plan_link: str = None,
        student_telegram_id: str = None,
        parent_telegram_id: str = None,
        parent_email: str = None,
    ) -> Dict[str, Any]:
        """发送学习计划通知"""
        results = []

        if channel in ["telegram", "all"]:
            for tg_id in [student_telegram_id, parent_telegram_id]:
                if tg_id:
                    gateway = TelegramGateway()
                    text = self.templates.learning_plan_telegram(student_name, barrier_type, weak_kps, plan_period, daily_tasks, plan_link)
                    result = gateway.send(tg_id, text)
                    results.append({"channel": "telegram", "recipient": tg_id, **result.__dict__})

        if channel in ["email", "all"] and parent_email:
            gateway = EmailGateway()
            subject = f"📖 {student_name} 个性化学习计划"
            body = f"""
学生姓名: {student_name}
计划周期: {plan_period}
主要障碍: {barrier_type}
薄弱知识点: {', '.join(weak_kps)}

每日学习任务:
{chr(10).join([f'Day {i+1}: {task}' for i, task in enumerate(daily_tasks)])}

查看完整计划: {plan_link or '请登录系统查看'}

ChemAI 智能教学助手
"""
            result = gateway.send(parent_email, subject, body)
            results.append({"channel": "email", **result.__dict__})

        return {"success": any(r["success"] for r in results), "results": results}

    # ===== 成绩预警 =====

    def notify_score_alert(
        self,
        student_id: str,
        student_name: str,
        exam_name: str,
        score: float,
        threshold: float,
        channel: str = "email",
        parent_email: str = None,
        parent_telegram_id: str = None,
    ) -> Dict[str, Any]:
        """发送成绩预警通知"""
        results = []

        if channel in ["email", "all"] and parent_email:
            gateway = EmailGateway()
            template = self.templates.score_alert_email(student_name, exam_name, score, threshold)
            result = gateway.send(parent_email, template["subject"], template["body"])
            results.append({"channel": "email", **result.__dict__})

        if channel in ["telegram", "all"] and parent_telegram_id:
            gateway = TelegramGateway()
            text = f"🚨 **{student_name}成绩预警**\n\n{exam_name}得分率{score}%，低于预警阈值{threshold}%\n\n请关注孩子的学习情况。"
            result = gateway.send(parent_telegram_id, text)
            results.append({"channel": "telegram", **result.__dict__})

        return {"success": any(r["success"] for r in results), "results": results}

    # ===== 班级通知 =====

    def notify_class(
        self, class_id: str, class_name: str, message: str, channel: str = "discord", urgent: bool = False
    ) -> Dict[str, Any]:
        """发送班级通知"""
        results = []

        if channel in ["discord", "all"]:
            gateway = DiscordGateway()
            content = f"🚨 **{class_name} 通知**\n\n{message}" if urgent else f"📢 **{class_name} 通知**\n\n{message}"
            result = gateway.send(content)
            results.append({"channel": "discord", **result.__dict__})

        if channel in ["slack", "all"]:
            gateway = SlackGateway()
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": f"📢 {class_name} 通知", "emoji": True}},
                {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            ]
            result = gateway.send(blocks)
            results.append({"channel": "slack", **result.__dict__})

        return {"success": any(r["success"] for r in results), "results": results}

    # ===== 日常鼓励 =====

    def notify_encouragement(
        self, student_id: str, student_name: str, message: str, channel: str = "telegram", telegram_id: str = None
    ) -> Dict[str, Any]:
        """发送日常鼓励消息"""
        results = []

        if channel in ["telegram", "discord"] and telegram_id:
            gateway = TelegramGateway()
            text = f"💪 **{student_name}**，加油！\n\n{message}"
            result = gateway.send(telegram_id, text)
            results.append({"channel": "telegram", **result.__dict__})

        return {"success": any(r["success"] for r in results), "results": results}

    # ===== 配置管理 =====

    def notify_config_get(self, teacher_id: str) -> Dict[str, Any]:
        """获取通知渠道配置"""
        config = self._get_gateway_config(teacher_id)
        # 隐藏敏感信息
        safe_config = {
            "teacher_id": teacher_id,
            "discord_configured": bool(config.get("discord_webhook")),
            "slack_configured": bool(config.get("slack_webhook")),
            "telegram_configured": bool(config.get("telegram_bot_token")),
            "email_configured": bool(config.get("email_smtp_host")),
        }
        return safe_config

    def notify_config_update(
        self,
        teacher_id: str,
        discord_webhook: str = None,
        slack_webhook: str = None,
        telegram_bot_token: str = None,
        email_smtp_host: str = None,
        email_smtp_port: int = None,
        email_username: str = None,
        email_password: str = None,
        email_from: str = None,
    ) -> Dict[str, Any]:
        """更新通知渠道配置"""
        if teacher_id not in self.configs:
            self.configs[teacher_id] = {}

        if discord_webhook:
            self.configs[teacher_id]["discord_webhook"] = discord_webhook
        if slack_webhook:
            self.configs[teacher_id]["slack_webhook"] = slack_webhook
        if telegram_bot_token:
            self.configs[teacher_id]["telegram_bot_token"] = telegram_bot_token
        if email_smtp_host:
            self.configs[teacher_id]["email_smtp_host"] = email_smtp_host
        if email_smtp_port:
            self.configs[teacher_id]["email_smtp_port"] = email_smtp_port
        if email_username:
            self.configs[teacher_id]["email_username"] = email_username
        if email_password:
            self.configs[teacher_id]["email_password"] = email_password
        if email_from:
            self.configs[teacher_id]["email_from"] = email_from

        self._save_config()

        return {"success": True, "teacher_id": teacher_id, "message": "配置已更新"}


# ==================== Tool 入口函数 ====================


def notify_assignment(
    class_id: str,
    class_name: str,
    exam_name: str,
    knowledge_points: List[str],
    question_count: int,
    deadline: str,
    channel: str = "all",
    practice_link: str = None,
) -> Dict:
    """Tool: 发送作业布置通知"""
    handler = NotificationHandler()
    return handler.notify_assignment(class_id, class_name, exam_name, knowledge_points, question_count, deadline, channel, practice_link)


def notify_error_report(
    student_id: str,
    student_name: str,
    exam_name: str,
    score: float,
    class_avg: float,
    weak_kps: List[Dict],
    channel: str = "telegram",
    report_link: str = None,
    parent_telegram_id: str = None,
    parent_email: str = None,
) -> Dict:
    """Tool: 发送错题报告通知"""
    handler = NotificationHandler()
    return handler.notify_error_report(student_id, student_name, exam_name, score, class_avg, weak_kps, channel, report_link, parent_telegram_id, parent_email)


def notify_learning_plan(
    student_id: str,
    student_name: str,
    barrier_type: str,
    weak_kps: List[str],
    plan_period: str,
    daily_tasks: List[str],
    channel: str = "telegram",
    plan_link: str = None,
    student_telegram_id: str = None,
    parent_telegram_id: str = None,
    parent_email: str = None,
) -> Dict:
    """Tool: 发送学习计划通知"""
    handler = NotificationHandler()
    return handler.notify_learning_plan(student_id, student_name, barrier_type, weak_kps, plan_period, daily_tasks, channel, plan_link, student_telegram_id, parent_telegram_id, parent_email)


def notify_score_alert(
    student_id: str,
    student_name: str,
    exam_name: str,
    score: float,
    threshold: float,
    channel: str = "email",
    parent_email: str = None,
    parent_telegram_id: str = None,
) -> Dict:
    """Tool: 发送成绩预警通知"""
    handler = NotificationHandler()
    return handler.notify_score_alert(student_id, student_name, exam_name, score, threshold, channel, parent_email, parent_telegram_id)


def notify_class(class_id: str, class_name: str, message: str, channel: str = "discord", urgent: bool = False) -> Dict:
    """Tool: 发送班级通知"""
    handler = NotificationHandler()
    return handler.notify_class(class_id, class_name, message, channel, urgent)


def notify_encouragement(student_id: str, student_name: str, message: str, channel: str = "telegram", telegram_id: str = None) -> Dict:
    """Tool: 发送日常鼓励消息"""
    handler = NotificationHandler()
    return handler.notify_encouragement(student_id, student_name, message, channel, telegram_id)


def notify_config_get(teacher_id: str) -> Dict:
    """Tool: 获取通知渠道配置"""
    handler = NotificationHandler()
    return handler.notify_config_get(teacher_id)


def notify_config_update(teacher_id: str, **kwargs) -> Dict:
    """Tool: 更新通知渠道配置"""
    handler = NotificationHandler()
    return handler.notify_config_update(teacher_id, **kwargs)


# ==================== 主入口 ====================

if __name__ == "__main__":

    def test():
        handler = NotificationHandler()

        # 测试配置获取
        config = handler.notify_config_get("test_teacher")
        print(f"配置获取: {config}")

        # 测试配置更新
        result = handler.notify_config_update("test_teacher", discord_webhook="https://discord.com/api/webhooks/test")
        print(f"配置更新: {result}")

        # 测试统计
        print("测试完成")

    test()
