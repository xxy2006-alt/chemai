"""ChemAI persona 配置加载。

移除 pydantic-ai Agent 工厂（ChemAIAgentFactory / factory），
旧 SSE 端点已删除。仅保留 load_persona 供 LangGraph v2 与测试使用。
"""
import os
import yaml


def load_persona(name: str) -> dict:
    """加载 persona YAML 配置"""
    persona_dir = os.path.join(os.path.dirname(__file__), "personas")
    path = os.path.join(persona_dir, f"{name}.yaml")
    if not os.path.exists(path):
        path = os.path.join(persona_dir, "tutor.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
