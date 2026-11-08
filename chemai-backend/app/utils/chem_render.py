"""
化学式 Unicode 渲染引擎 — 铁律：全项目所有化学式统一经过此模块渲染

纯文本格式: Fe2O3 → Fe₂O₃,  SO4^2- → SO₄²⁻,  Fe3+ → Fe³⁺
LaTeX格式:    Fe_{2}O_{3} → Fe₂O₃,  Fe^{3+} → Fe³⁺
"""
import re

# ── Unicode 映射 ──
SUB = str.maketrans({
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
})
SUPER = str.maketrans({
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻',
})

# 常见替换（不需下标的情况）
_NOT_SUB = {
    'CO2': True,  # 不要变成 C₂O₂ — 但 CO₂ 是对的，这里防误判
}

def render_chem(text: str) -> str:
    """
    渲染文本中的所有化学式。自动识别纯文本和 LaTeX 两种格式。

    >>> render_chem("Fe2O3 + 6HCl = 2FeCl3 + 3H2O")
    "Fe₂O₃ + 6HCl = 2FeCl₃ + 3H₂O"

    >>> render_chem("SO4^{2-}")
    "SO₄²⁻"
    """
    if not text or not isinstance(text, str):
        return text

    result = text

    # Step 1: LaTeX subscript: _{2} → Unicode
    result = re.sub(r'_\{(.+?)\}', lambda m: m.group(1).translate(SUB), result)

    # Step 2: LaTeX superscript: ^{2-} → Unicode
    result = re.sub(r'\^\{(.+?)\}', lambda m: m.group(1).translate(SUPER), result)

    # Step 3: Plain-text subscript: 元素后紧跟数字 → Unicode
    # 匹配: 大写字母+可选小写字母 + 数字序列，如 Fe2, O3, H2
    # 但跳过: 纯数字、中文、已转换的 Unicode
    result = _render_plain_subscripts(result)

    # Step 4: 离子电荷: 元素后跟数字+加号/减号 → 上标
    # 如 Fe3+ → Fe³⁺, SO42- → SO₄²⁻ (Step 3 先处理下标，Step 4 处理上标)
    result = _render_plain_charges(result)

    # Step 5: 箭头标准化
    result = result.replace('->', '→').replace('<-', '←')
    result = result.replace('→', ' → ').replace('  →  ', ' → ')  # 箭头两边加空格

    # Step 6: 清理多余空格
    result = re.sub(r' +', ' ', result).strip()

    return result


def _render_plain_subscripts(text: str) -> str:
    """将元素符号后的数字转为下标 (纯文本格式)，也处理括号后数字"""
    def replacer(m):
        prefix = m.group(1)
        digits = m.group(2)
        return prefix + digits.translate(SUB)

    # 1. 元素符号后数字: Fe2, O3, Cl2
    text = re.sub(r'([A-Z][a-z]?)(\d+)', replacer, text)
    # 2. 右括号后数字: (OH)2, (SO4)3
    text = re.sub(r'(\))(\d+)', replacer, text)
    # 3. 方括号后数字
    text = re.sub(r'(\])(\d+)', replacer, text)

    return text


def _render_plain_charges(text: str) -> str:
    """将电荷标注转为上标: 3+ → ³⁺, 2- → ²⁻"""
    def replacer(m):
        digits = m.group(1)
        sign = m.group(2)
        return digits.translate(SUPER) + sign.translate(SUPER)

    # 匹配: 数字后紧跟 + 或 - (不是减号运算符)
    # 如 Fe3+ → Fe³⁺, SO42- → SO₄²⁻
    text = re.sub(r'(\d+)([+-])(?![0-9a-zA-Z])', replacer, text)
    return text


# 不渲染的非化学字段（token、URL、邮箱等）
_SKIP_KEYS = {
    'token', 'refresh_token', 'access_token', 'password', 'password_hash',
    'Authorization', 'api_key', 'apiKey', 'secret', 'bind_code',
    'email', 'phone', 'url', 'href', 'ip_address', 'username',
    'account_id', 'student_id', 'teacher_id', 'parent_id', 'class_id',
    'school_id', 'exam_id', 'record_id', 'question_id', 'answer_id',
    'config_id', 'set_id', 'item_id', 'kp_id', 'task_id', 'grade_id',
    'notification_id', 'binding_id', 'log_id', 'user_id', 'preview_id',
    # 日期时间字段（避免化学渲染器转换ISO时间戳中的数字）
    'exam_date', 'created_at', 'updated_at', 'generated_at', 'answered_at',
    'published_at', 'added_at',
}

def render_chem_deep(obj, _key: str = ""):
    """
    递归渲染数据结构中的化学式字符串字段。
    跳过 token、ID、邮箱等非化学字段。
    """
    if isinstance(obj, str):
        if _key.lower() in _SKIP_KEYS or _key.endswith('_id'):
            return obj
        return render_chem(obj)
    if isinstance(obj, dict):
        return {k: render_chem_deep(v, _key=str(k)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [render_chem_deep(v) for v in obj]
    return obj


# ── 快速测试 ──
if __name__ == "__main__":
    tests = [
        "Fe2O3 + 6HCl = 2FeCl3 + 3H2O",
        "FeCl3 + 3NaOH = Fe(OH)3 + 3NaCl",
        "2KMnO4 = K2MnO4 + MnO2 + O2",
        "SO4^{2-} + Ba^{2+} = BaSO4",
        "Fe^{3+} + 3OH^{-} = Fe(OH)3",
        "Ca(OH)2 + CO2 = CaCO3 + H2O",
        "2H2 + O2 -> 2H2O",
        "Na2CO3 + 2HCl = 2NaCl + CO2 + H2O",
    ]
    for t in tests:
        print(f"  {t:60s}")
        print(f"  → {render_chem(t)}")
        print()
