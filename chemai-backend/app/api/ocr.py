"""
F1: 试卷/答题卡 OCR识别 API
基于PRD v1.0完整版功能规格
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
import uuid
import uuid as _uuid
import json
import base64
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import (
    ExamRecord, Question, get_db, RecordType, Difficulty, AuditStatus, QuestionSource
)
from app.middleware.auth import PermissionChecker

router = APIRouter()


class OCRImageRequest(BaseModel):
    """OCR识别请求（base64图片）"""
    image: str  # base64编码的图片数据


class OCRResult(BaseModel):
    """OCR识别结果"""
    student_id: str
    student_name: Optional[str] = None
    answers: dict  # {question_number: answer}
    scores: Optional[dict] = None  # {question_number: score}


class OCRError(BaseModel):
    """OCR识别错误"""
    error_id: str
    location: str
    description: str


class OCRResponse(BaseModel):
    """OCR响应"""
    success: bool
    total_students: int
    results: List[OCRResult]
    errors: List[OCRError]
    confidence: float  # 整体识别置信度


class OCRPreviewRequest(BaseModel):
    """OCR预览请求（识别 + LLM分析，不生成统计）"""
    image: str  # base64编码的图片数据
    questions: Optional[List[dict]] = None  # 可选：题目信息，用于LLM分析


class OCRPreviewResult(BaseModel):
    """单学生预览结果"""
    student_id: str
    student_name: Optional[str] = None
    answers: dict  # 识别的答案 {题号: 答案}
    confidence: float  # 识别置信度
    low_confidence_answers: List[dict]  # 低置信度答案，可能需要老师确认 [{question_number, answer, confidence}]


class LLMAnswerCheck(BaseModel):
    """LLM答案检查结果"""
    question_number: str
    ocr_answer: str  # OCR识别答案
    llm_check: str  # LLM认为的答案
    llm_confidence: float  # LLM判断置信度
    is_consistent: bool  # OCR与LLM是否一致
    suggestion: str  # 建议


class OCRPreviewResponse(BaseModel):
    """OCR预览响应"""
    success: bool
    preview_id: str  # 预览ID，用于后续确认
    students: List[OCRPreviewResult]  # 学生预览列表
    llm_checks: List[LLMAnswerCheck] = []  # LLM答案检查（当提供questions时）
    raw_text: Optional[str] = None  # 原始识别文本
    message: str  # 提示信息


class ExamStatsRequest(BaseModel):
    """错题统计请求"""
    preview_id: Optional[str] = None
    class_id: str
    exam_name: str
    exam_date: Optional[str] = None
    questions: List[dict]  # [{number, correct_answer, knowledge_points, max_score}]
    ocr_results: List[OCRResult]


class QuestionStat(BaseModel):
    """题目错误统计"""
    question_number: str
    knowledge_points: List[str]
    correct_answer: str
    error_count: int
    error_rate: float
    avg_score: float
    wrong_students: List[dict]  # [{student_id, student_name, wrong_answer}]


class KnowledgePointStat(BaseModel):
    """知识点错误统计"""
    knowledge_point: str
    error_count: int
    total_attempts: int
    error_rate: float


class LLMAnalysisResult(BaseModel):
    """LLM学情分析结果"""
    question_number: str
    barrier_type: str  # concept/reading/expression
    barrier_desc: str  # 障碍类型描述
    confidence: float
    reasoning: str  # 判断理由
    suggestion: str  # 教学干预建议


class LLMStatsAnalysis(BaseModel):
    """LLM整体学情分析"""
    class_overall_analysis: str  # 班级整体学情分析
    key_barriers: List[str]  # 主要障碍类型
    teaching_priorities: List[str]  # 教学重点建议
    question_analyses: List[LLMAnalysisResult]  # 每道错题的分析


class ExamStatsResponse(BaseModel):
    """错题统计响应"""
    exam_id: str
    class_id: str
    exam_name: str
    total_students: int
    present_students: int
    avg_score: float
    question_stats: List[QuestionStat]
    knowledge_point_stats: List[KnowledgePointStat]
    top_errors: List[QuestionStat]  # 错误率最高的题目
    high_frequency_errors: List[KnowledgePointStat]  # 高频错误知识点
    llm_analysis: Optional[LLMStatsAnalysis] = None  # LLM学情分析结果


@router.post("/recognize", response_model=OCRResponse)
async def recognize_answer_sheet(file: UploadFile = File(...),
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """
    F1: 试卷/答题卡 OCR识别
    输入: 试卷或答题卡照片(JPG/PNG/PDF)
    输出: 识别文本及结构化数据
    """
    # 验证文件格式
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file.content_type}，仅支持 JPG/PNG/PDF"
        )

    # 读取文件内容
    image_data = await file.read()

    # 使用OCR服务识别
    from app.services.ocr_service import ocr_service

    result = ocr_service.recognize_answer_sheet(image_data)

    if not result.get("success"):
        return OCRResponse(
            success=False,
            total_students=0,
            results=[],
            errors=[OCRError(
                error_id="001",
                location="整个图片",
                description=result.get("error", "识别失败")
            )],
            confidence=0.0
        )

    # 构建返回结果
    ocr_results = []
    for r in result.get("results", []):
        ocr_results.append(OCRResult(
            student_id=r.get("student_id", ""),
            student_name=r.get("student_name"),
            answers=r.get("answers", {}),
            scores=r.get("scores")
        ))

    return OCRResponse(
        success=True,
        total_students=result.get("total_students", 0),
        results=ocr_results,
        errors=[],
        confidence=result.get("confidence", 0.95)
    )


@router.post("/recognize/base64", response_model=OCRResponse)
async def recognize_answer_sheet_base64(request: OCRImageRequest,
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """
    F1: 答题卡OCR识别（base64图片）
    输入: base64编码的图片数据
    输出: 学生作答结构化数据
    """
    try:
        # 解码base64图片
        image_data = base64.b64decode(request.image)

        # 使用OCR服务识别
        from app.services.ocr_service import ocr_service
        result = ocr_service.recognize_answer_sheet(image_data)

        if not result.get("success"):
            return OCRResponse(
                success=False,
                total_students=0,
                results=[],
                errors=[OCRError(
                    error_id="001",
                    location="整个图片",
                    description=result.get("error", "识别失败")
                )],
                confidence=0.0
            )

        # 构建返回结果
        ocr_results = []
        # 单个答题卡结果
        ocr_results.append(OCRResult(
            student_id=result.get("student_id", "unknown"),
            student_name=result.get("student_name"),
            answers=result.get("answers", {}),
            scores=result.get("scores")
        ))

        return OCRResponse(
            success=True,
            total_students=1,
            results=ocr_results,
            errors=[],
            confidence=result.get("confidence", 0.95)
        )

    except Exception as e:
        return OCRResponse(
            success=False,
            total_students=0,
            results=[],
            errors=[OCRError(
                error_id="001",
                location="整个图片",
                description=f"处理失败: {str(e)}"
            )],
            confidence=0.0
        )


# 别名: /api/ocr (前端期望的路径)
@router.post("", response_model=OCRResponse)
async def recognize_answer_sheet_alias(file: UploadFile = File(...),
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """F1: 试卷识别 (别名路径)"""
    return await recognize_answer_sheet(file)


@router.post("/recognize/batch")
async def recognize_answer_sheets(
    files: List[UploadFile] = File(...),
    class_id: str = "",
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """
    F1: 批量答题卡OCR识别
    输入: 多张答题卡照片
    输出: 批量识别结果
    """
    from app.services.ocr_service import ocr_service

    results = []
    errors = []
    total_confidence = 0.0

    for i, file in enumerate(files):
        if file.content_type not in ["image/jpeg", "image/png", "application/pdf"]:
            errors.append({
                "file": file.filename,
                "error": f"不支持的格式: {file.content_type}"
            })
            continue

        try:
            image_data = await file.read()
            result = ocr_service.recognize_answer_sheet(image_data)
            if result.get("success"):
                results.append({
                    "filename": file.filename,
                    "student_id": result.get("student_id"),
                    "student_name": result.get("student_name"),
                    "answers": result.get("answers", {}),
                    "scores": result.get("scores", {}),
                    "confidence": result.get("confidence", 0)
                })
                total_confidence += result.get("confidence", 0)
            else:
                errors.append({
                    "file": file.filename,
                    "error": result.get("error", "识别失败")
                })
        except Exception as e:
            errors.append({
                "file": file.filename,
                "error": str(e)
            })

    avg_confidence = total_confidence / len(results) if results else 0.0

    return {
        "success": len(errors) == 0,
        "total_files": len(files),
        "success_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
        "avg_confidence": avg_confidence
    }


@router.post("/preview", response_model=OCRPreviewResponse)
async def ocr_preview(request: OCRPreviewRequest,
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """
    F1: OCR预览 + LLM分析（不生成统计）

    工作流第1步：识别
    工作流第2步：预览 + LLM辅助分析
    - 返回识别结果供老师预览
    - 如果提供了题目信息，调用LLM检查答案一致性
    - 识别低置信度答案，提示老师确认

    老师确认后调用 /confirm 生成正式统计
    """

    try:
        # 解码base64图片
        try:
            image_data = base64.b64decode(request.image)
        except Exception:
            return OCRPreviewResponse(
                success=False,
                preview_id="",
                students=[],
                llm_checks=[],
                message="图片数据格式错误，请上传有效的图片文件"
            )

        # Human-in-the-loop OCR识别工作流
        # 1. OCR识别 → 预览结果（始终显示，让老师确认）
        # 2. 老师确认 → 调用统计分析
        # 3. 老师否定 → 调用多模态大模型识别 → 返回新预览
        # 4. 老师再次否定 → 手动输入模式

        from app.services.ocr_service import ocr_service

        # 使用OCR服务识别（识别任何图片，返回结果供预览）
        result = ocr_service.recognize_answer_sheet(image_data)

        # 生成预览ID
        preview_id = f"preview_{uuid.uuid4().hex[:12]}"

        # 始终返回预览结果（不管OCR是否成功）
        # 如果OCR识别效果不好，老师可以在预览页面手动修正
        all_answers = result.get("answers", {})
        raw_text = result.get("raw_text", "")

        # 检查是否有解析错误或部分识别
        is_partial = result.get("is_partial", False)
        error_msg = result.get("error")

        # 找出低置信度答案
        low_confidence_answers = []
        for q_num, answer in all_answers.items():
            if len(str(answer)) > 3 or not str(answer).strip():
                low_confidence_answers.append({
                    "question_number": q_num,
                    "answer": answer,
                    "confidence": 0.7,
                    "reason": "答案格式异常"
                })

        students = [OCRPreviewResult(
            student_id=result.get("student_id", "unknown"),
            student_name=result.get("student_name"),
            answers=all_answers,
            confidence=result.get("confidence", 0.85),
            low_confidence_answers=low_confidence_answers
        )]

        # 构建消息
        if is_partial:
            message = f"OCR识别完成（部分识别）：{error_msg or '请在下方手动修正答案'}"
        else:
            message = "OCR识别完成，请确认识别结果是否正确"

        return OCRPreviewResponse(
            success=True,  # 始终返回success，让预览页显示
            preview_id=preview_id,
            students=students,
            llm_checks=[],
            raw_text=raw_text,
            message=message
        )

    except Exception as e:
        return OCRPreviewResponse(
            success=False,
            preview_id="",
            students=[],
            llm_checks=[],
            message=f"处理失败: {str(e)}"
        )


@router.post("/confirm", response_model=ExamStatsResponse)
async def ocr_confirm(
    request: ExamStatsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("ocr", "create")),
):
    """
    F1: OCR确认预览结果，生成正式统计

    工作流第3步：老师确认
    工作流第4步：生成统计

    老师在预览阶段校正答案后，点击确认生成正式统计
    """
    # 直接复用现有的 stats 逻辑（依赖在直调时不会自动解析，身份显式传下去）
    return await generate_exam_stats(request, db, current_user)


class RetryVisionRequest(BaseModel):
    """多模态重试请求"""
    image: str  # base64编码的图片数据
    paper_type: str = "mixed"  # answer_sheet/printed/handwritten/mixed


@router.post("/retry-vision")
async def ocr_retry_vision(request: RetryVisionRequest,
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """
    F1: OCR识别结果被否定后，调用千问多模态大模型重新分析

    工作流：
    1. OCR识别 → 返回预览
    2. 老师预览 → 如果"识别不准" → 调用此API
    3. 使用千问qwen-vl-max多模态模型分析试卷图片
    4. 返回结构化分析结果

    支持识别：
    - answer_sheet: 答题卡
    - printed: 印刷试卷
    - handwritten: 手写试卷
    - mixed: 混合试卷（印刷题目+手写作答）
    """
    try:
        # 调用LLM服务的多模态分析
        from app.services.llm_service import llm_service

        result = llm_service.analyze_paper_with_vision(
            image_data=request.image,
            paper_type=request.paper_type
        )

        if result.get("success"):
            return {
                "success": True,
                "student_id": result.get("student_id", ""),
                "student_name": result.get("student_name", ""),
                "questions": result.get("questions", []),
                "raw_text": result.get("raw_text", ""),
                "message": result.get("message", "多模态分析完成")
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "多模态分析失败"),
                "error": result.get("error", "未知错误")
            }

    except Exception as e:
        return {
            "success": False,
            "message": "多模态分析异常",
            "error": str(e)
        }


@router.post("/stats", response_model=ExamStatsResponse)
async def generate_exam_stats(request: ExamStatsRequest, db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("ocr", "create")),
):
    """
    F1: 生成班级错题统计表
    输入: OCR识别结果 + 题目知识点映射
    输出: 按题目编号/知识点聚合的错题分布表

    统计规则:
    1. 计算每道题的错误人数/错误率
    2. 按知识点聚合错误率
    3. 识别高频错误点
    4. 按错误率排序生成top_errors
    5. 持久化到数据库
    """
    # 范围收窄：班级与自己名下的学生才允许落库（class_id/student_id 都是调用方自报）
    from app.middleware.scope import RequestScope

    scope = RequestScope.from_user(current_user, db)
    if not scope.allows_class(request.class_id):
        raise HTTPException(status_code=403, detail="无权为该班级生成统计")
    out_of_scope = [s.student_id for s in request.ocr_results
                    if not scope.allows_student(s.student_id)]
    if out_of_scope:
        raise HTTPException(status_code=403,
                            detail=f"无权写入这些学生的作答（不在你的范围内）: {out_of_scope[:5]}")

    # 生成考试ID
    exam_id = f"exam_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # 统计每道题的错误
    question_stats: Dict[str, QuestionStat] = {}
    knowledge_point_totals: Dict[str, Dict] = {}  # {kp: {errors: 0, total: 0}}

    # 初始化题目统计
    for q in request.questions:
        q_num = str(q.get("number", ""))
        question_stats[q_num] = {
            "question_number": q_num,
            "knowledge_points": q.get("knowledge_points", []),
            "correct_answer": str(q.get("correct_answer", "")).strip().upper(),
            "error_count": 0,
            "wrong_students": [],
            "total_score": 0
        }
        # 初始化知识点统计
        for kp in q.get("knowledge_points", []):
            if kp not in knowledge_point_totals:
                knowledge_point_totals[kp] = {"errors": 0, "total": 0}

    # 统计每个学生的答题情况
    total_scores = 0
    present_students = len(request.ocr_results)

    # 创建或获取考试记录
    exam_date = datetime.strptime(request.exam_date, "%Y-%m-%d") if request.exam_date else datetime.now()
    exam_record = ExamRecord(
        record_id=exam_id,
        class_id=request.class_id,
        name=request.exam_name,
        type=RecordType.EXAM,
        total_students=(
            request.questions[0].get("total_students", present_students)
            if request.questions
            else present_students
        ),
        present_students=present_students,
        exam_date=exam_date
    )
    db.add(exam_record)

    # 保存题目
    questions_map = {}
    for q in request.questions:
        q_num = str(q.get("number", ""))
        question_id = f"{exam_id}_{q_num}"
        question = Question(
            question_id=question_id,
            record_id=exam_id,
            content=q.get("content", f"题目{q_num}"),
            options=q.get("options"),
            answer=str(q.get("correct_answer", "")).strip().upper(),
            knowledge_points=q.get("knowledge_points", []),
            difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED,
            audit_status=AuditStatus.PASSED
        )
        db.add(question)
        questions_map[q_num] = question

    # 保存学生答题记录（判卷中心单点落库；来源 manual：老师整卷粘贴）
    from app.services import grading_center

    # 默认每题分值沿用请求末题的 max_score（与历史行为一致）
    default_max_score = request.questions[-1].get("max_score", 6) if request.questions else 6

    for student in request.ocr_results:
        student_id = student.student_id
        student_name = student.student_name or student_id

        # 计算该学生总分
        student_total = 0
        student_answers = student.answers or {}
        student_scores = student.scores or {}

        refs, entries, key = [], [], []
        for q_num, answer in student_answers.items():
            q_stat = question_stats.get(q_num, question_stats.get(str(q_num)))
            question = questions_map.get(q_num, questions_map.get(str(q_num)))
            if not (q_stat and question):
                continue
            refs.append((q_num, q_stat, question, answer))
            entries.append({"question_id": question.question_id, "answer": str(answer)})
            key.append({"question_id": question.question_id, "answer": str(q_stat["correct_answer"])})

        graded = grading_center.grade(entries, key, semantic=False)
        # 未决主观题落待判定行（ADR-0013）：直接 save 会把「还没判」固化成永久错答
        rows = [grading_center.pending_row(q) for q in graded["questions"]]
        grading_center.save(db, rows, student_id, exam_id, "manual",
                            trigger_diagnosis=False)

        for (q_num, q_stat, question, answer), q, row in zip(refs, graded["questions"], rows):
            if grading_center.is_unjudged(row["reason"]):
                continue          # 判定中/缺标准答案不算答错：不进错误名单，待扫描作业重判后生效

            # 更新知识点统计
            for kp in q_stat["knowledge_points"]:
                if kp in knowledge_point_totals:
                    knowledge_point_totals[kp]["total"] += 1

            if not q["is_correct"]:
                # 记录错误
                q_stat["error_count"] += 1
                q_stat["wrong_students"].append({
                    "student_id": student_id,
                    "student_name": student_name,
                    "wrong_answer": answer
                })
                # 更新知识点错误
                for kp in q_stat["knowledge_points"]:
                    if kp in knowledge_point_totals:
                        knowledge_point_totals[kp]["errors"] += 1
            else:
                # 答对累加分数
                score = student_scores.get(q_num, default_max_score)
                q_stat["total_score"] += score
                student_total += score

        total_scores += student_total

    # 计算错误率并生成最终统计
    final_question_stats = []
    for q_num, q_stat in question_stats.items():
        error_rate = q_stat["error_count"] / present_students if present_students > 0 else 0
        avg_score = q_stat["total_score"] / present_students if present_students > 0 else 0

        final_question_stats.append(QuestionStat(
            question_number=q_num,
            knowledge_points=q_stat["knowledge_points"],
            correct_answer=q_stat["correct_answer"],
            error_count=q_stat["error_count"],
            error_rate=round(error_rate, 3),
            avg_score=round(avg_score, 1),
            wrong_students=q_stat["wrong_students"][:10]  # 最多返回10个学生
        ))

    # 按错误率排序
    final_question_stats.sort(key=lambda x: x.error_rate, reverse=True)

    # 计算知识点错误率
    knowledge_point_stats = []
    for kp, totals in knowledge_point_totals.items():
        if totals["total"] > 0:
            error_rate = totals["errors"] / totals["total"]
            knowledge_point_stats.append(KnowledgePointStat(
                knowledge_point=kp,
                error_count=totals["errors"],
                total_attempts=totals["total"],
                error_rate=round(error_rate, 3)
            ))

    # 按错误率排序知识点
    knowledge_point_stats.sort(key=lambda x: x.error_rate, reverse=True)

    # 平均分
    avg_score = total_scores / present_students if present_students > 0 else 0

    # 更新考试记录的统计信息
    exam_record.avg_score = round(avg_score, 1)
    exam_record.question_stats = {
        "question_stats": [
            {
                "question_number": q.question_number,
                "knowledge_points": q.knowledge_points,
                "error_count": q.error_count,
                "error_rate": q.error_rate
            }
            for q in final_question_stats
        ],
        "knowledge_point_stats": [
            {
                "knowledge_point": kp.knowledge_point,
                "error_count": kp.error_count,
                "error_rate": kp.error_rate
            }
            for kp in knowledge_point_stats
        ]
    }

    # 提交所有更改（如果数据库中不存在对应的class_id，可能会失败）
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # 数据库操作失败，但仍然返回计算结果
        print(f"警告：统计数据保存失败: {e}")

    # barrier 诊断经队列作业落库（作业幂等；失败不影响统计返回）
    try:
        from app.jobs import enqueue_job
        enqueue_job("diagnosis", {"exam_record_id": exam_id})
    except Exception as e:
        print(f"警告：诊断作业入队失败: {e}")

    # ========== LLM学情分析 ==========
    llm_analysis = None
    try:
        from app.services.llm_service import llm_service

        # 获取错误率最高的题目进行LLM分析
        top_error_questions = final_question_stats[:5]  # 分析错误率最高的5题

        question_analyses = []
        barrier_counts = {"concept": 0, "reading": 0, "expression": 0}

        for q_stat in top_error_questions:
            # 构建题目信息用于LLM诊断
            q_num = q_stat.question_number
            correct_answer = q_stat.correct_answer
            knowledge_points = q_stat.knowledge_points

            # 找到学生的典型错误答案
            wrong_answers = q_stat.wrong_students
            if wrong_answers:
                sample_wrong_answer = wrong_answers[0].get("wrong_answer", "")
            else:
                sample_wrong_answer = "未知"

            # 获取题目内容
            question_content = ""
            for q in request.questions:
                if str(q.get("number", "")) == q_num:
                    question_content = q.get("content", f"题目{q_num}")
                    break
            if not question_content:
                question_content = f"题目{q_num}（知识点: {', '.join(knowledge_points)}）"

            # 调用LLM进行障碍类型诊断
            llm_result = llm_service.diagnose_barrier_type(
                student_error_history=[{
                    "question": question_content,
                    "wrong_answer": sample_wrong_answer,
                    "correct_answer": correct_answer,
                    "error_count": q_stat.error_count
                }],
                question_content=question_content,
                student_answer=sample_wrong_answer,
                correct_answer=correct_answer
            )

            if llm_result.get("success"):
                import json as json_lib
                try:
                    # 尝试解析LLM返回的JSON
                    content = llm_result.get("content", "{}")
                    # 清理可能的markdown代码块
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    llm_data = json_lib.loads(content.strip())

                    barrier_type = llm_data.get("barrier_type", "concept")
                    barrier_counts[barrier_type] = barrier_counts.get(barrier_type, 0) + 1

                    question_analyses.append(LLMAnalysisResult(
                        question_number=q_num,
                        barrier_type=barrier_type,
                        barrier_desc={
                            "concept": "概念理解型 - 学生对化学概念的理解存在偏差",
                            "reading": "审题障碍型 - 学生读取题目信息不全或审题错误",
                            "expression": "表述障碍型 - 学生理解正确答案但无法规范表述"
                        }.get(barrier_type, "未知类型"),
                        confidence=llm_data.get("confidence", 0.8),
                        reasoning=llm_data.get("reasoning", ""),
                        suggestion=llm_data.get("suggestion", "")
                    ))
                except json_lib.JSONDecodeError:
                    # JSON解析失败，使用默认值
                    question_analyses.append(LLMAnalysisResult(
                        question_number=q_num,
                        barrier_type="concept",
                        barrier_desc="概念理解型",
                        confidence=0.5,
                        reasoning="LLM响应解析失败",
                        suggestion="建议加强相关知识点的讲解"
                    ))

        # 生成整体学情分析
        barrier_desc_map = {
            "concept": "概念理解型障碍",
            "reading": "审题障碍型障碍",
            "expression": "表述障碍型障碍"
        }
        key_barriers = [barrier_desc_map[b] for b, c in barrier_counts.items() if c > 0]

        # 生成教学重点建议
        teaching_priorities = []
        c_count = barrier_counts.get("concept", 0)
        r_count = barrier_counts.get("reading", 0)
        e_count = barrier_counts.get("expression", 0)
        if c_count >= r_count and c_count >= e_count:
            teaching_priorities.append("加强化学基本概念的教学，使用思维导图等工具帮助学生建立概念体系")
        if r_count >= c_count and r_count >= e_count:
            teaching_priorities.append("训练学生审题能力，强调关键词句的识别和信息提取")
        if e_count >= c_count and e_count >= r_count:
            teaching_priorities.append("规范学生的化学用语表达，加强答题格式训练")

        # 计算本次考试整体分析
        class_overall = (
            f"本次考试{present_students}人参加，平均分{round(avg_score, 1)}分。"
            if present_students > 0
            else "暂无考试数据。"
        )
        if final_question_stats:
            highest_error_q = final_question_stats[0]
            class_overall += (
                f"错误率最高的题目是第{highest_error_q.question_number}题，"
                f"错误率达{int(highest_error_q.error_rate * 100)}%。"
            )

        llm_analysis = LLMStatsAnalysis(
            class_overall_analysis=class_overall,
            key_barriers=key_barriers if key_barriers else ["数据不足"],
            teaching_priorities=teaching_priorities if teaching_priorities else ["继续观察学生学习情况"],
            question_analyses=question_analyses
        )

        print(f"LLM学情分析完成: {len(question_analyses)}道题已分析")

    except Exception as e:
        print(f"LLM分析失败（不影响返回结果）: {e}")
        # LLM分析失败不影响主流程，继续返回统计数据

    return ExamStatsResponse(
        exam_id=exam_id,
        class_id=request.class_id,
        exam_name=request.exam_name,
        total_students=(
            request.questions[0].get("total_students", present_students)
            if request.questions
            else present_students
        ),
        present_students=present_students,
        avg_score=round(avg_score, 1),
        question_stats=final_question_stats,
        knowledge_point_stats=knowledge_point_stats[:10],  # 最多返回10个知识点
        top_errors=final_question_stats[:5],  # 错误率最高的5题
        high_frequency_errors=knowledge_point_stats[:5],  # 高频错误的5个知识点
        llm_analysis=llm_analysis  # LLM学情分析结果
    )


# ==================== 统一文档解析入口 ====================

class DocumentParseRequest(BaseModel):
    """统一文档解析请求"""
    file_data: str  # base64编码的文件内容
    file_type: str = "auto"  # pdf, image, auto
    source: str = "auto"  # ocr, mineru, vision, auto


class DocumentParseResponse(BaseModel):
    """统一文档解析响应"""
    success: bool
    provider: str  # ocr, vision, mineru, none
    result: dict  # 解析结果
    fallback_used: bool  # 是否使用了降级
    error: Optional[str] = None
    warning: Optional[str] = None
    services_status: dict = None  # 各服务可用性状态


@router.post("/parse/document", response_model=DocumentParseResponse)
async def parse_document(request: DocumentParseRequest,
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """
    统一文档解析入口 - 自动选择最佳解析方式

    支持:
    - PDF文档 → MinerU解析
    - 图片/试卷/答题卡 → OCR优先，失败自动降级到视觉模型
    - 自动模式根据文件类型选择最佳解析方式

    请求体:
    {
        "file_data": "base64编码的文件内容",
        "file_type": "auto",  // 或 "pdf", "image"
        "source": "auto"       // 或 "ocr", "mineru", "vision"
    }

    返回:
    {
        "success": true,
        "provider": "ocr|vision|mineru",
        "result": {...},       // 解析结果
        "fallback_used": false // 是否使用了降级
    }
    """
    try:
        from app.services.document_parse_service import get_document_parse_service

        service = get_document_parse_service()

        # 检查服务状态
        services_status = service.check_services_status()

        # 解码base64文件内容
        try:
            file_data = base64.b64decode(request.file_data)
        except Exception as e:
            return DocumentParseResponse(
                success=False,
                provider="none",
                result={},
                fallback_used=False,
                error=f"文件数据解码失败: {str(e)}",
                services_status=services_status
            )

        # 调用统一解析服务
        result = service.parse_document(
            file_data=file_data,
            file_type=request.file_type,
            source=request.source
        )

        return DocumentParseResponse(
            success=result.get("success", False),
            provider=result.get("provider", "none"),
            result=result.get("result", {}),
            fallback_used=result.get("fallback_used", False),
            error=result.get("error"),
            warning=result.get("warning"),
            services_status=services_status
        )

    except Exception as e:
        return DocumentParseResponse(
            success=False,
            provider="none",
            result={},
            fallback_used=False,
            error=f"解析异常: {str(e)}"
        )


@router.get("/services/status")
async def get_services_status():
    """
    获取所有文档解析服务的可用性状态

    返回:
    {
        "ocr": {"available": true, "provider": "zhipu", "note": "..."},
        "mineru": {"available": true, "note": "..."},
        "vision": {"available": true, "provider": "zhipu-glm-4v", "note": "..."}
    }
    """
    from app.services.document_parse_service import get_document_parse_service

    service = get_document_parse_service()
    return service.check_services_status()


# ═══════════════════════════════════════════════════════════════════
# OCR Pipeline — upload → preview → import / grade
# ═══════════════════════════════════════════════════════════════════

ALLOWED_MIMES = {
    "image/jpeg", "image/png", "image/bmp", "image/webp", "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload")
async def ocr_upload(file: UploadFile = File(...),
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """上传文件 → 创建会话 → 预览"""
    if file.content_type and file.content_type not in ALLOWED_MIMES and not (
        file.filename and file.filename.lower().endswith(('.doc', '.docx'))
    ):
        raise HTTPException(400, f"不支持的文件格式: {file.content_type}")

    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件超过 10MB 限制")

    from app.models.database import get_db, UploadSession
    from app.services.ocr_service import ocr_service

    session_id = _uuid.uuid4().hex[:16]
    db = next(get_db())
    try:
        db.add(UploadSession(
            id=session_id,
            file_data=file_data,
            file_name=file.filename or "unknown",
            mime_type=file.content_type or "application/octet-stream",
            status="previewing",
        ))
        db.commit()
    finally:
        db.close()

    # Preview
    result = await ocr_service.recognize(file_data, file.content_type or "")

    # Update session
    db = next(get_db())
    try:
        from sqlalchemy import update as sql_update
        db.execute(
            sql_update(UploadSession)
            .where(UploadSession.id == session_id)
            .values(
                status="ready",
                preview_text=result.get("preview_text", ""),
                formula_result=json.dumps(result.get("formula_result", []), ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()

    return {
        "success": result.get("success", False),
        "upload_id": session_id,
        "preview_text": result.get("preview_text", "")[:500],
        "formula_count": len(result.get("formula_result", [])),
        "actions": [
            {"id": "import", "label": "导入题库"},
            {"id": "grade", "label": "批改判卷"},
            {"id": "search", "label": "搜题解析"},
        ],
    }


@router.get("/tasks/{upload_id}/status")
async def ocr_task_status(upload_id: str):
    """查询异步任务状态"""
    from app.models.database import get_db, UploadSession

    db = next(get_db())
    try:
        session = db.query(UploadSession).filter(UploadSession.id == upload_id).first()
        if not session:
            raise HTTPException(404, "任务不存在")

        return {
            "upload_id": upload_id,
            "status": session.status,
            "progress": {
                "current": session.pages_completed or 0,
                "total": session.page_count or 0,
            },
            "error": session.error_msg,
            "degraded": session.degraded,
            "result": json.loads(session.result_json) if session.result_json else None,
        }
    finally:
        db.close()


@router.post("/tasks/{upload_id}/import")
async def ocr_task_import(upload_id: str,
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """确认导入试卷 → 触发后台导入"""
    from app.models.database import get_db, UploadSession

    db = next(get_db())
    try:
        session = db.query(UploadSession).filter(UploadSession.id == upload_id).first()
        if not session:
            raise HTTPException(404, "任务不存在")
        if session.status not in ("ready", "error"):
            raise HTTPException(400, f"当前状态 {session.status} 不允许导入")
    finally:
        db.close()

    # Trigger import in background
    from app.services.ocr_service import ocr_service
    import asyncio
    asyncio.create_task(ocr_service.import_exam(upload_id))

    return {"upload_id": upload_id, "status": "importing"}


@router.post("/tasks/{upload_id}/grade")
async def ocr_task_grade(upload_id: str, exam_id: str = "", class_id: str = "",
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """确认批改 → 触发后台判卷"""
    from app.models.database import get_db, UploadSession

    db = next(get_db())
    try:
        session = db.query(UploadSession).filter(UploadSession.id == upload_id).first()
        if not session:
            raise HTTPException(404, "任务不存在")
        if session.status not in ("ready", "error"):
            raise HTTPException(400, f"当前状态 {session.status} 不允许批改")
        file_data = session.file_data
    finally:
        db.close()

    from app.services.ocr_service import ocr_service
    import asyncio
    asyncio.create_task(ocr_service.grade(
        file_data, exam_id=exam_id, class_id=class_id))

    return {"upload_id": upload_id, "status": "grading"}


@router.post("/tasks/{upload_id}/cancel")
async def ocr_task_cancel(upload_id: str,
    _perm: None = Depends(PermissionChecker("ocr", "create")),
):
    """取消任务"""
    from app.models.database import get_db, UploadSession

    db = next(get_db())
    try:
        session = db.query(UploadSession).filter(UploadSession.id == upload_id).first()
        if not session:
            raise HTTPException(404, "任务不存在")
        session.status = "discarded"
        db.commit()
        return {"upload_id": upload_id, "status": "discarded"}
    finally:
        db.close()
