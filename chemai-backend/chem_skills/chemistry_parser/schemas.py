"""
chemistry-parser Skill Schemas
定义与 MinerU 解析相关的 Pydantic 模型
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ParsedQuestion(BaseModel):
    """解析后的题目"""

    type: str = Field(description="题目类型: fill-blank/short-answer/calculation/choice")
    content: str = Field(description="题目内容")
    answer: Optional[str] = Field(default=None, description="答案")
    formulas: List[str] = Field(default_factory=list, description="包含的化学式")
    page_number: Optional[int] = Field(default=None, description="所在页码")


class ParseResult(BaseModel):
    """解析结果"""

    success: bool = Field(description="是否成功")
    questions: List[ParsedQuestion] = Field(default_factory=list, description="提取的题目列表")
    question_count: int = Field(default=0, description="题目数量")
    md_content: Optional[str] = Field(default=None, description="Markdown 格式内容")
    middle_json: Optional[str] = Field(default=None, description="中间JSON格式")
    images: List[str] = Field(default_factory=list, description="提取的图片路径")
    formulas: List[str] = Field(default_factory=list, description="识别的化学式列表")
    output_dir: Optional[str] = Field(default=None, description="输出目录")
    message: Optional[str] = Field(default=None, description="错误信息")


class FormulaStandardizationResult(BaseModel):
    """化学式标准化结果"""

    success: bool = Field(description="是否成功")
    original: str = Field(description="原始公式")
    standardized: str = Field(description="标准化后的公式")
    warning: Optional[str] = Field(default=None, description="警告信息")


class QuestionTypeClassification(BaseModel):
    """题目类型分类结果"""

    type: str = Field(description="题目类型")
    confidence: float = Field(description="置信度")
    text: str = Field(description="题目文本")


class OCRAnswerExtraction(BaseModel):
    """OCR答案提取结果"""

    question_type: str = Field(description="识别的题目类型")
    answers: List[str] = Field(description="提取的答案列表")
    raw_content: str = Field(description="原始OCR内容")


class BatchParseResult(BaseModel):
    """批量解析结果"""

    success: bool = Field(description="是否成功")
    total: int = Field(description="总文件数")
    success_count: int = Field(description="成功数量")
    failed_count: int = Field(description="失败数量")
    results: List[Dict[str, Any]] = Field(description="每个文件的解析结果")


class ValidationResult(BaseModel):
    """验证结果"""

    valid: bool = Field(description="是否有效")
    issues: List[str] = Field(description="问题列表")
    warnings: List[str] = Field(description="警告列表")
    content_length: int = Field(description="内容长度")
