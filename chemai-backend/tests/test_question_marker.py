"""010 — AI 出题产 [SMILES:...] 标记 → 后端解析替换为结构图 <img>。

测试缝 = replace_smiles_markers（输入含标记的 content，输出替换后的 content）。
RDKit 是本机已装依赖，真实渲染（mock LLM 输出即可独立测解析）。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.structure_render import replace_smiles_markers, IMG_DIR  # noqa: E402


class TestReplaceSmilesMarkers:
    def test_with_marker_replaced_to_img(self, tmp_path):
        """含 [SMILES:...] 标记 → 替换为 <img src="/static/question_images/...">，图片文件已生成。"""
        out = replace_smiles_markers(
            "下列有机物的结构简式是[SMILES:C1=CC=CC=C1]", out_dir=str(tmp_path))
        assert out.startswith("下列有机物的结构简式是")
        assert "<img" in out
        m = re.search(r'src="([^"]+)"', out)
        assert m and m.group(1).startswith("/static/question_images/")
        fname = m.group(1).rsplit("/", 1)[-1]
        assert os.path.exists(os.path.join(str(tmp_path), fname))

    def test_bracket_atom_smiles_not_truncated(self, tmp_path):
        """带括号原子（[N+](C)(C)C）的 SMILES 不被内层 ] 截断。"""
        out = replace_smiles_markers(
            "写出[SMILES:C[N+](C)(C)C]的命名", out_dir=str(tmp_path))
        assert "C[N+](C)(C)C" in out

    def test_no_marker_passthrough(self, tmp_path):
        """无标记 content 原样返回，不做任何改动。"""
        content = "下列物质中属于电解质的是 $H_2SO_4$"
        assert replace_smiles_markers(content, out_dir=str(tmp_path)) == content

    def test_invalid_smiles_fallback_text(self, tmp_path):
        """非法 SMILES → 退化为 \\ce{...} 文本，不抛异常、不产生 <img>。"""
        out = replace_smiles_markers("结构为[SMILES:NOT_A_SMILES]", out_dir=str(tmp_path))
        assert "<img" not in out
        assert "\\ce{NOT_A_SMILES}" in out

    def test_empty_content(self, tmp_path):
        assert replace_smiles_markers("", out_dir=str(tmp_path)) == ""


class TestMarkerEndpoint:
    def test_marker_img_serves_png(self):
        """标记生成的图片 URL 通过静态端点返回 200 image/png。"""
        from fastapi.testclient import TestClient
        from app.main import app

        out = replace_smiles_markers("[SMILES:C1=CC=CC=C1]", out_dir=IMG_DIR)
        m = re.search(r'src="([^"]+)"', out)
        assert m
        client = TestClient(app)
        r = client.get(m.group(1))
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")
