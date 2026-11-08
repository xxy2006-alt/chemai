"""
OCR服务封装 — 百度教育OCR + Vision降级 (async)
用于: F1 试卷/答题卡识别、题库导入、判卷

Architecture:
  baidu_auth.get_token() — shared token (all clients)
  doc_analysis          — preview + formula extraction (sync-ish via httpx)
  exam_import_client    — paper_cut_edu_vlm (async, batch)
  grading_client        — correct_edu (async)
"""
import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib import parse

import httpx

from app.services.baidu_auth import get_token

logger = logging.getLogger(__name__)

BAIDU_DOC_ANALYSIS_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/doc_analysis"


class OCRService:
    """OCR服务 - 百度教育产品识别 + Vision降级（全异步）"""

    def __init__(self):
        pass

    @property
    def enabled(self) -> bool:
        return bool(
            os.getenv("BAIDU_OCR_API_KEY", "") and
            os.getenv("BAIDU_OCR_SECRET_KEY", "")
        )

    # ═══════════════════════════════════════════════════════════════
    # 统一入口
    # ═══════════════════════════════════════════════════════════════

    async def recognize(self, file_data: bytes, mime_type: str = "image/png") -> Dict:
        """快速预览 — doc_analysis OCR，返回文本 + 化学式"""
        if not self.enabled:
            return self._not_configured()

        if mime_type == "application/pdf":
            img = await self._pdf_page_to_image(file_data, page_num=0)
        else:
            img = file_data

        result = await self._call_doc_analysis(img)
        if result.get("success"):
            return {
                "success": True,
                "preview_text": result.get("raw_text", ""),
                "formula_result": result.get("data", {}).get("formula_result", []),
                "confidence": result.get("confidence", 0.9),
                "provider": "baidu",
            }
        return {"success": False, "error": result.get("error", "OCR failed")}

    async def import_exam(self, upload_id: str) -> Dict:
        """从 upload_session 导入试卷 → 题库"""
        from app.models.database import get_db, UploadSession, Question
        from sqlalchemy import update as sql_update

        db = next(get_db())
        try:
            session = db.query(UploadSession).filter(
                UploadSession.id == upload_id
            ).first()
            if not session:
                return {"success": False, "error": f"Session {upload_id} not found"}

            # Update status → importing
            db.execute(
                sql_update(UploadSession)
                .where(UploadSession.id == upload_id, UploadSession.version == session.version)
                .values(status="importing", version=session.version + 1)
            )
            db.commit()

            # Convert file to page images
            pages = await self._file_to_pages(session.file_data, session.mime_type)
            session.page_count = len(pages)
            db.commit()

            # Cut + OCR each page
            from app.services.paper_cut_client import cut_page
            all_texts = []
            for pi, page_bytes in enumerate(pages):
                # Update progress
                db.execute(
                    sql_update(UploadSession)
                    .where(UploadSession.id == upload_id)
                    .values(pages_completed=pi + 1)
                )
                db.commit()

                # Try cut first, fall back to full-page OCR
                cut = await cut_page(page_bytes)
                if cut.success and cut.questions:
                    for q in cut.questions:
                        x, y, w, h = q.bbox
                        from PIL import Image
                        import io as _io
                        img = Image.open(_io.BytesIO(page_bytes))
                        crop = img.crop((x, y, x + w, y + h))
                        buf = _io.BytesIO()
                        crop.save(buf, format="PNG")
                        ocr = await self._call_doc_analysis(buf.getvalue())
                        if ocr.get("success"):
                            all_texts.append(ocr.get("raw_text", ""))
                else:
                    # Fallback: OCR full page
                    ocr = await self._call_doc_analysis(page_bytes)
                    if ocr.get("success"):
                        all_texts.append(ocr.get("raw_text", ""))

            if not all_texts:
                db.execute(
                    sql_update(UploadSession)
                    .where(UploadSession.id == upload_id)
                    .values(status="error", error_msg="No text extracted from any page")
                )
                db.commit()
                return {"success": False, "error": "No text extracted"}

            # LLM structuring
            full_text = "\n\n".join(all_texts)
            formula_hint = session.formula_result or ""
            questions = await self._llm_structure(full_text, formula_hint)

            # Save to DB
            saved = 0
            for q in questions:
                from app.models.database import Difficulty, QuestionSource
                diff_map = {"easy": Difficulty.EASY, "medium": Difficulty.MEDIUM,
                            "hard": Difficulty.HARD, "competition": Difficulty.COMPETITION}
                db.add(Question(
                    question_id=f"q_{uuid.uuid4().hex[:12]}",
                    content=q.get("content", ""),
                    options=q.get("options"),
                    answer=str(q.get("answer", "")),
                    analysis=q.get("analysis", ""),
                    knowledge_points=q.get("knowledge_points", []),
                    difficulty=diff_map.get(q.get("difficulty", "medium"), Difficulty.MEDIUM),
                    source=QuestionSource.OCR_IMPORT,
                    source_exam=session.detected_type or "imported",
                ))
                saved += 1
            db.commit()

            # Done
            db.execute(
                sql_update(UploadSession)
                .where(UploadSession.id == upload_id)
                .values(status="imported", result_json=json.dumps(questions, ensure_ascii=False))
            )
            db.commit()

            return {"success": True, "question_count": saved}

        except Exception as e:
            logger.error("import_exam failed: %s", e)
            db.execute(
                sql_update(UploadSession)
                .where(UploadSession.id == upload_id)
                .values(status="error", error_msg=str(e))
            )
            db.commit()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    # ═══════════════════════════════════════════════════════════════
    # 判卷
    # ═══════════════════════════════════════════════════════════════

    async def grade(self, image_data: bytes, exam_id: str = "", class_id: str = "") -> Dict:
        """判卷 — 批改答题卡，保存结果"""
        from app.services.grading_client import grade_image
        from app.models.database import get_db, StudentSubmission

        result = await grade_image(image_data)
        if not result.success:
            return {"success": False, "error": result.error}

        # Build answers JSON
        answers = []
        for q in result.questions:
            label = {1: "correct", 2: "wrong", 3: "unanswered"}.get(q.correct_result, "unknown")
            answers.append({
                "question_id": q.question_id,
                "seqence": q.seqence,
                "type": q.type,
                "result": label,
                "reason": q.reason,
                "crop_url": q.crop_url,
            })

        total = sum(1 for a in answers if a["result"] == "correct")

        # 本路径（correct_edu 上传会话）无学生身份（无 roster 匹配），
        # StudentSubmission 仅作图片/结果工件记录，不入 StudentAnswer 学情；
        # 需要入学情的判卷走 ocr_tasks 批量管线（grading_center.save_batch）。
        # Save to DB
        sub_id = uuid.uuid4().hex[:16]
        db = next(get_db())
        try:
            db.add(StudentSubmission(
                submission_id=sub_id,
                exam_id=exam_id or None,
                class_id=class_id or "",
                student_name="",
                original_image="",
                graded_image="",
                answers_json=json.dumps(answers, ensure_ascii=False),
                total_score=total,
                graded_at=datetime.utcnow(),
            ))
            db.commit()
        finally:
            db.close()

        return {
            "success": True,
            "submission_id": sub_id,
            "total_score": total,
            "questions": answers,
            "stat_result": result.stat_result,
        }

    # ═══════════════════════════════════════════════════════════════
    # 向后兼容
    # ═══════════════════════════════════════════════════════════════

    async def recognize_answer_sheet(self, image_data: bytes) -> Dict:
        """答题卡识别 — 保持旧接口兼容"""
        if not self.enabled:
            return self._not_configured()

        result = await self._call_doc_analysis(image_data)
        if result.get("success"):
            parsed = self._parse_answer_sheet_from_text(result)
            if parsed.get("success") and not parsed.get("is_partial"):
                parsed["provider"] = "baidu"
                return parsed

        vision = await self._try_vision_fallback(image_data)
        if vision.get("success"):
            vision["provider"] = "vision"
            return vision

        return {
            "success": True,
            "error": "自动识别效果不佳，请老师手动输入答案",
            "student_id": "unknown", "student_name": "待手动录入",
            "answers": parsed.get("answers", {}) if result.get("success") else {},
            "scores": {}, "total_score": 0, "confidence": 0,
            "raw_text": result.get("raw_text", ""),
            "provider": "manual", "mock": False, "is_partial": True,
            "triage_exhausted": True,
        }

    async def recognize_handwriting(self, image_data: bytes) -> Dict:
        return await self.recognize_answer_sheet(image_data)

    async def recognize_print(self, image_data: bytes) -> Dict:
        return await self.recognize_answer_sheet(image_data)

    async def recognize_table(self, image_data: bytes) -> Dict:
        return await self.recognize_answer_sheet(image_data)

    # ═══════════════════════════════════════════════════════════════
    # Internal: doc_analysis
    # ═══════════════════════════════════════════════════════════════

    async def _call_doc_analysis(self, image_data: bytes) -> Dict:
        """百度 doc_analysis OCR（同步API，但用httpx异步调用）"""
        token = await get_token()
        b64_image = base64.b64encode(image_data).decode("utf-8")

        body = parse.urlencode({
            "image": b64_image,
            "language_type": "CHN_ENG",
            "detect_direction": "true",
            "words_type": "handprint_mix",
            "recg_formula": "true",
        }).encode("utf-8")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{BAIDU_DOC_ANALYSIS_URL}?access_token={token}",
                    content=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                data = resp.json()

            words_result = data.get("words_result", [])
            if not words_result:
                err_code = data.get("error_code")
                err_msg = data.get("error_msg", "")
                return {
                    "success": False,
                    "error": f"百度OCR: {err_msg}" if err_code else "未识别到文本",
                    "provider": "baidu",
                }

            raw_text = " ".join(item.get("words", "") for item in words_result)
            return {
                "success": True, "data": data, "raw_text": raw_text,
                "confidence": 0.9, "provider": "baidu",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "baidu"}

    # ═══════════════════════════════════════════════════════════════
    # Internal: Vision fallback
    # ═══════════════════════════════════════════════════════════════

    async def _try_vision_fallback(self, image_data: bytes) -> Dict:
        try:
            from app.services.llm_service import llm_service
            b64 = base64.b64encode(image_data).decode("utf-8")
            result = llm_service.analyze_paper_with_vision(
                image_data=b64, paper_type="mixed"
            )
            if result.get("success") and result.get("questions"):
                answers = {}
                for q in result["questions"]:
                    num = str(q.get("number", ""))
                    ans = q.get("student_answer", q.get("correct_answer", ""))
                    if num and ans:
                        answers[num] = str(ans).strip().upper()
                return {
                    "success": True,
                    "student_id": result.get("student_id", "unknown"),
                    "student_name": result.get("student_name", "待识别"),
                    "answers": answers,
                    "scores": {k: 6 for k in answers},
                    "total_score": len(answers) * 6,
                    "confidence": 0.8,
                    "raw_text": result.get("raw_text", ""),
                    "mock": False,
                }
            return {"success": False, "error": result.get("error", "Vision fallback failed")}
        except Exception as e:
            return {"success": False, "error": f"Vision fallback error: {str(e)}"}

    # ═══════════════════════════════════════════════════════════════
    # Internal: helpers
    # ═══════════════════════════════════════════════════════════════

    async def _pdf_page_to_image(self, pdf_data: bytes, page_num: int = 0, dpi: int = 150) -> bytes:
        """PDF page → PNG bytes (PyMuPDF)"""
        import fitz
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        pix = doc[page_num].get_pixmap(dpi=dpi)
        img = pix.tobytes("png")
        doc.close()
        return img

    async def _file_to_pages(self, file_data: bytes, mime_type: str, dpi: int = 150) -> list[bytes]:
        """Convert file to list of page images."""
        if mime_type == "application/pdf":
            import fitz
            doc = fitz.open(stream=file_data, filetype="pdf")
            pages = []
            for i in range(doc.page_count):
                pix = doc[i].get_pixmap(dpi=dpi)
                pages.append(pix.tobytes("png"))
            doc.close()
            return pages
        else:
            return [file_data]

    async def _llm_structure(self, text: str, formula_hint: str = "") -> list[dict]:
        """LLM parsing: raw text → structured question list"""
        from app.services.llm_service import llm_service

        hint_block = f"化学式参考（LaTeX格式）:\n{formula_hint}" if formula_hint else ""

        prompt = f"""你是高中化学教研员。请将以下试卷文本提取为结构化题目JSON数组。
文本中可能有题目正文、解析、答案混杂在一起。请只提取题目本身（忽略纯解析片段）。
每道题必须含: number(题号), content, answer, analysis(不超过100字), knowledge_points, difficulty, question_type。
只返回JSON数组。

{hint_block}

试卷文本:
{text[:15000]}"""

        try:
            result = llm_service.generate_text(
                prompt=prompt,
                system_prompt="只返回JSON数组，不要其他文字。",
                temperature=0.2, max_tokens=8192,
            )
            if result.get("success"):
                content = result["content"]
                m = re.search(r'\[[\s\S]*\]', content)
                if m:
                    return json.loads(m.group())
        except Exception as e:
            logger.error("LLM structuring failed: %s", e)
        return []

    # ═══════════════════════════════════════════════════════════════
    # Internal: answer sheet parsing (kept from old code, sync, fine)
    # ═══════════════════════════════════════════════════════════════

    def _parse_answer_sheet_from_text(self, ocr_result: Dict) -> Dict:
        raw_text = ocr_result.get("raw_text", "") or ""
        if not raw_text or len(raw_text) < 10:
            return {
                "success": True, "error": "未识别到有效文本",
                "student_id": "unknown", "student_name": "待识别",
                "answers": {}, "scores": {}, "total_score": 0,
                "confidence": 0, "raw_text": raw_text,
                "provider": ocr_result.get("provider", "baidu"),
                "mock": False, "is_partial": True,
            }

        student_id = self._extract_student_id(raw_text)
        answers = self._extract_answers(raw_text)

        return {
            "success": True,
            "student_id": student_id or "unknown",
            "student_name": "学生" if student_id else "待识别",
            "answers": answers if answers else {},
            "scores": {k: 6 for k in answers} if answers else {},
            "total_score": len(answers) * 6 if answers else 0,
            "confidence": ocr_result.get("confidence", 0.85),
            "raw_text": raw_text,
            "provider": ocr_result.get("provider", "baidu"),
            "mock": False,
            "is_partial": not (student_id and answers),
        }

    def _extract_student_id(self, text: str) -> Optional[str]:
        match = re.search(r'[2][0][2][4-9][0-9]{4,7}', text)
        return match.group(0) if match else None

    def _extract_answers(self, text: str) -> Dict[str, str]:
        answers = {}
        for m in re.finditer(r'([1-9]|1[0-5])[.、]?\s*([A-D])', text):
            answers[m.group(1)] = m.group(2).upper()
        return answers

    def _not_configured(self) -> Dict:
        return {
            "success": False,
            "error": "OCR 服务未配置，请设置 BAIDU_OCR_API_KEY 和 BAIDU_OCR_SECRET_KEY",
            "student_id": "", "student_name": "",
            "answers": {}, "scores": {}, "total_score": 0,
            "confidence": 0, "provider": "none",
        }


class TencentOCRService(OCRService):
    pass


class OCRParser:
    @staticmethod
    def parse_handwriting_result(ocr_result: Dict) -> List[Dict]:
        return [{"text": t.get("DetectedText", ""),
                 "confidence": t.get("Confidence", 0),
                 "bbox": t.get("Polygon", [])}
                for t in ocr_result.get("TextDetections", [])]

    @staticmethod
    def parse_answer_sheet(ocr_result: Dict, question_count: int = 10) -> Dict:
        return {k: ocr_result.get(k, "") if k != "confidence" else ocr_result.get(k, 0)
                for k in ("student_id", "student_name", "answers", "scores", "total_score", "confidence")}

    @staticmethod
    def validate_answer_sheet(answers: Dict, question_count: int = 10) -> Tuple[bool, List[str]]:
        errors = []
        if not answers.get("student_id"):
            errors.append("缺少学号")
        if not answers.get("student_name"):
            errors.append("缺少姓名")
        for q_num in range(1, question_count + 1):
            if str(q_num) not in answers.get("answers", {}):
                errors.append(f"缺少第{q_num}题答案")
        return len(errors) == 0, errors


ocr_service = TencentOCRService()
ocr_parser = OCRParser()
