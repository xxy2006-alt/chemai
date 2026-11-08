"""
plan_task — 复杂任务拆解（Spec 06：planner 接入 v2 agent）。

agent/planner.py 的 PlanGenerator 原为零引用死代码；本工具把它接入 ReAct 循环：
LLM 判断任务复杂时调用本工具 → 生成 ≤6 步结构化计划（步骤/技能/依赖/描述）→
计划 JSON 经 SSE 适配器转成 plan_summary / plan_progress 事件，驱动前端步骤卡
（前端已有 addPlanCard/updatePlanCard 消费这些事件）。
"""
import json


async def plan_task(goal: str = "") -> str:
    """任务拆解 — 把复杂目标拆成结构化执行步骤计划。

    何时用：用户提出多步骤复杂任务（如「先诊断班级薄弱点，再按薄弱点出题，最后生成复习计划」）
    会发生什么：生成 ≤8 步执行计划（每步含技能/依赖/描述）——生成后你必须立即执行第 1 步，
              并逐步骤调用对应工具执行，直到全部步骤完成后再汇报。
    铁律（2026-08 长任务断链修复 + ADR-0013 确认门）：生成后禁止停下来问参数——
    参数不全时用合理默认值继续；但执行途中弹出的确认门（确认卡）必须停下等老师决定，
    门的结果会自动推进任务。出题类步骤调用 generate_questions 或 show_exam_workbench。
    NOT for 简单单步任务 — 闲聊、单次问答、单次搜索不需要计划"""
    if not goal or not goal.strip():
        return json.dumps({"error": "请提供要拆解的任务目标"}, ensure_ascii=False)

    from agent.planner import PlanGenerator
    from agent.provider.deepseek import DeepSeekProvider
    from agent.tools import TOOL_META

    available_skills = sorted(t.__name__ for t in TOOL_META)

    # 目标里的纯数字学号 → 查姓名，给规划器上下文（描述用人名，不再「学生241914」）
    student_context = ""
    try:
        import re
        from app.models.database import get_db
        from sqlalchemy import text as _text
        ids = sorted(set(re.findall(r"(?<!\d)\d{6,8}(?!\d)", goal)))[:5]
        if ids:
            # ids 来自 \d 正则，纯数字，可安全内插（text() 的 IN 不支持普通绑定）
            conds = " OR ".join(f"student_id = '{i}'" for i in ids)
            session = next(get_db())
            rows = session.execute(
                _text(f"SELECT student_id, name FROM students WHERE {conds}"),
            ).fetchall()
            session.close()
            if rows:
                student_context = "；".join(f"{r[0]} = {r[1]}" for r in rows)
    except Exception:
        student_context = ""

    generator = PlanGenerator(DeepSeekProvider())
    plan = await generator.generate(goal.strip(), available_skills, student_context)

    steps = [
        {
            "step": s.step,
            "skill": s.skill,
            "args": s.args,
            "depends_on": s.depends_on,
            "description": s.description,
            "status": "pending",
        }
        for s in plan.steps
    ]
    return json.dumps({
        "goal": plan.goal or goal.strip(),
        "total_steps": len(steps),
        "steps": steps,
    }, ensure_ascii=False)
