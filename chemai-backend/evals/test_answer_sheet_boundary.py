"""Boundary evals for Answer Sheet Grading feature.

Test edge cases: oversize upload, empty files, OCR failures.
"""
import pytest


class TestGradingBoundary:
    """Edge cases for LLM grading."""

    def test_empty_student_answer(self):
        """Empty answer should be compared correctly."""
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("", "B") == False
        assert _compare_answers("A", "") == False
        assert _compare_answers("", "") == False

    def test_grade_empty_ocr_returns_error(self):
        """Tasks with no ocr_result should return error."""
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime

        task = OCRTask(
            task_id="test_empty_ocr", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            ocr_result=None, created_at=datetime.utcnow(),
        )
        results = grade_batch_answers([task], correct_answers=[])
        assert results[0].get("error") == "No OCR answers found"
