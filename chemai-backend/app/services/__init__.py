# ChemAI Services
from app.services.chemical_balance import (
    ChemicalEquationAuditor,
    auditor,
    audit_chemical_equation,
    check_equation_balance,
)
# LLM service - optional (requires dashscope)
from app.services.llm_service import LLMService, llm_service, ChatGLMService, chatglm_service

# Knowledge graph service
from app.services.knowledge_graph import KnowledgeGraphService, kg_service

# Exam bank service
from app.services.exam_bank import ExamBankService, exam_bank_service

# Question bank service (AI-generated QuestionSet persistence)
from app.services.question_bank import QuestionBankService, question_bank_service

# OCR service
from app.services.ocr_service import TencentOCRService, ocr_service, OCRParser, ocr_parser

__all__ = [
    # Chemical balance
    "ChemicalEquationAuditor",
    "auditor",
    "audit_chemical_equation",
    "check_equation_balance",
    # LLM
    "LLMService",
    "llm_service",
    "ChatGLMService",
    "chatglm_service",
    # Knowledge graph
    "KnowledgeGraphService",
    "kg_service",
    # Exam bank
    "ExamBankService",
    "exam_bank_service",
    # Question bank
    "QuestionBankService",
    "question_bank_service",
    # OCR
    "TencentOCRService",
    "ocr_service",
    "OCRParser",
    "ocr_parser",
]
