"""ChemAI Single-Agent — one create_react_agent with all tools + GuardState.

Replaces the multi-agent coordinator+router+6-sub-agent architecture.
Single ReAct loop: LLM sees all tools, picks based on docstring descriptions.
GuardState provides dedup, call limits, and approval gating — same as v1.

Panel interrupt: when LLM calls show_exam_workbench, post_model_hook pauses the
graph via interrupt(). Frontend renders the panel, user fills params, clicks
"AI 出题" which resumes the graph with panel params → LLM calls generate_questions.
"""

import logging
from pathlib import Path

from langgraph.prebuilt import create_react_agent

# Use the shared AsyncSqliteSaver from guard (persists across requests and restarts)
_v2_checkpointer = None

async def _get_v2_checkpointer():
    global _v2_checkpointer
    if _v2_checkpointer is None:
        from agent.guard import _get_checkpointer
        _v2_checkpointer = await _get_checkpointer()
    return _v2_checkpointer

logger = logging.getLogger(__name__)

# ── Guard infrastructure (shared with v1) ──
from agent.guard import (  # noqa: E402
    get_langchain_model,
    GuardState,
    _make_guarded_tool,
    TOOL_APPROVAL_REQUIRED,
)

# ── All tools ──
from agent.tools import TOOLS  # noqa: E402
from agent.browser_tools import (  # noqa: E402
    browse_navigate,
    browse_read,
    browse_click,
    browse_input,
    browse_screenshot,
)

RECURSION_LIMIT = 12

# Store context — set before agent invocation for tool access
_store_context = None


def set_store_context(store):
    global _store_context
    _store_context = store


def get_store_context():
    return _store_context


SYSTEM_PROMPT = (
    "你是 ChemAI 化学教研助手。\n"
    "\n"
    "你必须调用一个工具。阅读每个工具的描述（何时用/会发生什么/下一步/NOT for）来决定用哪个。\n"
    "不确定时，选择最可能相关的工具并调用它。\n"
    "禁止在不调用工具的情况下直接生成回复。\n"
    "\n"
    "## 关键区分：学习计划 vs 布置练习\n"
    "- 用户说\"学习计划\"\"学习方案\"\"学习规划\"\"制定计划\" → generate_learning_plan（生成文本型学习方案："
    "周目标、日任务、干预建议）\n"
    "- 用户说\"出题\"\"布置练习\"\"针对性练习\"\"出几道题\"\"做题\" → assign_adaptive_practice（生成练习题："
    "题目、选项、答案）\n"
    "- 两词同时出现时，看用户核心诉求："
    "要\"方案/计划\"走 generate_learning_plan，要\"题/练习\"走 assign_adaptive_practice\n"
    "\n"
    "## 输出规则（严格遵守，违反即失败）\n"
    "- 工具返回了引导性回复后（如\"请把方程式发来\"），用一个简短的过渡语句承接（如\"试试发过来吧！\"），"
    "不要逐字重复工具的引导内容。\n"
    "- 工具返回了实质性内容（如实验结果、题目解析）后，直接展示，不要在前面加\"好的，我来为你...\"。\n"
    "- 【内联渲染工具，文本零复述】以下工具的结果会以图表/面板/卡片形式在聊天中内联渲染："
    "show_diagnosis、diagnose_barrier、generate_learning_plan、weekly_report、generate_parent_report、"
    "search_exam_bank、generate_questions。调用它们并收到结果后，你的文本回复最多一句话过渡"
    "（如\"诊断报告已生成，见下方图表\"、\"学习计划已生成，请在下方预览\"、\"题目如下\"），"
    "绝对不要在文本中复述任何数据明细——得分、正确率、障碍占比、成绩趋势、薄弱知识点列表、"
    "周目标、每日任务、题目正文、选项、答案等一律不重复。禁止使用\"以下是核心结论\""
    "\"详细数据如下\"\"内容如下\"这类开头后跟数据。\n"
    "- 连续调用多个内联渲染工具会重复生成面板：诊断类工具（diagnose_barrier/show_diagnosis）"
    "每次任务只调用一种；生成学习计划后不要再调用 diagnose_barrier 或 show_diagnosis。\n"
    "- 【内部标识零泄漏】回复文本中禁止出现 batch_id、task_id、record_id、set_id、"
    "thread_id 等内部技术标识——用学生姓名/批次描述等人类可读信息代替。\n"
    "- 【计划执行到底，确认门必须停】plan_task 生成计划后，立即按步骤顺序调用对应工具执行，"
    "每步完成后再做下一步，直到全部步骤完成才汇报。参数不全时用合理默认值继续，"
    "出题类步骤直接调用 generate_questions/show_exam_workbench。"
    "唯一例外：确认门（确认卡）开着时必须停下等老师的决定（批准/打回/放弃）——"
    "门的结果会自动推进或恢复任务，不要催促老师、不要代替老师决定、"
    "不要绕过门继续调用后续工具。\n"
    "- 禁止幻觉声称\"已展示图表/面板\"：只有实际调用了对应工具并收到结果后，才能说\"已展示\"；"
    "未调用工具时只能输出文字结论，不得声称展示了图表。\n"
    "\n"
    "## 工具结果处理\n"
    "- search_exam_bank 返回 STATUS=\"FOUND\" → 逐题展示，禁止说\"没找到\"，禁止再调 web_search\n"
    "- search_exam_bank 返回 STATUS=\"NOT_FOUND\" → 告知用户本地题库暂无，自动调用 web_search 搜索网上相关真题\n"
    "- web_search 也无结果 → 用你的知识总结该知识点的考点和常考方向，最后建议用户用出题面板自主生成\n"
    "- 【确认门自动处理】工具返回 approval_needed / awaiting_gate 时：确认卡已自动弹出，"
    "你只需用一句话向老师说明正在等待确认，禁止再调用 request_approval（已退役）、"
    "禁止重复调用同一工具、禁止代替老师决定。老师决定后系统会自动重放该操作并推进任务；"
    "门开着期间继续调用工具会被拒绝——请等待。\n"
    "- 【发送确认门】send_learning_plan/send_report_to_parent 调用后系统会弹确认卡"
    "等老师决定（批准/打回/放弃）。批准后系统自动发送并继续任务，禁止重复调用发送工具；"
    "老师打回时系统会按反馈修订学习计划/家长报告、更新预览并再次弹卡，你只需向老师说明本次"
    "修改点（主动修订学习计划用 revise_learning_plan）；老师放弃则继续执行计划中的剩余步骤。\n"
    "- 【发送范围】题目/练习题只发给学生（send_learning_plan）；学习计划/学习报告"
    "才可同步家长（send_report_to_parent）。禁止把题目发给家长。\n"
    "- 【失败治理】发送失败时向老师报告工具返回的真实失败原因，"
    "禁止重复调用同一发送工具盲目重试。\n"
    "- 【失败治理·通用】任何工具调用失败（返回 error/空结果/异常）时："
    "先分析原因，最多以修正后的参数重试 1 次；仍失败则停止重试，"
    "明确告诉老师「失败了 + 真实原因 + 可尝试的下一步」（如换路径、分页读取、稍后重试），"
    "严禁重复调用同一工具、严禁假装成功、严禁沉默结束。\n"
    "- 【任务无法完成时】必须明确说「无法完成 + 原因 + 建议」，而不是卡住、反复尝试或跳过步骤。\n"
    "- 【大文件读取】读取文件前不确定大小就用 read 的 limit/offset 分页，"
    "不要一次性读取超大文件。\n"
    "\n"
    "## 出题规则（2026-08 v3 参数分级）\n"
    "- 出题意图且给了知识点/主题 → 直接调 generate_questions（题型/难度用默认：选择题、中等）\n"
    "- 出题意图但完全没有知识点/主题 → 调 show_exam_workbench 打开面板，让面板收集参数\n"
    "- 用户明确说\"用工作台/面板出题\" → 调 show_exam_workbench\n"
    "- 禁止在对话中追问出题参数——要么默认补全执行，要么交给面板\n"
)

ALL_TOOLS = list(TOOLS) + [
    browse_navigate, browse_read, browse_click, browse_input, browse_screenshot,
]

_TOOL_BY_NAME = {t.__name__: t for t in ALL_TOOLS}


def build_system_prompt(persona_config, student_profile=None, class_context="", teacher_id=""):
    """Build the v2 system prompt from persona config + contexts. Pure, testable."""
    persona_prompt = persona_config.get("system_prompt", "").strip()

    # Build student context string and inject into prompt
    student_context = ""
    if student_profile and isinstance(student_profile, dict):
        sp = student_profile
        name = sp.get("name", "")
        sid = sp.get("student_id", "")
        barrier = sp.get("barrier", {})
        exercises = sp.get("exercises_completed", 0)
        if name:
            parts = [f"当前孩子: {name}（学号 {sid}）" if sid else f"当前孩子: {name}"]
            dom = max(barrier, key=barrier.get) if barrier else ""
            dom_labels = {"concept": "概念理解", "reading": "审题仔细度", "expression": "答题表述"}
            if dom:
                parts.append(f"主要学习特点: {dom_labels.get(dom, dom)}")
            if exercises:
                parts.append(f"已完成练习: {exercises} 次")
            student_context = "。".join(parts)

    if persona_prompt:
        prompt = persona_prompt.replace("{student_context}", student_context or "正在查看孩子的学习情况。")
        prompt = (
            prompt
            + "\n\n## 工具使用\n你必须调用工具来处理用户问题。阅读每个工具的 docstring（"
            "何时用/会发生什么/下一步/NOT for）来选择。"
            "不确定时选择最相关的工具并调用它。禁止不调工具直接回复。"
            "\n\n## 输出规则（严格遵守）\n1. 工具返回了完整引导回复（如 "
            "ionic_equation_tutor/stoichiometry_tutor/chemistry_tutor/simulate_experiment）后，最多说一句极短的过渡（如「试试看吧！」），"
            "不要把工具内容用自己的话重说一遍。"
            "\n2. 不要问「你是学生还是老师」—— persona 已经告诉你了。"
            "\n3. 工具返回的内容就是给学生的回复，你不要再复述、总结、或添加类似内容。"
        )
    else:
        prompt = SYSTEM_PROMPT

    if class_context:
        prompt = prompt + (
            f"\n\n## 班级学情上下文\n{class_context}\n"
            "（出题推荐等场景引用时注明数据依据）"
        )
    # 本机环境（文件访问路径不用猜）：老师提到桌面/文档等目录时直接拼路径调工具
    prompt = prompt + (
        f"\n\n## 本机环境\n用户主目录: {Path.home()}；"
        f"桌面目录通常是: {Path.home() / 'Desktop'}；"
        f"工作区默认: ~/ChemAI-Workspace。"
        "老师提到桌面/文档/下载等目录时，直接构造绝对路径调用 read 工具，"
        "不要反问路径。"
    )
    if teacher_id:
        prompt = prompt + (
            f"\n当前教师ID: {teacher_id}（需要 teacher_id 参数的工具会自动使用"
            "该 ID，不要向用户询问教师ID）。"
        )
    return prompt


async def create_chemai_agent(
    persona: str = "tutor",
    provider: str = "deepseek",
    student_profile=None,
    intent_hints="",
    guard_state=None,
    store=None,
    class_context="",
    teacher_id="",
):
    """Create a single ReAct agent with persona-filtered tools.

    Returns (graph, guard_state). The guard_state is shared across all tool
    calls within one invocation — it tracks dedup, call limits, and approval.

    Panel tools (show_exam_workbench) trigger post_model_hook interrupt:
    graph pauses → frontend shows panel → user fills params → resume.
    """
    # Set store context for tool access
    if store is not None:
        set_store_context(store)
    from agent.agents import load_persona

    persona_config = load_persona(persona)
    available_skills = persona_config.get("available_skills", [])

    # Build persona-aware system prompt (pure function, Spec 05)
    prompt = build_system_prompt(persona_config, student_profile, class_context, teacher_id)

    # Build tool set: persona YAML available_skills acts as whitelist filter
    # on top of TOOL_META auto-registration
    from agent.tools import TOOL_META as _TOOL_META
    yaml_skills = set(available_skills) if available_skills else None
    auto_skills = set(t.__name__ for t, meta in _TOOL_META.items() if persona in meta.get("personas",[]))
    if yaml_skills:
        persona_tool_names = auto_skills & yaml_skills
        if not persona_tool_names:
            persona_tool_names = auto_skills
    else:
        persona_tool_names = auto_skills
    domain_tools = [t for t in TOOLS if t.__name__ in persona_tool_names]
    browser_tools = [
        browse_navigate, browse_read, browse_click,
        browse_input, browse_screenshot,
    ]

    gs = guard_state or GuardState()
    approval_tools = set(TOOL_APPROVAL_REQUIRED) & persona_tool_names

    tools = [
        _make_guarded_tool(t, gs, t.__name__ in approval_tools)
        for t in domain_tools + browser_tools
    ]
    # ADR-0015 阶段 2：request_approval / interrupt() 退役——门统一数据强制
    # （requires_approval 工具被拦时直接返回门卡载荷，批准后 channel 确定性重放）。

    model = get_langchain_model(provider)

    checkpointer = await _get_v2_checkpointer()
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )

    logger.info(
        "[SingleAgent] Created — %d domain + %d browser tools, persona=%s",
        len(domain_tools), len(browser_tools), persona,
    )
    return agent, gs
