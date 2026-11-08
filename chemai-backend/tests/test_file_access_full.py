"""文件访问三档（2026-08 对齐 DSH）：off 关闭 / workspace 工作区(默认,区外按次审批)
/ full 完全访问(区外直接放行,敏感文件仍拒绝)。

测试自建工作区与区外文件（均在 tmp_path 下），不依赖机器上的任何真实路径。
"""
import asyncio
import json

import pytest

from agent.tools.filesystem import (
    read, set_file_access_level, set_workspace_root,
)


def _run(coro):
    async def go():
        return await coro

    return asyncio.run(go())


def _read(path):
    return json.loads(_run(read(path=str(path))))


@pytest.fixture(autouse=True)
def workspace(tmp_path):
    """把工作区钉在 tmp_path/ws，区内文件放 tmp_path/inside，区外文件放 tmp_path/outside。

    这样"工作区外"是结构上确定的，不依赖 ~/ChemAI-Workspace 或环境变量。
    """
    ws = tmp_path / "ws"
    ws.mkdir()
    set_workspace_root(str(ws))
    yield ws
    set_file_access_level("workspace")
    set_workspace_root("")


@pytest.fixture
def outside_file(tmp_path):
    """工作区外的一个普通文件（tmp_path/outside 与工作区 tmp_path/ws 平级）。"""
    d = tmp_path / "outside"
    d.mkdir(exist_ok=True)
    f = d / "sample.md"
    f.write_text("这是工作区外的内容", encoding="utf-8")
    return f


def test_full_mode_reads_outside_without_approval(outside_file):
    set_file_access_level("full")
    data = _read(outside_file)
    assert "approval_needed" not in data, f"full 档不应弹审批: {str(data)[:200]}"
    assert data.get("content") == "这是工作区外的内容"


def test_workspace_mode_still_requires_approval_outside(outside_file):
    set_file_access_level("workspace")
    data = _read(outside_file)
    assert data.get("approval_needed") is True


def test_off_mode_rejects_everything(outside_file):
    set_file_access_level("off")
    data = _read(outside_file)
    assert "error" in data
    assert "关闭" in str(data["error"])


def test_full_mode_still_rejects_sensitive_files(tmp_path):
    d = tmp_path / "outside"
    d.mkdir(exist_ok=True)
    env_file = d / ".env"
    env_file.write_text("SECRET=1", encoding="utf-8")

    set_file_access_level("full")
    data = _read(env_file)
    assert "error" in data
    assert "敏感文件" in str(data["error"])


def test_inside_workspace_needs_no_approval(workspace):
    """区内文件在默认 workspace 档下直接可读，不弹审批。"""
    f = workspace / "note.md"
    f.write_text("工作区内的内容", encoding="utf-8")

    set_file_access_level("workspace")
    data = _read(f)
    assert "approval_needed" not in data, f"区内不应弹审批: {str(data)[:200]}"
    assert data.get("content") == "工作区内的内容"


def test_set_level_accepts_full_and_falls_back_on_unknown():
    assert set_file_access_level("full") == "full"
    assert set_file_access_level("bogus") == "workspace"
    set_file_access_level("workspace")
