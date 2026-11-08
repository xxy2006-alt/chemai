"""
F6: 历年真题库管理 API
支持手动选题和自定义真题集管理
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import (
    QuestionSet, QuestionSetItem,
    get_db,
)
from app.middleware.auth import PermissionChecker
from app.services.question_bank import question_bank_service

router = APIRouter()


# ==================== 请求/响应模型 ====================

class QuestionSetCreate(BaseModel):
    """创建真题集请求"""
    name: str
    teacher_id: Optional[str] = None
    region: Optional[str] = None
    year: Optional[int] = None
    source: Optional[str] = None
    description: Optional[str] = None


class QuestionSetResponse(BaseModel):
    """真题集响应"""
    set_id: str
    name: str
    region: Optional[str]
    year: Optional[int]
    source: Optional[str]
    description: Optional[str]
    question_count: int
    is_system: bool
    created_at: str


class QuestionFormatRequest(BaseModel):
    """题目格式化请求（OCR识别结果转标准题目）"""
    raw_text: str  # OCR识别的原始文本
    source_info: Optional[str] = None  # 来源信息


class QuestionFormatResponse(BaseModel):
    """题目格式化响应"""
    success: bool
    questions: List[Dict]  # 格式化后的题目列表
    message: str


class ImportQuestionsRequest(BaseModel):
    """导入题目到真题集请求"""
    set_id: str
    questions: List[Dict]  # 题目列表 [{content, options, answer, knowledge_points, difficulty}]


# ==================== 真题集管理 API ====================

@router.post("/exam-sets", response_model=Dict)
async def create_exam_set(
    request: QuestionSetCreate,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam_bank", "create")),
):
    """
    创建自定义真题集
    """
    try:
        result = question_bank_service.create_set(
            db, name=request.name, teacher_id=request.teacher_id,
            region=request.region, year=request.year,
            source=request.source, description=request.description,
        )

        return {
            "success": True,
            "message": "真题集创建成功",
            "exam_set": {
                "set_id": result["set_id"],
                "name": result["name"],
                "region": request.region,
                "year": request.year,
                "source": request.source,
                "question_count": result.get("question_count", 0),
                "is_system": result.get("is_system", False),
                "created_at": result.get("created_at") or datetime.now().isoformat()
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"创建失败: {str(e)}"}


@router.get("/exam-sets", response_model=Dict)
async def get_exam_sets(
    teacher_id: Optional[str] = None,
    region: Optional[str] = None,
    year: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取真题集列表
    支持按教师、地区、年份筛选
    """
    result = question_bank_service.list_sets(
        db, teacher_id=teacher_id, region=region, year=year,
        page=page, page_size=page_size,
    )

    return {"success": True, "data": result}


@router.get("/exam-sets/{set_id}", response_model=Dict)
async def get_exam_set_detail(set_id: str, db: Session = Depends(get_db)):
    """
    获取真题集详情（包含所有题目）
    """
    detail = question_bank_service.get_set(db, set_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"真题集 {set_id} 不存在")

    return {"success": True, "data": detail}


@router.delete("/exam-sets/{set_id}/questions/{question_id}", response_model=Dict)
async def remove_question_from_set(
    set_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam_bank", "delete")),
):
    """从题库中移除单道题目"""
    question_set = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
    if not question_set:
        raise HTTPException(status_code=404, detail=f"题库 {set_id} 不存在")

    # 删除关联
    deleted = db.query(QuestionSetItem).filter(
        QuestionSetItem.set_id == set_id,
        QuestionSetItem.question_id == question_id
    ).delete()

    if deleted:
        # 更新题目计数
        question_set.question_count = db.query(QuestionSetItem).filter(
            QuestionSetItem.set_id == set_id
        ).count()
        db.commit()
        return {"success": True, "message": "题目已从题库移除"}
    else:
        return {"success": False, "message": "题库中未找到该题目"}


@router.delete("/exam-sets/{set_id}", response_model=Dict)
async def delete_exam_set(
    set_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam_bank", "delete")),
):
    """
    删除真题集（只能删除用户自定义的）
    """
    result = question_bank_service.delete_set(db, set_id)

    if result.get("success"):
        return {"success": True, "message": "真题集已删除"}

    if result.get("reason") == "is_system":
        return {"success": False, "message": "系统预设真题集不能删除"}

    raise HTTPException(status_code=404, detail=f"真题集 {set_id} 不存在")


# ==================== 题目格式化 API ====================

@router.post("/format-questions", response_model=QuestionFormatResponse)
async def format_questions_from_text(
    request: QuestionFormatRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam_bank", "create")),
):
    """
    将OCR识别的原始文本格式化为标准题目
    调用LLM进行格式化处理
    """
    try:
        from app.services.llm_service import llm_service

        system_prompt = """你是一位高中化学教研专家，负责将OCR识别的原始试卷文本格式化为标准的结构化题目。

要求：
1. 识别并提取每道题目，包括题号、正文、选项（如果有）、答案
2. 判断题目类型：选择题、填空题、解答题
3. 为每道题目标注知识点
4. 判断题目难度：easy/medium/hard
5. 保持题目原文，只做格式化和结构化，不修改内容

返回格式（JSON）：
{
    "questions": [
        {
            "type": "choice/fill/essay",
            "content": "题目正文",
            "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],  // 选择题需要
            "answer": "正确答案",  // 简化的答案标识，如 "A" 或 "1"
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": "easy/medium/hard"
        }
    ],
    "message": "处理说明"
}"""

        prompt = f"""请将以下OCR识别的试卷文本格式化为标准题目：

{request.raw_text}

{request.source_info if request.source_info else ''}

直接返回JSON，不要有其他文字。"""

        result = llm_service.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=4000
        )

        if result.get("success"):
            import json as json_lib
            content = result.get("content", "{}")

            # 清理可能的markdown代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            formatted_data = json_lib.loads(content.strip())

            return QuestionFormatResponse(
                success=True,
                questions=formatted_data.get("questions", []),
                message=formatted_data.get("message", "格式化完成")
            )
        else:
            return QuestionFormatResponse(
                success=False,
                questions=[],
                message=f"格式化失败: {result.get('error', '未知错误')}"
            )

    except Exception as e:
        return QuestionFormatResponse(
            success=False,
            questions=[],
            message=f"格式化异常: {str(e)}"
        )


# ==================== 导入题目 API ====================

@router.post("/import-questions", response_model=Dict)
async def import_questions_to_set(
    request: ImportQuestionsRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam_bank", "create")),
):
    """
    导入题目到真题集
    """
    try:
        result = question_bank_service.add_questions(db, request.set_id, request.questions)

        if not result.get("success"):
            return {"success": False, "message": "真题集不存在"}

        return {
            "success": True,
            "message": f"成功导入 {result['count']} 道题目",
            "imported_count": result["count"]
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"导入失败: {str(e)}"}


# ==================== 试卷分组查询 API ====================

@router.get("/papers", response_model=Dict)
async def get_papers_grouped():
    """获取所有真题试卷，按地区→年份分组"""
    from app.services.exam_bank import exam_bank_service
    groups = exam_bank_service.get_papers_grouped()
    # 只统计有数据的卷（空占位卷不计入）
    total_papers = sum(1 for g in groups for y in g["years"] for p in y["papers"] if not p.get("empty"))
    total_questions = len(exam_bank_service.questions)
    return {
        "success": True,
        "data": {
            "total_papers": total_papers,
            "total_questions": total_questions,
            "groups": groups
        }
    }


# ==================== 历史真题查询 API ====================

@router.get("/historical", response_model=Dict)
async def get_historical_questions(
    region: Optional[str] = None,
    year: Optional[int] = None,
    knowledge_point: Optional[str] = None,
    difficulty: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    """
    查询历年真题
    支持按地区、年份、知识点、难度筛选
    从 ExamBankService（内存加载JSON文件）读取，而非数据库表
    """
    from app.services.exam_bank import exam_bank_service

    # 参数映射：region 映射到 service 的 source（"全国卷" → 匹配 "全国卷2024"）
    results = exam_bank_service.search_questions(
        source=region,
        year=year,
        knowledge_point=knowledge_point,
        difficulty=difficulty
    )

    total = len(results)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_results = results[start:end]

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "questions": [
                {
                    "exam_id": q.exam_id,
                    "question_id": q.exam_id,
                    "source": q.source,
                    "year": q.year,
                    "region": q.region,
                    "question_number": q.question_number,
                    "question_type": q.question_type,
                    "content": q.content,
                    "options": q.options,
                    "answer": q.answer,
                    "analysis": q.analysis or "",
                    "knowledge_points": q.knowledge_points,
                    "difficulty": q.difficulty or "medium",
                    "discrimination": q.discrimination,
                    "page_image": q.page_image,
                }
                for q in page_results
            ]
        }
    }
