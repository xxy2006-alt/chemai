"""Centralized config — loads .env once, provides typed access.

Import: from app.config import config
Usage: config.DEEPSEEK_API_KEY, config.DATABASE_URL
"""
import os
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()


class _Config:
    """Application configuration singleton."""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chemai.db")

    # LLM Providers
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # 上下文窗口(token) — 用于前端上下文占用环展示,deepseek-chat 当前容量 128K
    CONTEXT_WINDOW: int = int(os.getenv("CONTEXT_WINDOW", "128000"))

    XIAOMI_API_KEY: str = os.getenv("XIAOMI_API_KEY", "")
    MIMO_MODEL: str = os.getenv("MIMO_MODEL", "mimo-v2.5")
    MIMO_BASE_URL: str = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")

    ZHIPU_API_KEY: str = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_MODEL: str = os.getenv("ZHIPU_MODEL", "GLM-4-Flash")

    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_MODEL: str = os.getenv("DASHSCOPE_MODEL", "qwen-turbo")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

    # Baidu OCR
    BAIDU_OCR_APP_ID: str = os.getenv("BAIDU_OCR_APP_ID", "")
    BAIDU_OCR_API_KEY: str = os.getenv("BAIDU_OCR_API_KEY", "")
    BAIDU_OCR_SECRET_KEY: str = os.getenv("BAIDU_OCR_SECRET_KEY", "")

    # MinerU
    MINERU_PATH: str = os.getenv("MINERU_PATH", "")
    MINERU_ENABLED: bool = os.getenv("MINERU_ENABLED", "1").lower() not in ("0", "false", "no")

    # OCR Sheet Provider (mineru / baidu / paddle) — ADR-0004: 默认 PP-OCRv6_small
    OCR_SHEET_PROVIDER: str = os.getenv("OCR_SHEET_PROVIDER", "paddle")
    # 低置信/缺答案任务单卡视觉复核（默认开，见 docs/ocr-answer-sheet-plan.md a4）
    OCR_VISION_REVIEW_ENABLED: bool = os.getenv("OCR_VISION_REVIEW_ENABLED", "1").lower() not in ("0", "false", "no")

    # Test
    SKIP_DB_INIT: bool = os.getenv("SKIP_DB_INIT", "").lower() in ("1", "true", "yes")

    # API
    WRAP_RESPONSES: bool = os.getenv("WRAP_RESPONSES", "1").lower() not in ("0", "false", "no")

    @property
    def provider_keys(self) -> dict:
        return {
            "deepseek": self.DEEPSEEK_API_KEY,
            "mimo": self.XIAOMI_API_KEY,
            "zhipu": self.ZHIPU_API_KEY,
            "dashscope": self.DASHSCOPE_API_KEY,
        }


@lru_cache
def get_config() -> _Config:
    return _Config()


# Module-level singleton
config = get_config()
