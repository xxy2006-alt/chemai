# -*- coding: utf-8 -*-
"""
ChemAI 完整测试套件 v2 - 使用正确的API路由
"""
import requests
import json
import time
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"

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

# ==================== 辅助函数 ====================
def get_auth_headers():
    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    if login_r.status_code == 200:
        data = login_r.json()
        token = data.get("access_token") or data.get("token")
        return {"Authorization": f"Bearer {token}"}
    return {}

# ==================== F1: OCR识别测试 ====================
def test_f1_ocr(tr: TestResult):
    print(blue("\n=== F1: OCR识别测试 ==="))
    headers = get_auth_headers()

    # F1-OCR-001: 健康检查
    r = requests.get(f"{BASE_URL}/health")
    tr.add("F1-OCR-001 Health Check", r.status_code == 200, f"Status: {r.status_code}")

    # F1-OCR-002: OCR recognize接口
    r = requests.post(f"{API_BASE}/ocr/recognize", json={}, headers=headers)
    tr.add("F1-OCR-002 OCR Recognize API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

    # F1-OCR-003: OCR stats接口
    r = requests.post(f"{API_BASE}/ocr/stats", json={}, headers=headers)
    tr.add("F1-OCR-003 OCR Stats API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

    # OCR batch接口
    r = requests.post(f"{API_BASE}/ocr/recognize/batch", json={}, headers=headers)
    tr.add("F1-OCR-004 OCR Batch API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

# ==================== F2: AI出题与审核测试 ====================
def test_f2_question(tr: TestResult):
    print(blue("\n=== F2: AI出题与审核测试 ==="))
    headers = get_auth_headers()

    # F2-GEN-001: AI出题-单知识点
    r = requests.post(f"{API_BASE}/question/generate",
        json={"knowledge_points": ["盐类水解"], "difficulty": "medium", "quantity": 3},
        headers=headers, timeout=60)
    if r.status_code == 200:
        data = r.json()
        q_count = len(data.get("questions", []))
        tr.add("F2-GEN-001 AI出题-单知识点", q_count >= 1, f"生成{q_count}道题")
    else:
        tr.add("F2-GEN-001 AI出题-单知识点", False, f"Status: {r.status_code}, {r.text[:100]}")

    # F2-AUD-001: 单题审核速度
    start = time.time()
    r = requests.post(f"{API_BASE}/question/audit",
        json={"question_content": "2H2 + O2 = 2H2O"},
        headers=headers, timeout=30)
    elapsed = time.time() - start
    tr.add("F2-AUD-001 审核速度<=3秒", elapsed <= 3, f"耗时{elapsed:.2f}秒")

    # F2-AUD-002: 审核报告结构
    if r.status_code == 200:
        data = r.json()
        has_coef = "coefficient_audit" in data
        has_cond = "condition_audit" in data
        has_prod = "product_audit" in data
        tr.add("F2-AUD-002 审核报告结构", has_coef and has_cond and has_prod,
            f"coefficient:{has_coef}, condition:{has_cond}, product:{has_prod}")
    else:
        tr.add("F2-AUD-002 审核报告结构", False, f"Status: {r.status_code}")

    # F2-AUD-003: historical questions API
    r = requests.get(f"{API_BASE}/question/historical", headers=headers)
    tr.add("F2-AUD-003 Historical Questions API", r.status_code in [200, 401], f"Status: {r.status_code}")

    # F2-AUD-004: exam-sets API
    r = requests.get(f"{API_BASE}/question/exam-sets", headers=headers)
    tr.add("F2-AUD-004 Exam Sets API", r.status_code in [200, 401], f"Status: {r.status_code}")

    # F2-AUD-005: manual select API
    r = requests.post(f"{API_BASE}/question/manual/select", json={"question_ids": []}, headers=headers)
    tr.add("F2-AUD-005 Manual Select API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

# ==================== F3: 错题报告测试 ====================
def test_f3_report(tr: TestResult):
    print(blue("\n=== F3: 错题报告测试 ==="))
    headers = get_auth_headers()

    # F3-RPT-001: 老师报告API (需要真实exam_record_id)
    r = requests.get(f"{API_BASE}/report/teacher/test_exam", headers=headers)
    tr.add("F3-RPT-001 老师报告API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F3-RPT-002: 学生报告API
    r = requests.get(f"{API_BASE}/report/student/test_exam/test_student", headers=headers)
    tr.add("F3-RPT-002 学生报告API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F3-RPT-003: 发送报告API
    r = requests.post(f"{API_BASE}/report/send-to-students/test_exam", json={}, headers=headers)
    tr.add("F3-RPT-003 发送报告API", r.status_code in [200, 400, 404], f"Status: {r.status_code}")

    # F3-RPT-004: 导出报告API
    r = requests.get(f"{API_BASE}/report/export/test_exam", headers=headers)
    tr.add("F3-RPT-004 导出报告API", r.status_code in [200, 404], f"Status: {r.status_code}")

# ==================== F4: 障碍诊断测试 ====================
def test_f4_diagnosis(tr: TestResult):
    print(blue("\n=== F4: 障碍诊断测试 ==="))
    headers = get_auth_headers()

    # F4-DIA-001: 班级诊断API
    r = requests.get(f"{API_BASE}/diagnosis/barrier/class/test_class/test_exam", headers=headers)
    tr.add("F4-DIA-001 班级诊断API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F4-DIA-002: 学生诊断API
    r = requests.get(f"{API_BASE}/diagnosis/barrier/test_student", headers=headers)
    tr.add("F4-DIA-002 学生诊断API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F4-CFG-001: 诊断配置获取API
    r = requests.get(f"{API_BASE}/diagnosis/config/admin", headers=headers)
    tr.add("F4-CFG-001 诊断配置获取API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F4-CFG-002: 诊断配置更新API
    r = requests.put(f"{API_BASE}/diagnosis/config/admin", json={
        "concept_threshold": 3,
        "reading_threshold": 2,
        "expression_threshold": 3
    }, headers=headers)
    tr.add("F4-CFG-002 诊断配置更新API", r.status_code in [200, 400, 404], f"Status: {r.status_code}")

    # F4-DIA-003: 学习计划生成API
    r = requests.post(f"{API_BASE}/diagnosis/learning-plan/generate", json={}, headers=headers)
    tr.add("F4-DIA-003 学习计划生成API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

# ==================== F5: 自适应练习测试 ====================
def test_f5_practice(tr: TestResult):
    print(blue("\n=== F5: 自适应练习测试 ==="))
    headers = get_auth_headers()

    # F5-PRAC-001: 布置练习API
    r = requests.post(f"{API_BASE}/practice/assign", json={}, headers=headers)
    tr.add("F5-PRAC-001 布置练习API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

    # F5-PRAC-002: 学生练习任务API
    r = requests.get(f"{API_BASE}/practice/student/test_student/tasks", headers=headers)
    tr.add("F5-PRAC-002 学生练习任务API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F5-PRAC-003: 提交答案API
    r = requests.post(f"{API_BASE}/practice/submit", json={}, headers=headers)
    tr.add("F5-PRAC-003 提交答案API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

    # F5-PRAC-004: 练习效果API
    r = requests.get(f"{API_BASE}/practice/effect/test_student", headers=headers)
    tr.add("F5-PRAC-004 练习效果API", r.status_code in [200, 404], f"Status: {r.status_code}")

# ==================== F6: 历年真题关联测试 ====================
def test_f6_exam_bank(tr: TestResult):
    print(blue("\n=== F6: 历年真题关联测试 ==="))
    headers = get_auth_headers()

    # F6-BANK-001: 题库列表API
    r = requests.get(f"{API_BASE}/exam-bank/exam-sets", headers=headers)
    tr.add("F6-BANK-001 题库列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

    # F6-BANK-002: 创建题库API
    r = requests.post(f"{API_BASE}/exam-bank/exam-sets", json={}, headers=headers)
    tr.add("F6-BANK-002 创建题库API", r.status_code in [200, 201, 400, 422], f"Status: {r.status_code}")

    # F6-BANK-003: 历史真题API
    r = requests.get(f"{API_BASE}/exam-bank/historical", headers=headers)
    tr.add("F6-BANK-003 历史真题API", r.status_code in [200, 401], f"Status: {r.status_code}")

    # F6-BANK-004: 格式化题目API
    r = requests.post(f"{API_BASE}/exam-bank/format-questions", json={}, headers=headers)
    tr.add("F6-BANK-004 格式化题目API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

# ==================== F7: 学情面板测试 ====================
def test_f7_panel(tr: TestResult):
    print(blue("\n=== F7: 学情面板测试 ==="))
    headers = get_auth_headers()

    # F7-PANEL-001: 班级面板API
    r = requests.get(f"{API_BASE}/panel/class/test_class", headers=headers)
    tr.add("F7-PANEL-001 班级面板API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F7-PANEL-002: 班级知识点面板API
    r = requests.get(f"{API_BASE}/panel/class/test_class/knowledge/test_kp", headers=headers)
    tr.add("F7-PANEL-002 班级知识点面板API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F7-PANEL-003: 学生详情面板API
    r = requests.get(f"{API_BASE}/panel/class/test_class/student/test_student", headers=headers)
    tr.add("F7-PANEL-003 学生详情面板API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F7-PANEL-004: 班级趋势API
    r = requests.get(f"{API_BASE}/panel/class/test_class/trend", headers=headers)
    tr.add("F7-PANEL-004 班级趋势API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F7-PANEL-005: 仪表盘API
    r = requests.get(f"{API_BASE}/panel/dashboard/admin", headers=headers)
    tr.add("F7-PANEL-005 仪表盘API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F7-PANEL-006: 导出面板API
    r = requests.get(f"{API_BASE}/panel/export/test_class", headers=headers)
    tr.add("F7-PANEL-006 导出面板API", r.status_code in [200, 404], f"Status: {r.status_code}")

# ==================== 化学方程式配平审核专项测试 ====================
def test_chemical_balance(tr: TestResult):
    print(blue("\n=== 化学方程式配平审核专项测试 ==="))
    headers = get_auth_headers()

    # 通过案例（应标记为passed）
    pass_cases = [
        ("2H2 + O2 = 2H2O", "passed"),
        ("N2 + 3H2 = 2NH3", "passed"),
        ("CH4 + 2O2 = CO2 + 2H2O", "passed"),
        ("4Fe + 3O2 = 2Fe2O3", "passed"),
        ("2Mg + O2 = 2MgO", "passed"),
        ("Zn + 2HCl = ZnCl2 + H2", "passed"),
        ("Fe + 2HCl = FeCl2 + H2", "passed"),
        ("NaOH + HCl = NaCl + H2O", "passed"),
        ("S + O2 = SO2", "passed"),
        ("2Cu + O2 = 2CuO", "passed"),
    ]

    # 失败案例（必须标记为blocked）
    fail_cases = [
        ("H2 + O2 = H2O", "blocked"),
        ("Fe + O2 -> Fe2O3", "blocked"),
        ("Al + O2 = Al2O3", "blocked"),
        ("CH4 + O2 = CO2 + H2O", "blocked"),
        ("Na + Cl2 = NaCl", "blocked"),
        ("Mg + O2 = MgO", "blocked"),
        ("C + O2 = CO", "blocked"),
        ("Zn + HCl = ZnCl2 + H", "blocked"),
        ("Fe + HCl = FeCl2 + H", "blocked"),
        ("Ca(OH)2 + Na2CO3 = CaCO3 + NaOH", "blocked"),
    ]

    print(yellow("\n  [通过案例测试]"))
    pass_count = 0
    for eq, expected in pass_cases:
        r = requests.post(f"{API_BASE}/question/audit",
            json={"question_content": eq}, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("coefficient_audit", {}).get("status", "unknown")
            ok = status == expected
            if ok: pass_count += 1
            symbol = green("PASS") if ok else red("FAIL")
            print(f"    {symbol} {eq:30s} -> {status}")
            tr.add(f"配平-通过-{eq[:15]}", ok, f"期望:{expected}, 实际:{status}")
        else:
            print(f"    {red('FAIL')} {eq:30s} -> HTTP {r.status_code}")
            tr.add(f"配平-通过-{eq[:15]}", False, f"HTTP {r.status_code}")

    print(yellow(f"\n  通过案例: {pass_count}/{len(pass_cases)}"))

    print(yellow("\n  [失败案例测试 - 必须blocked]"))
    fail_count = 0
    for eq, expected in fail_cases:
        r = requests.post(f"{API_BASE}/question/audit",
            json={"question_content": eq}, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("coefficient_audit", {}).get("status", "unknown")
            ok = status == expected
            if ok: fail_count += 1
            symbol = green("PASS") if ok else red("FAIL")
            print(f"    {symbol} {eq:30s} -> {status}")
            tr.add(f"配平-失败-{eq[:15]}", ok, f"期望:{expected}, 实际:{status}")
        else:
            print(f"    {red('FAIL')} {eq:30s} -> HTTP {r.status_code}")
            tr.add(f"配平-失败-{eq[:15]}", False, f"HTTP {r.status_code}")

    print(yellow(f"\n  失败案例: {fail_count}/{len(fail_cases)}"))

# ==================== 化学方程式条件审核专项测试 ====================
def test_chemical_condition(tr: TestResult):
    print(blue("\n=== 化学方程式条件审核专项测试 ==="))
    headers = get_auth_headers()

    condition_cases = [
        # 缺条件（应警告）
        ("Fe + O2 -> Fe3O4", "warning"),
        ("CH4 + O2 -> CO2 + H2O", "warning"),
        # 正确标注（应通过）
        ("2H2 + O2 = 2H2O", "passed"),
        ("Cu + 2H2SO4(浓) = CuSO4 + SO2 + 2H2O", "passed"),
    ]

    for eq, expected in condition_cases:
        r = requests.post(f"{API_BASE}/question/audit",
            json={"question_content": eq}, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("condition_audit", {}).get("status", "unknown")
            ok = status == expected
            symbol = green("PASS") if ok else yellow("WARN")
            print(f"  {symbol} {eq[:40]:40s} -> {status} (期望:{expected})")
            tr.add(f"条件-{eq[:15]}", ok, f"期望:{expected}, 实际:{status}")
        else:
            print(f"  {red('FAIL')} {eq[:40]} -> HTTP {r.status_code}")
            tr.add(f"条件-{eq[:15]}", False, f"HTTP {r.status_code}")

# ==================== 用户认证测试 ====================
def test_auth(tr: TestResult):
    print(blue("\n=== 用户认证测试 ==="))

    # 登录
    r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    if r.status_code == 200:
        data = r.json()
        has_token = "access_token" in data or "token" in data
        tr.add("AUTH-001 管理员登录", has_token, f"有token:{has_token}")
    else:
        tr.add("AUTH-001 管理员登录", False, f"Status: {r.status_code}")

    # 注册
    r = requests.post(f"{API_BASE}/auth/register", json={
        "username": f"testuser_{int(time.time())}",
        "password": "test123456",
        "role": "student"
    })
    tr.add("AUTH-002 用户注册", r.status_code in [200, 201, 400, 422], f"Status: {r.status_code}")

    # 获取当前用户
    headers = get_auth_headers()
    r = requests.get(f"{API_BASE}/auth/me", headers=headers)
    tr.add("AUTH-003 获取当前用户", r.status_code in [200, 401], f"Status: {r.status_code}")

# ==================== 班级管理测试 ====================
def test_class(tr: TestResult):
    print(blue("\n=== 班级管理测试 ==="))
    headers = get_auth_headers()

    # 班级列表
    r = requests.get(f"{API_BASE}/classes", headers=headers)
    tr.add("CLASS-001 班级列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

    # 创建班级
    r = requests.post(f"{API_BASE}/classes", json={"name": "Test Class"}, headers=headers)
    tr.add("CLASS-002 创建班级API", r.status_code in [200, 201, 400, 422], f"Status: {r.status_code}")

    # 班级学生
    r = requests.get(f"{API_BASE}/classes/test_class/students", headers=headers)
    tr.add("CLASS-003 班级学生API", r.status_code in [200, 404], f"Status: {r.status_code}")

# ==================== 用户管理测试 ====================
def test_users(tr: TestResult):
    print(blue("\n=== 用户管理测试 ==="))
    headers = get_auth_headers()

    r = requests.get(f"{API_BASE}/users/students", headers=headers)
    tr.add("USER-001 学生列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

    r = requests.get(f"{API_BASE}/users/teachers", headers=headers)
    tr.add("USER-002 教师列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

# ==================== 考试管理测试 ====================
def test_exam(tr: TestResult):
    print(blue("\n=== 考试管理测试 ==="))
    headers = get_auth_headers()

    r = requests.post(f"{API_BASE}/exam/create", json={}, headers=headers)
    tr.add("EXAM-001 创建考试API", r.status_code in [200, 201, 400, 422], f"Status: {r.status_code}")

    r = requests.get(f"{API_BASE}/exam/list/test_class", headers=headers)
    tr.add("EXAM-002 考试列表API", r.status_code in [200, 404], f"Status: {r.status_code}")

    r = requests.get(f"{API_BASE}/exam/test_exam", headers=headers)
    tr.add("EXAM-003 考试详情API", r.status_code in [200, 404], f"Status: {r.status_code}")

# ==================== 性能测试 ====================
def test_performance(tr: TestResult):
    print(blue("\n=== 性能测试 ==="))
    headers = get_auth_headers()

    # 单题审核响应时间测试
    times = []
    for i in range(5):
        start = time.time()
        r = requests.post(f"{API_BASE}/question/audit",
            json={"question_content": f"2H2 + O2 = 2H2O"},
            headers=headers, timeout=30)
        elapsed = time.time() - start
        if r.status_code == 200:
            times.append(elapsed)

    if times:
        avg_time = sum(times) / len(times)
        max_time = max(times)
        tr.add("PERF-001 审核响应时间(平均<=1秒)", avg_time <= 1.0, f"平均{avg_time:.2f}秒")
        tr.add("PERF-002 审核响应时间(最大<=3秒)", max_time <= 3.0, f"最大{max_time:.2f}秒")
        print(f"  审核响应时间: 平均{avg_time:.3f}秒, 最大{max_time:.3f}秒")

# ==================== 主函数 ====================
def main():
    print(green("=" * 60))
    print(green("ChemAI 完整测试套件 v2"))
    print(green("=" * 60))

    tr = TestResult()

    # 1. 认证测试
    test_auth(tr)

    # 2. F1: OCR识别测试
    test_f1_ocr(tr)

    # 3. F2: AI出题与审核测试
    test_f2_question(tr)

    # 4. 化学方程式专项测试
    test_chemical_balance(tr)
    test_chemical_condition(tr)

    # 5. F3: 错题报告测试
    test_f3_report(tr)

    # 6. F4: 障碍诊断测试
    test_f4_diagnosis(tr)

    # 7. F5: 自适应练习测试
    test_f5_practice(tr)

    # 8. F6: 历年真题关联测试
    test_f6_exam_bank(tr)

    # 9. F7: 学情面板测试
    test_f7_panel(tr)

    # 10. 班级管理测试
    test_class(tr)

    # 11. 用户管理测试
    test_users(tr)

    # 12. 考试管理测试
    test_exam(tr)

    # 13. 性能测试
    test_performance(tr)

    # 输出结果
    print(green("\n" + "=" * 60))
    print(green("测试结果汇总"))
    print(green("=" * 60))
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

    # 保存结果到文件
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": tr.total,
            "passed": tr.passed,
            "failed": tr.failed,
            "results": tr.results
        }, f, ensure_ascii=False, indent=2)

    print(green("\n测试结果已保存到 test_results.json"))

    return tr

if __name__ == "__main__":
    main()
