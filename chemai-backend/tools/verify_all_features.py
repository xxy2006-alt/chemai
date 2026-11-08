# -*- coding: utf-8 -*-
"""ChemAI 全功能演示核验脚本 — 只读 + 少量安全写入
用法: python tools/verify_all_features.py
"""
import sys, json, time, io
import requests

BASE = "http://127.0.0.1:8000"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RESULTS = {"ok": [], "empty": [], "fail": []}

def _call(method, path, token=None, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    headers.setdefault("Content-Type", "application/json")
    try:
        r = requests.request(method, BASE + path, headers=headers, timeout=8, **kw)
    except requests.exceptions.RequestException as e:
        return 599, {"err": str(e)[:120]}
    body = None
    try:
        body = r.json()
    except Exception:
        body = r.text[:200]
    return r.status_code, body

def check(name, method, path, token=None, expect_ok=True, **kw):
    st, body = _call(method, path, token, **kw)
    key = ""
    if isinstance(body, dict):
        if "success" in body and body["success"] is False:
            key = "FAIL-success-false"
        elif "notifications" in body or "students" in body or "questions" in body or \
             "history" in body or "tasks" in body or "results" in body or "list" in body or \
             "data" in body or "reports" in body or "warnings" in body or "overview" in body or \
             "papers" in body or "categories" in body or "kps" in body or "sets" in body or \
             "applications" in body or "logs" in body or "children" in body or "records" in body:
            key = "LIST"
        elif isinstance(body.get("data"), list):
            key = "LIST"
    status = "OK" if st < 400 else "HTTP%d" % st
    line = f"[{status}] {method:6s} {path}"
    if key == "LIST":
        size = None
        for k in ["notifications","students","questions","history","tasks","results","list","data","reports","warnings","papers","categories","kps","sets","applications","logs","children","records"]:
            v = body.get(k)
            if isinstance(v, list):
                size = len(v); break
        line += f"  (list size={size})"
        if size == 0:
            RESULTS["empty"].append((name, path))
        else:
            RESULTS["ok"].append((name, path))
    elif status == "OK":
        RESULTS["ok"].append((name, path))
    else:
        RESULTS["fail"].append((name, path, st, body if isinstance(body, dict) else str(body)[:200]))
    print(line)
    return st, body

def login(u, p):
    st, b = _call("POST", "/api/auth/login", json={"username": u, "password": p})
    if st == 200 and b.get("success"):
        return b["token"]
    print(f"  !!! login failed for {u}: {st} {b}")
    return None

def main():
    T_ADMIN = login("admin", "admin123")
    T_HAI = login("hai", "hai123456")
    T_LIU = login("liu", "123456")
    T_LYX = login("202610201", "123456")
    T_LJG = login("lijg", "123456")
    # 家长端自身 token 走 /api/parent/login
    st, b = _call("POST", "/api/parent/login", json={"username": "lijg", "password": "123456"})
    P_LJG = b.get("token") if st == 200 and isinstance(b, dict) else None
    print(f"tokens: admin={bool(T_ADMIN)} hai={bool(T_HAI)} liu={bool(T_LIU)} lyx={bool(T_LYX)} lijg={bool(T_LJG)} parent_token={bool(P_LJG)}")

    print("\n===== 认证 Auth =====")
    check("me", "GET", "/api/auth/me", T_ADMIN)
    st0, b0 = _call("POST", "/api/auth/login", json={"username": "admin", "password": "admin123"})
    rt = b0.get("refresh_token") if isinstance(b0, dict) else None
    if rt:
        check("refresh", "POST", "/api/auth/refresh", T_ADMIN, json={"refresh_token": rt})
    else:
        print("  !!! no refresh_token returned from login")

    print("\n===== 教师端: 班级/学生/用户管理 =====")
    check("classes", "GET", "/api/classes", T_HAI)
    check("class students", "GET", "/api/classes/class_2025_1/students", T_HAI)
    check("user students", "GET", "/api/users/students", T_ADMIN)
    check("user teachers", "GET", "/api/users/teachers", T_ADMIN)
    check("student detail", "GET", "/api/users/student/202610201/detail", T_ADMIN)
    check("teacher classes", "GET", "/api/users/teacher/teacher_hai/classes", T_ADMIN)

    print("\n===== 教师端: 学情面板 panel =====")
    check("panel class", "GET", "/api/panel/class/class_2025_1", T_HAI)
    check("panel student", "GET", "/api/panel/class/class_2025_1/student/202610201", T_HAI)
    check("panel trend", "GET", "/api/panel/class/class_2025_1/trend", T_HAI)
    check("panel knowledge", "GET", "/api/panel/class/class_2025_1/knowledge/化学平衡", T_HAI)
    check("panel dashboard", "GET", "/api/panel/dashboard/teacher_hai", T_HAI)
    check("panel export", "GET", "/api/panel/export/class_2025_1", T_HAI)

    print("\n===== 教师端: 数据分析 analytics =====")
    check("class overview", "GET", "/api/analytics/class/class_2025_1/overview", T_HAI)
    check("class ranking", "GET", "/api/analytics/class/class_2025_1/ranking", T_HAI)
    check("top-bottom", "GET", "/api/analytics/class/class_2025_1/top-bottom", T_HAI)
    check("barrier-distribution", "GET", "/api/analytics/class/class_2025_1/barrier-distribution", T_HAI)
    check("knowledge-heatmap", "GET", "/api/analytics/class/class_2025_1/knowledge-heatmap", T_HAI)
    check("score-distribution", "GET", "/api/analytics/class/class_2025_1/score-distribution", T_HAI)
    check("practice-trend", "GET", "/api/analytics/class/class_2025_1/practice-trend", T_HAI)
    check("teacher workload", "GET", "/api/analytics/teacher/teacher_hai/workload", T_HAI)
    check("class-comparison", "GET", "/api/analytics/teacher/teacher_hai/class-comparison", T_HAI)
    check("student personal-stats", "GET", "/api/analytics/student/202610201/personal-stats", T_HAI)
    check("dashboard teacher", "GET", "/api/analytics/dashboard/teacher/teacher_hai", T_HAI)
    check("dashboard student", "GET", "/api/analytics/dashboard/student/202610201", T_HAI)
    check("dashboard parent", "GET", "/api/analytics/dashboard/parent/202610201", T_HAI)

    print("\n===== 教师端: 考试管理 exam =====")
    check("exam list", "GET", "/api/exam/list/class_2025_1", T_HAI)
    check("exam detail", "GET", "/api/exam/demo_exam_001", T_HAI)
    check("exam questions", "GET", "/api/exam/demo_exam_001/questions", T_HAI)
    check("exam results", "GET", "/api/exam/demo_exam_001/results", T_HAI)
    check("exam result student", "GET", "/api/exam/demo_exam_001/result/202610201", T_HAI)

    print("\n===== 教师端: 题目管理 question =====")
    check("q categories", "GET", "/api/question/categories", T_HAI)
    check("q kps", "GET", "/api/question/kps", T_HAI)
    check("q available", "GET", "/api/question/available/list", T_HAI)
    check("q search", "POST", "/api/question/search", T_HAI, json={"keyword": "盐类水解"})
    check("q detail", "GET", "/api/question/demo_q_001", T_HAI)
    check("q historical", "GET", "/api/question/historical", T_HAI)
    check("q exam-sets", "GET", "/api/question/exam-sets", T_HAI)

    print("\n===== 教师端: 真题库 exam-bank =====")
    check("bank exam-sets", "GET", "/api/exam-bank/exam-sets", T_HAI)
    check("bank papers", "GET", "/api/exam-bank/papers", T_HAI)
    check("bank historical", "GET", "/api/exam-bank/historical", T_HAI)

    print("\n===== 教师端: 障碍诊断 diagnosis =====")
    check("diagnosis barrier", "GET", "/api/diagnosis/barrier/class_2025_1/demo_exam_001", T_HAI)
    check("diagnosis student barrier", "GET", "/api/diagnosis/barrier/202610201", T_HAI)
    check("diagnosis config", "GET", "/api/diagnosis/config/teacher_hai", T_HAI)
    check("learning plan current", "GET", "/api/diagnosis/learning-plan/202610201", T_HAI)
    check("learning plan history", "GET", "/api/diagnosis/learning-plan/202610201/history", T_HAI)
    check("diagnosis history", "GET", "/api/diagnosis/history/202610201", T_HAI)
    check("class stats", "GET", "/api/diagnosis/class/class_2025_1/stats", T_HAI)
    check("class kp", "GET", "/api/diagnosis/class/class_2025_1/kp/化学平衡", T_HAI)
    check("plan detail", "GET", "/api/diagnosis/plan/202610201", T_HAI)

    print("\n===== 教师端: 报告 report =====")
    check("report teacher", "GET", "/api/report/teacher/teacher_hai", T_HAI)
    check("report student by exam", "GET", "/api/report/student/demo_exam_001/202610201", T_HAI)
    check("report exam analytics", "GET", "/api/report/exam-analytics/demo_exam_001", T_HAI)
    check("report student", "GET", "/api/report/student/202610201", T_HAI)
    check("report class", "GET", "/api/report/class/class_2025_1", T_HAI)
    check("report kp-mastery", "GET", "/api/report/student/202610201/kp-mastery", T_HAI)
    check("report barrier-change", "GET", "/api/report/student/202610201/barrier-change", T_HAI)
    check("report trend", "GET", "/api/report/student/202610201/trend", T_HAI)

    print("\n===== 教师端: 练习 practice (读) =====")
    check("practice effect", "GET", "/api/practice/effect/202610201", T_HAI)
    check("practice history", "GET", "/api/practice/history/202610201", T_HAI)
    check("student tasks", "GET", "/api/practice/student/202610201/tasks", T_LYX)

    print("\n===== 教师端: 错题/复习 =====")
    check("wrong list", "GET", "/api/practice/wrong/list", T_HAI, params={"student_id": "202610201"})
    check("wrong historical", "GET", "/api/practice/historical", T_HAI, params={"student_id": "202610201"})
    check("review list", "GET", "/api/practice/review/list", T_HAI, params={"student_id": "202610201"})
    check("wrong-topic wrong-questions", "GET", "/api/practice/wrong-topic/student/202610201/wrong-questions", T_HAI)
    check("wrong-topic kps", "GET", "/api/practice/wrong-topic/knowledge-points", T_HAI, params={"student_id": "202610201"})
    check("wrong-topic training history", "GET", "/api/practice/wrong-topic/training/history/202610201", T_HAI)
    check("review due", "GET", "/api/review/student/202610201/due", T_HAI)
    check("review count", "GET", "/api/review/student/202610201/count", T_HAI)
    check("review history", "GET", "/api/review/history/202610201", T_HAI)

    print("\n===== 教师端: 学情预警 warning =====")
    check("warning pending", "GET", "/api/warning/pending", T_HAI)
    check("warning student", "GET", "/api/warning/student/202610201", T_HAI)
    check("warning class summary", "GET", "/api/warning/class/class_2025_1/summary", T_HAI)

    print("\n===== 教师端: 通知/日志/学校 =====")
    check("notification history", "GET", "/api/notification/history", T_HAI)
    check("notification channels", "GET", "/api/notification/channels", T_HAI)
    check("log list", "GET", "/api/logs", T_HAI)
    check("school", "GET", "/api/school", T_HAI)
    check("grades", "GET", "/api/grades", T_HAI)
    check("teacher applications", "GET", "/api/teacher-applications", T_HAI)

    print("\n===== 知识卡片 knowledge =====")
    check("knowledge list", "GET", "/api/knowledge/list", T_HAI)
    check("knowledge 盐类水解", "GET", "/api/knowledge/盐类水解", T_HAI)

    print("\n===== 学生端 =====")
    check("student tasks", "GET", "/api/practice/student/202610201/tasks", T_LYX)
    check("dashboard student", "GET", "/api/analytics/dashboard/student/202610201", T_LYX)
    check("report student", "GET", "/api/report/student/202610201", T_LYX)
    check("diagnosis barrier", "GET", "/api/diagnosis/barrier/202610201", T_LYX)
    check("personal-stats", "GET", "/api/analytics/student/202610201/personal-stats", T_LYX)
    check("learning plan", "GET", "/api/diagnosis/learning-plan/202610201", T_LYX)
    check("wrong questions", "GET", "/api/practice/wrong-topic/student/202610201/wrong-questions", T_LYX)

    print("\n===== 家长端 =====")
    check("parent children", "GET", "/api/parent/children", P_LJG, params={"parent_id": "parent_lyx"})
    check("parent notifications", "GET", "/api/parent/notifications", P_LJG, params={"parent_id": "parent_lyx"})
    check("parent child report", "GET", "/api/parent/child/202610201/report", P_LJG, params={"parent_id": "parent_lyx"})
    check("parent child weekly", "GET", "/api/parent/child/202610201/weekly", P_LJG, params={"parent_id": "parent_lyx"})

    print("\n===== 间隔复习 review / 预警 check (写, 安全) =====")
    check("review create", "POST", "/api/review/create", T_HAI, params={"student_id": "202610201", "question_id": "demo_q_001"})
    check("review sync", "POST", "/api/review/sync/202610201", T_HAI)

    print("\n===== 汇总 =====")
    print(f"通过: {len(RESULTS['ok'])}")
    print(f"空列表(需补数据): {len(RESULTS['empty'])}")
    for name, path in RESULTS["empty"]:
        print(f"   [空] {name}: {path}")
    print(f"失败: {len(RESULTS['fail'])}")
    for name, path, st, body in RESULTS["fail"]:
        print(f"   [FAIL] {name}: {path} -> {st} {body}")

if __name__ == "__main__":
    main()
