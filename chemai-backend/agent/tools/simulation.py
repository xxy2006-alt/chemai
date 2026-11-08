"""Experiment simulation tool."""

import json
import re

from dotenv import load_dotenv
load_dotenv()


async def simulate_experiment(experiment_name: str = "") -> str:
    """实验模拟 — 模拟高中化学实验过程

    何时用：用户想了解某个实验的操作步骤、现象、原理，或说"模拟XX实验"
    会发生什么：生成实验步骤、预测现象、写出方程式、解释原理，附带安全提醒
    下一步：基于实验结果回答用户追问；如需配平实验方程式 → balance_equation
    NOT for 一般化学概念讲解 — 用 chemistry_tutor"""
    from agent.provider.deepseek import DeepSeekProvider

    provider = DeepSeekProvider()

    system_prompt = """你是高中化学实验教学专家。为指定实验生成完整报告。

返回JSON:
{
  "experiment_name": "实验名称",
  "objectives": ["实验目的1", "实验目的2"],
  "equipment": ["仪器1", "药品1"],
  "steps": ["步骤1: ...", "步骤2: ..."],
  "expected_phenomena": ["现象1: ...", "现象2: ..."],
  "equations": ["化学方程式1", "化学方程式2"],
  "principles": ["原理1", "原理2"],
  "safety": ["安全提醒1", "安全提醒2"],
  "exam_tips": ["高考考点提示"]
}"""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请生成实验报告: {experiment_name}"},
        ],
        temperature=0.5, max_tokens=2048,
    )

    content = result.content
    json_match = re.search(r"\{[\s\S]*\}", content)

    await provider.close()

    if json_match:
        return json_match.group()
    return json.dumps({"experiment_name": experiment_name, "error": "JSON解析失败"}, ensure_ascii=False)
