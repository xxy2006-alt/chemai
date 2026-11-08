"""
L2 judge harness (Spec 04, seam 3) — LLM-as-judge with 5 rubric families.

Single entry contract:
    judge(sample, rubric_family) -> {score, confidence, rationale, severe_flags}
Everything below this entry (provider choice, calibration, human fallback,
cost caps) is hidden from callers. Scores NEVER gate a release — only
severe_flags feed the slow-layer veto.

Provider decision (Spec 04): the judge uses DEEPSEEK as 备选 provider (differs
from the evaluated mimo/qwen models) via the same DEEPSEEK_API_KEY /
DEEPSEEK_BASE_URL / DEEPSEEK_MODEL env CI already configures. JUDGE_API_KEY /
JUDGE_BASE_URL / JUDGE_MODEL override them when set.

Family enablement (Spec 04): a family is enabled only when its calibration set
has >= MIN_CALIBRATION_SAMPLES human-labeled samples AND judge-human agreement
>= ENABLE_THRESHOLD; otherwise it runs in 人机混合 mode (human review of low
confidence/low score samples).
"""
import json
import os
import re

MIN_CALIBRATION_SAMPLES = 20
AGREEMENT_TOLERANCE = 10        # |judge - human| <= 10 视为一致
ENABLE_THRESHOLD = 0.8          # 一致率 >= 80% 才启用
MAX_JUDGE_CALLS = 200           # 单次慢跑硬上限（Spec 04）
ESTIMATED_YUAN_PER_CALL = 0.02  # deepseek 单次判官调用估算（月度 ¥500 预算内）

CONFIDENCE_LEVELS = {"low", "medium", "high"}
KNOWN_SEVERE_FLAGS = {"chemical_error", "safety_issue", "end_to_end_failure"}

FAMILY_NAMES = {
    "question_gen": "出题",
    "grading": "判卷",
    "diagnosis": "诊断",
    "plan": "方案",
    "interaction": "交互智能",
}

# 五族 rubric：dimension -> (weight, 说明)。权重总和为 1。
RUBRICS = {
    "question_gen": {
        "dimensions": {
            "chemical_correctness": (0.5, "化学正确性（权重最高）：题干/选项/答案/解析在化学上必须正确"),
            "difficulty_match": (0.2, "难度匹配：符合要求的难度档位"),
            "parsing_correct": (0.15, "解析正确：解析过程与答案一致且无错误"),
            "format_standard": (0.15, "格式规范：题型结构、选项数量、题干表述规范"),
        },
        "severe": "chemical_error",
    },
    "grading": {
        "dimensions": {
            "correctness_vs_golden": (0.6, "判分正确性：每题判分与黄金答案一致"),
            "partial_credit": (0.2, "部分分：多步题的部分得分是否合理"),
            "consistency": (0.2, "一致性：同类型错误的扣分标准一致"),
        },
        "severe": None,
    },
    "diagnosis": {
        "dimensions": {
            "barrier_type_correct": (0.6, "障碍类型判断：concept/reading/expression 分类正确"),
            "evidence_usage": (0.2, "证据使用：诊断有错题/数据支撑"),
            "explanation": (0.2, "解释质量：诊断理由清楚可执行"),
        },
        "severe": None,
    },
    "plan": {
        "dimensions": {
            "fit": (0.4, "适配性：方案贴合学生障碍与当前水平"),
            "executable": (0.3, "可执行性：步骤具体、可落地"),
            "personalized": (0.3, "个性化：非模板化，针对该学生定制"),
        },
        "severe": None,
    },
    "interaction": {
        "dimensions": {
            "clarification": (0.25, "澄清追问：信息不足时主动追问"),
            "proactive": (0.25, "主动推荐：结合上下文给建议"),
            "options_guidance": (0.25, "给选项引导：追问以选项形式呈现，不开放式盘问"),
            "decomposition_progress": (0.25, "拆解与进度：复杂任务拆步骤并汇报进度"),
        },
        "severe": None,
    },
}

_OUTPUT_CONTRACT = (
    "只输出一个 JSON 对象，不要任何其他文字：\n"
    '{"score": 0到100的整数, "confidence": "low|medium|high", '
    '"rationale": "逐维度简述打分理由", "severe_flags": ["chemical_error"/"safety_issue" 等，无则为 []]}\n'
    '严重错误说明：出题族出现化学错误 → severe_flags=["chemical_error"]；'
    "安全问题 → [\"safety_issue\"]；其余族通常为空数组。"
)


def build_prompt(sample, rubric_family):
    """Build the judge prompt for one sample under one rubric family."""
    if rubric_family not in RUBRICS:
        raise ValueError(f"unknown rubric family: {rubric_family}")
    rubric = RUBRICS[rubric_family]
    dims = "\n".join(
        f"- {name}（权重 {w}）：{desc}" for name, (w, desc) in rubric["dimensions"].items()
    )
    parts = [f"输入：{sample.get('input', '')}"]
    if sample.get("output") is not None:
        parts.append(f"待评输出：{sample['output']}")
    if sample.get("reference") is not None:
        parts.append(f"黄金参考答案：{sample['reference']}")
    return (
        f"你是 ChemAI 化学教育 agent 的判官，负责「{FAMILY_NAMES[rubric_family]}」族评估。\n"
        f"按以下 rubric 给待评输出打 0-100 分：\n{dims}\n\n"
        + "\n".join(parts)
        + f"\n\n{_OUTPUT_CONTRACT}"
    )


def parse_judge_response(text, rubric_family):
    """Parse the judge's JSON output. Robust to code fences and markdown noise.

    On failure returns score=None, confidence=low, parse_error=True — the
    caller routes such samples to the human review queue (人机兜底)."""
    fallback = {
        "score": None, "confidence": "low",
        "rationale": f"判官输出解析失败: {str(text)[:200]}",
        "severe_flags": [], "parse_error": True,
    }
    if not text:
        return fallback
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return fallback
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, TypeError):
        return fallback
    score = data.get("score")
    if not isinstance(score, (int, float)):
        return fallback
    score = max(0, min(100, int(score)))
    confidence = data.get("confidence", "low")
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "low"
    flags = [f for f in data.get("severe_flags", [])
             if f in KNOWN_SEVERE_FLAGS and f == RUBRICS[rubric_family].get("severe")]
    return {
        "score": score,
        "confidence": confidence,
        "rationale": str(data.get("rationale", ""))[:500],
        "severe_flags": flags,
        "parse_error": False,
    }


class JudgeProvider:
    async def complete(self, prompt: str) -> str:
        raise NotImplementedError


class DeepSeekJudgeProvider(JudgeProvider):
    """Real judge provider (deepseek, OpenAI-compatible chat API)."""

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = (api_key or os.environ.get("JUDGE_API_KEY")
                        or os.environ.get("DEEPSEEK_API_KEY"))
        self.base_url = (os.environ.get("JUDGE_BASE_URL")
                         or os.environ.get("DEEPSEEK_BASE_URL")
                         or "https://api.deepseek.com/v1").rstrip("/")
        self.model = (model or os.environ.get("JUDGE_MODEL")
                      or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat")

    async def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY（判官备选 provider 未配置）")
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "temperature": 0,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


class ScriptedJudgeProvider(JudgeProvider):
    """Test/demo provider returning scripted responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)

    async def complete(self, prompt: str) -> str:
        if not self.responses:
            return '{"score": 50, "confidence": "low", "rationale": "scripted exhausted", "severe_flags": []}'
        return self.responses.pop(0)


class JudgeRunner:
    """Judges a batch with the hard call cap and cost ledger (Spec 04)."""

    def __init__(self, provider):
        self.provider = provider
        self.calls = 0
        self.truncated = 0

    @property
    def cost_yuan(self):
        return round(self.calls * ESTIMATED_YUAN_PER_CALL, 2)

    async def judge(self, sample, rubric_family, max_calls=MAX_JUDGE_CALLS):
        if self.calls >= max_calls:
            self.truncated += 1
            return {
                "score": None, "confidence": "low",
                "rationale": f"超出判官调用上限 {max_calls}，样本未测（转人工复核）",
                "severe_flags": [], "truncated": True,
            }
        self.calls += 1
        try:
            text = await self.provider.complete(build_prompt(sample, rubric_family))
        except Exception as exc:
            return {
                "score": None, "confidence": "low",
                "rationale": f"判官调用失败: {type(exc).__name__}: {exc}",
                "severe_flags": [], "provider_error": True,
            }
        return parse_judge_response(text, rubric_family)

    async def judge_batch(self, samples, rubric_family, max_calls=MAX_JUDGE_CALLS):
        results = []
        for sample in samples:
            results.append(await self.judge(sample, rubric_family, max_calls=max_calls))
        return results, self.truncated
