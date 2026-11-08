"""
L0 red tests for the filesystem tool quartet (Spec 03, eval-first).

Written BEFORE the tools exist — every case here is RED right now. The tools
(agent/tools/filesystem.py: read/write/edit/find/grep) must be implemented
until this file turns green, then the expected_fail markers in the registry
are removed (red -> green = development progress).

Deterministic, zero LLM, zero DB: tests run against a temp workspace injected
via CHEMAI_WORKSPACE.
"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from evals.conftest import EvalReport, parse_tool_result


def _setup_ws(files=None):
    """Create a temp workspace with the given files. Returns workspace root."""
    tmp = tempfile.mkdtemp(prefix="chemai_ws_")
    for name, content in (files or {}).items():
        p = os.path.join(tmp, name)
        dirname = os.path.dirname(p)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        if isinstance(content, bytes):
            with open(p, "wb") as f:
                f.write(content)
        else:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
    os.environ["CHEMAI_WORKSPACE"] = tmp
    return tmp


def _abs_escape_path():
    return "C:\\Windows\\win.ini" if os.name == "nt" else "/etc/passwd"


# ── read ─────────────────────────────────────────────────────────────────

def test_read():
    from agent.tools.filesystem import read

    async def run():
        results = []

        async def case(name, ws_files, path, check):
            _setup_ws(ws_files)
            raw = await read(path=path)
            data = parse_tool_result(raw)
            passed, detail = check(data)
            results.append({"name": name, "passed": passed, "details": detail})

        await case("utf8 read", {"a.txt": "你好化学"}, "a.txt", lambda d: (
            "error" not in d and d.get("content") == "你好化学" and d.get("chars") == 4,
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("gbk fallback", {"gbk.txt": "配平方程式".encode("gbk")}, "gbk.txt", lambda d: (
            "error" not in d and d.get("content") == "配平方程式",
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("missing file", {}, "nope.txt", lambda d: (
            "error" in d and ("不存在" in d["error"] or "找不到" in d["error"]),
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("binary refused", {"bin.dat": b"\x00\x01\x02"}, "bin.dat", lambda d: (
            "error" in d and "二进制" in d["error"],
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("traversal needs approval", {}, "../outside.txt", lambda d: (
            d.get("approval_needed") is True and "批准" in d.get("message", ""),
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("absolute needs approval", {}, _abs_escape_path(), lambda d: (
            d.get("approval_needed") is True and "批准" in d.get("message", ""),
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("sensitive refused", {".env": "SECRET=1"}, ".env", lambda d: (
            "error" in d and "敏感" in d["error"],
            json.dumps(d, ensure_ascii=False)[:150]))

        return results

    return asyncio.run(run())


# ── write ────────────────────────────────────────────────────────────────

def test_write():
    from agent.tools.filesystem import write

    async def run():
        results = []

        async def case(name, path, content, check):
            _setup_ws()
            raw = await write(path=path, content=content)
            data = parse_tool_result(raw)
            passed, detail = check(data)
            results.append({"name": name, "passed": passed, "details": detail})

        await case("write nested", "out/dir/a.txt", "内容123", lambda d: (
            d.get("written") is True and d.get("chars") == 5
            and os.path.exists(os.path.join(os.environ["CHEMAI_WORKSPACE"], "out", "dir", "a.txt")),
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("empty content", "empty.txt", "", lambda d: (
            d.get("written") is True and d.get("chars") == 0,
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("traversal needs approval", "../x.txt", "x", lambda d: (
            d.get("approval_needed") is True,
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("absolute needs approval", _abs_escape_path(), "x", lambda d: (
            d.get("approval_needed") is True,
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("sensitive refused", ".env", "SECRET=1", lambda d: (
            "error" in d and "敏感" in d["error"],
            json.dumps(d, ensure_ascii=False)[:150]))

        return results

    return asyncio.run(run())


# ── edit ─────────────────────────────────────────────────────────────────

def test_edit():
    from agent.tools.filesystem import edit

    async def run():
        results = []

        async def case(name, content, old, new, check):
            _setup_ws({"e.txt": content})
            raw = await edit(path="e.txt", old_string=old, new_string=new)
            data = parse_tool_result(raw)
            with open(os.path.join(os.environ["CHEMAI_WORKSPACE"], "e.txt"),
                      encoding="utf-8") as f:
                final = f.read()
            passed, detail = check(data, final)
            results.append({"name": name, "passed": passed, "details": detail})

        await case("exact replace", "hello world", "world", "chem", lambda d, f: (
            d.get("edited") is True and f == "hello chem",
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("not found", "hello world", "nope", "x", lambda d, f: (
            "error" in d and "未找到" in d["error"] and f == "hello world",
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("multiple matches", "aa bb aa", "aa", "cc", lambda d, f: (
            "error" in d and ("2" in d["error"] or "多处" in d["error"]) and f == "aa bb aa",
            json.dumps(d, ensure_ascii=False)[:150]))

        # sensitive-path case runs against .env directly
        _setup_ws({".env": "SECRET=1"})
        raw = await edit(path=".env", old_string="SECRET=1", new_string="SECRET=2")
        data = parse_tool_result(raw)
        results.append({
            "name": "sensitive refused",
            "passed": "error" in data and "敏感" in data["error"],
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        return results

    return asyncio.run(run())


# ── find / grep ──────────────────────────────────────────────────────────

def test_find_grep():
    from agent.tools.filesystem import find, grep

    async def run():
        results = []
        _setup_ws({"a.txt": "氧化还原反应", "sub/b.py": "print('x')", "sub/c.txt": "氧化还原 复习"})

        raw = await find(pattern="*.txt")
        data = parse_tool_result(raw)
        names = {m if isinstance(m, str) else m.get("path") for m in data.get("matches", [])}
        results.append({
            "name": "find by ext",
            "passed": "a.txt" in names and "sub/c.txt" in names and "sub/b.py" not in names,
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        raw = await grep(pattern="氧化")
        data = parse_tool_result(raw)
        files_hit = {m.get("file") for m in data.get("matches", [])}
        results.append({
            "name": "grep across workspace",
            "passed": data.get("count") == 2 and "a.txt" in files_hit and "sub/c.txt" in files_hit,
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        raw = await grep(pattern="氧化", path="sub")
        data = parse_tool_result(raw)
        results.append({
            "name": "grep scoped to subdir",
            "passed": data.get("count") == 1
                      and data.get("matches", [{}])[0].get("file", "").startswith("sub"),
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        return results

    return asyncio.run(run())


def test_access_levels():
    """off 全拒；按次审批（elevate）：放行一次工作区外访问，随后失效；敏感文件永远拒绝。"""
    from agent.tools.filesystem import (read, set_elevate_once,
                                        set_file_access_level, write)

    async def run():
        results = []
        try:
            _setup_ws({"a.txt": "你好"})
            set_file_access_level("off")
            raw = await read(path="a.txt")
            data = parse_tool_result(raw)
            results.append({
                "name": "off blocks read",
                "passed": "error" in data and "关闭" in data["error"],
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })
            raw = await write(path="b.txt", content="x")
            data = parse_tool_result(raw)
            results.append({
                "name": "off blocks write",
                "passed": "error" in data and "关闭" in data["error"],
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            set_file_access_level("workspace")
            outside = os.path.join(tempfile.gettempdir(), "chemai_elevate_test.txt")
            with open(outside, "w", encoding="utf-8") as f:
                f.write("外部文件")
            raw = await read(path=outside)
            data = parse_tool_result(raw)
            results.append({
                "name": "outside needs approval",
                "passed": data.get("approval_needed") is True,
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            set_elevate_once()
            raw = await read(path=outside)
            data = parse_tool_result(raw)
            results.append({
                "name": "elevate allows one outside access",
                "passed": data.get("content") == "外部文件",
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            raw = await read(path=outside)  # 放行已被消费
            data = parse_tool_result(raw)
            results.append({
                "name": "elevation consumed after one call",
                "passed": data.get("approval_needed") is True,
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            # 区内路径不浪费放行额度（真实流修复：先读相对路径再读绝对路径仍放行）
            set_elevate_once()
            raw = await read(path="a.txt")
            data = parse_tool_result(raw)
            results.append({
                "name": "inside path does not consume elevation",
                "passed": "error" not in data,
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })
            raw = await read(path=outside)
            data = parse_tool_result(raw)
            results.append({
                "name": "elevation survives inside reads",
                "passed": data.get("content") == "外部文件",
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })
            os.remove(outside)

            # 敏感文件即使放行也拒绝：用工作区外的 .env（绝对路径，消费放行额度）
            set_elevate_once()
            outside_env = os.path.join(tempfile.gettempdir(), ".env")
            with open(outside_env, "w", encoding="utf-8") as f:
                f.write("SECRET=1")
            raw = await read(path=outside_env)
            data = parse_tool_result(raw)
            results.append({
                "name": "sensitive refused even elevated",
                "passed": "error" in data and "敏感" in data["error"],
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })
            os.remove(outside_env)
        finally:
            set_file_access_level("workspace")
        return results

    return asyncio.run(run())


def test_workspace_skeleton_and_archive():
    """骨架：新工作区自动生成 README + 5 个子目录；write 到 AI生成/ 按日期归档。"""
    import datetime
    from agent.tools.filesystem import workspace_root, write

    async def run():
        results = []
        tmp = tempfile.mkdtemp(prefix="chemai_ws_")
        os.environ["CHEMAI_WORKSPACE"] = tmp
        try:
            root = workspace_root()
            dirs = {p.name for p in root.iterdir() if p.is_dir()}
            results.append({
                "name": "skeleton dirs",
                "passed": {"学生资料", "教案备课", "试卷真题", "AI生成", "临时"} <= dirs,
                "details": str(dirs),
            })
            results.append({
                "name": "skeleton readme",
                "passed": (root / "README.md").exists(),
                "details": "",
            })

            raw = await write(path="AI生成/卷子.txt", content="测试")
            data = parse_tool_result(raw)
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            results.append({
                "name": "AI生成 auto-archived by date",
                "passed": data.get("written") is True
                          and data.get("path") == f"AI生成/{today}/卷子.txt"
                          and (root / "AI生成" / today / "卷子.txt").exists(),
                "details": json.dumps(data, ensure_ascii=False)[:120],
            })
        finally:
            os.environ.pop("CHEMAI_WORKSPACE", None)
        return results

    return asyncio.run(run())


def test_read_pagination():
    """read 分页（pi agent 同款 offset/limit，1-indexed 行号）。"""
    from agent.tools.filesystem import read

    async def run():
        results = []
        _setup_ws({"lines.txt": "\n".join(f"line{i}" for i in range(1, 11))})

        raw = await read(path="lines.txt", offset=3, limit=2)
        data = parse_tool_result(raw)
        results.append({
            "name": "offset+limit window",
            "passed": data.get("content") == "line3\nline4"
                      and data.get("total_lines") == 10 and data.get("truncated") is True,
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        raw = await read(path="lines.txt", offset=0, limit=0)
        data = parse_tool_result(raw)
        results.append({
            "name": "no pagination = whole file",
            "passed": data.get("total_lines") == 10 and data.get("truncated") is False
                      and data["content"].count("\n") == 9,
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        raw = await read(path="lines.txt", offset=99, limit=5)
        data = parse_tool_result(raw)
        results.append({
            "name": "offset beyond end",
            "passed": data.get("content") == "" and data.get("total_lines") == 10,
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        return results

    return asyncio.run(run())


def test_edit_multi():
    """edit 多替换（pi agent edits 语义）：各自唯一、互不重叠、针对原文件。"""
    from agent.tools.filesystem import edit

    async def run():
        results = []

        async def case(name, content, edits, check):
            _setup_ws({"e.txt": content})
            raw = await edit(path="e.txt", edits=json.dumps(edits))
            data = parse_tool_result(raw)
            with open(os.path.join(os.environ["CHEMAI_WORKSPACE"], "e.txt"),
                      encoding="utf-8") as f:
                final = f.read()
            passed, detail = check(data, final)
            results.append({"name": name, "passed": passed, "details": detail})

        await case("two replacements", "foo bar baz", [
            {"old_text": "foo", "new_text": "F"}, {"old_text": "baz", "new_text": "Z"}],
            lambda d, f: (d.get("edited") is True and d.get("replacements") == 2
                          and f == "F bar Z", json.dumps(d, ensure_ascii=False)[:150]))

        await case("non-unique old rejected", "x x y", [
            {"old_text": "x", "new_text": "X"}],
            lambda d, f: ("error" in d and "2 处" in d["error"] and f == "x x y",
                          json.dumps(d, ensure_ascii=False)[:150]))

        await case("overlap rejected", "abcd", [
            {"old_text": "abc", "new_text": "X"}, {"old_text": "bcd", "new_text": "Y"}],
            lambda d, f: ("error" in d and "重叠" in d["error"] and f == "abcd",
                          json.dumps(d, ensure_ascii=False)[:150]))

        return results

    return asyncio.run(run())


def run():
    report = EvalReport()

    print("=== L0(red): filesystem read ===")
    for r in test_read():
        report.add(f"fs.read: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0(red): filesystem write ===")
    for r in test_write():
        report.add(f"fs.write: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0(red): filesystem edit ===")
    for r in test_edit():
        report.add(f"fs.edit: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0(red): find/grep ===")
    for r in test_find_grep():
        report.add(f"fs.find_grep: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0: 三档访问开关 ===")
    for r in test_access_levels():
        report.add(f"fs.access: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0: 工作区骨架 + AI生成归档 ===")
    for r in test_workspace_skeleton_and_archive():
        report.add(f"fs.ws: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0: read 分页 (pi 同款) ===")
    for r in test_read_pagination():
        report.add(f"fs.read_pg: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0: edit 多替换 (pi edits 语义) ===")
    for r in test_edit_multi():
        report.add(f"fs.edit_multi: {r['name']}", r["passed"], r.get("details", ""))

    print(report.summary())
    return report


if __name__ == "__main__":
    run()
