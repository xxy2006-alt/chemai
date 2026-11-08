"""Celery 任务——后台作业 handler 的薄包装。"""
from app.jobs.celery_app import celery_app
from app.jobs.handlers import handle_diagnosis


@celery_app.task(
    name="jobs.diagnosis",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def diagnosis_task(exam_record_id: str) -> dict:
    """诊断作业：包装幂等的 handle_diagnosis，失败自动重试（指数退避）。"""
    return handle_diagnosis(exam_record_id)


@celery_app.task(
    name="jobs.semantic_grading",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def semantic_grading_task(exam_record_id: str = None) -> dict:
    """主观题扫描作业：判定 PENDING 行（ADR-0013），失败自动重试。"""
    from app.jobs.handlers import handle_semantic_scan
    return handle_semantic_scan(exam_record_id)


@celery_app.task(
    name="jobs.assignment_student",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def assignment_student_task(batch_id: str, student_id: str) -> dict:
    """逐生布置作业：包装幂等的 run_batch_student（record_id 确定性，重放安全）。"""
    from app.services.assignment_service import handle_batch_student
    return handle_batch_student(batch_id, student_id)


@celery_app.task(
    name="jobs.diagnosis_student",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def diagnosis_student_task(student_id: str) -> dict:
    """学生级诊断作业：包装幂等的 handle_diagnosis_student，失败自动重试。"""
    from app.jobs.handlers import handle_diagnosis_student
    return handle_diagnosis_student(student_id)
