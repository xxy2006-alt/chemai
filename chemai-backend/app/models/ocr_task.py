"""OCR Task model for answer sheet grading pipeline.

Tasks track the lifecycle of each uploaded answer sheet:
  pending → processing → done/failed
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, JSON
from app.models.database import Base
from datetime import datetime


class OCRTask(Base):
    __tablename__ = "ocr_tasks"

    task_id = Column(String(128), primary_key=True)
    teacher_id = Column(String(64), nullable=False, index=True)
    batch_id = Column(String(64), nullable=False, index=True)
    image_path = Column(String(512), nullable=False)
    title = Column(String(256), default="")
    student_id = Column(String(64), default="")
    student_name = Column(String(128), default="")
    status = Column(String(32), default="pending", index=True)  # pending/processing/done/failed
    progress = Column(Integer, default=0)
    ocr_result = Column(JSON, default=None)
    grading_result = Column(JSON, default=None)
    confirmed = Column(Boolean, default=False)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, default=None)
