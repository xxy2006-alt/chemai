"""
ChemAgent Planner — decompose complex teaching goals into structured execution plans.
"""
import json
import re
from dataclasses import dataclass, field


PLAN_PROMPT = """你是化学教研助手的目标拆解器。将用户的复杂目标拆解为结构化执行步骤。

可用技能：
{skills}

已知学生（学号 → 姓名）：
{students}

返回 JSON（只返回 JSON，不要其他文字）：
{{
  "goal": "原始目标（复述）",
  "steps": [
    {{
      "step": 1,
      "skill": "技能名",
      "args": {{"参数名": "参数值"}},
      "depends_on": [],
      "description": "中文步骤描述"
    }}
  ]
}}

规则：
- 最多 8 个步骤
- 计划必须覆盖用户目标中的**全部**结果，不得遗漏：提到「家长/父母/同步/告知家长」
  必须包含 generate_parent_report（生成家长报告）与 send_report_to_parent（发送给家长）步骤；
  提到「发送给学生」必须包含 send_learning_plan 步骤
- depends_on 引用前序步骤编号（如 [1, 2]）
- 需要前序步骤输出时，使用 ${{step_N.field}} 引用（如 "${{step_1.question_ids}}"）
- 禁止循环依赖
- 如果不需要拆解，返回单步 Plan
- 步骤描述用学生姓名（如「陈湘旻」），不要只写学号；名称未知时先安排查找学生的步骤

用户目标: {goal}

JSON:"""


@dataclass
class PlanStep:
    step: int
    skill: str
    args: dict = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    description: str = ""
    status: str = "pending"  # pending / running / completed / failed / skipped


@dataclass
class Plan:
    goal: str = ""
    steps: list[PlanStep] = field(default_factory=list)


class PlanGenerator:
    def __init__(self, provider):
        self._provider = provider

    async def generate(self, user_goal: str, available_skills: list[str],
                       student_context: str = "") -> Plan:
        """LLM 调用拆解用户目标为结构化执行计划。失败时 fallback 到单步 Plan。

        student_context: 目标中出现的学号 → 姓名映射（给描述用人名、args 用学号），
        空串时占位为「（无）」。"""
        # Build skills description
        skills_desc = "\n".join(f"  - {s}" for s in available_skills)
        prompt = (PLAN_PROMPT
                  .replace("{skills}", skills_desc)
                  .replace("{students}", student_context or "（无）")
                  .replace("{goal}", user_goal))

        try:
            result = await self._provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1024,
            )
            plan = self._parse(result.content, available_skills)
            if not plan.steps:
                return self._single_step_fallback(user_goal, available_skills)
            return plan
        except Exception:
            return self._single_step_fallback(user_goal, available_skills)

    def _parse(self, content: str, available_skills: list[str]) -> Plan:
        """Parse LLM JSON, validate steps."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start < 0 or end <= start:
                return Plan()
            data = json.loads(content[start:end])
            steps = self._validate_steps(data.get("steps", []), available_skills)
            return Plan(goal=data.get("goal", ""), steps=steps)
        except (json.JSONDecodeError, KeyError):
            return Plan()

    def _validate_steps(self, steps_data: list[dict], available_skills: list[str]) -> list[PlanStep]:
        """Validate and sanitize steps. Cap at 8, check skill names, detect cycles."""
        valid = []
        seen_steps = set()
        for sd in steps_data:
            sn = sd.get("step", 0)
            if sn in seen_steps or sn < 1:
                continue
            seen_steps.add(sn)
            skill = sd.get("skill", "")
            if skill not in available_skills:
                continue  # skip unknown skills
            deps = sd.get("depends_on", [])
            # Detect self-reference cycles
            if sn in deps:
                deps = [d for d in deps if d != sn]
            valid.append(PlanStep(
                step=sn,
                skill=skill,
                args=sd.get("args", {}),
                depends_on=deps,
                description=sd.get("description", skill),
            ))
        return valid[:8]  # cap at 8 steps

    def _single_step_fallback(self, goal: str, available_skills: list[str]) -> Plan:
        """Fallback: single-step plan using the best-guess skill."""
        # Pick the most relevant skill based on keyword matching
        skill = available_skills[0] if available_skills else "search_exam_bank"
        if any(kw in goal for kw in ["题", "出题", "生成"]):
            skill = "generate_questions" if "generate_questions" in available_skills else skill
        elif any(kw in goal for kw in ["诊断", "障碍"]):
            skill = "diagnose_barrier" if "diagnose_barrier" in available_skills else skill
        elif any(kw in goal for kw in ["搜索", "真题", "查"]):
            skill = "search_exam_bank" if "search_exam_bank" in available_skills else skill

        return Plan(goal=goal, steps=[PlanStep(
            step=1, skill=skill, args={"keyword": goal[:50]},
            description=f"执行 {skill}"
        )])

    def inject_dependencies(self, step: PlanStep, prior_results: dict[int, dict]) -> dict:
        """Resolve ${step_N.field} template references in step.args."""
        resolved = {}
        for key, value in step.args.items():
            if not isinstance(value, str):
                resolved[key] = value
                continue
            def replacer(m):
                ref_step = int(m.group(1))
                ref_field = m.group(2)
                ref_data = prior_results.get(ref_step, {})
                val = ref_data.get(ref_field, "")
                return str(val) if not isinstance(val, list) else ",".join(str(v) for v in val)
            resolved[key] = re.sub(r"\$\{step_(\d+)\.(\w+)\}", replacer, value)
        return resolved
