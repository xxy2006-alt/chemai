"""
Gateway — LLM-powered intent classifier replacing keyword matching.

Two-class classification (v2):
- chat: needs tool execution (tool decides routing via _route field)
- navigate: pure page open, no tool needed ("打开考试工作台")
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Page name → route mapping
PAGE_ROUTES = {
    "exam": "exam-v2",
    "exam-v2": "exam-v2",
    "diagnosis": "diagnosis",
    "students": "students",
    "teacher": "teacher",
    "chat": None,
}

CLASSIFY_PROMPT = (
    "你是化学教研助手的意图分类器。回答两个问题：\n"
    "1. 用户消息是否需要调用工具？\n"
    "2. 如果不需要工具，目标页面是什么？\n"
    "\n"
    "分类规则：\n"
    "- **chat**: 需要调用工具完成任务（生成题目、诊断学情、查周报、搜索真题、答疑辅导、模拟实验、"
    "配平方程式、导入试卷等）。"
    "**不确定时一律走 chat**。\n"
    "- **navigate**: 纯页面跳转，不需要任何工具。**只有明确说\"打开XX页面\"\"跳转到XX\"的才走 navigate**。"
    "含\"看看\"\"查看\"等词的查询一律走 chat。\n"
    "\n"
    "返回 JSON（只返回 JSON，不要其他文字）：\n"
    "{\n"
    "  \"type\": \"chat\" | \"navigate\",\n"
    "  \"tools\": [],\n"
    "  \"page\": null | \"exam-v2\" | \"diagnosis\" | \"students\" | \"teacher\",\n"
    "  \"provider\": \"deepseek\" | \"mimo\"\n"
    "}\n"
    "\n"
    "页面映射（仅 navigate 时需要）：\n"
    "- \"打开考试工作台\" → exam-v2\n"
    "- \"打开诊断页面\" → diagnosis\n"
    "- \"打开学生管理\" → students\n"
    "- \"去首页/班级列表\" → teacher\n"
    "- 查询类（\"有哪些学生\"\"XX班的谁\"）一律走 chat，不走 navigate\n"
    "\n"
    "可用工具（仅 chat 时需要，最多3个，只从以下列表中选择）：\n"
    "{tool_list}\n"
    "\n"
    "Provider 选择：\n"
    "- 图片/拍照/OCR/识别/上传 → mimo\n"
    "- 其他 → deepseek\n"
    "\n"
    "{conversation_context}\n"
    "用户消息：{user_input}\n"
    "\n"
    "JSON："
)

# Full tool catalog with descriptions for prompt injection
# Tool → target agent mapping (used by keyword router, Phase 3)
_TOOL_TO_AGENT = {
    "search_exam_bank": "search_expert",
    "web_search": "search_expert",
    "show_exam_workbench": "exam_expert",
    "generate_questions": "exam_expert",
    "save_to_bank": "exam_expert",
    "diagnose_barrier": "diagnosis_expert",
    "show_diagnosis": "diagnosis_expert",
    "show_students": "diagnosis_expert",
    "assign_adaptive_practice": "diagnosis_expert",
    "chemistry_tutor": "tutor_expert",
    "simulate_experiment": "tutor_expert",
    "balance_equation": "tutor_expert",
    "weekly_report": "tutor_expert",
    "list_banks": "bank_manager",
    "delete_bank": "bank_manager",
    "browse_navigate": "browser_expert",
    "browse_read": "browser_expert",
    "browse_click": "browser_expert",
    "browse_input": "browser_expert",
    "browse_screenshot": "browser_expert",
}
_ALL_TOOL_DESCRIPTIONS = {
    "search_exam_bank": "搜索历年高考化学真题",
    "generate_questions": "AI生成化学题目",
    "diagnose_barrier": "诊断学生学习障碍类型",
    "web_search": "联网搜索最新化学资讯和高考动态",
    "balance_equation": "审核化学方程式配平",
    "chemistry_tutor": "引导式化学辅导答疑",
    "simulate_experiment": "模拟化学实验，生成实验报告",
    "weekly_report": "生成学生本周化学学习周报",
    "assign_adaptive_practice": "根据学生障碍布置自适应练习",
    "show_exam_workbench": "打开考试工作台面板",
    "show_students": "展示班级学生列表",
    "show_diagnosis": "在聊天中展示诊断结果图表",
    "list_banks": "列出所有题库文件夹",
    "delete_bank": "删除题库文件夹",
    "generate_learning_plan": "生成学生个性化学习计划",
    "send_learning_plan": "发送学习计划给学生",
    "generate_parent_report": "生成发给家长的学习报告",
    "send_report_to_parent": "推送学习报告给家长",
    "memory_student_get": "获取学生长期学情记忆",
}


def _build_tool_list(available_skills: list[str] | None) -> str:
    """Build the '可用工具' section for the classify prompt."""
    if not available_skills:
        skills = list(_ALL_TOOL_DESCRIPTIONS.keys())
    else:
        skills = available_skills

    lines = []
    for name in skills:
        desc = _ALL_TOOL_DESCRIPTIONS.get(name, "")
        if desc:
            lines.append(f"- {name}: {desc}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def _build_classify_prompt(
    user_input: str,
    available_skills: list[str] | None = None,
    conversation_context: str = "",
) -> str:
    """Build the full classification prompt with injected context."""
    tool_list = _build_tool_list(available_skills)
    ctx_block = f"对话历史：\n{conversation_context}" if conversation_context else ""
    return (
        CLASSIFY_PROMPT.replace("{tool_list}", tool_list)
        .replace("{conversation_context}", ctx_block)
        .replace("{user_input}", user_input)
    )


def _validate_tools(tools) -> list | None:
    """Validate and normalize the tools field from LLM output.

    Returns a list of tool name strings, or None if invalid.
    """
    if tools is None:
        return None
    if not isinstance(tools, list):
        logger.warning(
            "IntentClassifier: tools is not a list (got %s), falling back to None",
            type(tools).__name__,
        )
        return None
    result = [t for t in tools if isinstance(t, str)]
    if len(result) != len(tools):
        logger.warning(
            "IntentClassifier: %d non-string entries dropped from tools",
            len(tools) - len(result),
        )
    return result if result else None


@dataclass
class IntentResult:
    type: str = "chat"            # chat | navigate
    page: Optional[str] = None    # exam-v2 | diagnosis | students | teacher | None
    tools: Optional[list] = None  # None = all tools, [] = no tools
    provider: str = "deepseek"
    target_agent: Optional[str] = None   # Phase 3: pre-routed sub-agent name
    confidence: str = "low"              # high | low — for confidence-graded dispatch


class IntentClassifier:
    def __init__(self, provider):
        self._provider = provider

    async def classify(
        self,
        user_input: str,
        available_skills: list[str] | None = None,
        conversation_context: str = "",
    ) -> IntentResult:
        """LLM 语义分类 + tool 推荐。

        Args:
            user_input: 用户当前消息
            available_skills: 当前 persona 的可用 skill 名列表，None 表示全部
            conversation_context: 最近几轮对话历史（文本）
        """
        prompt = _build_classify_prompt(
            user_input,
            available_skills=available_skills,
            conversation_context=conversation_context,
        )

        try:
            result = await self._provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            llm_result = self._parse(result.content)
            # 合并关键词建议 — LLM 可能漏掉关键工具
            kw_result = self._keyword_fallback(user_input)
            if kw_result.tools and llm_result.tools:
                merged = list(set(llm_result.tools + kw_result.tools))
            elif kw_result.tools:
                merged = kw_result.tools
            else:
                merged = llm_result.tools
            llm_result.tools = merged
            return llm_result
        except Exception:
            logger.warning("IntentClassifier: LLM call failed", exc_info=True)
            return self._keyword_fallback(user_input)

    def _parse(self, content: str) -> IntentResult:
        """Parse LLM JSON response with type validation and keyword fallback."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                raw_tools = data.get("tools", None)
                tools = _validate_tools(raw_tools)
                return IntentResult(
                    type=data.get("type", "chat"),
                    page=data.get("page"),
                    tools=tools,
                    provider=data.get("provider", "deepseek"),
                )
        except (json.JSONDecodeError, KeyError):
            logger.warning("IntentClassifier: JSON parse failed", exc_info=True)

        return self._keyword_fallback(content)

    def _keyword_fallback(self, text: str) -> IntentResult:
        """Keyword-based fallback when LLM parsing fails.

        Enhanced v3: specific multi-char keywords, no single-char matches.
        Returns tool recommendations; sub-agent selects the right tool.
        """
        provider = "deepseek"

        if any(kw in text for kw in ["图片", "照片", "图像", "识别", "OCR", "上传"]):
            provider = "mimo"

        # Pure page navigation — only explicit open/go-to phrases
        if any(kw in text for kw in ["打开考试工作台", "打开学生管理", "打开诊断页面", "去首页"]):
            page = None
            if any(kw in text for kw in ["考试"]):
                page = "exam-v2"
            elif any(kw in text for kw in ["诊断"]):
                page = "diagnosis"
            elif any(kw in text for kw in ["学生管理"]):
                page = "students"
            elif any(kw in text for kw in ["首页"]):
                page = "teacher"
            if page:
                return IntentResult(type="navigate", page=page, tools=[], provider=provider)

        # Keyword-based tool recommendation (no single-char keywords)
        tools = []
        # Question generation: "出"+"题" or "组"+"卷" or explicit compounds
        _has_qword = any(kw in text for kw in ["题", "题目", "卷子", "卷", "试卷"])
        _has_gen = any(kw in text for kw in ["出", "生成", "组", "来几道", "给几道"])
        if _has_qword and _has_gen:
            tools.append("show_exam_workbench")
            tools.append("generate_questions")
        elif any(kw in text for kw in ["出题", "组卷", "出卷", "组考", "生成题目", "生成练习", "套卷"]):
            tools.append("show_exam_workbench")
            tools.append("generate_questions")
        if any(kw in text for kw in ["班", "班级", "学生"]):
            tools.append("show_students")
            tools.append("diagnose_barrier")
        if any(kw in text for kw in ["诊断", "学习障碍", "学情分析", "错题", "障碍", "薄弱", "弱点"]):
            if "diagnose_barrier" not in tools:
                tools.append("diagnose_barrier")
        if any(kw in text for kw in ["周报", "学习报告", "本周", "学习情况"]):
            tools.append("weekly_report")
        if any(kw in text for kw in ["搜索", "真题", "查一下", "查最新", "高考大纲", "考试大纲"]):
            tools.append("search_exam_bank")
        if any(kw in text for kw in ["网上", "上网", "联网", "搜一搜", "搜一下", "搜搜"]):
            tools.append("web_search")
        if any(kw in text for kw in ["模拟"]):
            tools.append("simulate_experiment")
        if any(kw in text for kw in ["配平", "方程式"]):
            tools.append("balance_equation")
        if any(kw in text for kw in ["导入", "PDF", "试卷上传"]):
            tools.append("show_exam_workbench")
        if any(kw in text for kw in ["自适应", "布置练习", "针对性练习"]):
            tools.append("assign_adaptive_practice")
        if any(kw in text for kw in ["学习计划", "学习方案", "学习规划", "制定计划"]):
            tools.append("generate_learning_plan")
        if any(kw in text for kw in ["发给家长", "家长报告", "学习报告发给家长"]):
            tools.append("generate_parent_report")
        if any(kw in text for kw in ["什么是", "什么意思", "怎么做", "原理", "为什么", "怎么理解",
                                      "讲解", "解释一下", "帮我讲", "怎么算"]):
            tools.append("chemistry_tutor")
        if any(kw in text for kw in ["题库文件夹", "列出题库", "我的题库", "保存到题库", "存到题库"]):
            tools.append("list_banks")
        if any(kw in text for kw in ["删除题库", "删掉题库"]):
            tools.append("delete_bank")

        if not tools:
            tools = None  # No keyword match → let Agent use all tools

        result = IntentResult(type="chat", tools=tools, provider=provider)
        result = self._route_agent(result)
        return result

    def _route_agent(self, intent: IntentResult) -> IntentResult:
        """Map suggested tools to target sub-agent with confidence grading (Phase 3).

        High confidence: all tools agree on one agent, or 2+ tools from same agent.
        Low confidence: single tool matched, or tools point to different agents.
        No tools (None): don't set agent — LLM fallback needed.
        """
        if intent.tools is None:
            return intent  # No keyword match — needs LLM

        agents = {}
        for t in intent.tools:
            agent = _TOOL_TO_AGENT.get(t)
            if agent:
                agents[agent] = agents.get(agent, 0) + 1

        if not agents:
            return intent  # Tools without agent mapping

        # Confidence grading
        unique_agents = len(agents)
        max_count = max(agents.values()) if agents else 0
        total_tools = len(intent.tools)

        if unique_agents == 1:
            intent.target_agent = list(agents.keys())[0]
            intent.confidence = "high" if max_count >= 2 else "low"
        elif max_count >= 2 and max_count >= total_tools * 0.6:
            # Majority vote: most tools point to same agent
            intent.target_agent = max(agents, key=agents.get)
            intent.confidence = "low"
        # else: tools disagree → leave agent=None, let LLM decide

        return intent
