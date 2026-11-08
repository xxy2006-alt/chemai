"""009 — RDKit SMILES→PNG 结构图渲染服务。

测试缝 = 渲染服务函数（输入 SMILES 输出 PNG 路径/字节）+ 静态图端点。
RDKit 是本机已装依赖（rdkit==2026.3.5），测试真实跑渲染。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.structure_render import render_smiles_png, IMG_DIR  # noqa: E402


class TestRenderSmilesPng:
    def test_valid_smiles_returns_png_path(self, tmp_path):
        """合法 SMILES（苯）→ 返回 PNG 文件路径，文件存在且非空。"""
        path = render_smiles_png("C1=CC=CC=C1", out_dir=str(tmp_path))
        assert path and os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n"  # PNG magic

    def test_same_smiles_cached(self, tmp_path):
        """相同 SMILES 二次调用命中缓存，返回同一路径，不重复渲染。"""
        p1 = render_smiles_png("C1=CC=CC=C1", out_dir=str(tmp_path))
        p2 = render_smiles_png("C1=CC=CC=C1", out_dir=str(tmp_path))
        assert p1 == p2

    def test_invalid_smiles_returns_none(self, tmp_path):
        """非法 SMILES → 返回 None（调用方退化为文本），不抛异常。"""
        assert render_smiles_png("NOT_A_SMILES", out_dir=str(tmp_path)) is None


class TestImageEndpoint:
    def test_serves_png(self, tmp_path, monkeypatch):
        """静态图端点返回 PNG 与正确 content-type。"""
        from fastapi.testclient import TestClient
        from app.main import app

        # 生成一张图写入默认 IMG_DIR，再通过 /static/question_images 访问
        p = render_smiles_png("C1=CC=CC=C1", out_dir=IMG_DIR)
        fname = os.path.basename(p)
        client = TestClient(app)
        r = client.get(f"/static/question_images/{fname}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")

    def test_missing_file_404(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        r = client.get("/static/question_images/nonexistent_000.png")
        assert r.status_code == 404
