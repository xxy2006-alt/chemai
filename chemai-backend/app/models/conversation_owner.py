"""会话归属表 —— 阶段 4.6 批次 E。

`thread_id` 由客户端自报、格式是 `{prefix}{毫秒时间戳}`（可枚举），在本次改造前
**没有任何归属记录**：任何登录用户都能列出、读取、删除任意会话（`delete_conversation`
甚至直接对 checkpoint 库 `DELETE`）。本表是归属的唯一真源。

新会话在创建/首次使用时登记；老会话（本表上线前的）无法回溯归属，由
`app.middleware.conversation.owns_conversation` 按 thread_id 前缀兜底。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, String

from app.models.database import Base


class ConversationOwner(Base):
    __tablename__ = "conversation_owners"

    thread_id = Column(String(128), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    role = Column(String(32), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
