"""工作区目录浏览器 — 老师在网页上「打开本地目录」选择/创建工作区。

浏览器安全模型下网页拿不到本机磁盘路径；本 API 在后端（单机部署 = 老师本机）
列出目录并支持新建文件夹，体验等同本地文件夹选择器。
只列目录与建目录，不读文件内容、不删除任何东西。
"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.middleware.auth import PermissionChecker

router = APIRouter(prefix="/api/workspace", tags=["工作区"])

DEFAULT_WORKSPACE = str(Path.home() / "ChemAI-Workspace")


def list_dirs(path: str) -> dict:
    """返回 {current, parent, dirs, default_ws}。path 为空时列出驱动器（Windows）
    或根目录（POSIX）。"""
    if not path or not path.strip():
        if os.name == "nt":
            import string
            drives = [f"{d}:\\" for d in string.ascii_uppercase
                      if os.path.exists(f"{d}:\\")]
            return {"current": "", "parent": None, "dirs": drives,
                    "default_ws": DEFAULT_WORKSPACE}
        path = "/"
    p = Path(path).expanduser()
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="目录不存在或不可访问")
    try:
        entries = sorted(
            (e.name for e in p.iterdir() if e.is_dir() and not e.name.startswith(".")),
            key=str.lower,
        )
    except PermissionError:
        raise HTTPException(status_code=400, detail="无权限访问该目录")
    parent = str(p.parent) if p.parent != p else None
    return {"current": str(p), "parent": parent, "dirs": entries,
            "default_ws": DEFAULT_WORKSPACE}


class MkdirRequest(BaseModel):
    path: str = ""
    name: str


def create_dir(path: str, name: str) -> str:
    """在当前浏览目录（空 = 默认工作区）下新建文件夹，返回完整路径。"""
    name = (name or "").strip()
    if not name or any(c in name for c in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="非法文件夹名")
    base = Path(path).expanduser() if path and path.strip() else Path(DEFAULT_WORKSPACE)
    target = base / name
    if target.exists():
        raise HTTPException(status_code=400, detail=f"文件夹已存在: {name}")
    target.mkdir(parents=True)
    return str(target)


@router.get("/dirs")
async def ws_dirs(path: str = ""):
    return list_dirs(path)


@router.post("/mkdir")
async def ws_mkdir(
    req: MkdirRequest,
    # 这是**写**端点（在服务器文件系统上建目录），原先只能靠 router 基线的
    # `workspace:read` 把关 —— 「read 权限能在服务器上建目录」读起来就是错的。
    # 四个员工角色本来就有 `workspace:create`，改门不改变可见性。
    _perm: None = Depends(PermissionChecker("workspace", "create")),
):
    return {"ok": True, "path": create_dir(req.path, req.name)}


@router.get("/default")
async def ws_default():
    return {"path": DEFAULT_WORKSPACE}
