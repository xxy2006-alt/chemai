"""
化学方程式配平检查引擎
复用 ChemAI 的 chemical_balance 服务
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.chemical_balance import (  # noqa: E402
    ChemicalEquationAuditor,
    BalanceResult,
    audit_chemical_equation,
)


class BalanceChecker:
    """
    化学方程式配平检查器

    提供独立的配平检查功能，不依赖 API 直接调用 chemical_balance 服务
    """

    def __init__(self):
        self.auditor = ChemicalEquationAuditor()

    def check_balance(self, equation: str) -> BalanceResult:
        """
        检查化学方程式是否配平

        Args:
            equation: 化学方程式，如 "2H2 + O2 → 2H2O"

        Returns:
            BalanceResult: 配平结果
        """
        return self.auditor.check_balance(equation)

    def check_conditions(self, equation: str) -> dict:
        """
        检查反应条件是否完整

        Args:
            equation: 化学方程式

        Returns:
            检查结果 dict
        """
        return self.auditor.check_conditions(equation)

    def check_product_stability(self, equation: str, products: list = None) -> dict:
        """
        检查产物稳定性

        Args:
            equation: 化学方程式
            products: 产物列表（可选）

        Returns:
            检查结果 dict
        """
        return self.auditor.check_product_stability(equation, products)

    def audit_equation(self, equation: str) -> dict:
        """
        综合审核化学方程式（四维审核）

        Args:
            equation: 化学方程式

        Returns:
            完整审核报告
        """
        return audit_chemical_equation(equation)


# 全局实例
balance_checker = BalanceChecker()


def check_balance(equation: str) -> BalanceResult:
    """快捷函数：检查配平"""
    return balance_checker.check_balance(equation)


def audit_equation(equation: str) -> dict:
    """快捷函数：综合审核"""
    return balance_checker.audit_equation(equation)
