"""parse_llm_json 回归测试（evals）
用户反馈：AI 出题的 \rightleftharpoons 反斜杠丢失（json.loads 把 \r 当回车符）。
修复后：未转义 LaTeX 命令反斜杠被转义；已转义的不重复转义；\n 换行不受影响。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_service import parse_llm_json  # noqa: E402


def test_unescaped_latex_backslash_repaired():
    """LLM 输出未转义的 \\rightleftharpoons（模拟真实损坏输入）→ 反斜杠保留、无 CR"""
    raw = '{"content": "对于可逆反应 AX+B \\rightleftharpoons CA+B\\rightleftharpoonsC，平衡如何变化？"}'
    d = parse_llm_json(raw)
    c = d["content"]
    assert "\\rightleftharpoons" in c
    assert "\r" not in c


def test_already_escaped_not_double_escaped():
    """已转义的双反斜杠不被重复转义"""
    raw = '{"content": "反应 N2 + 3H2 \\\\rightleftharpoons 2NH3"}'
    d = parse_llm_json(raw)
    assert d["content"] == "反应 N2 + 3H2 \\rightleftharpoons 2NH3"


def test_json_newline_escape_unaffected():
    """JSON 换行转义 \\n 不受影响"""
    raw = '{"content": "第一行\\n第二行"}'
    d = parse_llm_json(raw)
    assert d["content"] == "第一行\n第二行"


def test_code_fence_wrapped():
    """```json 代码块包裹也能解析"""
    raw = '```json\n{"questions": [{"content": "A $\\\\bf{N}$ 选项"}]}\n```'
    d = parse_llm_json(raw)
    assert d["questions"][0]["content"] == "A $\\bf{N}$ 选项"


def test_ph_and_text_commands():
    """\\pH 与 \\text 等命令修复"""
    raw = '{"content": "$\\\\frac{1}{2}$ 和 \\text 文字、\\pH=1"}'
    d = parse_llm_json(raw)
    assert "\\text" in d["content"]
    assert "\\pH" in d["content"]


def test_unicode_escape_sequence_untouched():
    """\\uXXXX unicode 转义（后接十六进制数字）不受影响"""
    raw = '{"content": "\\u00e9 字符"}'
    d = parse_llm_json(raw)
    assert d["content"] == "é 字符"
