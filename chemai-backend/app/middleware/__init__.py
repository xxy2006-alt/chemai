"""
权限认证中间件
"""
from app.middleware.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_refresh_token,
    can,
    get_current_user,
    require_auth,
    require_permission,
    PermissionChecker,
    get_teacher_classes,
    get_class_students,
    ROLE_PERMISSIONS
)

__all__ = [
    'create_access_token',
    'create_refresh_token',
    'verify_token',
    'verify_refresh_token',
    'can',
    'get_current_user',
    'require_auth',
    'require_permission',
    'PermissionChecker',
    'get_teacher_classes',
    'get_class_students',
    'ROLE_PERMISSIONS'
]
