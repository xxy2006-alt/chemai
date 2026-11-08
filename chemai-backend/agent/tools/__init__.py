"""ChemAI Tools — collected from domain sub-modules and re-exported.

TOOL_META maps tool function → {"personas": [...], "call_limit": N}.
Used by langgraph_agent_v2 to filter tools per persona.
"""

# ── Exam bank & search ──
from agent.tools.exam_bank import (
    search_exam_bank,
    web_search,
    show_exam_workbench,
    save_to_bank,
    list_banks,
    delete_bank,
)

# ── Tutoring ──
from agent.tools.tutoring import (
    chemistry_tutor,
    balance_equation,
    ionic_equation_tutor,
    stoichiometry_tutor,
    redox_tutor,
    equilibrium_tutor,
    periodic_law_tutor,
    organic_tutor,
)

# ── Diagnosis ──
from agent.tools.diagnosis import (
    diagnose_barrier,
    show_diagnosis,
    show_students,
    weekly_report,
    assign_adaptive_practice,
    query_assignment_progress,
)

# ── Question generation ──
from agent.tools.generation import generate_questions

# ── Experiment simulation ──
from agent.tools.simulation import simulate_experiment

# ── OCR & grading ──
from agent.tools.ocr_grading import (
    query_ocr_progress,
    grade_answer_sheets,
    save_grading_results,
    query_grading_queue,
    confirm_exam_grades,
    query_batch_grades,
    list_teacher_exams,
)

# ── Document parsing ──
from agent.tools.parser import (
    parse_chemistry_document,
    import_question_bank,
    check_parser_services,
)

# ── Long-term memory ──
from agent.tools.memory import (
    memory_student_get,
    memory_teacher_get,
)

# ── Filesystem & shell (Spec 03: read/write/edit/bash 沙箱四件套) ──
from agent.tools.filesystem import (
    read,
    write,
    edit,
    find,
    grep,
)
from agent.tools.shell import bash

# ── Planner (Spec 06: 复杂任务拆解接入 v2 agent) ──
from agent.tools.plan import plan_task

# ── Learning plan ──
from agent.tools.diagnosis import (
    generate_learning_plan,
    revise_learning_plan,
    send_learning_plan,
    generate_parent_report,
    send_report_to_parent,
)

# ── All tools (flat list for agent factories) ──

TOOLS = [
    search_exam_bank,
    web_search,
    show_exam_workbench,
    show_diagnosis,
    show_students,
    diagnose_barrier,
    chemistry_tutor,
    simulate_experiment,
    balance_equation,
    query_ocr_progress,
    grade_answer_sheets,
    save_grading_results,
    query_grading_queue,
    confirm_exam_grades,
    query_batch_grades,
    list_teacher_exams,
    ionic_equation_tutor,
    stoichiometry_tutor,
    redox_tutor,
    equilibrium_tutor,
    periodic_law_tutor,
    organic_tutor,
    weekly_report,
    assign_adaptive_practice,
    query_assignment_progress,
    save_to_bank,
    list_banks,
    delete_bank,
    generate_questions,
    memory_student_get,
    memory_teacher_get,
    generate_learning_plan,
    revise_learning_plan,
    send_learning_plan,
    generate_parent_report,
    send_report_to_parent,
    parse_chemistry_document,
    import_question_bank,
    check_parser_services,
    read,
    write,
    edit,
    find,
    grep,
    bash,
    plan_task,
]

# ── Per-tool metadata for persona filtering & call limits ──

TOOL_META = {
    search_exam_bank:         {"personas": ["tutor", "teacher"], "call_limit": 3},
    web_search:               {"personas": ["student", "tutor", "teacher", "parent"], "call_limit": 2},
    show_exam_workbench:      {"personas": ["tutor", "teacher"], "call_limit": 3},
    show_diagnosis:           {"personas": ["teacher"], "call_limit": 1,
                               "scope": {"student_id": "student", "student_name": "student", "class_id": "class"}},
    show_students:            {"personas": ["teacher"], "call_limit": 3,
                               "scope": {"class_id": "class", "class_name": "class", "student_name": "student"}},
    diagnose_barrier:         {"personas": ["teacher", "parent"], "call_limit": 2,
                               "scope": {"student_id": "student", "student_name": "student", "class_id": "class"}},
    chemistry_tutor:          {"personas": ["student", "tutor", "teacher"], "call_limit": 3},
    simulate_experiment:      {"personas": ["student", "tutor"], "call_limit": 2},
    balance_equation:         {"personas": ["tutor", "teacher"], "call_limit": 3},
    query_ocr_progress:       {"personas": ["teacher"], "call_limit": 3,
                               "scope": {"teacher_id": "teacher"}},
    grade_answer_sheets:      {"personas": ["teacher"], "call_limit": 2,
                               "scope": {"teacher_id": "teacher"}},
    save_grading_results:     {"personas": ["teacher"], "call_limit": 2,
                               "scope": {"teacher_id": "teacher"}},
    query_grading_queue:      {"personas": ["teacher"], "call_limit": 3,
                               "scope": {"teacher_id": "teacher"}},
    confirm_exam_grades:      {"personas": ["teacher"], "call_limit": 1},
    query_batch_grades:       {"personas": ["teacher"], "call_limit": 3,
                               "scope": {"teacher_id": "teacher"}},
    list_teacher_exams:       {"personas": ["teacher"], "call_limit": 3,
                               "scope": {"teacher_id": "teacher"}},
    ionic_equation_tutor:     {"personas": ["student"], "call_limit": 5},
    stoichiometry_tutor:      {"personas": ["student"], "call_limit": 5},
    redox_tutor:              {"personas": ["student"], "call_limit": 5},
    equilibrium_tutor:        {"personas": ["student"], "call_limit": 5},
    periodic_law_tutor:       {"personas": ["student"], "call_limit": 5},
    organic_tutor:            {"personas": ["student"], "call_limit": 5},
    weekly_report:            {"personas": ["teacher", "parent"], "call_limit": 2,
                               "scope": {"student_id": "student", "student_name": "student", "class_name": "class"}},
    assign_adaptive_practice: {"personas": ["teacher"], "call_limit": 1,
                               "scope": {"class_id": "class", "student_id": "student", "student_name": "student"}},
    query_assignment_progress: {"personas": ["teacher"], "call_limit": 3},
    save_to_bank:             {"personas": ["tutor", "teacher"], "call_limit": 1},
    list_banks:               {"personas": ["tutor", "teacher"], "call_limit": 1},
    delete_bank:              {"personas": ["tutor", "teacher"], "call_limit": 1},
    generate_questions:       {"personas": ["tutor", "teacher"], "call_limit": 5},
    memory_student_get:       {"personas": ["student", "tutor", "teacher", "parent"], "call_limit": 3,
                               "scope": {"student_id": "student"}},
    memory_teacher_get:       {"personas": ["teacher"], "call_limit": 3,
                               "scope": {"teacher_id": "teacher"}},
    generate_learning_plan:   {"personas": ["teacher"], "call_limit": 5,
                               "scope": {"student_id": "student", "student_name": "student"}},
    revise_learning_plan:     {"personas": ["teacher"], "call_limit": 8,
                               "scope": {"student_id": "student"}},
    send_learning_plan:       {"personas": ["teacher"], "call_limit": 8,  # 打回-修订-再确认循环会多次到门（ADR-0013）
                               "scope": {"student_id": "student", "teacher_id": "teacher"}},
    generate_parent_report:   {"personas": ["teacher"], "call_limit": 5,
                               "scope": {"student_name": "student", "student_id": "student"}},
    send_report_to_parent:    {"personas": ["teacher"], "call_limit": 3,
                               "scope": {"student_id": "student"}},
    parse_chemistry_document: {"personas": ["tutor", "teacher"], "call_limit": 3},
    import_question_bank:     {"personas": ["tutor", "teacher"], "call_limit": 2},
    check_parser_services:    {"personas": ["tutor", "teacher"], "call_limit": 2},
    read:                     {"personas": ["tutor", "teacher"], "call_limit": 5},
    write:                    {"personas": ["tutor", "teacher"], "call_limit": 3},
    edit:                     {"personas": ["tutor", "teacher"], "call_limit": 3},
    find:                     {"personas": ["tutor", "teacher"], "call_limit": 3},
    grep:                     {"personas": ["tutor", "teacher"], "call_limit": 3},
    bash:                     {"personas": ["tutor", "teacher"], "call_limit": 2},
    plan_task:                {"personas": ["tutor", "teacher"], "call_limit": 2},
}

# verify all TOOLS are in TOOL_META
assert set(TOOLS) == set(TOOL_META.keys()), f"TOOL_META missing: {set(TOOLS) - set(TOOL_META.keys())}"
