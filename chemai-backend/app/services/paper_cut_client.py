"""Baidu paper_cut_edu client — 试卷切题 (sync, only_split=true).

Returns question bounding boxes. Text recognition done separately via doc_analysis.
"""
import base64
import logging
from dataclasses import dataclass, field
from urllib import parse

import httpx

from app.services.baidu_auth import get_token

logger = logging.getLogger(__name__)

CUT_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/paper_cut_edu"


@dataclass
class QuestionBBox:
    seqence: int
    bbox: tuple[int, int, int, int]  # left_x, top_y, width, height


@dataclass
class CutResult:
    success: bool
    questions: list[QuestionBBox] = field(default_factory=list)
    error: str = ""


async def cut_page(image_bytes: bytes) -> CutResult:
    """同步切题: 提交图片 → 返回题目坐标列表.

    Uses paper_cut_edu with only_split=true (sync mode).
    Response: {qus_result: [{qus_location: {points: [{x,y},...]}, qus_element: [...]}]}
    """
    token = await get_token()
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    body = parse.urlencode({
        "image": b64,
        "only_split": "true",
    }).encode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{CUT_URL}?access_token={token}",
                content=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

        error_code = data.get("error_code", 0)
        if error_code and error_code != 0:
            return CutResult(success=False, error=data.get("error_msg", "cut failed"))

        questions = []
        for i, q in enumerate(data.get("qus_result", []) or []):
            pts = (q.get("qus_location") or {}).get("points", [])
            if len(pts) == 4:
                xs = [p["x"] for p in pts]
                ys = [p["y"] for p in pts]
                bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            else:
                # Fallback: use qus_element locations
                bbox = (0, 0, 0, 0)
                elems = q.get("qus_element", [])
                if elems:
                    elem_pts = (elems[0].get("elem_location") or {}).get("points", [])
                    if elem_pts:
                        xs = [p["x"] for p in elem_pts]
                        ys = [p["y"] for p in elem_pts]
                        bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            if bbox[2] > 0 and bbox[3] > 0:
                questions.append(QuestionBBox(seqence=i, bbox=bbox))

        return CutResult(success=len(questions) > 0, questions=questions,
                         error="" if questions else "no questions found")

    except Exception as e:
        logger.error("paper_cut_edu failed: %s", e)
        return CutResult(success=False, error=str(e))
