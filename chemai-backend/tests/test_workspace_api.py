"""工作区目录浏览器 API 测试 — 只测纯函数（list_dirs / create_dir），零网络。"""
import os

import pytest
from fastapi import HTTPException

from app.api.workspace_api import create_dir, list_dirs


def test_list_dirs_sorted_subdirs_only(tmp_path):
    (tmp_path / "zebra").mkdir()
    (tmp_path / "Alpha").mkdir()
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    (tmp_path / ".hidden").mkdir()
    result = list_dirs(str(tmp_path))
    assert result["dirs"] == ["Alpha", "zebra"]  # 排序 + 只目录 + 隐藏排除
    assert result["parent"] == str(tmp_path.parent)
    assert result["current"] == str(tmp_path)


def test_list_dirs_empty_path_lists_root():
    result = list_dirs("")
    if os.name == "nt":
        assert any(d.endswith(":\\") for d in result["dirs"])  # 盘符
    else:
        assert result["dirs"], "POSIX 应列出根目录"


def test_list_dirs_nonexistent_raises():
    with pytest.raises(HTTPException):
        list_dirs(str(__import__("tempfile").mkdtemp()) + "/nope")


def test_create_dir_makes_folder(tmp_path):
    p = create_dir(str(tmp_path), "学生资料")
    assert os.path.isdir(p)
    assert os.path.basename(p) == "学生资料"


def test_create_dir_rejects_illegal_names(tmp_path):
    for bad in ("", "..", "a/b", "a\\b"):
        with pytest.raises(HTTPException):
            create_dir(str(tmp_path), bad)


def test_create_dir_rejects_existing(tmp_path):
    (tmp_path / "已有").mkdir()
    with pytest.raises(HTTPException):
        create_dir(str(tmp_path), "已有")
