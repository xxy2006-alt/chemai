"""
L0 coverage manifest — data only (Spec 02: 工具 → 是否有 L0 确定性测试).

category:
  l0  — 有快跑层确定性断言（零 LLM/DB）
  llm — LLM 绑定工具，L1 golden 轨迹覆盖（L0 不可测）
  db  — DB/状态绑定工具，tests/ 套件与后续 L6 覆盖
  net — 网络探测工具（服务可用性检查）

Runner 对「TOOLS 中缺失于本清单」的工具打印 warning（coverage_warnings）。
新增工具时必须同步登记本清单，否则快跑层会提醒。
"""

TOOL_COVERAGE = {
    # ── l0: 确定性断言（快跑层）──
    "balance_equation":      {"category": "l0", "where": "evals/test_unit_tools.py"},
    "search_exam_bank":      {"category": "l0", "where": "evals/test_unit_tools.py (JSON 路径)"},
    "show_exam_workbench":   {"category": "l0", "where": "evals/test_tool_l0.py (参数解析/面板 JSON)"},
    "save_to_bank":          {"category": "l0", "where": "evals/test_tool_l0.py (校验错误路径)"},
    "delete_bank":           {"category": "l0", "where": "evals/test_tool_l0.py (空 id 校验)"},
    "memory_student_get":    {"category": "l0", "where": "evals/test_tool_l0.py (无上下文降级)"},
    "memory_teacher_get":    {"category": "l0", "where": "evals/test_tool_l0.py (无上下文降级)"},
    "read":                  {"category": "l0", "where": "evals/test_filesystem_tools.py"},
    "write":                 {"category": "l0", "where": "evals/test_filesystem_tools.py"},
    "edit":                  {"category": "l0", "where": "evals/test_filesystem_tools.py"},
    "find":                  {"category": "l0", "where": "evals/test_filesystem_tools.py"},
    "grep":                  {"category": "l0", "where": "evals/test_filesystem_tools.py"},
    "bash":                  {"category": "l0", "where": "evals/test_shell_tools.py (L3 对抗语料兼)"},
    "plan_task":             {"category": "llm",
                             "where": "planning golden (Spec 06) + evals/test_sse_plan.py 事件契约"},

    # ── llm: LLM 绑定（L1 golden 轨迹）──
    "web_search":                 {"category": "llm", "where": "L1 golden: web-search"},
    "chemistry_tutor":            {"category": "llm", "where": "L1 golden: knowledge-redox"},
    "ionic_equation_tutor":       {"category": "llm", "where": "L1 golden (待扩)"},
    "stoichiometry_tutor":        {"category": "llm", "where": "L1 golden (待扩)"},
    "redox_tutor":                {"category": "llm", "where": "L1 golden (待扩)"},
    "equilibrium_tutor":          {"category": "llm", "where": "L1 golden (待扩)"},
    "periodic_law_tutor":         {"category": "llm", "where": "L1 golden (待扩)"},
    "organic_tutor":              {"category": "llm", "where": "L1 golden (待扩)"},
    "simulate_experiment":        {"category": "llm", "where": "L1 golden: simulate-experiment"},
    "generate_questions":         {"category": "llm", "where": "L1 golden: gen-questions-*"},
    "diagnose_barrier":           {"category": "llm", "where": "L1 golden: diagnose-*"},
    "weekly_report":              {"category": "llm", "where": "L1 golden: weekly-report"},
    "generate_learning_plan":     {"category": "llm", "where": "L1 golden (待扩)"},
    "revise_learning_plan":       {"category": "llm", "where": "L1 golden (待扩)"},
    "send_learning_plan":         {"category": "llm", "where": "L1 golden (待扩)"},
    "generate_parent_report":     {"category": "llm", "where": "L1 golden (待扩)"},
    "send_report_to_parent":      {"category": "llm", "where": "L1 golden (待扩)"},
    "parse_chemistry_document":   {"category": "llm", "where": "L1 golden (待扩)"},
    "import_question_bank":       {"category": "llm", "where": "L1 golden: import-paper"},
    "grade_answer_sheets":        {"category": "llm", "where": "L1 golden (待扩)"},
    "assign_adaptive_practice":   {"category": "llm", "where": "L1 golden: adaptive-practice"},

    # ── db: DB/状态绑定 ──
    "query_ocr_progress":     {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "save_grading_results":   {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "query_batch_grades":     {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "query_grading_queue":    {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "confirm_exam_grades":    {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "query_assignment_progress": {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "list_teacher_exams":     {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "list_banks":             {"category": "db", "where": "tests/ 套件 + L6 (待)"},
    "show_diagnosis":         {"category": "db", "where": "L1 golden: navigate-diagnosis"},
    "show_students":          {"category": "db", "where": "L1 golden (待扩)"},

    # ── net: 网络探测 ──
    "check_parser_services":  {"category": "net", "where": "环境相关，不进常规层"},
}


def coverage_warnings(manifest=None, tool_names=None):
    """Warn for tools registered in TOOLS but missing from the manifest. Pure."""
    manifest = manifest if manifest is not None else TOOL_COVERAGE
    if tool_names is None:
        from agent.tools import TOOLS as _TOOLS
        tool_names = [t.__name__ for t in _TOOLS]
    return [
        f"tool '{name}' missing from L0 coverage manifest (evals/tool_coverage.py)"
        for name in tool_names
        if name not in manifest
    ]
