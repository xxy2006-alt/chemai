"""
ChemAI Configuration
基于PRD v1.0完整版技术选型
"""
from pathlib import Path

from pydantic_settings import BaseSettings
from typing import List

# 后端根目录锚定：所有数据路径以此为基准，与启动时的 cwd 无关。
# （此前 ./ 相对路径导致从仓库根启动时在 D:\化学\data\ 下生成幽灵数据副本）
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    APP_NAME: str = "智辅化学 ChemAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 通知外发网关（chemistry_notification 四网关；默认关闭仅站内）
    NOTIFY_EXTERNAL_GATEWAYS: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # 数据库配置 (SQLite for MVP, 可切换MySQL)
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'chemai.db').as_posix()}"

    # 小米 MiMo-V2.5 API (主力)
    XIAOMI_API_KEY: str = ""
    MIMO_MODEL: str = "mimo-v2.5"
    MIMO_API_URL: str = "https://api.xiaomimimo.com/v1/chat/completions"
    LLM_PROVIDER: str = "mimo"  # mimo / dashscope / deepseek

    # 通义千问API配置 (备选)
    DASHSCOPE_API_KEY: str = ""
    LLM_MODEL: str = "qwen-turbo"
    LLM_API_URL: str = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    # 腾讯OCR配置
    TENCENT_OCR_SECRET_ID: str = ""   # 需在环境变量设置
    TENCENT_OCR_SECRET_KEY: str = ""  # 需在环境变量设置
    TENCENT_OCR_REGION: str = "ap-guangzhou"

    # 智谱AI OCR配置
    ZHIPU_API_KEY: str = ""  # 需在环境变量设置

    # 百度AI OCR配置（教育产品识别）
    BAIDU_OCR_API_KEY: str = ""     # API Key
    BAIDU_OCR_SECRET_KEY: str = ""  # Secret Key
    BAIDU_OCR_TOKEN: str = ""       # 运行时缓存的 access token
    BAIDU_OCR_TOKEN_EXPIRES: float = 0  # token 过期时间戳

    # Chroma向量数据库
    CHROMA_DB_PATH: str = str(BASE_DIR / "data" / "chromadb")

    # 化学知识图谱配置
    KNOWLEDGE_GRAPH_PATH: str = str(BASE_DIR / "data" / "knowledge_graph")
    EXAM_QUESTIONS_PATH: str = str(BASE_DIR / "data" / "exam_questions")

    # OCR识别配置
    OCR_CONFIDENCE_THRESHOLD: float = 0.85  # 识别置信度阈值
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB

    # 化学方程式审核配置
    BALANCE_CHECK_ENABLED: bool = True  # 系数配平检查
    CONDITION_CHECK_ENABLED: bool = True  # 反应条件检查
    PRODUCT_CHECK_ENABLED: bool = True  # 产物稳定性检查
    STRUCTURE_CHECK_ENABLED: bool = True  # 分子结构检查

    # 障碍诊断配置（默认值，可由教师调整）
    DEFAULT_CONCEPT_THRESHOLD: int = 3  # 概念理解型：连续错误N次触发
    DEFAULT_READING_THRESHOLD: int = 2  # 审题障碍型：连续错误N次触发
    DEFAULT_EXPRESSION_THRESHOLD: int = 3  # 表述障碍型：连续错误N次触发
    DEFAULT_MASTERY_THRESHOLD: int = 3  # 掌握标准：连续答对N次

    # 考试覆盖范围（基于PRD）
    EXAM_COVERAGE: List[str] = [
        "全国卷2022", "全国卷2023", "全国卷2024",
        "湖南卷2022", "湖南卷2023", "湖南卷2024"
    ]

    # MVP月度成本上限
    MAX_MONTHLY_COST: float = 500.0  # ¥500/月

    # 频率限制
    LLM_RATE_LIMIT_PER_MINUTE: int = 30  # LLM API 每分钟最大请求数
    FILE_UPLOAD_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB

    # 数据库
    SQLITE_WAL_MODE: bool = True  # WAL模式提升并发

    # 缓存
    CACHE_TTL_SECONDS: int = 300  # 内存缓存默认TTL

    class Config:
        env_file = str(BASE_DIR / ".env")
        case_sensitive = True
        extra = "allow"  # 允许新 Provider 的环境变量


settings = Settings()
