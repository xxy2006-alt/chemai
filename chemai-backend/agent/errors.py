"""
AgentError hierarchy — unified error handling for agent execution.
"""


class AgentError(Exception):
    """Base exception for all agent errors."""
    code: str = "AGENT_ERROR"
    recoverable: bool = False

    def __init__(self, message: str = "", code: str = None, recoverable: bool = None):
        super().__init__(message)
        if code:
            self.code = code
        if recoverable is not None:
            self.recoverable = recoverable

    def to_sse(self) -> dict:
        return {"type": "error", "code": self.code, "message": str(self), "recoverable": self.recoverable}


class SkillExecutionError(AgentError):
    """Skill execution failed."""
    code = "SKILL_EXECUTION_ERROR"
    recoverable = True

    def __init__(self, skill_name: str, original_error: Exception):
        super().__init__(f"Skill '{skill_name}' failed: {original_error}")
        self.skill_name = skill_name
        self.original_error = original_error


class SkillNotFoundError(AgentError):
    """Skill not registered."""
    code = "SKILL_NOT_FOUND"
    recoverable = False

    def __init__(self, skill_name: str):
        super().__init__(f"Skill '{skill_name}' not found")
        self.skill_name = skill_name


class SkillPermissionError(AgentError):
    """Skill not allowed for current persona."""
    code = "SKILL_PERMISSION_DENIED"
    recoverable = False

    def __init__(self, skill_name: str, persona: str):
        super().__init__(f"Skill '{skill_name}' not allowed for persona '{persona}'")
        self.skill_name = skill_name
        self.persona = persona


class ProviderError(AgentError):
    """LLM provider error (timeout, rate limit, etc.)."""
    code = "PROVIDER_ERROR"
    recoverable = True

    def __init__(self, message: str, provider: str = "", status_code: int = 0):
        super().__init__(message, recoverable=status_code in (429, 500, 502, 503))
        self.provider = provider
        self.status_code = status_code


class PlanError(AgentError):
    """Planning failed."""
    code = "PLAN_ERROR"
    recoverable = True

    def __init__(self, goal: str, reason: str):
        super().__init__(f"Plan for '{goal[:50]}' failed: {reason}")
        self.goal = goal
        self.reason = reason


class ToolError(AgentError):
    """Tool execution failed — recoverable, LLM should try alternative."""
    code = "TOOL_ERROR"
    recoverable = True

    def __init__(self, tool: str, reason: str):
        super().__init__(f"Tool '{tool}' failed: {reason}")
        self.tool = tool
        self.reason = reason


def safe_tool_call(tool_name: str, fn, *args, **kwargs) -> str:
    """Execute a tool function safely, returning structured error on failure.

    Returns JSON string — either the tool's result or {"error": ..., "_tool_error": true}.
    This lets the SSE adapter and LLM handle failures gracefully.
    """
    import json as _json
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        err = ToolError(tool_name, str(e))
        return _json.dumps({"error": str(err), "code": err.code, "_tool_error": True}, ensure_ascii=False)
