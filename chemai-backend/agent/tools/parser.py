"""Document parsing tools — 化学文档解析、真题导入、服务状态查询"""

import json

from chem_skills.chemistry_parser import (
    smart_parse_document as _smart_parse_document,
    import_question_bank as _import_question_bank,
    get_services_status as _get_services_status,
)


async def parse_chemistry_document(
    file_data: str = "",
    file_type: str = "auto",
    task: str = "extract_questions",
) -> str:
    """化学文档解析 — 上传PDF/图片，自动识别提取化学题目

    何时用：老师或助教说"帮我看看这张试卷""把这张PDF解析一下""识别这张图里的题目"
    会发生什么：调用智能文档解析，自动选择OCR/MinerU/视觉模型提取题目、公式和答案
    下一步：解析成功后提取为题目列表，老师可确认后导入题库（用 import_question_bank）
    NOT for 学生上传 — 此工具仅用于老师/助教解析教学文档"""
    result = _smart_parse_document(
        file_data=file_data,
        file_type=file_type or "auto",
        task=task or "extract_questions",
    )
    return json.dumps(result, ensure_ascii=False)


async def import_question_bank(
    file_data: str = "",
    file_type: str = "auto",
    source_name: str = "老师导入",
    year: int = 2024,
    region: str = "通用",
) -> str:
    """真题导入 — 上传试卷/真题图片，自动识别并导入题库

    何时用：老师说"把这份真题加到题库""导入这套高考题""上传试卷到题库"
    会发生什么：智能解析文档，自动提取题目内容、选项、答案，返回待确认的题目列表
    下一步：老师确认后直接存入题库，学生可搜索和使用这些题目
    NOT for 学生自行导入 — 此工具仅用于老师/助教管理题库资源"""
    result = _import_question_bank(
        file_data=file_data,
        file_type=file_type or "auto",
        source_name=source_name or "老师导入",
        year=year or 2024,
        region=region or "通用",
    )
    return json.dumps(result, ensure_ascii=False)


async def check_parser_services() -> str:
    """解析服务检测 — 检查当前可用的文档解析后端

    何时用：老师说"解析不了""上传失败""检查一下解析服务"
    会发生什么：检测OCR（百度）、MinerU、视觉模型三个后端是否可用
    下一步：根据状态告知老师哪些后端可用、哪些需要配置
    NOT for 解析文档 — 用 parse_chemistry_document 或 import_question_bank"""
    result = _get_services_status()
    return json.dumps(result, ensure_ascii=False)
