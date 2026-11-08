"""
Filesystem tools — read / write / edit / find / grep, confined to a workspace.

Workspace（2026-08 设计定稿，参考 DSH/WorkBuddy）：
  - 工作区 = 老师的主权文件夹，不是程序目录。默认 ~/ChemAI-Workspace，
    可经 set_workspace_root 按对话覆盖（老师自定义路径），env CHEMAI_WORKSPACE
    优先（评估环境用）。
  - 首次创建自动生成骨架：README.md + 学生资料/教案备课/试卷真题/AI生成/临时。
  - write 到 AI生成/ 自动按日期归档（AI生成/YYYY-MM-DD/…）。

访问控制（前端开关 + 按次审批，DSH danger-full-access 模式）：
  - off       — 全部文件工具拒绝
  - workspace — 仅工作区（默认）：区内直接读写；区外每次按次审批
  - full      — 完全访问（DSH danger-full-access 等价档）：全路径直接放行，
    区外不再弹审批卡；破坏性工具（assign/delete）仍走 request_approval
  敏感文件（.env/密钥/证书）在任何档位下永远拒绝。
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

WORKSPACE_ENV = "CHEMAI_WORKSPACE"
DEFAULT_WORKSPACE = "~/ChemAI-Workspace"

MAX_FIND_RESULTS = 200
MAX_GREP_MATCHES = 100

_ACCESS_LEVEL = "workspace"   # off | workspace | full
_elevate_once = False         # 按次审批：放行一次工作区外访问
# （ADR-0013/#12：学习计划与家长报告的发送门已由草稿数据状态强制，
#   不再消费提权布尔；现役消费方：工作区外文件访问、布置练习等）
_ws_override = None           # 老师自定义工作区路径（按对话下发）

_SKELETON_DIRS = ["学生资料", "教案备课", "试卷真题", "AI生成", "临时"]
_SKELETON_README = (
    "# ChemAI 教师工作区\n\n"
    "这是 AI 助教的文件工作区（老师的本地文件夹）。\n\n"
    "目录约定：\n"
    "- 学生资料/：上传的试卷、答题卡、名单等学生材料\n"
    "- 教案备课/：教案、课件与备课笔记\n"
    "- 试卷真题/：真题与试卷存档\n"
    "- AI生成/：AI 生成的试卷、诊断报告、学习计划（自动按日期归档）\n"
    "- 临时/：中转与草稿文件\n\n"
    "AI 使用规则：读写默认锚定本工作区；访问工作区外需老师批准；"
    "生成物请写入 AI生成/ 对应日期目录。\n"
)

_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def set_file_access_level(level: str) -> str:
    """Set the per-conversation file access level. Unknown values fall back
    to workspace (default-deny). 对话边界：清除残留的一次性放行与 bash 会话 cwd。
    档位：off 关闭 | workspace 工作区（默认，区外按次审批）| full 完全访问
    （区外直接放行，敏感文件仍拒绝；2026-08 对齐 DSH danger-full-access）。"""
    global _ACCESS_LEVEL, _elevate_once, _session_cwd_rel
    _ACCESS_LEVEL = level if level in ("off", "workspace", "full") else "workspace"
    _elevate_once = False
    _session_cwd_rel = ""
    return _ACCESS_LEVEL


# bash 会话工作目录（pi agent session-cwd 同款：cd 在对话内持久，锚定工作区内）
_session_cwd_rel = ""


def set_session_cwd(rel: str):
    """设置 bash 会话 cwd（相对工作区）。越界或不存在返回 None，空串回到工作区根。"""
    global _session_cwd_rel
    if not rel:
        _session_cwd_rel = ""
        return ""
    root = workspace_root()
    target = (root / rel).resolve()
    if not _is_inside(target, root) or not target.is_dir():
        return None
    _session_cwd_rel = target.relative_to(root).as_posix()
    return _session_cwd_rel


def session_cwd_rel() -> str:
    return _session_cwd_rel


def bash_cwd() -> Path:
    """bash 执行的当前目录（工作区内会话 cwd）。"""
    root = workspace_root()
    return (root / _session_cwd_rel) if _session_cwd_rel else root


def file_access_level() -> str:
    return _ACCESS_LEVEL


def set_elevate_once():
    """放行下一次工作区外访问（按次审批，批准后由 guard 层调用）。"""
    global _elevate_once
    _elevate_once = True


def _consume_elevation() -> bool:
    global _elevate_once
    granted = _elevate_once
    _elevate_once = False
    return granted


def set_workspace_root(path: str):
    """Override the workspace root for the current conversation (teacher-chosen
    folder). Empty string resets to the default."""
    global _ws_override
    if not path:
        _ws_override = None
        return None
    _ws_override = str(Path(path).expanduser())
    return _ws_override


def _ensure_skeleton(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    if not (root / "README.md").exists():
        for d in _SKELETON_DIRS:
            (root / d).mkdir(exist_ok=True)
        (root / "README.md").write_text(_SKELETON_README, encoding="utf-8")


def workspace_root() -> Path:
    if _ws_override:
        root = Path(_ws_override).resolve()
    else:
        default = os.environ.get(WORKSPACE_ENV) or DEFAULT_WORKSPACE
        root = Path(default).expanduser().resolve()
    _ensure_skeleton(root)
    return root


def _is_inside(resolved: Path, root: Path) -> bool:
    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False


def _is_sensitive(name: str) -> bool:
    low = name.lower()
    return (
        low.endswith((".env", ".pem", ".key", ".p12", ".pfx"))
        or "secret" in low
        or "credentials" in low
        or low.startswith(("id_rsa", ".htpasswd"))
    )


def _approval_needed(path_str: str) -> dict:
    return {
        "approval_needed": True,
        "message": f"工作区外访问需要批准: {path_str}",
        "target": path_str,
    }


def _resolve(path_str: str):
    """Return (resolved_path, None) or (None, error). error 为 dict 时表示
    approval_needed（工作区外访问，待批准重放）。

    elevation（按次放行）只在真正越界时消费——区内路径不浪费放行额度。"""
    if _ACCESS_LEVEL == "off":
        return None, "文件访问已关闭（当前对话设置为「关闭」档）"
    if not path_str:
        return None, "请指定路径"
    p = Path(path_str)
    root = workspace_root()
    if p.is_absolute():
        resolved = p.resolve()
        outside = not _is_inside(resolved, root)
    else:
        resolved = (root / p).resolve()
        outside = not _is_inside(resolved, root)
    if outside:
        # full 档（完全访问）：区外直接放行，不再按次审批（敏感文件仍拒绝）
        if _ACCESS_LEVEL != "full":
            elevated = _consume_elevation()
            if not elevated:
                return None, _approval_needed(path_str)
    if _is_sensitive(resolved.name):
        return None, f"敏感文件被拒绝: {resolved.name}"
    return resolved, None


def _error_json(err):
    if isinstance(err, dict) and err.get("approval_needed"):
        return json.dumps({
            "approval_needed": True,
            "message": err["message"],
            "target": err["target"],
        }, ensure_ascii=False)
    return json.dumps({"error": err}, ensure_ascii=False)


def _rel_display(resolved: Path):
    """Relative path inside workspace (posix separators), absolute otherwise."""
    try:
        return resolved.relative_to(workspace_root()).as_posix()
    except ValueError:
        return str(resolved)


def _read_text(path: Path):
    """Return (text, None) or (None, error). utf-8 first, gbk fallback,
    binary refused."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, f"文件不存在: {path.name}"
    if b"\x00" in raw[:8192]:
        return None, f"二进制文件，拒绝读取: {path.name}"
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return None, f"无法解码（不支持编码）: {path.name}"


async def read(path: str = "", offset: int = 0, limit: int = 0) -> str:
    """读取文件 — 读取文本文件（utf-8/gbk），支持行分页。

    何时用：需要读取文件内容时——工作区内直接读；老师要求读工作区外的文件
    （桌面/其他目录/绝对路径）时也直接调用本工具尝试（路径不确定也直接尝试，
    不要先问老师要路径、不要未尝试就声称无法访问）。
    会发生什么：工作区外路径会返回「工作区外访问需要批准」——此时立即调
    request_approval 说明要访问的路径，老师批准后重试本工具即可读取（按次审批）。
    offset/limit 为 1-indexed 行号分页：offset 起始行（0=从头），limit 最大行数（0=全部）"""
    resolved, err = _resolve(path)
    if err:
        return _error_json(err)
    text, err = _read_text(resolved)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)
    lines = text.splitlines()
    total_lines = len(lines)
    start = max(0, offset - 1) if offset > 0 else 0
    end = (start + limit) if limit > 0 else total_lines
    shown = lines[start:end]
    return json.dumps({
        "content": "\n".join(shown),
        "path": _rel_display(resolved),
        "chars": len("\n".join(shown)),
        "line_offset": offset,
        "total_lines": total_lines,
        "truncated": end < total_lines,
    }, ensure_ascii=False)


async def write(path: str = "", content: str = "") -> str:
    """写入文件 — 创建/覆盖文本文件（自动建目录）。

    何时用：把生成的内容（试卷、报告、笔记）保存为文件；老师指定工作区外路径时
    也直接尝试本工具（会返回「工作区外访问需要批准」→ 调 request_approval → 批准后重试）
    会发生什么：写入 AI生成/ 下的文件自动按日期归档；工作区外需老师按次批准"""
    resolved, err = _resolve(path)
    if err:
        return _error_json(err)
    # AI生成/ 自动按日期归档（Spec: 骨架 + 按日期归档）
    root = workspace_root()
    if _is_inside(resolved, root):
        rel = resolved.relative_to(root)
        if rel.parts and rel.parts[0] == "AI生成" and (
                len(rel.parts) == 1 or not _DATE_DIR.match(rel.parts[1])):
            resolved = root / "AI生成" / datetime.now().strftime("%Y-%m-%d") / rel.name
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return json.dumps({"written": True, "path": _rel_display(resolved),
                       "chars": len(content)}, ensure_ascii=False)


async def edit(path: str = "", old_string: str = "", new_string: str = "",
               edits: str = "") -> str:
    """精确替换 — 单处（old_string/new_string）或多处（edits JSON 数组）替换。

    何时用：需要修改工作区文件的指定片段
    会发生什么（pi agent 同款语义）：每个 old_text 必须在原文件中恰好匹配 1 次，
    同一调用内的多个替换互不重叠、全部针对原文件匹配；任一条不符则报错且文件保持不变
    edits 格式：[{"old_text": "...", "new_text": "..."}]"""
    resolved, err = _resolve(path)
    if err:
        return _error_json(err)
    text, err = _read_text(resolved)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)

    # ── 多替换（edits）优先 ──
    if edits:
        try:
            edit_list = json.loads(edits)
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "edits 必须是 JSON 数组"}, ensure_ascii=False)
        if not isinstance(edit_list, list) or not edit_list:
            return json.dumps({"error": "edits 不能为空"}, ensure_ascii=False)
        pairs = []
        for e in edit_list:
            if not isinstance(e, dict):
                return json.dumps({"error": "edits 元素必须是 {old_text, new_text}"}, ensure_ascii=False)
            old_t = str(e.get("old_text", ""))
            new_t = str(e.get("new_text", ""))
            if not old_t:
                return json.dumps({"error": "edits 元素缺少 old_text"}, ensure_ascii=False)
            cnt = text.count(old_t)
            if cnt == 0:
                return json.dumps({"error": f"未找到目标片段: {old_t[:40]}（文件保持不变）"},
                                  ensure_ascii=False)
            if cnt > 1:
                return json.dumps({
                    "error": f"目标片段匹配到 {cnt} 处，请提供唯一片段: {old_t[:40]}（文件保持不变）",
                }, ensure_ascii=False)
            pairs.append((old_t, new_t))
        # 互不重叠检查（针对原文件区间）
        ranges = []
        for old_t, _ in pairs:
            start = text.find(old_t)
            ranges.append((start, start + len(old_t)))
        for i in range(len(ranges)):
            for j in range(i + 1, len(ranges)):
                if ranges[i][0] < ranges[j][1] and ranges[j][0] < ranges[i][1]:
                    return json.dumps({"error": "edits 存在重叠区间，请合并为一条（文件保持不变）"}, ensure_ascii=False)
        new_text = text
        for old_t, new_t in pairs:
            new_text = new_text.replace(old_t, new_t, 1)
        resolved.write_text(new_text, encoding="utf-8")
        return json.dumps({"edited": True, "path": _rel_display(resolved),
                           "replacements": len(pairs)}, ensure_ascii=False)

    # ── 单替换（向后兼容） ──
    if not old_string:
        return json.dumps({"error": "请提供要替换的原文片段 old_string"}, ensure_ascii=False)

    count = text.count(old_string)
    if count == 0:
        context = text[:100].replace("\n", " ")
        return json.dumps({
            "error": f"未找到目标片段（匹配 0 处），文件保持不变。文件开头上下文: {context}…",
        }, ensure_ascii=False)
    if count > 1:
        return json.dumps({
            "error": f"目标片段匹配到 {count} 处，请提供更精确的唯一片段；文件保持不变",
        }, ensure_ascii=False)

    new_text = text.replace(old_string, new_string, 1)
    resolved.write_text(new_text, encoding="utf-8")
    return json.dumps({"edited": True, "path": _rel_display(resolved),
                       "replaced_chars": len(old_string)}, ensure_ascii=False)


async def find(pattern: str = "*") -> str:
    """查找文件 — 在工作区内按名称模式（支持 * 通配符）查找文件。

    何时用：需要定位工作区里的文件
    会发生什么：返回相对路径列表，最多 200 条"""
    import fnmatch
    if _ACCESS_LEVEL == "off":
        return json.dumps({"error": "文件访问已关闭（当前对话设置为「关闭」档）"}, ensure_ascii=False)
    root = workspace_root()
    matches = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        rel_str = rel.as_posix()
        if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(p.name, pattern):
            matches.append(rel_str)
        if len(matches) >= MAX_FIND_RESULTS:
            break
    return json.dumps({"matches": matches, "count": len(matches)}, ensure_ascii=False)


async def grep(pattern: str = "", path: str = "") -> str:
    """文本搜索 — 在工作区（或子目录）内的文本文件中按内容搜索。

    何时用：需要按内容定位工作区信息
    会发生什么：返回 文件/行号/行内容 匹配列表，最多 100 条；二进制文件自动跳过"""
    if _ACCESS_LEVEL == "off":
        return json.dumps({"error": "文件访问已关闭（当前对话设置为「关闭」档）"}, ensure_ascii=False)
    if not pattern:
        return json.dumps({"error": "请提供搜索模式 pattern"}, ensure_ascii=False)
    root = workspace_root()
    if path:
        target, err = _resolve(path)
        if err:
            return _error_json(err)
        base = target
    else:
        base = root

    files = [base] if base.is_file() else list(base.rglob("*"))
    matches = []
    for p in files:
        if not p.is_file():
            continue
        try:
            text, err = _read_text(p)
        except (OSError, UnicodeDecodeError):
            continue
        if err:
            continue  # binary / undecodable -> skip silently
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern in line:
                matches.append({"file": str(p.relative_to(root).as_posix()),
                                "line": lineno, "text": line[:200]})
                if len(matches) >= MAX_GREP_MATCHES:
                    return json.dumps({"matches": matches, "count": len(matches),
                                       "truncated": True}, ensure_ascii=False)
    return json.dumps({"matches": matches, "count": len(matches)}, ensure_ascii=False)
