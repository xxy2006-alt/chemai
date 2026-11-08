"""a4 回归测试 — 低置信/漏检单卡视觉复核。

覆盖调度器视觉复核的两个纯函数 seam：
- `_needs_vision_review`：什么情况下触发（空作答 / 学生信息全空 / 题号断层）
- `_vision_review_answers`：用 mock 视觉结果补齐缺失题号、不覆盖已有结果
"""
import base64

from app.scheduler.ocr_scheduler import _needs_vision_review, _vision_review_answers


class TestNeedsVisionReview:
    def test_empty_answers_triggers(self):
        assert _needs_vision_review({"student_id": "1", "student_name": "张", "answers": []}) is True

    def test_no_student_info_triggers(self):
        res = {"student_id": "", "student_name": "", "answers": [{"q_number": 1, "answer": "A"}]}
        assert _needs_vision_review(res) is True

    def test_qnumber_gap_triggers(self):
        """楷体样本 9-12 整行漏检：answers 1..8,13..15 → 题号断层 → 触发。"""
        answers = [{"q_number": n, "answer": "A"} for n in [1, 2, 3, 4, 5, 6, 7, 8, 13, 14, 15]]
        assert _needs_vision_review({"student_id": "1", "student_name": "张", "answers": answers}) is True

    def test_contiguous_no_trigger(self):
        answers = [{"q_number": n, "answer": "A"} for n in [1, 2, 3, 4, 5]]
        assert _needs_vision_review({"student_id": "1", "student_name": "张", "answers": answers}) is False


class TestVisionReviewAnswers:
    def test_merges_missing_answers(self, tmp_path, monkeypatch):
        """视觉复核补回漏检题号，已有作答不被覆盖。"""
        from app.services.llm_service import llm_service

        img = tmp_path / "sheet.png"
        img.write_bytes(b"\x89PNG fake image")
        extract = {
            "student_id": "2026101035", "student_name": "张伟",
            "answers": [{"q_number": 8, "type": "choice", "answer": "B", "confidence": 0.7}],
        }
        vision = {
            "success": True,
            "student_id": "2026101035", "student_name": "张伟",
            "questions": [
                {"number": "9", "student_answer": "A"},
                {"number": "10", "student_answer": "C"},
                {"number": "11", "student_answer": "B"},
                {"number": "12", "student_answer": "D"},
            ],
        }
        seen = {}
        def fake_vision(image_data, paper_type="answer_sheet"):
            seen["paper_type"] = paper_type
            seen["image_bytes"] = base64.b64decode(image_data)
            return vision
        monkeypatch.setattr(llm_service, "analyze_paper_with_vision", fake_vision)

        merged = _vision_review_answers(str(img), extract)
        assert seen["paper_type"] == "answer_sheet"
        assert seen["image_bytes"] == b"\x89PNG fake image"
        assert merged["vision_reviewed"] is True
        got = {a["q_number"]: a["answer"] for a in merged["answers"]}
        assert got == {8: "B", 9: "A", 10: "C", 11: "B", 12: "D"}
        # 已有学生信息不覆盖
        assert merged["student_id"] == "2026101035"
        assert merged["student_name"] == "张伟"

    def test_fill_empty_student_info(self, tmp_path, monkeypatch):
        from app.services.llm_service import llm_service

        img = tmp_path / "sheet2.png"
        img.write_bytes(b"x")
        extract = {"student_id": "", "student_name": "", "answers": [{"q_number": 1, "answer": "A"}]}
        monkeypatch.setattr(llm_service, "analyze_paper_with_vision", lambda image_data, paper_type="answer_sheet": {
            "success": True, "student_id": "2026101055", "student_name": "李四",
            "questions": [{"number": "1", "student_answer": "A"}],
        })
        merged = _vision_review_answers(str(img), extract)
        assert merged["student_id"] == "2026101055"
        assert merged["student_name"] == "李四"

    def test_failure_keeps_extract_result(self, tmp_path, monkeypatch):
        from app.services.llm_service import llm_service

        img = tmp_path / "sheet3.png"
        img.write_bytes(b"x")
        extract = {"student_id": "", "student_name": "", "answers": [], "error": None}
        monkeypatch.setattr(llm_service, "analyze_paper_with_vision", lambda image_data, paper_type="answer_sheet": {
            "success": False, "error": "无可用视觉模型",
        })
        merged = _vision_review_answers(str(img), extract)
        # 复核失败不降级已提取结果
        assert merged == extract
