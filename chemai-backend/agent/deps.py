"""ChemAI pydantic-ai 依赖注入容器"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChemAIDeps:
    """传递给 pydantic-ai RunContext.deps 的上下文对象。

    tool 函数通过 ctx.deps 访问学生画像、episodic 记忆等。
    """
    student_id: Optional[str] = None
    student_profile: dict = field(default_factory=dict)
    persona: str = "tutor"
    episodic: dict = field(default_factory=dict)
    provider_name: str = "deepseek"
