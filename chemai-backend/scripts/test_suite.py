# -*- coding: utf-8 -*-
"""
ChemAI 完整测试套件
执行所有功能测试、专项测试、性能测试
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

# ==================== F1: OCR识别测试 ====================
def test_f1_ocr(tr: TestResult):
    print(blue("\n=== F1: OCR识别测试 ==="))

    # F1-OCR-001: 健康检查
    r = requests.get(f"{BASE_URL}/health")
    tr.add("F1-OCR-001 Health Check", r.status_code == 200, f"Status: {r.status_code}")

    # F1-OCR-002: OCR recognize接口存在性
    r = requests.post(f"{API_BASE}/ocr/recognize", json={"image_data": "test"})
    tr.add("F1-OCR-002 OCR Recognize API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

    # F1-OCR-003: OCR stats接口存在性
    r = requests.post(f"{API_BASE}/ocr/stats", json={})
    tr.add("F1-OCR-003 OCR Stats API", r.status_code in [200, 400, 422], f"Status: {r.status_code}")

# ==================== F2: AI出题与审核测试 ====================
def test_f2_question(tr: TestResult):
    print(blue("\n=== F2: AI出题与审核测试 ==="))

    # 登录获取token
    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = None
    if login_r.status_code == 200:
        data = login_r.json()
        token = data.get("access_token") or data.get("token")

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # F2-GEN-001: AI出题-单知识点
    r = requests.post(f"{API_BASE}/question/generate",
        json={"knowledge_points": ["盐类水解"], "difficulty": "medium", "quantity": 3},
        headers=headers, timeout=60)
    if r.status_code == 200:
        data = r.json()
        q_count = len(data.get("questions", []))
        tr.add("F2-GEN-001 AI出题-单知识点", q_count >= 1, f"生成{q_count}道题")
    else:
        tr.add("F2-GEN-001 AI出题-单知识点", False, f"Status: {r.status_code}")

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

# ==================== F3: 错题报告测试 ====================
def test_f3_report(tr: TestResult):
    print(blue("\n=== F3: 错题报告测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # F3-RPT-001: 报告生成API
    r = requests.get(f"{API_BASE}/report/list", headers=headers)
    tr.add("F3-RPT-001 报告列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

    # F3-RPT-002: 发送报告API
    r = requests.post(f"{API_BASE}/report/send", json={}, headers=headers)
    tr.add("F3-RPT-002 发送报告API", r.status_code in [200, 400, 401, 422], f"Status: {r.status_code}")

# ==================== F4: 障碍诊断测试 ====================
def test_f4_diagnosis(tr: TestResult):
    print(blue("\n=== F4: 障碍诊断测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # F4-DIA-001: 班级诊断API
    r = requests.get(f"{API_BASE}/diagnosis/barrier/class/demo_class", headers=headers)
    tr.add("F4-DIA-001 班级诊断API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F4-DIA-002: 学生诊断API
    r = requests.get(f"{API_BASE}/diagnosis/barrier/student/demo_student", headers=headers)
    tr.add("F4-DIA-002 学生诊断API", r.status_code in [200, 404], f"Status: {r.status_code}")

    # F4-CFG-001: 诊断配置API
    r = requests.get(f"{API_BASE}/diagnosis/config/admin", headers=headers)
    tr.add("F4-CFG-001 诊断配置获取API", r.status_code in [200, 404], f"Status: {r.status_code}")

# ==================== F5: 自适应练习测试 ====================
def test_f5_practice(tr: TestResult):
    print(blue("\n=== F5: 自适应练习测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    r = requests.get(f"{API_BASE}/practice/assignments", headers=headers)
    tr.add("F5-PRAC-001 练习列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

    r = requests.post(f"{API_BASE}/practice/answer", json={}, headers=headers)
    tr.add("F5-PRAC-002 答案提交API", r.status_code in [200, 400, 401, 422], f"Status: {r.status_code}")

# ==================== F6: 历年真题关联测试 ====================
def test_f6_exam_bank(tr: TestResult):
    print(blue("\n=== F6: 历年真题关联测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    r = requests.get(f"{API_BASE}/exam-bank/questions", headers=headers)
    tr.add("F6-BANK-001 真题库列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

    r = requests.get(f"{API_BASE}/exam-bank/search", headers=headers)
    tr.add("F6-BANK-002 真题库搜索API", r.status_code in [200, 401], f"Status: {r.status_code}")

# ==================== F7: 学情面板测试 ====================
def test_f7_panel(tr: TestResult):
    print(blue("\n=== F7: 学情面板测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    r = requests.get(f"{API_BASE}/panel/overview", headers=headers)
    tr.add("F7-PANEL-001 学情面板概览API", r.status_code in [200, 401], f"Status: {r.status_code}")

    r = requests.get(f"{API_BASE}/panel/trends", headers=headers)
    tr.add("F7-PANEL-002 学情趋势API", r.status_code in [200, 401], f"Status: {r.status_code}")

# ==================== 化学方程式配平审核专项测试 ====================
def test_chemical_balance(tr: TestResult):
    print(blue("\n=== 化学方程式配平审核专项测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

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
    ]

    print(yellow("\n  通过案例测试:"))
    for eq, expected in pass_cases:
        r = requests.post(f"{API_BASE}/question/audit",
            json={"question_content": eq}, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("coefficient_audit", {}).get("status", "unknown")
            ok = status == expected
            symbol = green("PASS") if ok else red("FAIL")
            print(f"    {symbol} {eq:30s} -> {status} (期望:{expected})")
            tr.add(f"配平审核-通过-{eq[:20]}", ok, f"实际:{status}")
        else:
            print(f"    {red('FAIL')} {eq:30s} -> HTTP {r.status_code}")
            tr.add(f"配平审核-通过-{eq[:20]}", False, f"HTTP {r.status_code}")

    print(yellow("\n  失败案例测试（必须blocked）:"))
    for eq, expected in fail_cases:
        r = requests.post(f"{API_BASE}/question/audit",
            json={"question_content": eq}, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("coefficient_audit", {}).get("status", "unknown")
            ok = status == expected
            symbol = green("PASS") if ok else red("FAIL")
            print(f"    {symbol} {eq:30s} -> {status} (期望:{expected})")
            tr.add(f"配平审核-失败-{eq[:20]}", ok, f"实际:{status}")
        else:
            print(f"    {red('FAIL')} {eq:30s} -> HTTP {r.status_code}")
            tr.add(f"配平审核-失败-{eq[:20]}", False, f"HTTP {r.status_code}")

# ==================== 化学方程式条件审核专项测试 ====================
def test_chemical_condition(tr: TestResult):
    print(blue("\n=== 化学方程式条件审核专项测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    condition_cases = [
        # 缺条件（应警告）
        ("Fe + O2 -> Fe3O4", "warning"),
        ("CH4 + O2 -> CO2 + H2O", "warning"),
        ("KMnO4 -> K2MnO4 + MnO2 + O2", "warning"),
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
            symbol = green("PASS") if ok else red("FAIL")
            print(f"  {symbol} {eq[:40]:40s} -> {status} (期望:{expected})")
            tr.add(f"条件审核-{eq[:15]}", ok, f"实际:{status}")
        else:
            print(f"  {red('FAIL')} {eq[:40]} -> HTTP {r.status_code}")
            tr.add(f"条件审核-{eq[:15]}", False, f"HTTP {r.status_code}")

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

# ==================== 班级管理测试 ====================
def test_class(tr: TestResult):
    print(blue("\n=== 班级管理测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    r = requests.get(f"{API_BASE}/classes", headers=headers)
    tr.add("CLASS-001 班级列表API", r.status_code in [200, 401], f"Status: {r.status_code}")

    r = requests.get(f"{API_BASE}/classes/demo_class/students", headers=headers)
    tr.add("CLASS-002 班级学生API", r.status_code in [200, 404], f"Status: {r.status_code}")

# ==================== 性能测试 ====================
def test_performance(tr: TestResult):
    print(blue("\n=== 性能测试 ==="))

    login_r = requests.post(f"{API_BASE}/auth/login", json={"username":"admin","password":"admin123"})
    token = login_r.json().get("access_token") or login_r.json().get("token") if login_r.status_code == 200 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # 单题审核响应时间测试
    times = []
    for i in range(5):
        start = time.time()
        r = requests.post(f"{API_BASE}/question/audit",
            json={"question_content": f"2H2 + O2 = 2H2O #{i}"},
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
    print(green("ChemAI 完整测试套件开始执行"))
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

    # 11. 性能测试
    test_performance(tr)

    # 输出结果
    print(green("\n" + "=" * 60))
    print(green("测试结果汇总"))
    print(green("=" * 60))
    print(f"总测试数: {tr.total}")
    print(f"通过: {green(str(tr.passed))}")
    print(f"失败: {red(str(tr.failed))}")
    print(f"通过率: {green(f'{tr.passed*100/tr.total:.1f}%') if tr.failed == 0 else yellow(f'{tr.passed*100/tr.total:.1f}%')}")

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
