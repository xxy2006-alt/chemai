"""
学情记忆 API
用于将诊断结果持久化到学生的 memory.md 文件
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Dict, List
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker, get_current_user
from app.middleware.scope import ScopeGuard, require_student
from app.models.database import get_db

router = APIRouter()


class DiagnosisCompleteRequest(BaseModel):
    """诊断完成请求"""
    student_id: str
    barrier_type: Dict[str, float]  # {concept: 0.3, reading: 0.5, expression: 0.2}
    dominant_barrier: str  # 主要障碍类型
    weak_kps: List[str]  # 薄弱知识点列表


class DiagnosisCompleteResponse(BaseModel):
    """诊断完成响应"""
    success: bool
    message: str
    student_id: str


@router.post("/diagnosis-complete", response_model=DiagnosisCompleteResponse)
async def memory_diagnosis_complete(
    request: DiagnosisCompleteRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    # 这是**写**端点（把诊断结果落盘到 memory.md），原先只能靠 router 基线的
    # `memory:read` 把关 —— 「read 权限能写文件」读起来就是错的。
    # 阶段「矩阵动作扩展」给它自己的动作；基线仍会执行，四个员工角色两者都有。
    _perm: None = Depends(PermissionChecker("memory", "create")),
):
    """
    将诊断结果持久化到学生的 memory.md 文件

    这是一个关键的后端API，用于实现"持久进化的Agent学习系统"：
    1. 老师上传答题卡 → OCR识别
    2. 老师确认学生身份
    3. 生成统计和诊断
    4. 【此处】将诊断结果写入学生的memory.md，实现学情持久化

    下次该学生再上传答题卡时，Agent会读取memory.md，
    结合历史诊断给出更准确的学情分析。
    """
    # student_id 在请求体里（守卫够不着），就地按数据范围收窄：跨班/跨校一律 403
    # 身份取自 token（权限已由本端点的 memory:create 校验，此处只要范围）
    require_student(get_current_user(http_request), db, request.student_id)
    try:
        # 导入 memory handler
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        from chem_skills.chemistry_memory.handler import MemoryHandler

        handler = MemoryHandler()

        # 调用 memory_on_diagnosis_completed
        result = handler.memory_on_diagnosis_completed(
            student_id=request.student_id,
            barrier_type=request.barrier_type,
            dominant_barrier=request.dominant_barrier,
            weak_kps=request.weak_kps
        )

        if result.get("success"):
            return DiagnosisCompleteResponse(
                success=True,
                message="诊断结果已持久化到学生记忆",
                student_id=request.student_id
            )
        else:
            return DiagnosisCompleteResponse(
                success=False,
                message=f"持久化失败: {result.get('error', '未知错误')}",
                student_id=request.student_id
            )

    except Exception as e:
        return DiagnosisCompleteResponse(
            success=False,
            message=f"持久化异常: {str(e)}",
            student_id=request.student_id
        )


@router.get("/student/{student_id}")
async def get_student_memory(
    student_id: str,
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取学生的学情记忆
    """
    try:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        from chem_skills.chemistry_memory.handler import MemoryHandler

        handler = MemoryHandler()
        result = handler.memory_student_get(student_id, memory_type="all")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_memory_stats():
    """
    获取记忆系统统计信息
    """
    try:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        from chem_skills.chemistry_memory.handler import MemoryHandler

        handler = MemoryHandler()
        result = handler.memory_stats()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
