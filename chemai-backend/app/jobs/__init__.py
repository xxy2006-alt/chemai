"""后台作业模块——「作业调度边界」。

入队面 enqueue_job 投递到 Celery；broker（Redis）不可达时降级为同步执行，
保证未部署 Redis 的环境下请求不会被队列拖垮。
"""
from typing import Any, Dict


def enqueue_job(job_type: str, payload: Dict[str, Any]):
    """投递后台作业到队列（Celery）；broker 不可达时同步降级执行。"""
    if job_type == "diagnosis":
        from app.jobs.tasks import diagnosis_task
        try:
            return diagnosis_task.delay(payload["exam_record_id"])
        except Exception as exc:  # noqa: BLE001 — 仅 broker 连接失败才降级
            if not _broker_unreachable(exc):
                raise
            from app.jobs.handlers import handle_diagnosis
            return handle_diagnosis(payload["exam_record_id"])
    if job_type == "semantic_grading":
        from app.jobs.tasks import semantic_grading_task
        try:
            return semantic_grading_task.delay(payload.get("exam_record_id"))
        except Exception as exc:  # noqa: BLE001 — 仅 broker 连接失败才降级
            if not _broker_unreachable(exc):
                raise
            # ADR-0013：同步降级不内联跑 LLM（会阻塞提交请求）；
            # PENDING 行由 APScheduler 周期扫描兜底，此处仅记录。
            import logging
            logging.getLogger(__name__).info(
                "semantic scan deferred to scheduler (broker unreachable): %s", payload)
            return None
    if job_type == "assignment_student":
        from app.jobs.tasks import assignment_student_task
        try:
            return assignment_student_task.delay(payload["batch_id"], payload["student_id"])
        except Exception as exc:  # noqa: BLE001 — 仅 broker 连接失败才降级
            if not _broker_unreachable(exc):
                raise
            # 同 ADR-0013 原则：降级不内联跑 LLM——大班批次会在请求里串行跑完整班，
            # 请求一断未处理的目标永不重试。未完成目标交 APScheduler 兜底作业逐生推进。
            import logging
            logging.getLogger(__name__).info(
                "assignment batch deferred to scheduler (broker unreachable): %s", payload)
            return {"deferred": "scheduler", "batch_id": payload["batch_id"],
                    "student_id": payload["student_id"]}
    if job_type == "diagnosis_student":
        from app.jobs.tasks import diagnosis_student_task
        try:
            return diagnosis_student_task.delay(payload["student_id"])
        except Exception as exc:  # noqa: BLE001 — 仅 broker 连接失败才降级
            if not _broker_unreachable(exc):
                raise
            # ADR-0013：降级不内联跑 LLM——这条链挂在对话作答上，内联会在
            # 学生这一轮对话里跑最多 10 次障碍判定（TURN_TIMEOUT 撑不住）。
            # 交后台线程尽力补跑；丢了由该生下一条 chat 作答重新触发（去抖窗口外）。
            import logging
            import threading

            from app.jobs.handlers import handle_diagnosis_student

            logging.getLogger(__name__).info(
                "student diagnosis deferred to background thread (broker unreachable): %s",
                payload.get("student_id"))
            threading.Thread(
                target=handle_diagnosis_student, args=(payload["student_id"],),
                daemon=True,
            ).start()
            return {"deferred": "thread", "student_id": payload["student_id"]}
    raise ValueError(f"未知作业类型: {job_type}")


def _broker_unreachable(exc: Exception) -> bool:
    """异常是否源于 broker（Redis/kombu/amqp）不可达，而非任务执行错误。"""
    module = type(exc).__module__ or ""
    return module.startswith(("kombu", "redis", "amqp", "vine"))
