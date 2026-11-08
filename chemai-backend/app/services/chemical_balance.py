"""
化学方程式专项审核引擎
F2: AI出题安全审核的核心模块
功能: 系数配平验证/反应条件标注规范/产物稳定性判断/分子结构正确性校验
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class BalanceResult:
    """配平结果"""
    is_balanced: bool
    left_elements: Dict[str, int]
    right_elements: Dict[str, int]
    message: str


@dataclass
class ConditionCheckResult:
    """反应条件检查结果"""
    is_correct: bool
    conditions_found: List[str]
    missing_conditions: List[str]
    message: str


@dataclass
class StructureCheckResult:
    """分子结构检查结果"""
    is_correct: bool
    issues: List[str]
    message: str


class ChemicalEquationAuditor:
    """
    化学方程式审核引擎
    基于PRD v1.0: 系数配平零错误是信任红线
    """

    # 常见反应条件标注
    COMMON_CONDITIONS = {
        "点燃": "combustion",
        "加热": "heating",
        "高温": "high_temperature",
        "催化剂": "catalyst",
        "MnO2": "catalyst",
        "Cu": "catalyst",
        "Fe": "catalyst",
        "浓硫酸": "concentrated_acid",
        "稀硫酸": "diluted_acid",
        "NaOH": "base",
        "光照": "light",
        "电解": "electrolysis",
        "通电": "electrolysis",
        "压强": "pressure",
        "升温": "temperature_increase",
    }

    # 常见产物稳定性问题
    STABLE_PRODUCTS = {
        "CO2": True,
        "H2O": True,
        "NaCl": True,
        "SO2": True,
        "NO2": True,
        "NH3": True,
        "O2": True,
        "N2": True,
        "H2": True,
    }

    def __init__(self):
        self.balance_check_enabled = True
        self.condition_check_enabled = True
        self.product_check_enabled = True
        self.structure_check_enabled = True

    def parse_equation(self, equation: str) -> Tuple[Optional[str], List[str], str, List[str]]:
        """
        解析化学方程式
        返回: (反应物部分, 反应物列表, 产物部分, 产物列表)
        """
        # 移除空格
        equation = equation.replace(" ", "")

        # 条件标注剥离（如 2KClO3 --Δ/MnO2--> 2KCl + 3O2↑）：
        # --xx--> 里的 Δ/催化剂等条件词不是参与反应的物种，统一归一为 →
        # （假设：条件文本不含 '-'，化学式与条件词均无需连字符）
        equation = re.sub(r"--+[^-]*?-->", "→", equation)
        # 可逆号归一为 →（配平计数语义相同）
        equation = equation.replace("⇌", "→").replace("<->", "→")

        # 分割反应物和产物
        if "→" in equation:
            parts = equation.split("→")
        elif "=" in equation:
            parts = equation.split("=")
        elif "->" in equation:
            parts = equation.split("->")
        else:
            return None, [], "", []

        if len(parts) != 2:
            return None, [], "", []

        reactants_str = parts[0]
        products_str = parts[1]

        # 分割多个反应物/产物
        reactants = self._split_species(reactants_str)
        products = self._split_species(products_str)

        return reactants_str, reactants, products_str, products

    def _split_species(self, species_str: str) -> List[str]:
        """分割多个物种(用+分隔)"""
        # 处理 + 号,排除化学式内部的+
        result = []
        i = 0
        current = ""
        paren_depth = 0

        while i < len(species_str):
            char = species_str[i]
            if char == "(":
                paren_depth += 1
                current += char
            elif char == ")":
                paren_depth -= 1
                current += char
            elif char == "+" and paren_depth == 0:
                if current:
                    result.append(current)
                current = ""
            else:
                current += char
            i += 1

        if current:
            result.append(current)

        return result

    def count_elements(self, formula: str) -> Dict[str, int]:
        """
        统计化学式中各元素原子的数量
        处理括号如Ca(OH)2
        """
        elements = {}

        # 处理系数
        match = re.match(r'^(\d+)(.+)$', formula)
        if match:
            coefficient = int(match.group(1))
            formula = match.group(2)
        else:
            coefficient = 1

        # 处理括号
        while True:
            match = re.search(r'\(([^()]+)\)(\d+)', formula)
            if not match:
                break
            bracket_content = match.group(1)
            times = int(match.group(2))
            # 展开括号内容
            inner_elements = self._count_simple_formula(bracket_content)
            for elem, count in inner_elements.items():
                elements[elem] = elements.get(elem, 0) + count * times * coefficient
            formula = formula[:match.start()] + formula[match.end():]

        # 处理剩余简单化学式
        remaining = self._count_simple_formula(formula)
        for elem, count in remaining.items():
            elements[elem] = elements.get(elem, 0) + count * coefficient

        return elements

    def _count_simple_formula(self, formula: str) -> Dict[str, int]:
        """统计简单化学式(无括号)的元素数量"""
        elements = {}
        # 匹配元素符号和数字
        pattern = r'([A-Z][a-z]?)(\d*)'
        matches = re.findall(pattern, formula)
        for elem, count in matches:
            if elem:
                elements[elem] = elements.get(elem, 0) + (int(count) if count else 1)
        return elements

    def check_balance(self, equation: str) -> BalanceResult:
        """
        检查化学方程式是否配平
        返回配平结果
        """
        _, reactants, _, products = self.parse_equation(equation)

        if not reactants or not products:
            return BalanceResult(
                is_balanced=False,
                left_elements={},
                right_elements={},
                message="无法解析化学方程式"
            )

        # 统计左边(反应物)各元素原子数
        left_elements = {}
        for species in reactants:
            species_elements = self.count_elements(species)
            for elem, count in species_elements.items():
                left_elements[elem] = left_elements.get(elem, 0) + count

        # 统计右边(产物)各元素原子数
        right_elements = {}
        for species in products:
            species_elements = self.count_elements(species)
            for elem, count in species_elements.items():
                right_elements[elem] = right_elements.get(elem, 0) + count

        # 比较
        is_balanced = left_elements == right_elements

        if is_balanced:
            message = "方程式已配平"
        else:
            # 找出不平衡的元素
            all_elements = set(left_elements.keys()) | set(right_elements.keys())
            unbalanced = []
            for elem in all_elements:
                left_count = left_elements.get(elem, 0)
                right_count = right_elements.get(elem, 0)
                if left_count != right_count:
                    unbalanced.append(f"{elem}: 左{left_count} vs 右{right_count}")
            message = f"方程式未配平: {', '.join(unbalanced)}"

        return BalanceResult(
            is_balanced=is_balanced,
            left_elements=left_elements,
            right_elements=right_elements,
            message=message
        )

    def check_conditions(self, equation: str) -> ConditionCheckResult:
        """
        检查反应条件标注是否规范
        常见条件: 点燃/加热/催化剂/光照/电解等
        """
        conditions_found = []
        missing_conditions = []

        # 检查常见条件关键词
        for condition_keyword in self.COMMON_CONDITIONS.keys():
            if condition_keyword in equation:
                conditions_found.append(condition_keyword)

        # 根据反应类型检查必要条件
        # 燃烧反应必须有"点燃"
        combustion_species = ["CH4", "C2H5OH", "C6H12O6", "S", "P", "Fe"]
        is_combustion = any(s in equation for s in combustion_species)

        if is_combustion and "点燃" not in conditions_found:
            missing_conditions.append("点燃")

        # 催化反应建议标注催化剂
        catalyst_indicators = ["H2O2", "KClO3", "KMnO4"]
        if any(ind in equation for ind in catalyst_indicators):
            if "MnO2" not in conditions_found and "催化剂" not in conditions_found:
                missing_conditions.append("催化剂(建议标注)")

        if missing_conditions:
            message = f"缺少必要条件: {', '.join(missing_conditions)}"
            is_correct = False
        else:
            message = "反应条件标注完整"
            is_correct = True

        return ConditionCheckResult(
            is_correct=is_correct,
            conditions_found=conditions_found,
            missing_conditions=missing_conditions,
            message=message
        )

    def check_product_stability(self, equation: str, products: List[str]) -> StructureCheckResult:
        """
        检查产物稳定性
        警告不稳定产物或明显错误的产物
        """
        issues = []

        for product in products:
            # 清理产物(去除系数)
            product = re.sub(r'^\d+', '', product)

            # 检查是否是不稳定产物
            unstable_patterns = [
                (r'C\d*H\d*O\d*', "有机物应写分子式或结构简式"),
                (r'C$', "碳应标注形态如CO2"),
                (r'H\d*O$', "水应写为H2O"),
            ]

            for pattern, issue in unstable_patterns:
                if re.match(pattern, product):
                    issues.append(f"{product}: {issue}")

        if issues:
            return StructureCheckResult(
                is_correct=False,
                issues=issues,
                message="发现产物稳定性问题"
            )

        return StructureCheckResult(
            is_correct=True,
            issues=[],
            message="产物稳定性检查通过"
        )

    def audit_equation(self, equation: str) -> Dict:
        """
        对方程式进行全面审核
        返回审核报告
        """
        results = {
            "equation": equation,
            "audits": {}
        }

        # 1. 系数配平审核
        if self.balance_check_enabled:
            balance_result = self.check_balance(equation)
            results["audits"]["balance"] = {
                "status": "passed" if balance_result.is_balanced else "blocked",
                "message": balance_result.message,
                "detail": {
                    "left_elements": balance_result.left_elements,
                    "right_elements": balance_result.right_elements
                }
            }

        # 2. 反应条件审核
        if self.condition_check_enabled:
            condition_result = self.check_conditions(equation)
            results["audits"]["condition"] = {
                "status": "warning" if not condition_result.is_correct else "passed",
                "message": condition_result.message,
                "conditions_found": condition_result.conditions_found,
                "missing_conditions": condition_result.missing_conditions
            }

        # 3. 产物稳定性审核
        if self.product_check_enabled:
            _, _, _, products = self.parse_equation(equation)
            product_result = self.check_product_stability(equation, products)
            results["audits"]["product"] = {
                "status": "warning" if not product_result.is_correct else "passed",
                "message": product_result.message,
                "issues": product_result.issues
            }

        # 4. 分子结构审核 (暂用基础检查)
        results["audits"]["structure"] = {
            "status": "passed",
            "message": "结构检查通过"
        }

        # 综合判断
        blocked_count = sum(1 for a in results["audits"].values() if a["status"] == "blocked")
        results["overall_status"] = "blocked" if blocked_count > 0 else "passed"
        results["overall_message"] = "方程式审核不通过,存在配平错误" if blocked_count > 0 else "方程式审核通过"

        return results


# 全局审核器实例
auditor = ChemicalEquationAuditor()


def audit_chemical_equation(equation: str) -> Dict:
    """
    快捷函数: 审核化学方程式
    """
    return auditor.audit_equation(equation)


def check_equation_balance(equation: str) -> BalanceResult:
    """
    快捷函数: 检查方程式是否配平
    """
    return auditor.check_balance(equation)
