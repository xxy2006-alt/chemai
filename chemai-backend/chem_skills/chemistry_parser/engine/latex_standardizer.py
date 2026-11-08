"""
LaTeX 化学公式标准化引擎
将 MinerU 解析出的 LaTeX 化学式转换为标准格式
"""
import re
from typing import Dict, List, Tuple


class LaTeXChemicalStandardizer:
    """LaTeX 化学公式标准化器"""

    # 下标数字映射
    SUBSCRIPT_MAP = {
        "0": "₀",
        "1": "₁",
        "2": "₂",
        "3": "₃",
        "4": "₄",
        "5": "₅",
        "6": "₆",
        "7": "₇",
        "8": "₈",
        "9": "₉",
    }

    # 上标数字映射（用于离子等）
    SUPERSCRIPT_MAP = {
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
        "+": "⁺",
        "-": "⁻",
    }

    def __init__(self):
        self.conversions: List[Tuple[str, str, str]] = []

    def standardize(self, latex: str) -> str:
        """
        标准化 LaTeX 化学公式

        Args:
            latex: LaTeX 格式的化学式

        Returns:
            标准化后的化学式
        """
        result = latex

        # 1. 处理下标 { } 格式，如 H_{2}O -> H2O 或 H₂O
        result = self._process_subscripts(result)

        # 2. 处理化学式中的希腊字母
        result = self._process_greek_letters(result)

        # 3. 处理箭头符号
        result = self._process_arrows(result)

        # 4. 处理离子格式
        result = self._process_ions(result)

        # 5. 处理括号和配对
        result = self._validate_parentheses(result)

        return result

    def _process_subscripts(self, text: str) -> str:
        """处理下标格式 H_{2} -> H₂"""
        # 匹配 {数字} 格式的下标
        pattern = r"\{(\d+)\}"
        matches = re.finditer(pattern, text)
        for match in matches:
            digit = match.group(1)
            subscript = self.SUBSCRIPT_MAP.get(digit, digit)
            text = text.replace(match.group(0), subscript)
        return text

    def _process_greek_letters(self, text: str) -> str:
        """处理希腊字母"""
        greek_map = {
            r"\alpha": "α",
            r"\beta": "β",
            r"\gamma": "γ",
            r"\delta": "δ",
            r"\Delta": "Δ",
            r"\theta": "θ",
            r"\lambda": "λ",
            r"\mu": "μ",
            r"\pi": "π",
            r"\sigma": "σ",
            r"\phi": "φ",
            r"\omega": "ω",
            r"\Omega": "Ω",
        }
        for latex, greek in greek_map.items():
            text = text.replace(latex, greek)
        return text

    def _process_arrows(self, text: str) -> str:
        """处理化学反应箭头"""
        arrow_map = {
            r"\rightarrow": "→",
            r"\leftarrow": "←",
            r"\leftrightarrow": "⇌",
            r"\Longrightarrow": "⇒",
            r"\Longleftarrow": "⇐",
            r"\xrightarrow": "→",
            r"\xleftarrow": "←",
            r"->": "→",
            r"<-": "←",
        }
        for latex, arrow in arrow_map.items():
            text = text.replace(latex, arrow)
        return text

    def _process_ions(self, text: str) -> str:
        """处理离子格式，如 Fe^{3+} -> Fe³⁺"""
        # 匹配 ^{3+} 等格式
        pattern = r"\^\{(\d*)([+-])\}"
        matches = re.finditer(pattern, text)
        for match in matches:
            num = match.group(1)
            sign = match.group(2)
            superscript = self.SUPERSCRIPT_MAP.get(num, num) + self.SUPERSCRIPT_MAP.get(sign, sign)
            text = text.replace(match.group(0), superscript)
        return text

    def _validate_parentheses(self, text: str) -> str:
        """验证括号匹配"""
        stack = []
        pairs = {"(": ")", "[": "]", "{": "}"}
        issues = []

        for char in text:
            if char in pairs.keys():
                stack.append(char)
            elif char in pairs.values():
                if stack and pairs.get(stack[-1]) == char:
                    stack.pop()
                else:
                    issues.append(f"括号不匹配: 意外的 {char}")

        if stack:
            issues.append(f"未闭合的括号: {stack}")

        return text

    def validate_chemical_formula(self, formula: str) -> Dict[str, any]:
        """
        验证化学式有效性

        Args:
            formula: 化学式

        Returns:
            验证结果
        """
        issues = []

        # 基本格式检查
        if not formula:
            issues.append("化学式为空")

        # 检查元素符号格式（首字母大写，后续小写）
        element_pattern = r"[A-Z][a-z]?"
        elements = re.findall(element_pattern, formula)

        if not elements:
            issues.append("未找到有效的元素符号")

        # 检查数字位置（通常在元素符号后）
        # 检查括号匹配
        paren_count = formula.count("(") - formula.count(")")
        if paren_count != 0:
            issues.append(f"括号不匹配: 差 {abs(paren_count)} 个")

        # 检查常见错误
        if "OO" in formula and "O2" not in formula:  # 可能是 O 和 O 而非 O₂
            issues.append("可能存在连续相同元素符号")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "elements_found": elements,
            "formula": formula,
        }


def standardize_latex_chemical(latex_str: str) -> str:
    """
    便捷函数：标准化 LaTeX 化学公式

    Args:
        latex_str: LaTeX 格式的化学式

    Returns:
        标准化后的化学式
    """
    standardizer = LaTeXChemicalStandardizer()
    return standardizer.standardize(latex_str)


if __name__ == "__main__":
    standardizer = LaTeXChemicalStandardizer()

    test_cases = [
        r"H_{2}O",
        r"Ca(OH)_{2}",
        r"Fe^{3+}",
        r"2H_{2} + O_{2} \rightarrow 2H_{2}O",
        r"CaCO_{3} \rightarrow CaO + CO_{2}",
        r"\alpha-Fe_{2}O_{3}",
    ]

    for case in test_cases:
        result = standardizer.standardize(case)
        validation = standardizer.validate_chemical_formula(result)
        print(f"输入: {case}")
        print(f"输出: {result}")
        print(f"有效: {validation['valid']}")
        print()
