## Why

验证报告发现的关键问题：认证中间件不生效、OCR 静默返回假数据、AI 出题和真题搜索 API 报错。

## What Changes

- P0: JWT 认证中间件强制校验（无 token → 401）
- P0: 删除 `ocr_service.py` 中所有 `_mock_*` 函数
- P1: 修复 `POST /api/question/generate` Pydantic 校验
- P1: 修复 `GET /api/exam-bank/search` 路由
- 配置：`app/core/config.py` extra=allow（已完成）

## Capabilities

### Modified Capabilities
- `auth`: JWT 认证从"注册但不生效"改为强制校验
