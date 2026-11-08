"""Exam bank tools — search, generation, save, and panel management."""

import json
import re
import os as _os

from dotenv import load_dotenv
load_dotenv()


# ═══════════════════════════════════════════════════════════════════════
# search_exam_bank
# ═══════════════════════════════════════════════════════════════════════

async def search_exam_bank(
    keyword: str = "",
    year: int = 0,
    difficulty: str = "",
    limit: int = 5,
) -> str:
    """考试工作台 — 搜索历年高考化学真题（内部自动补齐：关键词→向量→联网）

    何时用：用户说"搜索真题""找高考题"等任何真题搜索意图时使用
    会发生什么：先关键词匹配本地题库，不够时向量召回补充，还不够时联网搜索补齐
    返回：已整理好的真题列表，已在返回文本中逐题列出全部题目，直接输出即可
    禁止：调完本工具后不要再调 web_search"""
    from app.services.exam_bank import exam_bank_service

    results = exam_bank_service.search_questions(
        knowledge_point=keyword or None,
        keyword=keyword or None,
        year=year if year else None,
        difficulty=difficulty or None,
        limit=limit,
        use_vector=True if keyword else False,
    )
    # AI 生成题库已同步进历史真题库（source="AI生成"），由下方 🤖 节统一渲染，避免重复
    results = [q for q in results if getattr(q, "source", "") != "AI生成"]

    lines = []
    images = []

    if results:
        lines.append(f"## 🏫 本地题库（{len(results)} 道）\n")
        for i, q in enumerate(results, 1):
            # Only show year in source label if not already obvious from search context
            src_label = q.source or ""
            if q.year and str(q.year) not in src_label:
                src_label = str(q.year) + " " + src_label
            lines.append(f"**第{i}题**  🏫 本地题库 · {src_label} 第{q.question_number}题")
            lines.append(f"知识点：{', '.join(q.knowledge_points)}  |  难度：{q.difficulty}")
            lines.append(f"> {q.content}")
            if q.options:
                lines.append(f"选项：{'；'.join(q.options)}")
            lines.append(f"答案：**{q.answer}**")
            if q.analysis:
                lines.append(f"解析：{q.analysis[:200]}")
            if q.page_image:
                import urllib.parse
                fig_url = "/static/figures/" + urllib.parse.quote(f"{q.region}/{q.year}/figures/{q.page_image}")
                images.append({"q_index": i - 1, "title": f"第{i}题 · 题目附图", "urls": [fig_url]})
            lines.append("")

    # AI 生成题库联合检索（spec: 搜索联合返回历史真题与 AI 题库）
    ai_lines = []
    from app.models.database import get_db
    from app.services.question_bank import question_bank_service

    db = next(get_db())
    try:
        ai_hits = question_bank_service.search_ai_generated(db, keyword=keyword or None, limit=limit)
    finally:
        db.close()

    if ai_hits:
        ai_lines.append(f"## 🤖 AI生成题库（{len(ai_hits)} 道）\n")
        for i, q in enumerate(ai_hits, 1):
            kps = ", ".join(q.get("knowledge_points") or [])
            ai_lines.append(f"**第{i}题**  🤖 AI生成题库")
            ai_lines.append(f"知识点：{kps}  |  难度：{q.get('difficulty') or 'medium'}")
            ai_lines.append(f"> {q['content']}")
            if q.get("options"):
                ai_lines.append(f"选项：{'；'.join(q['options'])}")
            ai_lines.append(f"答案：**{q.get('answer') or ''}**")
            if q.get("analysis"):
                ai_lines.append(f"解析：{q['analysis'][:200]}")
            ai_lines.append("")
        lines.append("---\n")
        lines.extend(ai_lines)

    kw_count = getattr(results, 'keyword_count', len(results))
    web_lines = []
    if kw_count < 3 and keyword:
        try:
            web_result_str = await _do_web_search(keyword)
            web_data = json.loads(web_result_str)
            web_text = web_data.get("result", "")
            web_sources = web_data.get("sources", [])
            if web_text and len(web_text) > 50:
                web_lines.append(f"\n## 🌐 网络补充（本地仅 {len(results)} 道，AI搜索补充，仅供教学参考）\n")
                web_lines.append(web_text[:2000])
                if web_sources:
                    web_lines.append("\n**📎 参考来源:**")
                    for si, src in enumerate(web_sources[:5], 1):
                        title = src.get("title", f"来源{si}")
                        url = src.get("url", "")
                        if url:
                            web_lines.append(f"  {si}. [{title}]({url})")
                        else:
                            web_lines.append(f"  {si}. {title}")
                web_lines.append("\n> ⚠️ 网络搜索结果不含图片，点击上方链接查看原网页中的配图。")
        except Exception:
            pass

    if web_lines:
        lines.append("---\n")
        lines.extend(web_lines)

    if not results and not ai_lines and not web_lines:
        lines.append("未找到相关真题，建议尝试更简短的关键词")

    result_text = "\n".join(lines)
    result_text += ("\n\n> 以上是全部搜索结果。已在上面逐题列出，直接输出即可，"
                    "不要省略任何一题，不要额外添加知识点总结。")

    if images:
        return json.dumps({"text": result_text, "images": images}, ensure_ascii=False)
    return result_text


async def _anysearch_search(query: str, max_results: int = 5) -> tuple[str, list]:
    """AnySearch 独立搜索 API（anysearch.com）——web_search 主通道（2026-08 集成）。

    独立搜索引擎（非大模型内置搜索）：返回结构化原始结果（标题/摘要/URL），
    来源可验证——高考真题等场景必须能追溯到具体网页。支持 zone=cn 中文分区。
    key 从环境变量 ANYSEARCH_API_KEY 读取（用户可在 anysearch.com 控制台申请，
    写入 chemai-backend/.env 或系统环境变量）。失败/无 key 时返回 ("", [])，
    由调用方回退到 mimo 内置搜索 / Bing 兜底，绝不抛异常。
    """
    import httpx as _httpx
    api_key = _os.getenv("ANYSEARCH_API_KEY", "")
    if not api_key:
        return "", []
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anysearch.com/v1/search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "query": query,
                    "max_results": max_results,
                    "zone": "cn",
                    "language": "zh",
                },
            )
        if resp.status_code != 200:
            return "", []
        data = resp.json()
        results = ((data.get("data") or {}).get("results")) or []
        parts = []
        sources = []
        for i, r in enumerate(results[:max_results], 1):
            title = str(r.get("title", "") or "")
            url = str(r.get("url", "") or "")
            snippet = str(r.get("snippet", "") or "")
            if url:
                sources.append({"title": title or f"来源{i}", "url": url})
            if title or snippet:
                parts.append(f"{i}. {title}\n{snippet}".strip())
        return "\n\n".join(parts), sources
    except Exception:
        return "", []


async def _do_web_search(query: str) -> str:
    """Internal web search helper — AnySearch 优先（2026-08 集成），MiMo 兜底。
    返回 text + source URLs（供 search_exam_bank 网络补充展示）。"""
    import httpx as _httpx

    # 主通道：AnySearch 独立搜索 API——结构化来源可验证（真题场景关键）
    anysearch_text, sources = await _anysearch_search(query, max_results=5)
    if anysearch_text and len(anysearch_text) > 50:
        return json.dumps({"result": anysearch_text, "sources": sources}, ensure_ascii=False)

    # 兜底：小米 mimo 内置搜索（key 失效/无结果时回退，原行为）
    api_key = _os.getenv("XIAOMI_API_KEY", "")
    if not api_key:
        return json.dumps({"result": "", "sources": []})

    try:
        async with _httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.xiaomimimo.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "mimo-v2.5",
                    "messages": [{"role": "user", "content": (
                        f"搜索关于「{query}」的高考化学真题。要求："
                        "1. 逐题列出，每道题必须包含：年份、省份/卷别、完整的题目内容、"
                        "选项（如有）、标准答案、简要解析。"
                        "2. 如果搜不到原题，请明确说明'未搜到原题'，然后列出该知识点的典型考法和例题。"
                        "3. 禁止编造不存在的题目，你输出的每道题都应该是真实存在的高考真题。"
                        "4. 每条结果末尾用 [来源: 网页标题](URL) 格式附上来源链接。"
                    )}],
                    "enable_search": True, "max_tokens": 2048, "temperature": 0.1,
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            result_text = data["choices"][0]["message"]["content"]
            # Try to extract search result URLs from MiMo response metadata
            sources = []
            try:
                sr = data["choices"][0].get("message", {}).get("search_results", [])
                if not sr:
                    sr = data.get("search_info", {}).get("search_results", [])
                for s in sr[:5]:
                    if isinstance(s, dict):
                        sources.append({"title": s.get("title", ""), "url": s.get("url", s.get("link", ""))})
            except Exception:
                pass
            # Fallback: extract markdown links [text](url) from result
            if not sources:
                link_matches = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', result_text)
                sources = [{"title": t, "url": u} for t, u in link_matches[:5]]
            return json.dumps({"result": result_text, "sources": sources}, ensure_ascii=False)
    except Exception:
        pass
    return json.dumps({"result": "", "sources": []})


# ═══════════════════════════════════════════════════════════════════════
# web_search
# ═══════════════════════════════════════════════════════════════════════

async def web_search(query: str = "") -> str:
    """联网搜索 — 查询最新化学信息、高考动态、教学资源。也是真题搜索的兜底方案。

    何时用：
    - search_exam_bank 返回 NOT_FOUND → 调本工具搜索网上真题弥补
    - 用户明确要求"上网搜"、查询最新政策/新闻/大纲
    会发生什么：返回联网搜索结果摘要 + 来源链接
    严格禁止：
    - 禁止在 search_exam_bank 返回 FOUND 后调用本工具
    - 禁止跳过 search_exam_bank 直接调本工具搜真题"""
    import httpx as _httpx

    search_text = ""
    sources = []

    # 主通道：AnySearch 独立搜索 API（2026-08 集成）——结构化来源可验证，
    # 真题/资料场景优于模型内置搜索；无 key 或失败时静默回退
    search_text, sources = await _anysearch_search(query)

    miimo_key = _os.getenv("XIAOMI_API_KEY", "")
    if (not search_text or len(search_text) < 50) and miimo_key:
        try:
            async with _httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.xiaomimimo.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {miimo_key}", "Content-Type": "application/json"},
                    json={
                        "model": "mimo-v2.5",
                        "messages": [{"role": "user", "content": query}],
                        "enable_search": True, "max_tokens": 2048, "temperature": 0.3,
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                search_text = data["choices"][0]["message"]["content"]
                # Extract search result URLs from MiMo metadata
                try:
                    sr = data["choices"][0].get("message", {}).get("search_results", [])
                    if not sr:
                        sr = data.get("search_info", {}).get("search_results", [])
                    for s in sr[:5]:
                        if isinstance(s, dict):
                            sources.append({"title": s.get("title", ""), "url": s.get("url", s.get("link", ""))})
                except Exception:
                    pass
                # Fallback: extract markdown links from result text
                if not sources:
                    link_matches = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', search_text)
                    sources = [{"title": t, "url": u} for t, u in link_matches[:5]]
        except Exception as e:
            print(f"MiMo search failed: {e}")

    if not search_text or len(search_text) < 50:
        import urllib.parse as _urlparse
        try:
            async with _httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://www.bing.com/search?q={_urlparse.quote(query)}",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
            if resp.status_code == 200:
                import re as _re
                snippets = _re.findall(r'<li class="b_algo"[^>]*>.*?</li>', resp.text, _re.DOTALL)
                if not snippets:
                    snippets = _re.findall(r'<p[^>]*>(.*?)</p>', resp.text, _re.DOTALL)
                parts = []
                for s in snippets[:5]:
                    text = _re.sub(r'<[^>]+>', '', s).strip()[:200]
                    # Extract URL from <a href="..."> in snippet
                    url_m = _re.search(r'<a[^>]+href="(https?://[^"]+)"', s)
                    if url_m and not sources:
                        sources.append({"title": text[:50], "url": url_m.group(1)})
                    if len(text) > 20:
                        parts.append(text)
                search_text = "\n\n".join(parts)
        except Exception:
            pass

    if not search_text or len(search_text) < 20:
        return json.dumps({"error": "未获取到搜索结果，请稍后重试"}, ensure_ascii=False)

    # Build sources footer
    source_text = ""
    if sources:
        source_lines = ["\n---\n**📎 参考来源:**"]
        for i, s in enumerate(sources[:5], 1):
            title = s.get("title", f"来源{i}")
            url = s.get("url", "")
            if url:
                source_lines.append(f"  {i}. [{title}]({url})")
            else:
                source_lines.append(f"  {i}. {title}")
        source_text = "\n".join(source_lines)

    ds_key = _os.getenv("DEEPSEEK_API_KEY", "")
    if ds_key and len(search_text) > 100:
        try:
            async with _httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {ds_key}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "用简洁中文总结以下搜索结果，列出关键信息。不超过400字。"},
                            {"role": "user", "content": f"搜索词: {query}\n\n搜索结果:\n{search_text[:3000]}"},
                        ],
                        "max_tokens": 1024, "temperature": 0.3,
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                result = data["choices"][0]["message"]["content"]
                return json.dumps({"query": query, "result": result + source_text}, ensure_ascii=False)
        except Exception:
            pass

    return json.dumps({"query": query, "result": search_text[:2000] + source_text}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# show_exam_workbench
# ═══════════════════════════════════════════════════════════════════════

async def show_exam_workbench(
    knowledge_points: str = "",
    difficulty: str = "medium",
    question_types: str = "",
    variant_source: str = "",
    set_name: str = "",
) -> str:
    """考试工作台 — 在聊天中打开内联出题面板

    何时用：用户说"出题""出卷""生成题目""组卷"等任何出题意图时，立即调用！
    如果用户已给出知识点/难度/题型，打开面板并预填；用户明确说"用工作台/面板"时也直接打开。
    信息不全且未明确要求面板时，按 persona 出题交互契约先追问（题型/难度/知识点）。
    不要先搜真题、不要确认难度等其他参数。
    会发生什么：在聊天界面中渲染考试工作台面板，用户可直接在面板中配置参数、出题、预览、编辑、保存
    下一步：用户在面板中操作完成后，Agent 收到总结消息。question_types 格式如 "single_choice:5,fill_blank:2"
    NOT for 先搜真题再问要不要出题 — 直接调此工具，不要调 search_exam_bank
    NOT for 保存/归档已生成的题目 — 用户要保存已完成题目时调 save_to_bank，不要调此工具"""
    import logging
    _log = logging.getLogger(__name__)

    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]

    types = []
    if question_types:
        for item in question_types.split(","):
            parts = item.strip().split(":")
            if len(parts) == 2:
                val, qty = parts[0].strip(), int(parts[1].strip())
                types.append({"val": val, "active": True, "qty": qty})

    if not types:
        types = [{"val": "single_choice", "active": True, "qty": 3}]

    _data = {
        "knowledge_points": kps,
        "difficulty": difficulty,
        "types": types,
    }
    if variant_source:
        _data["variant_source"] = variant_source
    if set_name:
        _data["set_name"] = set_name

    _log.info(f"[show_exam_workbench] kps={kps}, diff={difficulty}, types={types}")

    return json.dumps({
        "message": f"参数已确认：{knowledge_points}，{difficulty}难度。请在下方面板中生成题目。",
        "_component": {
            "component": "exam-workbench",
            "params": _data,
        },
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# save_to_bank
# ═══════════════════════════════════════════════════════════════════════

async def save_to_bank(
    questions: str = "",
    knowledge_points: str = "",
    set_name: str = "",
    description: str = "",
) -> str:
    """考试工作台 — 将生成的题目保存到题库

    何时用：用户在考试工作台面板中出题完成后保存
    会发生什么：创建题库文件夹（自动命名），将题目存入数据库，可在考试工作台中管理和复用
    下一步：保存后告知用户文件夹名，引导用户去考试工作台查看 → 页面跳转到 exam-v2 题库 tab
    questions 参数格式：JSON 字符串 {"questions": [{"content": "题干", "options": ["A","B","C","D"],
    "answer": "B", "explanation": "解析", "difficulty": "easy|medium|hard", "knowledge_points": ["知识点"]}]}
    NOT for 出题 — 先调 show_exam_workbench 让用户出题，出完再保存"""
    from datetime import datetime
    from app.models.database import get_db
    from app.services.question_bank import question_bank_service

    try:
        if isinstance(questions, str):
            data = json.loads(questions)
        else:
            data = questions
        q_list = data.get("questions", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "题目数据格式无效", "_route": {"navigate": False}}, ensure_ascii=False)

    if not q_list:
        return json.dumps({"error": "没有可保存的题目", "_route": {"navigate": False}}, ensure_ascii=False)

    if not set_name:
        kps = knowledge_points or "综合"
        ts = datetime.now().strftime("%m%d%H%M")
        set_name = f"AI生成-{kps}-{ts}"

    db = next(get_db())
    try:
        description = description or f"Agent 自动生成: {knowledge_points}"
        created = question_bank_service.create_set(
            db, name=set_name, region="AI生成", source="agent",
            description=description,
        )
        set_id = created["set_id"]

        saved = question_bank_service.add_questions(
            db, set_id, q_list,
            set_name=set_name, description=description,
            knowledge_points=knowledge_points,
        )
        count = saved["count"]

        return json.dumps({
            "saved": True, "set_id": set_id, "set_name": set_name,
            "count": count,
            "message": f"已保存 {count} 道题目到题库「{set_name}」",
            "_route": {
                "navigate": True, "page": "exam-v2",
                "populate": {"target": "exam-set", "data": {"set_id": set_id, "set_name": set_name}},
                "actions": [{"action": "openTab", "payload": "bank"}],
            },
        }, ensure_ascii=False)

    except Exception as e:
        db.rollback()
        return json.dumps({"error": f"保存失败: {str(e)}", "_route": {"navigate": False}}, ensure_ascii=False)
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════
# list_banks / delete_bank
# ═══════════════════════════════════════════════════════════════════════

async def list_banks() -> str:
    """题库管理 — 列出所有题库文件夹

    何时用：用户想查看有哪些题库文件夹，或需要知道题库名称和题目数量
    会发生什么：返回题库列表（set_id、名称、题目数量）
    下一步：用户可能要求删除某个题库（delete_bank）或查看某个题库的内容
    NOT for 搜索题库里面的题目内容 — 用 search_exam_bank"""
    from app.models.database import get_db
    from app.services.question_bank import question_bank_service

    db = next(get_db())
    try:
        data = question_bank_service.list_sets(db, page=1, page_size=1000)
        result = [{
            "set_id": s["set_id"], "name": s["name"],
            "question_count": s["question_count"] or 0,
            "created_at": s["created_at"],
        } for s in data["exam_sets"]]
        return json.dumps({"banks": result, "total": len(result)}, ensure_ascii=False)
    finally:
        db.close()


async def delete_bank(set_id: str = "") -> str:
    """题库管理 — 删除题库文件夹及其中所有题目

    何时用：用户明确要求删除某个题库文件夹
    会发生什么：删除题库文件夹和其中的题目关联（题目本身保留）
    下一步：告知用户删除结果
    ⚠ 此操作不可逆，需要先调 request_approval 确认"""
    from app.models.database import get_db
    from app.services.question_bank import question_bank_service

    if not set_id:
        return json.dumps({"error": "请指定要删除的题库 set_id"}, ensure_ascii=False)

    db = next(get_db())
    try:
        result = question_bank_service.delete_set(db, set_id)

        if not result.get("success"):
            if result.get("reason") == "is_system":
                return json.dumps({"error": "系统预设题库不能删除"}, ensure_ascii=False)
            return json.dumps({"error": f"题库 {set_id} 不存在"}, ensure_ascii=False)

        name = result["name"]
        count = result["question_count"] or 0
        return json.dumps({
            "deleted": True, "set_id": set_id, "name": name,
            "question_count": count,
            "message": f"已删除题库「{name}」（含 {count} 道题目关联）",
        }, ensure_ascii=False)
    except Exception as e:
        db.rollback()
        return json.dumps({"error": f"删除失败: {str(e)}"}, ensure_ascii=False)
    finally:
        db.close()
