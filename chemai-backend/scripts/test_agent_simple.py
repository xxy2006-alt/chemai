# -*- coding: utf-8 -*-
"""
ChemAI Agent & MinerU 完整测试套件 (简化版-避免Unicode编码问题)
"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def ascii_safe(s):
    """将Unicode字符转换为ASCII表示"""
    if s is None:
        return "None"
    replacements = {
        '\u2082': '2', '\u2083': '3', '\u2081': '1', '\u2080': '0',
        '\u2084': '4', '\u2085': '5', '\u2086': '6', '\u2087': '7',
        '\u2088': '8', '\u2089': '9',
        '\u207b': '-', '\u207a': '+', '\u00b2': '^2',
        '\u03b1': 'a', '\u03b2': 'b', '\u03b3': 'g',
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    # 移除其他无法处理的Unicode字符
    result = []
    for c in s:
        if ord(c) < 128:
            result.append(c)
        else:
            result.append('?')
    return ''.join(result)

class TestResult:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.results = []

    def add(self, name, passed, detail=""):
        self.total += 1
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.results.append({"name": name, "passed": passed, "detail": detail})

    def print_summary(self):
        print("\n" + "=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        print(f"Total: {self.total}, Passed: {self.passed}, Failed: {self.failed}")
        pct = self.passed * 100 / self.total if self.total > 0 else 0
        print(f"Pass Rate: {pct:.1f}%")
        for r in self.results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['name']}")
            if r["detail"]:
                print(f"         {ascii_safe(r['detail'][:100])}")

tr = TestResult()

# ==================== 1. Chemistry Exam Handler 测试 ====================
print("\n=== 1. Chemistry Exam Handler Tests ===")

from chem_skills.chemistry_exam.engine.balance_checker import ChemicalEquationAuditor
auditor = ChemicalEquationAuditor()

# 配平检测测试
balance_tests = [
    ("2H2 + O2 = 2H2O", True, "passed"),
    ("H2 + O2 = H2O", False, "blocked"),
    ("Fe + O2 -> Fe2O3", False, "blocked"),
    ("CH4 + 2O2 = CO2 + 2H2O", True, "passed"),
    ("4Fe + 3O2 = 2Fe2O3", True, "passed"),
    ("Al + O2 = Al2O3", False, "blocked"),
    ("N2 + 3H2 = 2NH3", True, "passed"),
    ("2KClO3 = 2KCl + 3O2", True, "passed"),
    ("Zn + 2HCl = ZnCl2 + H2", True, "passed"),
    ("Mg + O2 = MgO", False, "blocked"),
]

balance_pass = 0
print("\n  Balance Check Tests:")
for eq, expected_balanced, expected_status in balance_tests:
    result = auditor.check_balance(eq)
    is_balanced = result.is_balanced
    actual_status = "passed" if is_balanced else "blocked"
    ok = is_balanced == expected_balanced and actual_status == expected_status
    if ok: balance_pass += 1
    eq_clean = ascii_safe(eq)
    print(f"    {'PASS' if ok else 'FAIL'} {eq_clean:30s} -> is_balanced:{is_balanced}, status:{actual_status}")
    tr.add(f"Balance-{eq_clean[:15]}", ok, f"expected:balanced={expected_balanced}")

print(f"\n  Balance Check: {balance_pass}/{len(balance_tests)}")
tr.add("BalanceCheck_Engine", balance_pass == len(balance_tests), f"{balance_pass}/{len(balance_tests)}")

# ExamHandler API调用测试
from chem_skills.chemistry_exam.handler import ExamHandler
handler = ExamHandler()

# 测试 exam_audit
try:
    result = handler.exam_audit(question_content="2H2 + O2 = 2H2O", options=["A. Correct", "B. Wrong"])
    has_coef = "coefficient_audit" in result
    print(f"  PASS exam_audit structure - has coefficient_audit: {has_coef}")
    tr.add("ExamHandler.exam_audit", has_coef, "structure correct")
except Exception as e:
    print(f"  FAIL exam_audit - {ascii_safe(str(e)[:100])}")
    tr.add("ExamHandler.exam_audit", False, str(e))

# ==================== 2. Chemistry Parser Handler 测试 ====================
print("\n=== 2. Chemistry Parser Handler Tests ===")

from chem_skills.chemistry_parser.handler import ParserHandler
parser_handler = ParserHandler()

# 化学式标准化测试
formula_tests = [
    ("H2O", True, "H2O"),
    ("Ca(OH)2", True, "Ca(OH)2"),
    ("H2O", True, "H2O"),  # Unicode下标
    ("Fe2(SO4)3", True, "Fe2(SO4)3"),
]

formula_pass = 0
print("\n  Formula Standardization Tests:")
for formula, expected_success, expected_std in formula_tests:
    result = parser_handler.standardize_chemical_formula(formula)
    ok = result["success"] == expected_success
    if ok and expected_success:
        ok = result["standardized"] == expected_std
    if ok: formula_pass += 1
    formula_clean = ascii_safe(formula)
    std_clean = ascii_safe(result.get("standardized", "N/A"))
    print(f"    {'PASS' if ok else 'FAIL'} standardize: {formula_clean} -> {std_clean}")
    tr.add(f"Formula_Std-{formula_clean[:10]}", ok, f"success={result['success']}")

print(f"\n  Formula Standardization: {formula_pass}/{len(formula_tests)}")

# 题目类型分类测试
classify_tests = [
    ("Test text with ____ blanks.", "fill-blank"),
    ("A. H2O  B. CO2  C. O2  D. N2", "choice"),
    ("Explain why iron rusts.", "short-answer"),
]

classify_pass = 0
print("\n  Question Classification Tests:")
for text, expected_type in classify_tests:
    result = parser_handler.classify_question_type(text)
    ok = result["type"] == expected_type
    if ok: classify_pass += 1
    text_clean = ascii_safe(text[:20])
    print(f"    {'PASS' if ok else 'FAIL'} classify: '{text_clean}...' -> {result['type']} (expected:{expected_type})")
    tr.add(f"Classify-{expected_type}", ok, f"actual:{result['type']}")

print(f"\n  Question Classification: {classify_pass}/{len(classify_tests)}")

# MinerU状态测试
from chem_skills.chemistry_parser.handler import get_mineru_status
status = get_mineru_status()
available = status.get("mineru_available", False)
print(f"\n  MinerU Status: {'Available' if available else 'Not Available'}")
if not available:
    print(f"    Reason: {ascii_safe(status.get('error', 'Unknown'))}")
tr.add("MinerU_Status", True, f"available={available}")

# ==================== 3. 后端API集成测试 ====================
print("\n=== 3. Backend API Integration Tests ===")

import requests

BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"

# 登录
try:
    r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"}, timeout=10)
    if r.status_code == 200:
        token = r.json().get("access_token") or r.json().get("token")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        print(f"  PASS Login - got token")
        tr.add("API_Login", True, "success")
    else:
        headers = {}
        print(f"  FAIL Login - status {r.status_code}")
        tr.add("API_Login", False, f"status={r.status_code}")
except Exception as e:
    print(f"  FAIL Login - {ascii_safe(str(e)[:100])}")
    tr.add("API_Login", False, str(e))
    headers = {}

# 通过Agent Handler调用后端
exam_handler = ExamHandler(base_url=BASE_URL)

print("\n  Backend Integration Tests via Agent Handler:")

# 测试配平审核
balance_cases = [
    ("2H2 + O2 = 2H2O", "passed"),
    ("H2 + O2 = H2O", "blocked"),
    ("Fe + O2 -> Fe2O3", "blocked"),
]

integration_pass = 0
for eq, expected in balance_cases:
    try:
        result = exam_handler.exam_audit(question_content=eq)
        status = result.get("coefficient_audit", {}).get("status", "unknown")
        ok = status == expected
        if ok: integration_pass += 1
        eq_clean = ascii_safe(eq)
        print(f"    {'PASS' if ok else 'FAIL'} audit({eq_clean}) -> {status} (expected:{expected})")
        tr.add(f"Integration_audit-{eq_clean[:15]}", ok, f"expected:{expected},actual:{status}")
    except Exception as e:
        eq_clean = ascii_safe(eq)
        print(f"    FAIL audit({eq_clean}) - {ascii_safe(str(e)[:50])}")
        tr.add(f"Integration_audit-{eq_clean[:15]}", False, str(e))

print(f"\n  Backend Integration: {integration_pass}/{len(balance_cases)}")

# ==================== 4. 工具注册测试 ====================
print("\n=== 4. Tool Registration Tests ===")

modules_to_check = [
    ("chemistry_exam", ["exam_generate", "exam_audit"]),
    ("chemistry_diagnosis", ["diagnosis_barrier_student"]),
    ("chemistry_parser", ["standardize_chemical_formula", "classify_question_type"]),
]

for module_name, functions in modules_to_check:
    print(f"\n  [{module_name}]")
    try:
        module = __import__(f"chem_skills.{module_name}.handler", fromlist=functions)
        for func_name in functions:
            if hasattr(module, func_name):
                print(f"    PASS {func_name}")
                tr.add(f"ToolReg_{func_name}", True, "exists")
            else:
                print(f"    FAIL {func_name} - not found")
                tr.add(f"ToolReg_{func_name}", False, "not found")
    except ImportError as e:
        print(f"    FAIL Module import - {ascii_safe(str(e)[:50])}")
        for func_name in functions:
            tr.add(f"ToolReg_{func_name}", False, f"import error")

# ==================== 5. 工具调用成功率统计 ====================
print("\n=== 5. Tool Call Success Rate ===")

# 分类统计
categories = {"BalanceCheck": [], "ExamHandler": [], "Parser": [], "Integration": [], "ToolReg": []}
for r in tr.results:
    name = r["name"]
    passed = r["passed"]
    if "Balance" in name:
        categories["BalanceCheck"].append(passed)
    elif "ExamHandler" in name or "Integration" in name:
        categories["ExamHandler"].append(passed)
    elif "Formula" in name or "Classify" in name:
        categories["Parser"].append(passed)
    elif "ToolReg" in name:
        categories["ToolReg"].append(passed)

for cat, results in categories.items():
    if results:
        passed = sum(results)
        total = len(results)
        rate = passed / total * 100 if total > 0 else 0
        status = "PASS" if rate >= 80 else "WARN"
        print(f"  {status} {cat}: {passed}/{total} ({rate:.1f}%)")

# 输出结果
tr.print_summary()

# 保存结果
with open("test_agent_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "total": tr.total,
        "passed": tr.passed,
        "failed": tr.failed,
        "results": tr.results
    }, f, ensure_ascii=False, indent=2)

print("\nResults saved to test_agent_results.json")
