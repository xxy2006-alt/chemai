"""Celery 应用与配置。

broker 默认 redis://localhost:6379/0；测试用 eager 模式（task_always_eager）无需 broker。
"""
import os
from celery import Celery

celery_app = Celery(
    "chemai",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "0") == "1",
    task_eager_propagates=True,
)
