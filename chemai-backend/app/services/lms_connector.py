"""
LMS连接器服务
P2-3: 支持与学校LMS、智慧校园、钉钉/企业微信等系统对接
"""

import json
import hmac
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests


class LMSConnector:
    """LMS连接器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.platform = config.get("platform", "generic")

    def send_assignment(self, assignment_data: Dict) -> Dict[str, Any]:
        """发送作业/练习到LMS"""
        raise NotImplementedError

    def get_student_scores(self, assignment_id: str) -> List[Dict]:
        """获取学生成绩"""
        raise NotImplementedError

    def sync_users(self, users: List[Dict]) -> Dict[str, Any]:
        """同步用户到LMS"""
        raise NotImplementedError


class GenericLMSConnector(LMSConnector):
    """通用REST API连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", "")
        self.api_key = config.get("api_key", "")
        self.secret = config.get("secret", "")

    def _sign_request(self, params: Dict, timestamp: str) -> str:
        """签名请求"""
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        sign_str = f"{param_str}&timestamp={timestamp}"
        signature = hmac.new(
            self.secret.encode(),
            sign_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _make_headers(self) -> Dict[str, str]:
        """生成请求头"""
        timestamp = str(int(time.time()))
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "X-Timestamp": timestamp,
            "X-Platform": self.platform
        }

    def send_assignment(self, assignment_data: Dict) -> Dict[str, Any]:
        """发送作业/练习"""
        if not self.enabled or not self.api_url:
            return {"success": False, "message": "LMS未启用或未配置"}

        try:
            response = requests.post(
                f"{self.api_url}/assignments",
                json=assignment_data,
                headers=self._make_headers(),
                timeout=10
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_student_scores(self, assignment_id: str) -> List[Dict]:
        """获取学生成绩"""
        if not self.enabled:
            return []

        try:
            response = requests.get(
                f"{self.api_url}/assignments/{assignment_id}/scores",
                headers=self._make_headers(),
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("scores", [])
        except Exception:
            pass
        return []

    def sync_users(self, users: List[Dict]) -> Dict[str, Any]:
        """同步用户"""
        if not self.enabled:
            return {"success": False, "message": "LMS未启用"}

        try:
            response = requests.post(
                f"{self.api_url}/users/sync",
                json={"users": users},
                headers=self._make_headers(),
                timeout=15
            )
            if response.status_code == 200:
                return {"success": True, "synced": len(users)}
            else:
                return {"success": False, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}


class DingTalkConnector(LMSConnector):
    """钉钉连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.app_key = config.get("app_key", "")
        self.app_secret = config.get("app_secret", "")
        self.agent_id = config.get("agent_id", "")

    def _get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        try:
            url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
            response = requests.post(url, json={
                "appKey": self.app_key,
                "appSecret": self.app_secret
            }, timeout=10)
            if response.status_code == 200:
                return response.json().get("accessToken")
        except Exception:
            pass
        return None

    def send_assignment(self, assignment_data: Dict) -> Dict[str, Any]:
        """发送作业到钉钉"""
        if not self.enabled:
            return {"success": False, "message": "钉钉未启用"}

        token = self._get_access_token()
        if not token:
            return {"success": False, "message": "获取访问令牌失败"}

        try:
            url = "https://api.dingtalk.com/v1.0/notification/grades/send"
            headers = {
                "x-acs-dingtalk-access-token": token,
                "Content-Type": "application/json"
            }
            payload = {
                "agentId": self.agent_id,
                "userIds": assignment_data.get("student_ids", []),
                "msg": {
                    "msgType": "markdown",
                    "markdown": {
                        "title": assignment_data.get("title", "新作业"),
                        "text": f"### {assignment_data.get('title', '新作业')}\n\n"
                               f"{assignment_data.get('content', '')}\n\n"
                               f"截止时间: {assignment_data.get('deadline', '未设置')}"
                    }
                }
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}


class WeComConnector(LMSConnector):
    """企业微信连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.corp_id = config.get("corp_id", "")
        self.corp_secret = config.get("corp_secret", "")
        self.agent_id = config.get("agent_id", "")

    def _get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        try:
            url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            params = {
                "corpid": self.corp_id,
                "corpsecret": self.corp_secret
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("errcode") == 0:
                    return data.get("access_token")
        except Exception:
            pass
        return None

    def send_assignment(self, assignment_data: Dict) -> Dict[str, Any]:
        """发送作业到企业微信"""
        if not self.enabled:
            return {"success": False, "message": "企业微信未启用"}

        token = self._get_access_token()
        if not token:
            return {"success": False, "message": "获取访问令牌失败"}

        try:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
            payload = {
                "touser": "|".join(assignment_data.get("student_ids", [])),
                "msgtype": "markdown",
                "agentid": self.agent_id,
                "markdown": {
                    "content": f"### {assignment_data.get('title', '新作业')}\n\n"
                              f"{assignment_data.get('content', '')}\n\n"
                              f"截止时间: {assignment_data.get('deadline', '未设置')}"
                }
            }
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            if result.get("errcode") == 0:
                return {"success": True}
            else:
                return {"success": False, "message": result.get("errmsg", "发送失败")}
        except Exception as e:
            return {"success": False, "message": str(e)}


class LTI13Connector(LMSConnector):
    """LTI 1.3连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.issuer = config.get("issuer", "")
        self.client_id = config.get("client_id", "")
        self.deployment_id = config.get("deployment_id", "")
        self.public_key = config.get("public_key", "")
        self.private_key = config.get("private_key", "")
        self.platform_jwks_url = config.get("platform_jwks_url", "")

    def create_deep_link(self, content_items: List[Dict]) -> Dict[str, Any]:
        """创建Deep Linking响应"""
        if not self.enabled:
            return {"success": False, "message": "LTI未启用"}

        # 生成JWT声明
        now = int(time.time())
        claims = {
            "iss": self.client_id,
            "aud": self.issuer,
            "iat": now,
            "exp": now + 3600,
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": self.deployment_id,
            "https://purl.imsglobal.org/spec/lti/claim/message_type": "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_launch_request",
            "https://purl.imsglobal.org/spec/lti-dl/claim/content_items": content_items
        }

        try:
            import jwt
            # 签名JWT (简化版，实际需要使用完整的LTI流程)
            token = jwt.encode(claims, self.private_key, algorithm="RS256")
            return {
                "success": True,
                "content_items": content_items,
                "jwt_token": token
            }
        except Exception as e:
            return {"success": False, "message": str(e)}


class WebhookService:
    """Webhook服务 - 事件推送"""

    def __init__(self):
        self.webhooks: Dict[str, Dict] = {}  # event_type -> {url, secret, enabled}

    def register_webhook(self, event_type: str, url: str, secret: str = "") -> Dict[str, Any]:
        """注册Webhook"""
        self.webhooks[event_type] = {
            "url": url,
            "secret": secret,
            "enabled": True,
            "registered_at": datetime.now().isoformat()
        }
        return {"success": True, "event_type": event_type}

    def unregister_webhook(self, event_type: str) -> Dict[str, Any]:
        """取消注册Webhook"""
        if event_type in self.webhooks:
            del self.webhooks[event_type]
            return {"success": True}
        return {"success": False, "message": "Webhook不存在"}

    def trigger_event(self, event_type: str, payload: Dict) -> List[Dict]:
        """触发Webhook事件"""
        results = []
        webhook = self.webhooks.get(event_type)
        if not webhook or not webhook.get("enabled"):
            return results

        try:
            headers = {"Content-Type": "application/json"}
            if webhook.get("secret"):
                # 添加签名
                timestamp = str(int(time.time()))
                sign_str = f"{timestamp}.{json.dumps(payload)}"
                signature = hmac.new(
                    webhook["secret"].encode(),
                    sign_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = signature
                headers["X-Webhook-Timestamp"] = timestamp

            response = requests.post(
                webhook["url"],
                json=payload,
                headers=headers,
                timeout=10
            )
            results.append({
                "event_type": event_type,
                "status_code": response.status_code,
                "success": response.status_code in [200, 201, 202, 204]
            })
        except Exception as e:
            results.append({
                "event_type": event_type,
                "success": False,
                "error": str(e)
            })

        return results

    def list_webhooks(self) -> List[Dict]:
        """列出所有注册的Webhook"""
        return [
            {"event_type": k, **v}
            for k, v in self.webhooks.items()
        ]


# 支持的事件类型
WEBHOOK_EVENT_TYPES = [
    "practice.assigned",      # 练习布置
    "practice.completed",     # 练习完成
    "exam.created",           # 考试创建
    "exam.graded",            # 考试成绩发布
    "warning.triggered",      # 预警触发
    "student.login",          # 学生登录
    "review.due",             # 复习任务到期
]


# 全局实例
_lti_connectors: Dict[str, LMSConnector] = {}
_webhook_service = WebhookService()


def get_lms_connector(platform: str, config: Dict) -> LMSConnector:
    """获取LMS连接器"""
    if platform == "generic":
        return GenericLMSConnector(config)
    elif platform == "dingtalk":
        return DingTalkConnector(config)
    elif platform == "wecom":
        return WeComConnector(config)
    elif platform == "lti13":
        return LTI13Connector(config)
    else:
        return LMSConnector(config)


def get_webhook_service() -> WebhookService:
    """获取Webhook服务"""
    return _webhook_service


def trigger_webhook_event(event_type: str, payload: Dict) -> List[Dict]:
    """触发Webhook事件"""
    return _webhook_service.trigger_event(event_type, payload)
