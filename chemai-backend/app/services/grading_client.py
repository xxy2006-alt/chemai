"""Baidu correct_edu client — answer sheet grading.

Async API: create_task → poll get_result.
Returns GradingResult with per-question correct/incorrect, reasons, and crop images.
"""
import asyncio
import base64
import logging
from dataclasses import dataclass, field

import httpx

from app.services.baidu_auth import get_token

logger = logging.getLogger(__name__)

CREATE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/correct_edu/create_task"
GET_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/correct_edu/get_result"
POLL_INTERVAL = 3.0
POLL_TIMEOUT = 120.0


@dataclass
class GradedQuestion:
    question_id: str
    seqence: int
    type: int          # 2=choice, 4=fill, etc.
    correct_result: int  # 0=unprocessed, 1=correct, 2=wrong, 3=unanswered
    reason: str        # grading reason
    crop_url: str      # Baidu crop image URL
    crop_local_path: str = ""  # local path after download


@dataclass
class GradingResult:
    success: bool
    paper_subject: str = ""
    questions: list[GradedQuestion] = field(default_factory=list)
    stat_result: dict = field(default_factory=dict)
    error: str = ""


async def grade_image(image_bytes: bytes) -> GradingResult:
    """Grade a single answer sheet image.

    Args:
        image_bytes: Raw image bytes (PNG/JPG).

    Returns:
        GradingResult with per-question grading.
    """
    token = await get_token()
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Submit
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{CREATE_URL}?access_token={token}",
            json={"image": b64, "paperSubject": "chemistry"},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    error_code = data.get("error_code", 0)
    if error_code and error_code != 0:
        return GradingResult(
            success=False,
            error=data.get("error_msg", "create_task failed"),
        )

    task_id = data.get("result", {}).get("task_id", "")
    if not task_id:
        return GradingResult(success=False, error=f"No task_id: {data}")

    logger.info("correct_edu submitted: task_id=%s", task_id)

    # Poll
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT
    async with httpx.AsyncClient(timeout=30.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(POLL_INTERVAL)
            resp = await client.post(
                f"{GET_URL}?access_token={token}",
                json={"task_id": task_id},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            result = data.get("result", {})
            if result.get("isAllFinished"):
                return _parse_result(result)

    return GradingResult(success=False, error="Grading poll timeout")


def _parse_result(raw: dict) -> GradingResult:
    """Parse Baidu correct_edu response into GradingResult."""
    image_results = raw.get("imageResults", [])
    stat = raw.get("stat_result", {})

    questions = []
    for ir in image_results:
        subject = ir.get("paperSubject", "")
        for q in ir.get("result", []):
            slot = q.get("slot", [{}])[0] if q.get("slot") else {}
            questions.append(GradedQuestion(
                question_id=q.get("questionId", ""),
                seqence=q.get("seqence", 0),
                type=q.get("type", 0),
                correct_result=q.get("correctResult", 0),
                reason=slot.get("reason", ""),
                crop_url=q.get("cropUrl", ""),
            ))

    return GradingResult(
        success=True,
        paper_subject=subject,
        questions=questions,
        stat_result={"all": stat.get("all", 0), "corrected": stat.get("corrected", 0)},
    )
