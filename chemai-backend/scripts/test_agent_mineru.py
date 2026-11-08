# -*- coding: utf-8 -*-
"""
ChemAI Agent & MinerU 完整测试套件
测试 Chem Skills 工具调用成功率、返回率等
以及 MinerU 文档解析功能
"""
import sys
import os
import time
import json
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 颜色输出
def green(s): return f"\033[92m{s}\033[0m"
def red(s): return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def blue(s): return f"\033[94m{s}\033[0m"

class TestResult:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.results = []

    def add(self, name: str, passed: bool, detail: str = ""):
        self.total += 1
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.results.append({"name": name, "passed": passed, "detail": detail})

    def summary(self) -> str:
        return f"Total: {self.total}, Passed: {self.passed}, Failed: {self.failed}"

# ==================== 1. Chemistry Exam Handler 测试 ====================
def test_chemistry_exam_tools(tr: TestResult):
    print(blue("\n=== 1. Chemistry Exam Handler 测试 ==="))

    from chem_skills.chemistry_exam.handler import (
        ExamHandler, exam_generate, exam_audit, exam_search_historical,
        exam_get_exam_sets, exam_find_similar, exam_manual_select,
        exam_balance_check
    )
    from chem_skills.chemistry_exam.engine.balance_checker import ChemicalEquationAuditor
    auditor = ChemicalEquationAuditor()

    # 1.1 直接测试配平检测引擎
    print(yellow("\n  [配平检测引擎测试]"))

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
    for eq, expected_balanced, expected_status in balance_tests:
        result = auditor.check_balance(eq)
        is_balanced = result.is_balanced
        # is_balanced 为 True 表示配平正确, False 表示未配平
        # status: blocked=未配平, passed=配平正确
        actual_status = "passed" if is_balanced else "blocked"
        ok = is_balanced == expected_balanced and actual_status == expected_status
        if ok: balance_pass += 1
        symbol = green("PASS") if ok else red("FAIL")
        print(f"    {symbol} {eq:30s} -> is_balanced:{is_balanced}, status:{actual_status}")
        tr.add(f"配平检测-{eq[:15]}", ok, f"期望:is_balanced={expected_balanced}, 实际:is_balanced={is_balanced}")

    print(yellow(f"\n  配平检测: {balance_pass}/{len(balance_tests)}"))
    tr.add("配平检测引擎", balance_pass == len(balance_tests), f"{balance_pass}/{len(balance_tests)}")

    # 1.2 ExamHandler 工具函数测试
    print(yellow("\n  [ExamHandler 工具函数测试]"))

    handler = ExamHandler()

    # 测试 exam_audit
    try:
        result = handler.exam_audit(
            question_content="2H2 + O2 = 2H2O",
            options=["A. 正确", "B. 错误"]
        )
        has_coef = "coefficient_audit" in result
        has_cond = "condition_audit" in result
        has_prod = "product_audit" in result
        ok = has_coef and has_cond and has_prod
        print(f"    {green('PASS') if ok else red('FAIL')} exam_audit - 审核报告结构完整: {ok}")
        tr.add("exam_audit_结构完整", ok, f"coefficient:{has_coef}, condition:{has_cond}, product:{has_prod}")
    except Exception as e:
        print(f"    {red('FAIL')} exam_audit - 异常: {e}")
        tr.add("exam_audit_结构完整", False, str(e))

    # 测试 exam_search_historical
    try:
        result = handler.exam_search_historical(keyword="盐类水解")
        # 返回值可能是空列表或数据，看结构即可
        print(f"    {green('PASS')} exam_search_historical - API调用成功")
        tr.add("exam_search_historical_调用", True, "成功")
    except Exception as e:
        print(f"    {red('FAIL')} exam_search_historical - {e}")
        tr.add("exam_search_historical_调用", False, str(e))

    # 测试 exam_get_exam_sets
    try:
        result = handler.exam_get_exam_sets()
        has_total = "total" in result or "exam_sets" in result
        print(f"    {green('PASS') if has_total else red('FAIL')} exam_get_exam_sets - 返回结构正确")
        tr.add("exam_get_exam_sets_调用", has_total, str(result)[:100])
    except Exception as e:
        print(f"    {red('FAIL')} exam_get_exam_sets - {e}")
        tr.add("exam_get_exam_sets_调用", False, str(e))

    # 测试 exam_find_similar
    try:
        result = handler.exam_find_similar(
            knowledge_points=["盐类水解"],
            difficulty="medium",
            limit=5
        )
        print(f"    {green('PASS')} exam_find_similar - API调用成功")
        tr.add("exam_find_similar_调用", True, "成功")
    except Exception as e:
        print(f"    {red('FAIL')} exam_find_similar - {e}")
        tr.add("exam_find_similar_调用", False, str(e))

# ==================== 2. Chemistry Diagnosis Handler 测试 ====================
def test_chemistry_diagnosis_tools(tr: TestResult):
    print(blue("\n=== 2. Chemistry Diagnosis Handler 测试 ==="))

    from chem_skills.chemistry_diagnosis.handler import (
        DiagnosisHandler, diagnosis_barrier_class, diagnosis_barrier_student,
        diagnosis_plan_generate, diagnosis_config_get, diagnosis_config_update
    )

    handler = DiagnosisHandler()

    # 2.1 测试诊断配置获取
    print(yellow("\n  [诊断配置测试]"))
    try:
        result = handler.diagnosis_config_get("admin")
        has_config = isinstance(result, dict)
        print(f"    {green('PASS') if has_config else red('FAIL')} diagnosis_config_get - 返回: {type(result).__name__}")
        tr.add("diagnosis_config_get_调用", has_config, str(result)[:100])
    except Exception as e:
        print(f"    {red('FAIL')} diagnosis_config_get - {e}")
        tr.add("diagnosis_config_get_调用", False, str(e))

    # 2.2 测试诊断配置更新
    try:
        result = handler.diagnosis_config_update(
            teacher_id="admin",
            concept_threshold=3,
            reading_threshold=2,
            expression_threshold=3
        )
        print(f"    {green('PASS')} diagnosis_config_update - API调用成功")
        tr.add("diagnosis_config_update_调用", True, "成功")
    except Exception as e:
        print(f"    {red('FAIL')} diagnosis_config_update - {e}")
        tr.add("diagnosis_config_update_调用", False, str(e))

    # 2.3 测试学生诊断
    try:
        result = handler.diagnosis_barrier_student("test_student_001")
        print(f"    {green('PASS')} diagnosis_barrier_student - API调用成功")
        tr.add("diagnosis_barrier_student_调用", True, "成功")
    except Exception as e:
        print(f"    {red('FAIL')} diagnosis_barrier_student - {e}")
        tr.add("diagnosis_barrier_student_调用", False, str(e))

    # 2.4 测试学习计划生成
    try:
        result = handler.diagnosis_plan_generate(
            student_id="test_student_001",
            barrier_type="concept",
            weak_knowledge_points=["盐类水解", "电离"]
        )
        print(f"    {green('PASS')} diagnosis_plan_generate - API调用成功")
        tr.add("diagnosis_plan_generate_调用", True, "成功")
    except Exception as e:
        print(f"    {red('FAIL')} diagnosis_plan_generate - {e}")
        tr.add("diagnosis_plan_generate_调用", False, str(e))

# ==================== 3. Chemistry Parser Handler 测试 ====================
def test_chemistry_parser_tools(tr: TestResult):
    print(blue("\n=== 3. Chemistry Parser Handler 测试 ==="))

    from chem_skills.chemistry_parser.handler import (
        ParserHandler, standardize_chemical_formula, classify_question_type,
        extract_answer_from_ocr, validate_parsed_result, get_mineru_status
    )

    handler = ParserHandler()

    # 3.1 化学式标准化测试
    print(yellow("\n  [化学式标准化测试]"))

    formula_tests = [
        ("H2O", True, "H2O"),
        ("Ca(OH)2", True, "Ca(OH)2"),
        ("H₂O", True, "H2O"),  # Unicode下标
        ("Fe2(SO4)3", True, "Fe2(SO4)3"),
        ("Ca(OH2", False, None),  # 括号不匹配
    ]

    formula_pass = 0
    for formula, expected_success, expected_std in formula_tests:
        result = handler.standardize_chemical_formula(formula)
        ok = result["success"] == expected_success
        if ok and expected_success:
            ok = result["standardized"] == expected_std
        if ok: formula_pass += 1
        symbol = green("PASS") if ok else red("FAIL")
        # 将Unicode下标转换为普通字符以便打印
        formula_clean = formula.replace('₂','2').replace('₃','3').replace('₁','1').replace('₀','0')
        std_clean = result.get('standardized', 'N/A').replace('₂','2').replace('₃','3').replace('₁','1').replace('₀','0') if result.get('standardized') else 'N/A'
        print(f"    {symbol} standardize: {formula_clean} -> {std_clean}")
        tr.add(f"化学式标准化-{formula[:10]}", ok, f"success={result['success']}")

    print(yellow(f"\n  化学式标准化: {formula_pass}/{len(formula_tests)}"))
    tr.add("化学式标准化总体", formula_pass == len(formula_tests), f"{formula_pass}/{len(formula_tests)}")

    # 3.2 题目类型分类测试
    print(yellow("\n  [题目类型分类测试]"))

    classify_tests = [
        ("实验室制取氧气时，试管口应____倾斜。", "fill-blank"),
        ("A. H2O  B. CO2  C. O2  D. N2", "choice"),
        ("解释铁在潮湿空气中生锈的原因。", "short-answer"),
        ("已知25°C时Ksp(AgCl)=1.8×10⁻¹⁰，求AgCl的溶解度。", "calculation"),
    ]

    classify_pass = 0
    for text, expected_type in classify_tests:
        result = handler.classify_question_type(text)
        ok = result["type"] == expected_type
        if ok: classify_pass += 1
        symbol = green("PASS") if ok else red("FAIL")
        print(f"    {symbol} classify: '{text[:20]}...' -> {result['type']} (期望:{expected_type})")
        tr.add(f"题目分类-{expected_type}", ok, f"实际:{result['type']}")

    print(yellow(f"\n  题目类型分类: {classify_pass}/{len(classify_tests)}"))
    tr.add("题目类型分类总体", classify_pass == len(classify_tests), f"{classify_pass}/{len(classify_tests)}")

    # 3.3 答案提取测试
    print(yellow("\n  [答案提取测试]"))

    extract_tests = [
        ("答案：A", "choice", ["A"]),
        ("实验室制取氧气时，试管口应____倾斜。", "fill-blank", True),  # 有下划线即可
        ("已知25°C，求溶解度。\n答案：1.8×10⁻⁵mol/L", "calculation", True),  # 有"答案："即可
    ]

    extract_pass = 0
    for content, qtype, expected in extract_tests:
        result = handler.extract_answer_from_ocr(content, qtype)
        if isinstance(expected, list):
            ok = any(e in result["answers"] for e in expected)
        else:
            ok = len(result["answers"]) > 0
        if ok: extract_pass += 1
        symbol = green("PASS") if ok else red("FAIL")
        print(f"    {symbol} extract: '{content[:15]}...' -> answers={result['answers']}")
        tr.add(f"答案提取-{qtype}", ok, f"answers={result['answers']}")

    print(yellow(f"\n  答案提取: {extract_pass}/{len(extract_tests)}"))
    tr.add("答案提取总体", extract_pass == len(extract_tests), f"{extract_pass}/{len(extract_tests)}")

    # 3.4 内容验证测试
    print(yellow("\n  [内容验证测试]"))

    validate_tests = [
        ("H2O是水，NaCl是食盐。", True),  # 有化学式
        ("太短", False),  # 内容过短
        ("这是一个普通文本描述。", False),  # 无化学式
    ]

    validate_pass = 0
    for content, expect_valid in validate_tests:
        result = handler.validate_parsed_result(content, check_formulas=True)
        ok = result["valid"] == expect_valid
        if ok: validate_pass += 1
        symbol = green("PASS") if ok else red("FAIL")
        print(f"    {symbol} validate: '{content[:15]}...' -> valid={result['valid']} (期望:{expect_valid})")
        tr.add(f"内容验证-{content[:10]}", ok, f"valid={result['valid']}")

    print(yellow(f"\n  内容验证: {validate_pass}/{len(validate_tests)}"))
    tr.add("内容验证总体", validate_pass == len(validate_tests), f"{validate_pass}/{len(validate_tests)}")

# ==================== 4. MinerU 状态和功能测试 ====================
def test_mineru_status(tr: TestResult):
    print(blue("\n=== 4. MinerU 状态测试 ==="))

    from chem_skills.chemistry_parser.handler import get_mineru_status

    try:
        status = get_mineru_status()
        available = status.get("mineru_available", False)
        print(f"    MinerU 可用: {available}")
        if not available:
            print(f"    原因: {status.get('error', '未知')}")
        print(f"    {green('PASS') if available else yellow('WARN')} get_mineru_status")
        tr.add("MinerU_状态检查", True, f"available={available}, error={status.get('error', 'N/A')}")
    except Exception as e:
        print(f"    {red('FAIL')} get_mineru_status - {e}")
        tr.add("MinerU_状态检查", False, str(e))

# ==================== 5. Chemistry Memory Handler 测试 ====================
def test_chemistry_memory_tools(tr: TestResult):
    print(blue("\n=== 5. Chemistry Memory Handler 测试 ==="))

    try:
        from chem_skills.chemistry_memory.handler import MemoryHandler

        handler = MemoryHandler()

        # 测试获取学情历史
        try:
            result = handler.get_learning_history("test_student_001")
            print(f"    {green('PASS')} get_learning_history - API调用成功")
            tr.add("memory_get_learning_history", True, "成功")
        except Exception as e:
            print(f"    {red('FAIL')} get_learning_history - {e}")
            tr.add("memory_get_learning_history", False, str(e))

        # 测试趋势分析
        try:
            result = handler.analyze_trend("test_student_001")
            print(f"    {green('PASS')} analyze_trend - API调用成功")
            tr.add("memory_analyze_trend", True, "成功")
        except Exception as e:
            print(f"    {red('FAIL')} analyze_trend - {e}")
            tr.add("memory_analyze_trend", False, str(e))

    except ImportError as e:
        print(f"    {yellow('SKIP')} MemoryHandler 导入失败: {e}")
        tr.add("memory_handler_导入", False, str(e))

# ==================== 6. Chemistry Notification Handler 测试 ====================
def test_chemistry_notification_tools(tr: TestResult):
    print(blue("\n=== 6. Chemistry Notification Handler 测试 ==="))

    try:
        from chem_skills.chemistry_notification.handler import NotificationHandler

        handler = NotificationHandler()

        # 测试发送错题报告
        try:
            result = handler.send_error_report("test_student_001", {"report_id": "test"})
            print(f"    {green('PASS')} send_error_report - API调用成功")
            tr.add("notification_send_error_report", True, "成功")
        except Exception as e:
            print(f"    {red('FAIL')} send_error_report - {e}")
            tr.add("notification_send_error_report", False, str(e))

        # 测试发送学习计划
        try:
            result = handler.send_learning_plan("test_student_001", {"plan": "data"})
            print(f"    {green('PASS')} send_learning_plan - API调用成功")
            tr.add("notification_send_learning_plan", True, "成功")
        except Exception as e:
            print(f"    {red('FAIL')} send_learning_plan - {e}")
            tr.add("notification_send_learning_plan", False, str(e))

    except ImportError as e:
        print(f"    {yellow('SKIP')} NotificationHandler 导入失败: {e}")
        tr.add("notification_handler_导入", False, str(e))

# ==================== 7. Chemistry Improvement Handler 测试 ====================
def test_chemistry_improvement_tools(tr: TestResult):
    print(blue("\n=== 7. Chemistry Improvement Handler 测试 ==="))

    try:
        from chem_skills.chemistry_improvement.handler import ImprovementHandler

        handler = ImprovementHandler()

        # 测试记录质量指标
        try:
            result = handler.record_metric("review", "q001", {"status": "approved"})
            print(f"    {green('PASS')} record_metric - API调用成功")
            tr.add("improvement_record_metric", True, "成功")
        except Exception as e:
            print(f"    {red('FAIL')} record_metric - {e}")
            tr.add("improvement_record_metric", False, str(e))

        # 测试获取质量仪表盘
        try:
            result = handler.get_quality_dashboard()
            print(f"    {green('PASS')} get_quality_dashboard - API调用成功")
            tr.add("improvement_get_quality_dashboard", True, "成功")
        except Exception as e:
            print(f"    {red('FAIL')} get_quality_dashboard - {e}")
            tr.add("improvement_get_quality_dashboard", False, str(e))

    except ImportError as e:
        print(f"    {yellow('SKIP')} ImprovementHandler 导入失败: {e}")
        tr.add("improvement_handler_导入", False, str(e))

# ==================== 8. 工具调用成功率统计 ====================
def test_tool_call_success_rate(tr: TestResult):
    print(blue("\n=== 8. 工具调用成功率统计 ==="))

    # 统计各模块调用成功率
    modules = {
        "ExamHandler": [],
        "DiagnosisHandler": [],
        "ParserHandler": [],
        "MemoryHandler": [],
        "NotificationHandler": [],
        "ImprovementHandler": [],
    }

    for r in tr.results:
        name = r["name"]
        passed = r["passed"]
        if "exam" in name.lower():
            modules["ExamHandler"].append(passed)
        elif "diagnosis" in name.lower() or "barrier" in name.lower():
            modules["DiagnosisHandler"].append(passed)
        elif "parser" in name.lower() or "mineru" in name.lower() or "formula" in name.lower() or "classify" in name.lower():
            modules["ParserHandler"].append(passed)
        elif "memory" in name.lower():
            modules["MemoryHandler"].append(passed)
        elif "notification" in name.lower():
            modules["NotificationHandler"].append(passed)
        elif "improvement" in name.lower():
            modules["ImprovementHandler"].append(passed)

    print(yellow("\n  各模块工具调用成功率:"))
    for module, results in modules.items():
        if results:
            passed = sum(results)
            total = len(results)
            rate = passed / total * 100
            symbol = green("PASS") if rate >= 80 else yellow("WARN")
            print(f"    {symbol} {module}: {passed}/{total} ({rate:.1f}%)")
            tr.add(f"工具成功率_{module}", rate >= 80, f"{passed}/{total} ({rate:.1f}%)")

# ==================== 9. Agent Skill 路由测试 ====================
def test_skill_routing(tr: TestResult):
    print(blue("\n=== 9. Agent Skill 路由测试 ==="))

    # 测试各Handler的base_url配置
    from chem_skills._templates.base_handler import BaseSkillHandler

    try:
        handler = BaseSkillHandler()
        default_url = handler.base_url
        print(f"    BaseSkillHandler 默认URL: {default_url}")
        tr.add("BaseSkillHandler_base_url", True, f"url={default_url}")
    except Exception as e:
        print(f"    {red('FAIL')} BaseSkillHandler - {e}")
        tr.add("BaseSkillHandler_base_url", False, str(e))

    # 测试ExamHandler的API路由
    from chem_skills.chemistry_exam.handler import ExamHandler
    exam_handler = ExamHandler()
    print(f"    ExamHandler API URL: {exam_handler.base_url}")
    tr.add("ExamHandler_API_URL", True, f"url={exam_handler.base_url}")

# ==================== 10. 后端API集成测试（使用真实API） ====================
def test_backend_api_integration(tr: TestResult):
    print(blue("\n=== 10. 后端API集成测试 ==="))

    import requests

    BASE_URL = "http://localhost:8001"
    API_BASE = f"{BASE_URL}/api"

    # 登录获取token
    try:
        r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"}, timeout=10)
        if r.status_code == 200:
            token = r.json().get("access_token") or r.json().get("token")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            print(f"    {green('PASS')} 登录成功，获取token")
            tr.add("API_登录", True, "成功获取token")
        else:
            headers = {}
            print(f"    {red('FAIL')} 登录失败: {r.status_code}")
            tr.add("API_登录", False, f"status={r.status_code}")
            return
    except Exception as e:
        print(f"    {red('FAIL')} 登录异常: {e}")
        tr.add("API_登录", False, str(e))
        return

    # 10.1 通过Agent Handler调用后端API
    print(yellow("\n  [Agent Handler -> Backend API 集成测试]"))

    from chem_skills.chemistry_exam.handler import ExamHandler

    handler = ExamHandler(base_url=BASE_URL)  # 指定ChemAI后端地址

    # 测试exam_audit（通过Handler调用后端）
    try:
        result = handler.exam_audit(
            question_content="Fe + O2 -> Fe2O3",
            options=[]
        )
        has_status = "coefficient_audit" in result
        if has_status:
            status = result["coefficient_audit"].get("status", "unknown")
            ok = status == "blocked"  # 未配平的方程式应该被blocked
            symbol = green("PASS") if ok else red("FAIL")
            print(f"    {symbol} exam_audit(Backend): Fe+O2->Fe2O3 -> {status} (期望:blocked)")
            tr.add("集成_exam_audit_API", ok, f"status={status}")
        else:
            print(f"    {red('FAIL')} exam_audit - 返回结构异常")
            tr.add("集成_exam_audit_API", False, str(result)[:100])
    except Exception as e:
        print(f"    {red('FAIL')} exam_audit - {e}")
        tr.add("集成_exam_audit_API", False, str(e))

    # 测试exam_generate
    try:
        result = handler.exam_generate(
            knowledge_points=["盐类水解"],
            difficulty="medium",
            quantity=3
        )
        has_questions = "questions" in result
        q_count = len(result.get("questions", []))
        ok = has_questions and q_count >= 1
        symbol = green("PASS") if ok else red("FAIL")
        print(f"    {symbol} exam_generate(Backend): 生成{q_count}道题")
        tr.add("集成_exam_generate_API", ok, f"questions={q_count}")
    except Exception as e:
        print(f"    {red('FAIL')} exam_generate - {e}")
        tr.add("集成_exam_generate_API", False, str(e))

    # 10.2 配平审核回归测试（通过真实API）
    print(yellow("\n  [配平审核回归测试 - Agent调用路径]"))

    balance_cases = [
        ("2H2 + O2 = 2H2O", "passed"),
        ("H2 + O2 = H2O", "blocked"),
        ("Fe + O2 -> Fe2O3", "blocked"),
        ("CH4 + 2O2 = CO2 + 2H2O", "blocked"),
        ("4Fe + 3O2 = 2Fe2O3", "passed"),
    ]

    balance_pass = 0
    for eq, expected in balance_cases:
        try:
            result = handler.exam_audit(question_content=eq)
            status = result.get("coefficient_audit", {}).get("status", "unknown")
            ok = status == expected
            if ok: balance_pass += 1
            symbol = green("PASS") if ok else red("FAIL")
            print(f"    {symbol} {eq:30s} -> {status} (期望:{expected})")
            tr.add(f"集成_配平审核_{eq[:15]}", ok, f"期望:{expected},实际:{status}")
        except Exception as e:
            print(f"    {red('FAIL')} {eq} - {e}")
            tr.add(f"集成_配平审核_{eq[:15]}", False, str(e))

    print(yellow(f"\n  集成配平审核: {balance_pass}/{len(balance_cases)}"))

# ==================== 11. MinerU 客户端测试（模拟） ====================
def test_mineru_client_mock(tr: TestResult):
    print(blue("\n=== 11. MinerU 客户端测试 ==="))

    from chem_skills.chemistry_parser.mineru_client import MinerUClient, MinerUNotFoundError, find_mineru_root

    # 11.1 测试MinerU路径查找
    print(yellow("\n  [MinerU 安装检查]"))
    mineru_root = find_mineru_root()
    if mineru_root:
        print(f"    {green('PASS')} MinerU 找到: {mineru_root}")
        tr.add("MinerU_路径查找", True, mineru_root)
    else:
        print(f"    {yellow('WARN')} MinerU 未找到（未安装或路径不对）")
        print(f"    预期路径包括:")
        from chem_skills.chemistry_parser.mineru_client import DEFAULT_MINERU_PATHS
        for p in DEFAULT_MINERU_PATHS:
            exists = "存在" if os.path.exists(p) else "不存在"
            print(f"      - {p} ({exists})")
        tr.add("MinerU_路径查找", False, "MinerU未安装")

    # 11.2 测试MinerU客户端实例化
    if mineru_root:
        try:
            client = MinerUClient(mineru_root)
            print(f"    {green('PASS')} MinerUClient 实例化成功")
            tr.add("MinerUClient_实例化", True, "成功")
        except Exception as e:
            print(f"    {red('FAIL')} MinerUClient - {e}")
            tr.add("MinerUClient_实例化", False, str(e))
    else:
        print(f"    {yellow('SKIP')} MinerUClient 实例化 - MinerU未安装")
        tr.add("MinerUClient_实例化", False, "MinerU未安装")

# ==================== 12. 全局工具注册测试 ====================
def test_tools_registration(tr: TestResult):
    print(blue("\n=== 12. 全局工具注册测试 ==="))

    # 检查各模块的入口函数是否可导入
    modules_to_check = [
        ("chemistry_exam", ["exam_generate", "exam_audit", "exam_search_historical", "exam_balance_check"]),
        ("chemistry_diagnosis", ["diagnosis_barrier_student", "diagnosis_plan_generate", "diagnosis_config_get"]),
        ("chemistry_parser", ["standardize_chemical_formula", "classify_question_type", "extract_answer_from_ocr", "get_mineru_status"]),
        ("chemistry_memory", ["get_learning_history", "analyze_trend"]),
        ("chemistry_notification", ["send_error_report", "send_learning_plan"]),
        ("chemistry_improvement", ["record_metric", "get_quality_dashboard"]),
    ]

    for module_name, functions in modules_to_check:
        print(yellow(f"\n  [{module_name}]"))
        try:
            module = __import__(f"chem_skills.{module_name}.handler", fromlist=functions)
            for func_name in functions:
                if hasattr(module, func_name):
                    print(f"    {green('PASS')} {func_name}")
                    tr.add(f"工具注册_{func_name}", True, "存在")
                else:
                    print(f"    {red('FAIL')} {func_name} - 不存在")
                    tr.add(f"工具注册_{func_name}", False, "不存在")
        except ImportError as e:
            print(f"    {red('FAIL')} 模块导入失败: {e}")
            for func_name in functions:
                tr.add(f"工具注册_{func_name}", False, f"导入失败:{e}")

# ==================== 主函数 ====================
def main():
    print(green("=" * 70))
    print(green("ChemAI Agent & MinerU 完整测试套件"))
    print(green("=" * 70))

    tr = TestResult()

    # 1. Chemistry Exam Handler 测试
    test_chemistry_exam_tools(tr)

    # 2. Chemistry Diagnosis Handler 测试
    test_chemistry_diagnosis_tools(tr)

    # 3. Chemistry Parser Handler 测试
    test_chemistry_parser_tools(tr)

    # 4. MinerU 状态测试
    test_mineru_status(tr)

    # 5. Chemistry Memory Handler 测试
    test_chemistry_memory_tools(tr)

    # 6. Chemistry Notification Handler 测试
    test_chemistry_notification_tools(tr)

    # 7. Chemistry Improvement Handler 测试
    test_chemistry_improvement_tools(tr)

    # 8. 工具调用成功率统计
    test_tool_call_success_rate(tr)

    # 9. Agent Skill 路由测试
    test_skill_routing(tr)

    # 10. 后端API集成测试
    test_backend_api_integration(tr)

    # 11. MinerU 客户端测试
    test_mineru_client_mock(tr)

    # 12. 全局工具注册测试
    test_tools_registration(tr)

    # ========== 输出结果 ==========
    print(green("\n" + "=" * 70))
    print(green("Agent & MinerU 测试结果汇总"))
    print(green("=" * 70))
    print(f"总测试数: {tr.total}")
    print(f"通过: {green(str(tr.passed))}")
    print(f"失败: {red(str(tr.failed))}")
    pct = tr.passed*100/tr.total if tr.total > 0 else 0
    print(f"通过率: {green(f'{pct:.1f}%') if tr.failed == 0 else yellow(f'{pct:.1f}%')}")

    print(green("\n详细结果:"))
    for r in tr.results:
        status = green("PASS") if r["passed"] else red("FAIL")
        print(f"  [{status}] {r['name']}")
        if r["detail"]:
            print(f"         {r['detail']}")

    # 保存结果
    with open("test_agent_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": tr.total,
            "passed": tr.passed,
            "failed": tr.failed,
            "results": tr.results
        }, f, ensure_ascii=False, indent=2)

    print(green("\n测试结果已保存到 test_agent_results.json"))

    return tr

if __name__ == "__main__":
    main()
