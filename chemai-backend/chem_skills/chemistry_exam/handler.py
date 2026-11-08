"""
chemistry-exam Skill Handler
AI出题与安全审核 Skill 的 Tool 实现，调用 ChemAI FastAPI 后端
"""
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import quote

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills._templates.base_handler import BaseSkillHandler  # noqa: E402


class ExamHandler(BaseSkillHandler):
    """AI出题与安全审核 Skill Handler"""

    # ==================== 出题 ====================

    def exam_generate(
        self,
        knowledge_points: List[str],
        difficulty: str = "medium",
        quantity: int = 10,
        exam_type: str = "单元练习",
    ) -> Dict[str, Any]:
        """
        使用AI生成化学练习题目

        Args:
            knowledge_points: 知识点列表
            difficulty: 难度 (easy/medium/hard/competition)
            quantity: 生成数量
            exam_type: 考试类型

        Returns:
            QuestionGenerateResponse: 题目列表 + 审核报告
        """
        return self.post(
            "/api/question/generate",
            json_data={
                "knowledge_points": knowledge_points,
                "difficulty": difficulty,
                "quantity": quantity,
                "exam_type": exam_type,
            },
        )

    def exam_audit(
        self, question_content: str, options: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        对单道题目进行四维安全审核

        Args:
            question_content: 题目内容
            options: 选项列表（可选）

        Returns:
            AuditReport: 审核报告
        """
        return self.post(
            "/api/question/audit",
            json_data={
                "question_content": question_content,
                "options": options or [],
            },
        )

    # ==================== 历年真题 ====================

    def exam_search_historical(
        self,
        source: Optional[str] = None,
        year: Optional[int] = None,
        difficulty: Optional[str] = None,
        knowledge_point: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        检索历年真题库

        Args:
            source: 来源筛选
            year: 年份筛选
            difficulty: 难度筛选
            knowledge_point: 知识点筛选
            keyword: 关键词搜索

        Returns:
            符合条件的真题列表
        """
        params = {}
        if source:
            params["source"] = source
        if year:
            params["year"] = year
        if difficulty:
            params["difficulty"] = difficulty
        if knowledge_point:
            params["knowledge_point"] = knowledge_point
        if keyword:
            params["keyword"] = keyword

        return self.get("/api/question/historical", params=params)

    def exam_get_exam_sets(self) -> Dict[str, Any]:
        """
        获取真题集列表

        Returns:
            真题集列表（不含题目详情）
        """
        return self.get("/api/question/exam-sets")

    def exam_get_exam_set_detail(self, source: str) -> Dict[str, Any]:
        """
        获取指定真题集的题目详情

        Args:
            source: 真题集名称（如"全国卷2024"）

        Returns:
            真题集详情 + 题目列表
        """
        # URL 编码：真题集名可能含 "/" 等路径字符，整段编码防路径撕裂
        encoded_source = quote(str(source), safe="")
        return self.get(f"/api/question/exam-sets/{encoded_source}")

    def exam_find_similar(
        self,
        knowledge_points: List[str],
        difficulty: str = "medium",
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        查找与指定知识点相似的历年真题

        Args:
            knowledge_points: 知识点列表
            difficulty: 难度
            limit: 返回数量

        Returns:
            相似真题列表
        """
        return self.post(
            "/api/question/similar",
            json_data={
                "knowledge_points": knowledge_points,
                "difficulty": difficulty,
                "limit": limit,
            },
        )

    # ==================== 手动选题 ====================

    def exam_manual_select(self, exam_ids: List[str]) -> List[Dict[str, Any]]:
        """
        手动选题（教师从历年真题库选择）+ AI安全审核

        Args:
            exam_ids: 历年真题ID列表

        Returns:
            审核后的题目列表
        """
        return self.post(
            "/api/question/manual/select",
            json_data={"exam_ids": exam_ids},
        )

    # ==================== 导入题目 ====================

    def exam_import(
        self,
        source_name: str,
        year: int,
        questions: List[Dict],
        region: str = "老师导入",
    ) -> Dict[str, Any]:
        """
        老师自助导入题目到真题库

        Args:
            source_name: 来源名称
            year: 年份
            questions: 题目列表
            region: 地区

        Returns:
            导入结果
        """
        return self.post(
            "/api/question/import",
            json_data={
                "source_name": source_name,
                "region": region,
                "year": year,
                "questions": questions,
            },
        )

    def exam_import_batch(
        self,
        source_name: str,
        year: int,
        file_content: str,
        region: str = "老师导入",
    ) -> Dict[str, Any]:
        """
        批量导入题目（Base64编码文件）

        Args:
            source_name: 来源名称
            year: 年份
            file_content: Base64编码的文件内容
            region: 地区

        Returns:
            导入结果
        """
        return self.post(
            "/api/question/import/batch",
            json_data={
                "source_name": source_name,
                "region": region,
                "year": year,
                "file_content": file_content,
            },
        )

    def exam_import_ocr(
        self,
        source_name: str,
        year: int,
        file_path: str,
        region: str = "老师导入",
    ) -> Dict[str, Any]:
        """
        通过OCR扫描试卷导入题目

        Args:
            source_name: 来源名称
            year: 年份
            file_path: 试卷文件路径
            region: 地区

        Returns:
            识别结果
        """
        # 注意：OCR导入需要上传文件，这里用 file_path 作为标识
        # 实际实现需要读取文件并转为 Base64
        import base64

        try:
            with open(file_path, "rb") as f:
                file_content = base64.b64encode(f.read()).decode()
        except Exception:
            # 如果文件不存在，返回错误
            return {
                "success": False,
                "message": f"文件不存在: {file_path}",
            }

        return self.post(
            "/api/question/import/ocr",
            json_data={
                "source_name": source_name,
                "region": region,
                "year": year,
                "file_content": file_content,
            },
        )

    # ==================== 化学方程式审核 ====================

    def exam_balance_check(self, equation: str) -> Dict[str, Any]:
        """
        化学方程式配平检查（调用独立审核端点）

        Args:
            equation: 化学方程式

        Returns:
            配平检查结果
        """
        # 使用 exam_audit 来检查含方程式的题目
        result = self.exam_audit(question_content=equation)
        return result


# ==================== Tool 入口函数 ====================
# ChemAI Agent 调用入口


def exam_generate(
    knowledge_points: List[str],
    difficulty: str = "medium",
    quantity: int = 10,
    exam_type: str = "单元练习",
) -> Dict:
    """Tool: 使用AI生成化学练习题目"""
    handler = ExamHandler()
    return handler.exam_generate(knowledge_points, difficulty, quantity, exam_type)


def exam_audit(
    question_content: str, options: Optional[List[str]] = None
) -> Dict:
    """Tool: 对单道题目进行四维安全审核"""
    handler = ExamHandler()
    return handler.exam_audit(question_content, options)


def exam_search_historical(
    source: Optional[str] = None,
    year: Optional[int] = None,
    difficulty: Optional[str] = None,
    knowledge_point: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Dict:
    """Tool: 检索历年真题库"""
    handler = ExamHandler()
    return handler.exam_search_historical(
        source, year, difficulty, knowledge_point, keyword
    )


def exam_get_exam_sets() -> Dict:
    """Tool: 获取真题集列表"""
    handler = ExamHandler()
    return handler.exam_get_exam_sets()


def exam_get_exam_set_detail(source: str) -> Dict:
    """Tool: 获取指定真题集的题目详情"""
    handler = ExamHandler()
    return handler.exam_get_exam_set_detail(source)


def exam_find_similar(
    knowledge_points: List[str],
    difficulty: str = "medium",
    limit: int = 5,
) -> Dict:
    """Tool: 查找相似历年真题"""
    handler = ExamHandler()
    return handler.exam_find_similar(knowledge_points, difficulty, limit)


def exam_manual_select(exam_ids: List[str]) -> List[Dict]:
    """Tool: 手动选题 + AI审核"""
    handler = ExamHandler()
    return handler.exam_manual_select(exam_ids)


def exam_import(
    source_name: str,
    year: int,
    questions: List[Dict],
    region: str = "老师导入",
) -> Dict:
    """Tool: 导入题目"""
    handler = ExamHandler()
    return handler.exam_import(source_name, year, questions, region)


def exam_import_batch(
    source_name: str,
    year: int,
    file_content: str,
    region: str = "老师导入",
) -> Dict:
    """Tool: 批量导入题目"""
    handler = ExamHandler()
    return handler.exam_import_batch(source_name, year, file_content, region)


def exam_import_ocr(
    source_name: str,
    year: int,
    file_path: str,
    region: str = "老师导入",
) -> Dict:
    """Tool: OCR扫描导入"""
    handler = ExamHandler()
    return handler.exam_import_ocr(source_name, year, file_path, region)


def exam_balance_check(equation: str) -> Dict:
    """Tool: 化学方程式配平检查"""
    handler = ExamHandler()
    return handler.exam_balance_check(equation)


# ==================== 主入口 ====================

if __name__ == "__main__":
    def test():
        handler = ExamHandler()
        # 测试真题集列表
        result = handler.exam_get_exam_sets()
        print(f"真题集数量: {result.get('total', 0)}")

    test()
