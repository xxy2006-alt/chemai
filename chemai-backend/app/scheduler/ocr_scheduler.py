"""APScheduler job for OCR task processing.

Polls ocr_tasks table every 5 seconds for pending tasks.
Processes one task at a time sequentially.
"""
import base64
import logging
from datetime import datetime
from app.config import config
from app.services.ocr_mineru import get_ocr_provider, _is_choice

logger = logging.getLogger(__name__)


def _needs_vision_review(result: dict) -> bool:
    """低置信/漏检触发视觉复核：无作答、学生信息全空、或题号断层（疑似整行漏检）。

    楷体样本 9-12 题整行消失即题号断层场景（answers 1..8,13..15）。
    """
    answers = result.get("answers") or []
    if not answers:
        return True
    if not result.get("student_id") and not result.get("student_name"):
        return True
    nums = sorted(a["q_number"] for a in answers)
    return any(b - a > 1 for a, b in zip(nums, nums[1:]))


def _vision_review_answers(image_path: str, extract_result: dict) -> dict:
    """单卡视觉复核（llm_service.analyze_paper_with_vision），缺失题号用视觉结果补齐。

    复核失败不降级已提取结果（返回原样）。默认开关见 config.OCR_VISION_REVIEW_ENABLED（a4）。
    """
    from app.services.llm_service import llm_service

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    resp = llm_service.analyze_paper_with_vision(image_data, paper_type="answer_sheet")
    if not resp.get("success"):
        return extract_result

    merged = dict(extract_result)
    answers = list(merged.get("answers") or [])
    have = {a["q_number"] for a in answers}
    for q in resp.get("questions") or []:
        num = str(q.get("number", "")).strip()
        ans = str(q.get("student_answer", "")).strip()
        if not num.isdigit() or not ans:
            continue
        n = int(num)
        if n not in have:
            answers.append({
                "q_number": n,
                "type": "choice" if _is_choice(ans) else "free",
                "answer": ans,
                "confidence": 0.4,
            })
    merged["answers"] = answers
    if not merged.get("student_id"):
        merged["student_id"] = resp.get("student_id", "")
    if not merged.get("student_name"):
        merged["student_name"] = resp.get("student_name", "")
    merged["vision_reviewed"] = True
    return merged


def process_pending_ocr_tasks():
    """Single job: find next pending task, process it, update result."""
    from app.models.database import get_db
    from app.models.ocr_task import OCRTask

    db = next(get_db())
    try:
        task = db.query(OCRTask).filter(
            OCRTask.status == "pending"
        ).order_by(OCRTask.created_at).first()

        if not task:
            return

        task.status = "processing"
        task.progress = 10
        db.commit()

        provider = get_ocr_provider()
        logger.info(f"OCR processing {task.task_id}: {task.image_path}")

        task.progress = 50
        db.commit()

        result = provider.extract(task.image_path)

        if not result.get("error") and config.OCR_VISION_REVIEW_ENABLED and _needs_vision_review(result):
            logger.info(f"OCR {task.task_id}: 低置信/漏检，触发视觉复核")
            result = _vision_review_answers(task.image_path, result)

        if result.get("error"):
            task.status = "failed"
            task.error_message = result["error"]
        else:
            task.status = "done"
            task.progress = 100
            task.student_id = result.get("student_id", "")
            task.student_name = result.get("student_name", "")
            task.ocr_result = {"answers": result.get("answers", [])}
            task.processed_at = datetime.utcnow()

        db.commit()
        logger.info(f"OCR {task.task_id}: {task.status} (sid={task.student_id}, name={task.student_name})")

    except Exception as e:
        logger.error(f"OCR scheduler error: {e}")
        try:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def start_ocr_scheduler(scheduler):
    """Register OCR job with existing APScheduler instance."""
    scheduler.add_job(
        process_pending_ocr_tasks,
        trigger="interval",
        seconds=5,
        id="ocr_processor",
        replace_existing=True,
    )
    logger.info("OCR scheduler started (5s interval)")
