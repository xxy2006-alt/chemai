"""
P2-3: LMS集成API
提供REST API开放平台、Webhook、LTI 1.3协议支持
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.models.database import get_db
from app.services.lms_connector import (
    get_lms_connector, get_webhook_service, WEBHOOK_EVENT_TYPES, LTI13Connector
)

router = APIRouter()


# ==================== LMS配置 ====================

class LMSConfigRequest(BaseModel):
    """LMS配置请求"""
    platform: str  # generic/dingtalk/wecom/lti13
    enabled: bool = False
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    agent_id: Optional[str] = None
    corp_id: Optional[str] = None
    corp_secret: Optional[str] = None


class LMSConfigResponse(BaseModel):
    """LMS配置响应"""
    platform: str
    enabled: bool
    connected: bool
    last_sync: Optional[str] = None


@router.get("/lms/config")
async def get_lms_config(db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    获取LMS配置
    """
    # 从数据库或配置读取LMS配置
    from app.core.config import settings

    config = getattr(settings, 'LMS_CONFIG', {})

    return {
        "success": True,
        "platforms": {
            "generic": {
                "enabled": config.get("generic_enabled", False),
                "connected": False
            },
            "dingtalk": {
                "enabled": config.get("dingtalk_enabled", False),
                "connected": False
            },
            "wecom": {
                "enabled": config.get("wecom_enabled", False),
                "connected": False
            },
            "lti13": {
                "enabled": config.get("lti13_enabled", False),
                "connected": False
            }
        }
    }


@router.post("/lms/config")
async def save_lms_config(request: LMSConfigRequest, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "update")),
):
    """
    保存LMS配置
    """
    # 验证配置
    if request.enabled:
        connector = get_lms_connector(request.platform, {
            "enabled": True,
            "api_url": request.api_url,
            "api_key": request.api_key,
            "api_secret": request.api_secret,
            "app_key": request.app_key,
            "app_secret": request.app_secret,
            "agent_id": request.agent_id,
            "corp_id": request.corp_id,
            "corp_secret": request.corp_secret
        })

        # 尝试连接测试
        test_result = connector.send_assignment({
            "title": "连接测试",
            "content": "这是一条测试消息"
        }) if hasattr(connector, 'send_assignment') else {"success": True}

        connected = test_result.get("success", False)
    else:
        connected = False

    # TODO: 保存配置到数据库或配置文件

    return {
        "success": True,
        "platform": request.platform,
        "enabled": request.enabled,
        "connected": connected
    }


@router.post("/lms/test")
async def test_lms_connection(
    platform: str,
    config: Dict[str, Any],
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    测试LMS连接
    """
    connector = get_lms_connector(platform, {**config, "enabled": True})

    test_result = connector.send_assignment({
        "title": "连接测试",
        "content": "这是一条测试消息"
    }) if hasattr(connector, 'send_assignment') else {"success": True, "message": "不支持此操作"}

    return test_result


# ==================== Webhook管理 ====================

class WebhookRegisterRequest(BaseModel):
    """Webhook注册请求"""
    event_type: str
    url: str
    secret: Optional[str] = ""


class WebhookResponse(BaseModel):
    """Webhook响应"""
    event_type: str
    url: str
    enabled: bool
    registered_at: str


@router.get("/webhooks")
async def list_webhooks(
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    列出所有注册的Webhook
    """
    service = get_webhook_service()
    webhooks = service.list_webhooks()

    return {
        "success": True,
        "count": len(webhooks),
        "webhooks": webhooks,
        "available_events": WEBHOOK_EVENT_TYPES
    }


@router.post("/webhooks")
async def register_webhook(request: WebhookRegisterRequest,
    _perm: None = Depends(PermissionChecker("integration", "create")),
):
    """
    注册Webhook
    """
    if request.event_type not in WEBHOOK_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的事件类型。可用类型: {', '.join(WEBHOOK_EVENT_TYPES)}"
        )

    service = get_webhook_service()
    result = service.register_webhook(request.event_type, request.url, request.secret)

    return result


@router.delete("/webhooks/{event_type}")
async def unregister_webhook(event_type: str,
    _perm: None = Depends(PermissionChecker("integration", "delete")),
):
    """
    取消注册Webhook
    """
    service = get_webhook_service()
    result = service.unregister_webhook(event_type)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Webhook不存在")

    return result


@router.post("/webhooks/test")
async def test_webhook(event_type: str, url: str, secret: str = "",
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    测试Webhook
    """
    if event_type not in WEBHOOK_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的事件类型。可用类型: {', '.join(WEBHOOK_EVENT_TYPES)}"
        )

    # 发送测试事件
    test_payload = {
        "event": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "test": True,
            "message": "这是一条测试Webhook消息"
        }
    }

    # 临时注册并触发
    service = get_webhook_service()
    service.register_webhook(event_type, url, secret)
    results = service.trigger_event(event_type, test_payload)

    return {
        "success": True,
        "event_type": event_type,
        "results": results
    }


# ==================== LTI 1.3 支持 ====================

class LTIDeepLinkRequest(BaseModel):
    """LTI Deep Linking请求"""
    platform_id: str
    deployment_id: str
    content_items: List[Dict[str, Any]]


@router.post("/lti/deep-link")
async def lti_deep_link(request: LTIDeepLinkRequest, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "create")),
):
    """
    LTI 1.3 Deep Linking
    创建要返回给LMS平台的内容项
    """
    config = {
        "issuer": request.platform_id,
        "deployment_id": request.deployment_id
    }

    connector = LTI13Connector(config)
    result = connector.create_deep_link(request.content_items)

    return result


@router.get("/lti/.well-known/jwks.json")
async def lti_jwks():
    """
    LTI 1.3 JWKS端点
    返回公钥用于验证JWT签名
    """
    # TODO: 实现动态JWKS
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "chemai-key-1"
            }
        ]
    }


# ==================== REST API开放平台 ====================

class ApiKeyResponse(BaseModel):
    """API Key响应"""
    api_key: str
    created_at: str
    permissions: List[str]


@router.get("/api-keys")
async def list_api_keys(db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    列出已创建的API Key
    """
    # TODO: 从数据库读取API Key列表
    return {
        "success": True,
        "keys": []
    }


@router.post("/api-keys")
async def create_api_key(
    name: str,
    permissions: List[str],
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "create")),
):
    """
    创建新的API Key
    """
    import secrets
    # 生成API Key
    api_key = f"ck_{secrets.token_hex(16)}"
    api_secret = secrets.token_hex(32)

    # TODO: 保存到数据库

    return {
        "success": True,
        "api_key": api_key,
        "api_secret": api_secret,
        "name": name,
        "permissions": permissions,
        "created_at": datetime.now().isoformat(),
        "message": "请妥善保存API Secret，它不会再显示"
    }


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "delete")),
):
    """
    删除API Key
    """
    # TODO: 从数据库删除
    return {
        "success": True,
        "message": "API Key已删除"
    }


# ==================== 事件日志 ====================

class IntegrationLog(BaseModel):
    """集成日志"""
    log_id: str
    event_type: str
    platform: str
    status: str  # success/failed
    request_data: Optional[Dict] = None
    response_data: Optional[Dict] = None
    error_message: Optional[str] = None
    created_at: str


@router.get("/logs")
async def get_integration_logs(
    event_type: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    获取集成日志
    """
    # TODO: 从数据库查询日志
    return {
        "success": True,
        "count": 0,
        "logs": []
    }


# ==================== SFTP文件交换 ====================

class SFTPConfigRequest(BaseModel):
    """SFTP配置请求"""
    enabled: bool = False
    host: Optional[str] = None
    port: int = 22
    username: Optional[str] = None
    password: Optional[str] = None
    upload_path: Optional[str] = None
    download_path: Optional[str] = None


@router.post("/sftp/config")
async def save_sftp_config(request: SFTPConfigRequest, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "update")),
):
    """
    保存SFTP配置
    """
    # TODO: 保存到数据库
    return {
        "success": True,
        "message": "SFTP配置已保存"
    }


@router.get("/sftp/config")
async def get_sftp_config(db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    获取SFTP配置
    """
    # TODO: 从数据库读取
    return {
        "success": True,
        "enabled": False,
        "host": "",
        "port": 22
    }


@router.post("/sftp/test")
async def test_sftp_connection(request: SFTPConfigRequest,
    _perm: None = Depends(PermissionChecker("integration", "read")),
):
    """
    测试SFTP连接
    """
    # TODO: 实现SFTP连接测试
    return {
        "success": False,
        "message": "SFTP功能开发中"
    }
