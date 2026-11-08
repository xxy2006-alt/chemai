"""
chemistry-parser Skill Handler
MinerU文档解析 Skill，调用 MinerU v3.0.0 进行 PDF/Word/图片化学题目提取
支持智能选择最佳解析方式（OCR/MinerU/视觉模型）
"""
import sys
import os
import base64
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills._templates.base_handler import BaseSkillHandler  # noqa: E402

# 导入 MinerU 客户端
from .mineru_client import MinerUClient, MinerUNotFoundError, get_mineru_client  # noqa: E402

# 导入统一文档解析服务
from app.services.document_parse_service import DocumentParseService  # noqa: E402


class ParserHandler(BaseSkillHandler):
    """chemistry-parser Skill Handler - 支持智能文档解析"""

    def __init__(self, mineru_root: Optional[str] = None):
        """
        初始化 Parser Handler

        Args:
            mineru_root: MinerU 安装路径，默认自动查找
        """
        super().__init__()
        try:
            self.mineru = MinerUClient(mineru_root) if mineru_root else get_mineru_client()
            self.mineru_available = True
        except MinerUNotFoundError as e:
            self.mineru = None
            self.mineru_available = False
            self.mineru_error = str(e)

        # 初始化统一文档解析服务
        self._doc_service = None

    @property
    def doc_service(self) -> DocumentParseService:
        """懒加载统一文档解析服务"""
        if self._doc_service is None:
            self._doc_service = DocumentParseService()
        return self._doc_service

    # ==================== 智能文档解析 ====================

    def smart_parse_document(
        self,
        file_data: bytes,
        file_type: str = "auto",
        task: str = "extract_questions"
    ) -> Dict[str, Any]:
        """
        智能文档解析 - 根据文件类型和任务自动选择最佳解析方式

        Args:
            file_data: 文件内容（字节）
            file_type: 文件类型 ("auto", "pdf", "image")
            task: 任务类型
                - "extract_questions": 提取题目（用于上传真题）
                - "answer_sheet": 识别答题卡
                - "chemical_formula": 提取化学式

        Returns:
            {
                "success": bool,
                "provider": str,  # "ocr", "mineru", "vision"
                "result": {...},
                "fallback_used": bool
            }
        """
        return self.doc_service.parse_document(
            file_data=file_data,
            file_type=file_type,
            source="auto"
        )

    def import_question_bank(
        self,
        file_data: bytes,
        file_type: str = "auto",
        source_name: str = "老师导入",
        year: int = 2024,
        region: str = "通用"
    ) -> Dict[str, Any]:
        """
        上传真题到题库 - 智能识别 + 导入

        流程:
        1. 智能解析（自动选择OCR/MinerU/视觉模型）
        2. 识别题目
        3. 返回待确认的题目列表

        Args:
            file_data: 文件内容
            file_type: 文件类型 ("auto", "pdf", "image")
            source_name: 来源名称
            year: 年份
            region: 地区

        Returns:
            {
                "success": bool,
                "provider": str,
                "questions": [...],  # 识别到的题目
                "preview": {...}  # 预览信息
            }
        """
        # 检测文件类型
        if file_type == "auto":
            file_type = self._detect_file_type(file_data)

        # 根据文件类型选择解析策略
        if file_type == "pdf":
            # PDF使用MinerU
            parse_result = self._parse_pdf_for_questions(file_data)
            provider = "mineru"
        else:
            # 图片优先用OCR，失败降级视觉模型
            parse_result = self._parse_image_for_questions(file_data)
            provider = parse_result.get("provider", "ocr")

        if not parse_result.get("success"):
            return {
                "success": False,
                "error": parse_result.get("error", "解析失败"),
                "provider": provider
            }

        # 从解析结果中提取题目
        md_content = parse_result.get("md_content", "")
        questions = self._extract_questions_from_text(md_content, year, region)

        return {
            "success": True,
            "provider": provider,
            "source_name": source_name,
            "year": year,
            "region": region,
            "question_count": len(questions),
            "questions": questions,
            "preview": {
                "md_content": md_content[:500] if md_content else "",
                "image_count": len(parse_result.get("images", []))
            }
        }

    def _detect_file_type(self, file_data: bytes) -> str:
        """检测文件类型"""
        if file_data[:4] == b'%PDF':
            return "pdf"
        if file_data[:3] == b'\xFF\xD8\xFF':
            return "image"
        if file_data[:4] == b'\x89PNG':
            return "image"
        return "image"

    def _parse_pdf_for_questions(self, file_data: bytes) -> Dict[str, Any]:
        """PDF解析 - 使用MinerU"""
        if not self.mineru_available:
            return {"success": False, "error": f"MinerU不可用: {self.mineru_error}"}

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            result = self.mineru.parse_by_cli(
                file_path=tmp_path,
                lang="ch",
                backend="hybrid-auto-engine"
            )
            return {
                "success": result.success,
                "md_content": result.md_content,
                "questions": result.questions or [],
                "images": result.images or [],
                "formulas": result.formulas or []
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _parse_image_for_questions(self, file_data: bytes) -> Dict[str, Any]:
        """图片解析 - OCR优先，降级到视觉模型"""
        from app.services.ocr_service import OCRService
        from app.services.llm_service import LLMService

        ocr_service = OCRService()
        llm_service = LLMService()

        # Step 1: 尝试OCR
        ocr_result = ocr_service.recognize_answer_sheet(file_data)

        if ocr_result.get("success") and not ocr_result.get("is_partial"):
            return {
                "success": True,
                "provider": "ocr",
                "md_content": ocr_result.get("raw_text", ""),
                "questions": [],
                "images": []
            }

        # Step 2: OCR失败，尝试视觉模型
        b64_image = base64.b64encode(file_data).decode('utf-8')
        vision_result = llm_service.analyze_paper_with_vision(
            image_data=b64_image,
            paper_type="mixed"
        )

        if vision_result.get("success"):
            return {
                "success": True,
                "provider": "vision",
                "md_content": vision_result.get("raw_text", ""),
                "questions": vision_result.get("questions", []),
                "images": []
            }

        # Step 3: 都失败，返回OCR原始结果
        return {
            "success": ocr_result.get("success", False),
            "provider": "ocr-partial",
            "md_content": ocr_result.get("raw_text", ""),
            "questions": [],
            "images": [],
            "error": "识别置信度较低"
        }

    def _extract_questions_from_text(
        self,
        text: str,
        year: int,
        region: str
    ) -> List[Dict[str, Any]]:
        """从文本中提取题目"""
        questions = []
        lines = text.split('\n')

        current_question = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测题目开始 (如 "1.", "2.", "第1题", "1、")
            import re
            q_match = re.match(r'^(?:第)?(\d+)[题\.、]\s*(.*)', line)
            if q_match:
                if current_question:
                    questions.append(current_question)
                q_num = q_match.group(1)
                q_content = q_match.group(2) if q_match.group(2) else ""
                current_question = {
                    "number": q_num,
                    "content": q_content,
                    "options": [],
                    "answer": None,
                    "year": year,
                    "region": region,
                    "source": "OCR识别"
                }
            elif current_question:
                # 检测选项 (A. B. C. D. 或 A、 B、 C、 D、)
                opt_match = re.match(r'^([A-D])[题\.、:]\s*(.*)', line)
                if opt_match:
                    current_question["options"].append({
                        "label": opt_match.group(1),
                        "content": opt_match.group(2)
                    })
                elif line.startswith("答案"):
                    ans_match = re.search(r'[答案][:：]\s*([A-Da-d\d]+)', line)
                    if ans_match:
                        current_question["answer"] = ans_match.group(1).upper()
                else:
                    current_question["content"] += "\n" + line

        if current_question:
            questions.append(current_question)

        return questions

    # ==================== 文档解析 ====================

    def parse_pdf_questions(
        self,
        file_path: str,
        lang: str = "ch",
        start_page: int = 0,
        end_page: Optional[int] = None,
        backend: str = "hybrid-auto-engine",
    ) -> Dict[str, Any]:
        """
        解析 PDF 文档提取化学题目

        Args:
            file_path: PDF 文件路径
            lang: 语言
            start_page: 起始页
            end_page: 结束页
            backend: MinerU 后端

        Returns:
            解析结果包含 md_content, questions 等
        """
        if not self.mineru_available:
            return {
                "success": False,
                "message": f"MinerU不可用: {self.mineru_error}",
                "mineru_available": False,
            }

        try:
            result = self.mineru.parse_by_cli(
                file_path=file_path,
                lang=lang,
                backend=backend,
                start_page=start_page,
                end_page=end_page,
            )

            return {
                "success": result.success,
                "questions": result.questions or [],
                "question_count": result.question_count,
                "md_content": result.md_content,
                "middle_json": result.middle_json,
                "images": result.images or [],
                "formulas": result.formulas or [],
                "output_dir": result.output_dir,
                "error": result.error,
                "mineru_available": True,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"PDF解析失败: {str(e)}",
                "mineru_available": self.mineru_available,
            }

    def parse_docx_questions(
        self,
        file_path: str,
        lang: str = "ch",
        backend: str = "hybrid-auto-engine",
    ) -> Dict[str, Any]:
        """
        解析 Word 文档提取化学题目

        Args:
            file_path: Word 文件路径
            lang: 语言
            backend: MinerU 后端

        Returns:
            解析结果
        """
        # Word 文档也通过 MinerU 解析
        return self.parse_pdf_questions(file_path, lang, backend=backend)

    def parse_image_chemical(
        self,
        file_path: str,
        lang: str = "ch",
        backend: str = "hybrid-auto-engine",
    ) -> Dict[str, Any]:
        """
        解析图片提取化学公式和反应

        Args:
            file_path: 图片路径
            lang: 语言
            backend: MinerU 后端

        Returns:
            识别结果
        """
        if not self.mineru_available:
            return {
                "success": False,
                "message": f"MinerU不可用: {self.mineru_error}",
                "mineru_available": False,
            }

        try:
            result = self.mineru.parse_by_cli(
                file_path=file_path,
                lang=lang,
                backend=backend,
            )

            return {
                "success": result.success,
                "content": result.md_content,
                "images": result.images or [],
                "formulas": result.formulas or [],
                "output_dir": result.output_dir,
                "error": result.error,
                "mineru_available": True,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"图片解析失败: {str(e)}",
                "mineru_available": self.mineru_available,
            }

    # ==================== 化学公式处理 ====================

    def standardize_chemical_formula(self, formula: str) -> Dict[str, Any]:
        """
        标准化化学公式

        Args:
            formula: 化学公式

        Returns:
            标准化后的公式
        """
        import re

        # 常见化学式符号替换
        replacements = {
            "₂": "2",
            "₃": "3",
            "₄": "4",
            "₀": "0",
            "₁": "1",
            "₅": "5",
            "₆": "6",
            "₇": "7",
            "₈": "8",
            "₉": "9",
            "△": "Δ",
            "→": "->",
        }

        standardized = formula
        for old, new in replacements.items():
            standardized = standardized.replace(old, new)

        # 验证括号匹配
        if standardized.count("(") != standardized.count(")"):
            return {
                "success": False,
                "original": formula,
                "standardized": standardized,
                "warning": "括号不匹配",
            }

        # 验证化学式基本格式（字母+数字组合）
        if not re.search(r"[A-Z][a-z]?", standardized):
            return {
                "success": False,
                "original": formula,
                "standardized": standardized,
                "warning": "未识别到有效化学式",
            }

        return {
            "success": True,
            "original": formula,
            "standardized": standardized,
        }

    def classify_question_type(self, question_text: str) -> Dict[str, Any]:
        """
        分类题目类型

        Args:
            question_text: 题目文本

        Returns:
            题目类型
        """
        text = question_text.strip()

        # 填空题特征
        if "____" in text or "______" in text or "_____" in text:
            return {"type": "fill-blank", "confidence": 0.9, "text": text}

        # 简答题特征
        short_answer_keywords = ["解释", "说明", "原因", "如何", "为什么", "描述", "阐述"]
        if any(kw in text for kw in short_answer_keywords) and len(text) < 500:
            return {"type": "short-answer", "confidence": 0.8, "text": text}

        # 计算题特征
        calc_keywords = ["计算", "求", "证明", "若", "已知", "当", "若将"]
        if any(kw in text for kw in calc_keywords):
            return {"type": "calculation", "confidence": 0.85, "text": text}

        # 选择题（默认）
        if text.startswith(("A.", "B.", "C.", "D.", "A、", "B、", "C、", "D、")):
            return {"type": "choice", "confidence": 0.95, "text": text}

        return {"type": "unknown", "confidence": 0.3, "text": text}

    def extract_answer_from_ocr(self, ocr_content: str, question_type: str = "auto") -> Dict[str, Any]:
        """
        从 OCR 内容中提取答案

        Args:
            ocr_content: OCR 原始内容
            question_type: 题目类型

        Returns:
            提取的答案
        """
        import re

        lines = [line.strip() for line in ocr_content.split("\n") if line.strip()]

        if question_type == "auto":
            # 自动识别题目类型
            type_confidence = self.classify_question_type("\n".join(lines[:5]))
            question_type = type_confidence["type"]

        # 提取答案模式
        answers = []

        # 模式1: 答案在"答案："或"答："后面
        for line in lines:
            if line.startswith("答案：") or line.startswith("答："):
                answers.append(line[line.index("：") + 1 :].strip())
            elif line.startswith("答案:") or line.startswith("答:"):
                answers.append(line[line.index(":") + 1 :].strip())

        # 模式2: 填空题下划线后的内容
        if question_type == "fill-blank":
            for line in lines:
                blanks = re.findall(r"_+([^_\n]+)", line)
                answers.extend(blanks)

        return {
            "question_type": question_type,
            "answers": answers,
            "raw_content": ocr_content,
        }

    def batch_parse_documents(
        self,
        directory_path: str,
        file_pattern: str = "*.pdf",
        lang: str = "ch",
        backend: str = "hybrid-auto-engine",
    ) -> Dict[str, Any]:
        """
        批量解析目录下的文档

        Args:
            directory_path: 目录路径
            file_pattern: 文件匹配模式
            lang: 语言
            backend: MinerU 后端

        Returns:
            批量解析结果
        """
        dir_path = Path(directory_path)
        if not dir_path.exists() or not dir_path.is_dir():
            return {"success": False, "message": f"目录不存在: {directory_path}"}

        files = list(dir_path.glob(file_pattern))
        if not files:
            # 尝试其他常见格式
            for pattern in ["*.docx", "*.png", "*.jpg"]:
                files = list(dir_path.glob(pattern))
                if files:
                    break

        if not files:
            return {"success": False, "message": f"未找到匹配的文件: {file_pattern}"}

        results = []
        for file_path in files:
            try:
                result = self.parse_pdf_questions(str(file_path), lang, backend=backend)
                results.append(
                    {
                        "file": str(file_path.name),
                        "success": result.get("success", False),
                        "question_count": result.get("question_count", 0),
                        "error": result.get("message") or result.get("error"),
                    }
                )
            except Exception as e:
                results.append({"file": str(file_path.name), "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r["success"])
        return {
            "success": True,
            "total": len(results),
            "success_count": success_count,
            "failed_count": len(results) - success_count,
            "results": results,
        }

    def validate_parsed_result(self, parsed_content: str, check_formulas: bool = True) -> Dict[str, Any]:
        """
        验证解析结果

        Args:
            parsed_content: 解析的内容
            check_formulas: 是否检查化学式

        Returns:
            验证结果
        """
        import re

        issues = []
        warnings = []

        # None/空输入归一化：短内容记 issue，但不让 None 冲进后续正则
        text = parsed_content or ""
        if not text or len(text.strip()) < 10:
            issues.append("内容过短，可能解析失败")

        # 检查化学式格式
        found_formulas = []
        if check_formulas:
            # 查找疑似化学式的模式
            chemical_patterns = [
                r"[A-Z][a-z]?\d*",  # 如 H2, NaCl
                r"[A-Z][a-z]?\([A-Za-z0-9]+\)\d*",  # 如 Ca(OH)2
            ]

            for pattern in chemical_patterns:
                found_formulas.extend(re.findall(pattern, text))

            if not found_formulas:
                warnings.append("未识别到化学式")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "content_length": len(text),
            "formulas_found": len(set(found_formulas)),
        }

    def get_mineru_status(self) -> Dict[str, Any]:
        """
        获取 MinerU 状态

        Returns:
            MinerU 可用性状态
        """
        return {
            "mineru_available": self.mineru_available,
            "error": getattr(self, "mineru_error", None),
        }


# ==================== Tool 入口函数 ====================


def parse_pdf_questions(
    file_path: str,
    lang: str = "ch",
    start_page: int = 0,
    end_page: Optional[int] = None,
    backend: str = "hybrid-auto-engine",
) -> Dict:
    """Tool: 解析 PDF 文档提取化学题目"""
    handler = ParserHandler()
    return handler.parse_pdf_questions(file_path, lang, start_page, end_page, backend)


def parse_docx_questions(file_path: str, lang: str = "ch") -> Dict:
    """Tool: 解析 Word 文档提取化学题目"""
    handler = ParserHandler()
    return handler.parse_docx_questions(file_path, lang)


def parse_image_chemical(file_path: str, lang: str = "ch") -> Dict:
    """Tool: 解析图片提取化学公式"""
    handler = ParserHandler()
    return handler.parse_image_chemical(file_path, lang)


def standardize_chemical_formula(formula: str) -> Dict:
    """Tool: 标准化化学公式"""
    handler = ParserHandler()
    return handler.standardize_chemical_formula(formula)


def classify_question_type(question_text: str) -> Dict:
    """Tool: 分类题目类型"""
    handler = ParserHandler()
    return handler.classify_question_type(question_text)


def extract_answer_from_ocr(ocr_content: str, question_type: str = "auto") -> Dict:
    """Tool: 从 OCR 内容提取答案"""
    handler = ParserHandler()
    return handler.extract_answer_from_ocr(ocr_content, question_type)


def batch_parse_documents(directory_path: str, file_pattern: str = "*.pdf", lang: str = "ch") -> Dict:
    """Tool: 批量解析文档"""
    handler = ParserHandler()
    return handler.batch_parse_documents(directory_path, file_pattern, lang)


def validate_parsed_result(parsed_content: str, check_formulas: bool = True) -> Dict:
    """Tool: 验证解析结果"""
    handler = ParserHandler()
    return handler.validate_parsed_result(parsed_content, check_formulas)


def get_mineru_status() -> Dict:
    """Tool: 获取 MinerU 状态"""
    handler = ParserHandler()
    return handler.get_mineru_status()


def smart_parse_document(file_data: str, file_type: str = "auto", task: str = "extract_questions") -> Dict:
    """
    Tool: 智能文档解析 - 自动选择最佳解析方式

    Args:
        file_data: 文件内容（base64编码）
        file_type: 文件类型 ("auto", "pdf", "image")
        task: 任务类型 ("extract_questions", "answer_sheet", "chemical_formula")

    Returns:
        智能解析结果
    """
    import base64
    handler = ParserHandler()
    try:
        decoded_data = base64.b64decode(file_data)
    except Exception:
        return {"success": False, "error": "文件数据解码失败"}
    return handler.smart_parse_document(decoded_data, file_type, task)


def import_question_bank(
    file_data: str,
    file_type: str = "auto",
    source_name: str = "老师导入",
    year: int = 2024,
    region: str = "通用"
) -> Dict:
    """
    Tool: 上传真题到题库 - 智能识别 + 导入

    Args:
        file_data: 文件内容（base64编码）
        file_type: 文件类型 ("auto", "pdf", "image")
        source_name: 来源名称
        year: 年份
        region: 地区

    Returns:
        识别结果，包含题目列表
    """
    import base64
    handler = ParserHandler()
    try:
        decoded_data = base64.b64decode(file_data)
    except Exception:
        return {"success": False, "error": "文件数据解码失败"}
    return handler.import_question_bank(decoded_data, file_type, source_name, year, region)


def get_services_status() -> Dict:
    """Tool: 获取所有解析服务的可用性状态"""
    from app.services.document_parse_service import get_document_parse_service
    service = get_document_parse_service()
    return service.check_services_status()


# ==================== 主入口 ====================

if __name__ == "__main__":

    def test():
        handler = ParserHandler()

        # 检查 MinerU 状态
        status = handler.get_mineru_status()
        print(f"MinerU 状态: {status}")

        # 测试化学式标准化
        result = handler.standardize_chemical_formula("Ca(OH)2")
        print(f"标准化测试: {result}")

        # 测试题目分类
        result = handler.classify_question_type("实验室制取氧气时，试管口应____倾斜。")
        print(f"题目分类: {result}")

        result = handler.classify_question_type("解释铁在潮湿空气中生锈的原因。")
        print(f"简答分类: {result}")

        # 测试验证
        result = handler.validate_parsed_result("实验室制取氧气时，试管口应向下倾斜。")
        print(f"验证测试: {result}")

    test()
