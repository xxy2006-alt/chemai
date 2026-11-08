"""
知识点学习卡片 API
GET /api/knowledge/list - 获取所有知识点
GET /api/knowledge/{name} - 获取单个知识点详情
"""
from fastapi import APIRouter, HTTPException
from app.services.knowledge_graph import kg_service

router = APIRouter()


@router.get("/list")
async def list_knowledge_points():
    """获取所有知识点列表"""
    kps = kg_service.knowledge_points
    result = []
    for name, data in kps.items():
        result.append({
            "name": name,
            "category": data.get("category", ""),
            "description": data.get("description", ""),
            "difficulty": data.get("difficulty", "medium"),
            "exam_frequency": data.get("exam_frequency", "medium"),
            "related_kps": data.get("related_kps", [])
        })
    # 按分类排序
    result.sort(key=lambda x: (x["category"], x["name"]))
    return {"success": True, "knowledge_points": result}


@router.get("/{name}")
async def get_knowledge_point(name: str):
    """获取单个知识点详情"""
    kp = kg_service.get_knowledge_point(name)
    if not kp:
        raise HTTPException(status_code=404, detail=f"知识点 '{name}' 不存在")
    return {"success": True, "knowledge_point": kp}
