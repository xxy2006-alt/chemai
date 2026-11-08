"""
ChemAI LLM Service — MiMo-V2.5 (主力) / DashScope / DeepSeek
"""
import os
import json
import base64
import time
import threading
import httpx
from typing import List, Dict, Optional
from app.core.config import settings

_rate_lock = threading.Lock()
_rate_window: Dict[str, list] = {}

def _check_rate_limit(key: str, max_per_minute: int = 30) -> bool:
    now = time.time()
    with _rate_lock:
        if key not in _rate_window:
            _rate_window[key] = []
        _rate_window[key] = [t for t in _rate_window[key] if now - t < 60]
        if len(_rate_window[key]) >= max_per_minute:
            return False
        _rate_window[key].append(now)
        return True

cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()

def cache_get(key: str):
    with _cache_lock:
        e = cache.get(key)
        if e and time.time() < e[1]:
            return e[0]
        if e:
            del cache[key]
    return None

def cache_set(key: str, value, ttl: int = 300):
    with _cache_lock:
        cache[key] = (value, time.time() + ttl)


def parse_llm_json(raw: str) -> dict:
    """解析 LLM 输出的 JSON，修复未转义的 LaTeX 命令反斜杠。

    LLM 常按提示词输出 `\rightleftharpoons`（反斜杠未转义），json.loads 会把 `\r` 当回车符、
    `\b` 当退格、`\t` 当制表符等，导致题目内容损坏（如 "ightleftharpoons"）。
    修复：反斜杠后紧跟字母且再接字母的序列视为 LaTeX 命令，转义其反斜杠；
    已转义（双反斜杠）的不重复转义。u 后接十六进制数字（unicode 转义）不受影响。"""
    import re as _re
    content = raw
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    content = _re.sub(r'(?<!\\)\\([a-zA-Z])(?=[a-zA-Z])', r'\\\\\1', content)
    return json.loads(content)


class LLMService:
    MIMO_URL = "https://api.xiaomimimo.com/v1/chat/completions"
    MIMO_MODEL = "mimo-v2.5"
    DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
    ZHIPU_VISION_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def __init__(self):
        self.mimo_key = settings.XIAOMI_API_KEY or os.getenv("XIAOMI_API_KEY", "")
        self.dashscope_key = settings.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY", "")
        self.deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = settings.LLM_MODEL
        self.enabled = bool(self.mimo_key or self.dashscope_key or self.deepseek_key)

    def _call_llm_api(self, url: str, key: str, payload: dict, timeout: float = 30.0) -> Dict:
        h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, headers=h, json=payload)
        if r.status_code == 200:
            d = r.json()
            if d.get("error"):
                return {"success": False, "error": str(d["error"])}
            choices = d.get("choices", [{}])
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            return {"success": True, "content": content, "usage": d.get("usage", {}), "request_id": d.get("id", "")}
        return {"success": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}

    def _call_with_retry(self, url: str, key: str, payload: dict, timeout: float = 30.0, max_retries: int = 3) -> Dict:
        last = None
        for i in range(max_retries):
            try:
                r = self._call_llm_api(url, key, payload, timeout)
                if r.get("success"):
                    return r
                last = r.get("error", "unknown")
            except httpx.TimeoutException:
                last = f"timeout ({timeout}s)"
            except Exception as e:
                last = str(e)
            if i < max_retries - 1:
                time.sleep(2 ** i)
        return {"success": False, "error": last or "retries exhausted"}

    def generate_text(
        self, prompt: str, system_prompt: Optional[str] = None,
        temperature: float = 0.7, max_tokens: int = 2000, provider: str = "auto",
        enable_search: bool = False, **kw,
    ) -> Dict:
        if not self.enabled:
            return self._mock_generate(prompt)
        if not _check_rate_limit("llm", settings.LLM_RATE_LIMIT_PER_MINUTE):
            return {"success": False, "error": "请求过于频繁，请稍后再试"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Provider priority
        if provider == "auto":
            # dashscope/deepseek 优先: mimo 对复杂 JSON 生成慢(~30s)且偶发返回空内容
            order = [
                ("dashscope", self.dashscope_key, self.DASHSCOPE_URL, self.model),
                ("deepseek", self.deepseek_key, self.DEEPSEEK_URL, "deepseek-chat"),
                ("mimo", self.mimo_key, self.MIMO_URL, self.MIMO_MODEL),
            ]
        elif provider == "mimo" and self.mimo_key:
            order = [("mimo", self.mimo_key, self.MIMO_URL, self.MIMO_MODEL)]
        elif provider == "dashscope" and self.dashscope_key:
            order = [("dashscope", self.dashscope_key, self.DASHSCOPE_URL, self.model)]
        elif provider == "deepseek" and self.deepseek_key:
            order = [("deepseek", self.deepseek_key, self.DEEPSEEK_URL, "deepseek-chat")]
        else:
            return {"success": False, "error": f"no available provider: {provider}"}

        last = None
        for name, key, url, model in order:
            if not key:
                continue
            p = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
            if kw.get("response_format"):
                p["response_format"] = kw["response_format"]
            # MiMo web search
            if name == "mimo" and enable_search:
                p["enable_search"] = True
            r = self._call_with_retry(url, key, p, timeout=30.0)
            r["provider"] = name
            if r.get("success") and r.get("content"):
                return r
            last = r.get("error") or (r.get("provider", "?") + ": 返回内容为空")
            last = r.get("error", "unknown")
        return {"success": False, "error": last or "all providers failed"}

    def search_web(self, query: str, max_tokens: int = 500) -> Dict:
        """MiMo 联网搜索 — 适用于需要实时信息的查询"""
        return self.generate_text(query, temperature=0.3, max_tokens=max_tokens, provider="mimo", enable_search=True)

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> Dict:
        """Qwen-VL-OCR 图片文字提取（阿里百炼）"""
        import base64
        if not self.dashscope_key:
            return {"success": False, "error": "DASHSCOPE_API_KEY not set"}

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": "qwen-vl-ocr",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                     "min_pixels": 28 * 28 * 4, "max_pixels": 28 * 28 * 5000},
                    {"type": "text", "text": "Read all the text in the image. Output in markdown format."},
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        return self._call_with_retry(self.DASHSCOPE_URL, self.dashscope_key, payload, timeout=60.0)

    def _mock_generate(self, prompt: str) -> Dict:
        return {
            "success": True,
            "content": "[MOCK] configure XIAOMI_API_KEY / DASHSCOPE_API_KEY / DEEPSEEK_API_KEY to enable.",
            "usage": {"input_tokens": len(prompt), "output_tokens": 50},
            "request_id": "mock",
        }

    # ═══════════════════════════════════════════════════
    # AI Generate Questions
    # ═══════════════════════════════════════════════════

    def generate_questions(
        self, knowledge_points: List[str], difficulty: str, quantity: int = 10,
        question_types: List[str] = None, rag_context: List[Dict] = None,
    ) -> Dict:
        # 前端题型值 → LLM 内部类型（single_choice/multiple_choice/fill_blank/calculation 等）
        TYPE_ALIAS = {
            'single_choice': 'choice',
            'multiple_choice': 'multi',
            'fill_blank': 'fill',
            'calculation': 'calc',
        }
        question_types = [TYPE_ALIAS.get(t, t) for t in (question_types or ['choice'])]
        type_map = {
            'choice': '单选题', 'multi': '多选题', 'fill': '填空题', 'calc': '计算题',
            'experiment': '实验题', 'inference': '推断题',
        }
        type_names = [type_map.get(t, t) for t in (question_types or ['choice'])]
        type_desc = '、'.join(type_names)
        active_types = question_types or ['choice']

        type_specs = {
            'choice': {
                'rules': '4个选项(A/B/C/D)，有且仅有1个正确选项，标注正确选项。设置1-2个陷阱选项。',
                'example': (
                    '{"content":"下列关于盐类水解的说法正确的是（ ）",'
                    '"type":"choice",'
                    '"options":["A. $Na_2CO_3$溶液显碱性是因为$CO_3^{2-}$水解",'
                    '"B. $NaCl$溶液显中性是因为$Na^+$和$Cl^-$都不水解",'
                    '"C. $FeCl_3$溶液显酸性是因为$Fe^{3+}$水解",'
                    '"D. 以上都对"],'
                    '"answer":"D",'
                    '"knowledge_points":["盐类水解"],'
                    '"difficulty":"medium"}'
                ),
            },
            'multi': {
                'rules': (
                    '4个选项(A/B/C/D)，有2-3个正确选项，题目标注（多选），'
                    'answer 用逗号分隔多个正确选项（如 "A,C"）。'
                ),
                'example': (
                    '{"content":"下列说法正确的有（　　）（多选）",'
                    '"type":"multi",'
                    '"options":["A. $Na_2CO_3$溶液显碱性",'
                    '"B. $NaCl$溶液显中性",'
                    '"C. $FeCl_3$溶液显酸性",'
                    '"D. $NH_4Cl$溶液显碱性"],'
                    '"answer":"A,C",'
                    '"knowledge_points":["盐类水解"],'
                    '"difficulty":"medium"}'
                ),
            },
            'fill': {
                'rules': '题目用___标记填空。答案只填空缺内容。每道题可有1-3个空。不要设选项。',
                'example': (
                    '{"content":"实验室制氧气的方程式为___，$MnO_2$是___。",'
                    '"type":"fill",'
                    '"answer":"$2KClO_3 \\\\xrightarrow{{MnO_2}} 2KCl + 3O_2\\\\uparrow$; 催化剂",'
                    '"knowledge_points":["氧气制备"],'
                    '"difficulty":"medium"}'
                ),
            },
            'calc': {
                'rules': '具体数值条件。答案含分步计算: 公式→数据→结果→结论。不要设选项。',
                'example': (
                    '{"content":"5.85g $NaCl$溶于水配成500mL溶液。求:(1)物质的量(2)浓度。$M(NaCl)=58.5g/mol$",'
                    '"type":"calc",'
                    '"answer":"(1)$n=m/M=5.85/58.5=0.10mol$ (2)$c=n/V=0.10/0.5=0.20mol/L$",'
                    '"knowledge_points":["物质的量浓度"],'
                    '"difficulty":"medium"}'
                ),
            },
            'experiment': {
                'rules': '描述化学实验情境(仪器/试剂/操作)。2-3个子问题。不要设选项。',
                'example': (
                    '{"content":"用右图装置进行铜与浓硫酸反应实验。(1)写出化学方程式(2)品红褪色说明生成了什么(3)棉花蘸$NaOH$溶液的作用是什么",'
                    '"type":"experiment",'
                    '"answer":"(1)$Cu + 2H_2SO_4(浓) \\\\xrightarrow{{\\\\triangle}} '
                    'CuSO_4 + SO_2\\\\uparrow + 2H_2O$ (2)生成了$SO_2$ (3)吸收$SO_2$防止污染空气",'
                    '"knowledge_points":["浓硫酸","$SO_2$"],'
                    '"difficulty":"medium"}'
                ),
            },
            'inference': {
                'rules': '给出物质转化线索或实验现象，推断未知物质并写方程式。答案含推断过程。不要设选项。',
                'example': (
                    '{"content":"A、B、C三种常见物质。A为黑色粉末，与稀硫酸反应生成蓝色溶液B。B与铁反应析出红色固体C。推断A、B、C并写出涉及的反应方程式。",'
                    '"type":"inference",'
                    '"answer":"A:$CuO$ B:$CuSO_4$ C:$Cu$。$CuO + H_2SO_4 = CuSO_4 + H_2O$。'
                    '"$Fe + CuSO_4 = FeSO_4 + Cu$",'
                    '"knowledge_points":["金属活动性","置换反应"],'
                    '"difficulty":"hard"}'
                ),
            },
        }

        type_sections = []
        for qt in active_types:
            if qt in type_specs:
                s = type_specs[qt]
                type_sections.append(f"【{type_map[qt]}】{s['rules']}\nJSON示例: {s['example']}")

        q_json = (
            r'{"questions":[{"content":"下列关于氧化还原反应的说法正确的是（ ）","type":"choice","options":['
            r'"A. $2Na + Cl_2 \rightarrow 2NaCl$属于氧化还原反应",'
            r'"B. $NaOH + HCl \rightarrow NaCl + H_2O$属于氧化还原反应",'
            r'"C. $CaCO_3 \rightarrow CaO + CO_2$属于氧化还原反应",'
            r'"D. $NH_4Cl \rightarrow NH_3 + HCl$属于氧化还原反应"],'
            r'"answer":"A","knowledge_points":["氧化还原反应"],"difficulty":"medium"}]}'
        )

        system_prompt = f"""你是资深高中化学教师。

生成: {type_desc}

格式规范（严格遵循）:
{chr(10).join(type_sections)}

⚠️ 化学式格式规范（严格遵循，每道题每条选项都必须遵守）:
1. 所有化学式/离子/方程式 必须用 $...$ 包裹（LaTeX行内公式）
2. 下标用 _ 表示，上标用 ^ 表示。元素符号首字母大写
   正确: $H_2O$ $CO_2$ $Fe_2O_3$ $Fe^{{3+}}$ $SO_4^{{2-}}$ $Cl^-$
   错误: H2O CO2 Fe2O3 Fe3+ SO42-
3. 化学方程式中箭头必须用 \\rightarrow，可逆用 \\rightleftharpoons
   正确: $2H_2 + O_2 \\rightarrow 2H_2O$
   错误: 2H2 + O2 → 2H2O
4. 单质原子不需下标1: $Fe$ 而非 $Fe_1$
5. 气体↑用 \\uparrow，沉淀↓用 \\downarrow
6. 反应条件用 \\xrightarrow{{{{条件}}}}，加热用 \\xrightarrow{{{{\\triangle}}}}
   正确: $2KClO_3 \\xrightarrow{{{{MnO_2}}}} 2KCl + 3O_2\\uparrow$
7. 普通中文文字中嵌入的化学式也必须$包裹: 如"$MnO_2$是催化剂"
8. 离子电子用 e^-: $Cu^{{2+}} + 2e^- \\rightarrow Cu$
9. 复杂有机结构（苯环/杂环/立体结构等，文字难以表达）用 [SMILES:...] 标记输出，
   后端会自动渲染成结构图: 如 "[SMILES:C1=CC=CC=C1]"（苯）。
   【有机化学题目强制要求】题干或选项中出现环状/苯环/杂环/立体构型等结构时，
   必须用 [SMILES:...] 标记给出该结构，例如：
   - 苯: [SMILES:C1=CC=CC=C1]
   - 甲苯: [SMILES:Cc1ccccc1]
   - 乙酸乙酯: [SMILES:CCOC(=O)C]
   - 乙醇: [SMILES:CCO]
   至少一处（题干或选项或答案）必须包含 [SMILES:...] 结构标记，禁止用纯文字
   描述结构代替（如"苯环""六元环"）。简单链式分子式/方程式仍用上面的 $...$ 规范。

核心原则:
1. 科学性100%正确，方程式配平
2. 选择题带options，非选择题不带options
3. 非选择题content必须是该题型的真实内容（不能是选择题去掉选项）
4. 填空题必含___标记。计算题必含分步计算。实验题必含2-3个子问题。
5. 所有化学式必须用$...$包裹并使用LaTeX下标（见上方化学式格式规范）

返回纯JSON（无markdown代码块）:
{q_json}"""

        if rag_context and len(rag_context) >= 3:
            ctx = "\n\n".join(
                f"真题{i+1}: {q.get('content','')} 答案:{q.get('answer','')}"
                for i, q in enumerate(rag_context[:5])
            )
            prompt = f"基于以下真题生成变种题:\n{ctx}\n生成{quantity}道{difficulty}难度的{type_desc}，直接返回JSON:"
        else:
            prompt = (
                f"为以下知识点生成{quantity}道{difficulty}难度的{type_desc}:\n"
                f"知识点: {', '.join(knowledge_points)}\n"
                f"类型从 [{', '.join(active_types)}] 中选择。直接返回JSON:"
            )

        return self.generate_text(prompt, system_prompt, temperature=0.7)

    def audit_question_with_llm(self, question_content: str) -> Dict:
        audit_prompt = f"审核以下高中化学题目:\n{question_content}\n返回JSON: {{'is_qualified':bool,'issues':['...']}}"
        return self.generate_text(
            audit_prompt,
            "你是高中化学教研专家，审核题目的科学性/准确性/适当性。严格审核，发现任何科学性错误必须指出。",
            temperature=0.3,
        )

    def diagnose_barrier_type(
        self, student_error_history: List[Dict], question_content: str,
        student_answer: str, correct_answer: str,
    ) -> Dict:
        d_prompt = (
            f"学生答题情况:\n题目: {question_content}\n学生答案: {student_answer}\n"
            f"正确答案: {correct_answer}\n历史错误: {json.dumps(student_error_history, ensure_ascii=False)}\n"
            f"返回JSON: {{'barrier_type':'concept/reading/expression',"
            f"'confidence':0.8,'reasoning':'...','suggestion':'...'}}"
        )
        return self.generate_text(
            d_prompt,
            "你是教育心理学专家。分析学生障碍类型: concept(概念理解偏差)/reading(审题信息不全)/"
            "expression(无法规范表述)。",
            temperature=0.3,
        )

    def generate_learning_plan(
        self, student_name: str, barrier_type: str,
        weak_knowledge_points: List[str], recent_performance: Optional[Dict] = None,
    ) -> Dict:
        bd = {
            "concept": "概念理解型-基础概念和原理掌握不扎实",
            "reading": "审题障碍型-读题时容易忽略关键条件或掉入陷阱选项",
            "expression": "表述障碍型-化学用语书写不规范或答题逻辑不清晰",
        }.get(barrier_type, barrier_type)
        perf_info = ""
        if recent_performance and isinstance(recent_performance, dict):
            perf_info = f"\n学生近期数据: 已完成{recent_performance.get('exercises_completed', 0)}道练习。"
        result = self.generate_text(
            f"你是资深高中化学教师，正在为高一学生{student_name}制定个性化学习提升计划。"
            f"学生水平: 高中化学高一阶段，知识点范围为高考大纲必修内容。{perf_info}\n"
            f"主要障碍类型: {bd}\n薄弱知识点: "
            f"{', '.join(weak_knowledge_points) if weak_knowledge_points else '暂无'}\n\n"
            "请按以下Markdown格式输出（严格遵循标题层级，不要用代码块包裹）:\n\n"
            "## 计划标题\n{10字以内标题}\n\n"
            "## 周期\n{如: 2周}\n\n"
            "## 周目标\n- {目标1}\n- {目标2}\n\n"
            "## 每日任务\n- Day 1: {具体可执行的任务}\n- Day 2: {具体可执行的任务}\n...\n\n"
            "## 障碍干预\n- {障碍类型}: {干预策略}\n\n"
            "## 激励建议\n- {建议1}\n- {建议2}\n\n"
            "要求: 1.知识点必须是高中化学内容 2.每日任务具体可执行 3.障碍干预结合化学学科特点 4.激励建议真诚不空洞",
            "你是资深高中化学教师，在制定学习计划时始终围绕高考化学大纲和高中生的实际学习需求。",
            temperature=0.3,
            max_tokens=4096)
        # Parse markdown into structured data
        return self._parse_plan_markdown(result, student_name)

    def revise_parent_report(
        self, student_name: str, previous_report: Dict, feedback: str,
    ) -> Dict:
        """按老师反馈修订家长报告 —— 报告是数据聚合工件：事实字段（练习量、
        正确率、薄弱知识点、障碍分布）不动，LLM 只改写叙述性字段
        （suggestion 建议、可新增 teacher_note 给家长的话）。输出合并后的完整报告。"""
        import json as _json
        report_json = _json.dumps(previous_report, ensure_ascii=False, indent=1)
        result = self.generate_text(
            "你是班主任，正在根据家长的沟通反馈调整学生" + student_name + "的学习报告给家长的建议部分。\n\n"
            "【现有报告】\n" + report_json + "\n\n"
            "【老师的修订意见】\n" + feedback + "\n\n"
            "报告中的统计数据（exercises_completed/week_practice_count/week_accuracy/"
            "weak_knowledge_points/barrier_distribution）是事实数据，保持原样不要改动。"
            "只输出一个 JSON 对象（不要用代码块包裹），包含："
            '"suggestion": 按老师意见改写后的给家长的建议（字符串）；'
            '"teacher_note": 可选，按老师意见补充给家长的一句话（没有就不输出该键）。',
            "你是班主任，在修订家长报告时尊重老师意见、只调整叙述性内容、绝不改动事实数据。",
            temperature=0.3,
            max_tokens=2048)
        content = result.get("content", "")
        if not content:
            return {"success": False, "error": "LLM returned empty content"}
        try:
            patched = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "LLM 返回的报告修订无法解析，请重试"}
        if not isinstance(patched, dict):
            return {"success": False, "error": "LLM 返回的报告修订格式不正确，请重试"}
        merged = dict(previous_report)
        for key in ("suggestion", "teacher_note"):
            if key in patched and isinstance(patched[key], str) and patched[key].strip():
                merged[key] = patched[key].strip()
        return {"success": True, "report": merged}

    def revise_learning_plan(
        self, student_name: str, previous_plan: Dict, feedback: str,
        barrier_type: str = "concept",
    ) -> Dict:
        """按老师反馈修订既有计划——feedback + 旧版本一起进 prompt（有上下文的修订，
        不是无上下文重新生成）。输出格式与 generate_learning_plan 一致。"""
        import json as _json
        bd = {
            "concept": "概念理解型-基础概念和原理掌握不扎实",
            "reading": "审题障碍型-读题时容易忽略关键条件或掉入陷阱选项",
            "expression": "表述障碍型-化学用语书写不规范或答题逻辑不清晰",
        }.get(barrier_type, barrier_type)
        result = self.generate_text(
            f"你是资深高中化学教师，正在为高一学生{student_name}修订一份已有的个性化学习计划。"
            f"学生主要障碍类型: {bd}\n\n"
            f"【现有计划】\n{_json.dumps(previous_plan, ensure_ascii=False, indent=1)}\n\n"
            f"【老师的修订意见】\n{feedback}\n\n"
            "请输出修订后的完整计划（未涉及修改意见的部分保持原样，不要无故改动）。"
            "严格按以下Markdown格式输出（不要用代码块包裹）:\n\n"
            "## 计划标题\n{10字以内标题}\n\n"
            "## 周期\n{如: 2周}\n\n"
            "## 周目标\n- {目标1}\n- {目标2}\n\n"
            "## 每日任务\n- Day 1: {具体可执行的任务}\n- Day 2: {具体可执行的任务}\n...\n\n"
            "## 障碍干预\n- {障碍类型}: {干预策略}\n\n"
            "## 激励建议\n- {建议1}\n- {建议2}\n\n"
            "要求: 1.只按修订意见改动对应部分 2.每日任务具体可执行 3.保持与原计划一致的风格",
            "你是资深高中化学教师，在修订学习计划时尊重老师意见并保持计划的完整性与连贯性。",
            temperature=0.3,
            max_tokens=4096)
        return self._parse_plan_markdown(result, student_name)

    def _parse_plan_markdown(self, result: Dict, student_name: str) -> Dict:
        """解析 LLM 返回的 Markdown 为结构化学习计划"""
        content = result.get("content", "")
        if not content:
            return {"success": False, "error": "LLM returned empty content"}

        import re
        plan = {
            "plan_title": f"{student_name} 个性化学习计划",
            "plan_period": "1-2周",
            "daily_tasks": [],
            "weekly_goals": [],
            "barrier_interventions": {},
            "motivation_tips": [],
        }

        # Extracting sections by ## headers
        sections = re.split(r'\n##\s+', content)
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue

            # Title
            if sec.startswith('计划标题') or sec.startswith('标题'):
                lines = sec.split('\n', 1)
                if len(lines) > 1 and lines[1].strip():
                    plan["plan_title"] = lines[1].strip()[:60]

            # Period
            elif sec.startswith('周期'):
                lines = sec.split('\n', 1)
                if len(lines) > 1 and lines[1].strip():
                    plan["plan_period"] = lines[1].strip()[:20]

            # Weekly goals
            elif sec.startswith('周目标'):
                items = re.findall(r'[-•]\s*(.+)', sec)
                plan["weekly_goals"] = [i.strip() for i in items[:5] if i.strip()]

            # Daily tasks
            elif '任务' in sec[:4] or sec.startswith('每日'):
                items = re.findall(r'[-•]\s*(.+)', sec)
                for i, item in enumerate(items[:14]):
                    item = item.strip()
                    if not item:
                        continue
                    # Extract Day number if present
                    day_match = re.match(r'Day\s*(\d+)[:：\s]*(.*)', item, re.I)
                    if day_match:
                        plan["daily_tasks"].append({"day": int(day_match.group(1)), "task": day_match.group(2).strip()})
                    else:
                        plan["daily_tasks"].append({"day": i + 1, "task": item})

            # Barrier interventions
            elif '障碍' in sec[:4] or sec.startswith('干预'):
                items = re.findall(r'[-•]\s*(.+?)[:：]\s*(.+)', sec)
                bt_map = {"概念理解": "concept", "审题": "reading", "审题仔细": "reading", "审题障碍": "reading",
                          "表述": "expression", "答题表述": "expression", "规范表述": "expression"}
                for k, v in items:
                    bt_key = bt_map.get(k.strip(), k.strip())
                    plan["barrier_interventions"][bt_key] = v.strip()

            # Motivation tips
            elif '激励' in sec[:4] or sec.startswith('建议'):
                items = re.findall(r'[-•]\s*(.+)', sec)
                plan["motivation_tips"] = [i.strip() for i in items[:5] if i.strip()]

        # If no tasks parsed, keep raw content for rendering
        if not plan["daily_tasks"] and not plan["weekly_goals"]:
            plan["raw_text"] = content

        result["content"] = json.dumps(plan, ensure_ascii=False)
        return result

    def analyze_paper_with_vision(self, image_data: str, paper_type: str = "mixed") -> Dict:
        prompt = self._get_vision_prompt(paper_type)
        mime = self._detect_image_mime(image_data)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
                {"type": "text", "text": prompt},
            ],
        }]

        # MiMo first (native vision)
        if self.mimo_key:
            try:
                r = self._call_with_retry(
                    self.MIMO_URL, self.mimo_key,
                    {"model": self.MIMO_MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 2000},
                    timeout=120.0, max_retries=2,
                )
                if r.get("success"):
                    return self._parse_vision_response(r.get("content", ""))
            except Exception:
                pass

        # ZhiPu fallback
        zk = os.getenv("ZHIPU_API_KEY", "") or settings.ZHIPU_API_KEY
        if zk:
            try:
                r = self._call_with_retry(
                    self.ZHIPU_VISION_URL, zk,
                    {"model": "glm-4v", "messages": messages, "temperature": 0.1, "max_tokens": 2000},
                    timeout=120.0, max_retries=2,
                )
                if r.get("success"):
                    return self._parse_vision_response(r.get("content", ""))
                return {"success": False, "error": r.get("error", "Vision API failed"), "message": "多模态分析失败"}
            except Exception as e:
                return {"success": False, "error": str(e), "message": "多模态分析异常"}

        return {"success": False, "error": "无可用视觉模型", "message": "请配置 MiMo 或 智谱 API Key"}

    def _get_vision_prompt(self, pt: str) -> str:
        return {
            "answer_sheet": "分析答题卡图片，识别学号、姓名、每题答案(A/B/C/D)。返回JSON: "
                            '{"student_id":"","student_name":"",'
                            '"questions":[{"number":"1","student_answer":"A"}],'
                            '"message":""}',
            "printed": "分析印刷试卷图片，识别标题、所有题目内容和选项、标准答案。返回JSON: "
                       '{"title":"",'
                       '"questions":[{"number":"1","content":"",'
                       '"options":["A","B"],'
                       '"correct_answer":"A"}]}',
            "handwritten": "分析手写试卷图片，识别姓名、手写题目内容、作答内容。返回JSON: "
                           '{"student_name":"",'
                           '"questions":[{"number":"1","content":"",'
                           '"student_answer":""}]}',
            "mixed": "分析混合试卷图片(印刷题目+手写作答)，识别学号、姓名、印刷题目、手写作答。返回JSON: "
                     '{"student_id":"","student_name":"",'
                     '"questions":[{"number":"1","content":"",'
                     '"options":[],'
                     '"student_answer":""}]}',
        }.get(pt, "分析试卷图片，提取所有题目信息和作答内容。")

    def _detect_image_mime(self, data: str) -> str:
        try:
            raw = base64.b64decode(data[:24])
            if raw[:4] == b'\x89PNG':
                return "image/png"
            if raw[:3] == b'\xff\xd8\xff':
                return "image/jpeg"
        except Exception:
            pass
        return "image/png"

    def _parse_vision_response(self, content: str) -> Dict:
        try:
            for d in ("```json", "```"):
                if d in content:
                    parts = content.split(d)
                    content = parts[1].split("```")[0] if len(parts) > 1 else content
                    break
            data = json.loads(content.strip())
            return {
                "success": True,
                "student_id": data.get("student_id", ""),
                "student_name": data.get("student_name", ""),
                "questions": data.get("questions", []),
                "raw_text": content,
                "message": data.get("message", "识别完成"),
            }
        except json.JSONDecodeError:
            return {
                "success": True, "student_id": "", "student_name": "",
                "questions": [], "raw_text": content,
                "message": "识别完成，请查看原始文本",
            }


class ChatGLMService:
    def __init__(self):
        self.api_url = os.getenv("CHATGLM_API_URL", "http://localhost:8001")
        self.enabled = False
    def generate_text(self, prompt: str, **kw) -> Dict:
        if not self.enabled:
            return {"success": False, "error": "ChatGLM not enabled"}
        try:
            import httpx as hx
            r = hx.post(self.api_url, json={"prompt": prompt, **kw}, timeout=30.0)
            if r.status_code == 200:
                return {"success": True, "content": r.json().get("response", "")}
            return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


llm_service = LLMService()
chatglm_service = ChatGLMService()
