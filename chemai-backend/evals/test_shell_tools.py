"""
L0 + L3 red tests for the sandboxed bash tool (Spec 03, eval-first).

Written BEFORE the tool exists — every case here is RED right now.
Doubles as the deterministic half of the L3 adversarial corpus:
bash injection, dangerous-command interception, sandbox escape attempts.

Deterministic, zero LLM. Platform-aware: must pass on Windows AND ubuntu CI.
"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from evals.conftest import EvalReport, parse_tool_result


def _setup_ws():
    tmp = tempfile.mkdtemp(prefix="chemai_ws_")
    os.environ["CHEMAI_WORKSPACE"] = tmp
    return tmp


# ── 白名单 / 危险命令 ────────────────────────────────────────────────────

def test_whitelist_and_dangerous():
    from agent.tools.shell import bash

    async def run():
        results = []

        async def case(name, command, timeout=0, check=None):
            _setup_ws()
            raw = await bash(command=command, timeout=timeout)
            data = parse_tool_result(raw)
            passed, detail = check(data) if check else (True, "")
            results.append({"name": name, "passed": passed, "details": detail})

        await case("echo allowed", "echo hello", check=lambda d: (
            d.get("ok") is True and "hello" in d.get("stdout", ""),
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("dangerous rm blocked", "rm -rf /", check=lambda d: (
            "error" in d and any(k in d["error"] for k in ("拒绝", "白名单", "不允许")),
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("curl blocked", "curl http://x", check=lambda d: (
            "error" in d and any(k in d["error"] for k in ("拒绝", "白名单", "不允许")),
            json.dumps(d, ensure_ascii=False)[:150]))

        await case("empty command", "", check=lambda d: (
            "error" in d,
            json.dumps(d, ensure_ascii=False)[:150]))

        return results

    return asyncio.run(run())


# ── 注入 / 逃逸 (L3) ─────────────────────────────────────────────────────

def test_injection_and_escape():
    from agent.tools.shell import bash

    async def run():
        results = []

        async def case(name, command):
            _setup_ws()
            raw = await bash(command=command)
            data = parse_tool_result(raw)
            passed = data.get("approval_needed") is True or (
                "error" in data and any(
                    k in data["error"] for k in ("元字符", "逃逸", "拒绝", "不允许")))
            results.append({"name": name, "passed": passed,
                            "details": json.dumps(data, ensure_ascii=False)[:150]})

        await case("semicolon injection", "echo hi; rm -rf /")
        await case("and injection", "echo hi && whoami")
        await case("command substitution", "echo $(whoami)")
        await case("redirect injection", "echo hi > out.txt")
        await case("pipe injection", "echo hi | wc")
        await case("backtick injection", "echo `whoami`")
        await case("traversal escape", "ls ..")
        await case("absolute path arg", "type C:\\Windows\\win.ini" if os.name == "nt" else "cat /etc/passwd")

        return results

    return asyncio.run(run())


# ── 超时 / 输出截断 ──────────────────────────────────────────────────────

def test_timeout_and_truncation():
    from agent.tools.shell import bash

    async def run():
        results = []
        _setup_ws()

        raw = await bash(command="python -c \"import time; time.sleep(10)\"", timeout=1)
        data = parse_tool_result(raw)
        results.append({
            "name": "timeout enforced",
            "passed": data.get("timed_out") is True or "超时" in json.dumps(data, ensure_ascii=False),
            "details": json.dumps(data, ensure_ascii=False)[:150],
        })

        raw = await bash(command="python -c \"print('x'*20000)\"")
        data = parse_tool_result(raw)
        results.append({
            "name": "output truncated",
            "passed": len(data.get("stdout", "")) <= 8000 and data.get("truncated") is True,
            "details": f"stdout_len={len(data.get('stdout', ''))} truncated={data.get('truncated')}",
        })

        return results

    return asyncio.run(run())


def test_access_levels():
    """off 全拒；按次审批：绝对路径参数默认请求批准，elevate 放行一次。"""
    from agent.tools import filesystem as fs
    from agent.tools.shell import bash

    async def run():
        results = []
        try:
            _setup_ws()
            fs.set_file_access_level("off")
            raw = await bash(command="echo hi")
            data = parse_tool_result(raw)
            results.append({
                "name": "off blocks bash",
                "passed": "error" in data and "关闭" in data["error"],
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            fs.set_file_access_level("workspace")
            outside = os.path.join(tempfile.gettempdir(), "chemai_shell_elevate.txt")
            with open(outside, "w", encoding="utf-8") as f:
                f.write("hello-elevate")
            cmd = f"findstr hello-elevate {outside}" if os.name == "nt" else f"cat {outside}"
            raw = await bash(command=cmd)
            data = parse_tool_result(raw)
            results.append({
                "name": "abs arg needs approval",
                "passed": data.get("approval_needed") is True,
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            fs.set_elevate_once()
            raw = await bash(command=cmd)
            data = parse_tool_result(raw)
            results.append({
                "name": "elevate allows one abs arg",
                "passed": data.get("ok") is True and "hello-elevate" in data.get("stdout", ""),
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })
            os.remove(outside)
        finally:
            fs.set_file_access_level("workspace")
        return results

    return asyncio.run(run())


def test_session_cwd():
    """bash 会话 cwd（pi agent session-cwd 同款）：cd 持久、锚定工作区、对话边界重置。"""
    from agent.tools import filesystem as fs
    from agent.tools.shell import bash

    async def run():
        results = []
        try:
            ws = _setup_ws()
            import os as _os
            _os.makedirs(_os.path.join(ws, "sub"), exist_ok=True)
            with open(_os.path.join(ws, "sub", "inside.txt"), "w", encoding="utf-8") as f:
                f.write("x")

            list_cmd = "dir" if _os.name == "nt" else "ls"

            raw = await bash(command="cd sub")
            data = parse_tool_result(raw)
            results.append({
                "name": "cd into subdir",
                "passed": data.get("ok") is True and "sub" in data.get("stdout", ""),
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            raw = await bash(command=list_cmd)
            data = parse_tool_result(raw)
            results.append({
                "name": "cwd persists (lists subdir)",
                "passed": "inside.txt" in data.get("stdout", ""),
                "details": json.dumps(data, ensure_ascii=False)[:120],
            })

            raw = await bash(command="cd ..")
            data = parse_tool_result(raw)
            results.append({
                "name": "cd .. back to root",
                "passed": data.get("ok") is True,
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            raw = await bash(command="cd outside")
            data = parse_tool_result(raw)
            results.append({
                "name": "cd outside rejected",
                "passed": "error" in data and "工作区外" in data["error"],
                "details": json.dumps(data, ensure_ascii=False)[:100],
            })

            # 对话边界重置（set_file_access_level 清除会话 cwd）
            await bash(command="cd sub")
            fs.set_file_access_level("workspace")
            raw = await bash(command=list_cmd)
            data = parse_tool_result(raw)
            results.append({
                "name": "cwd reset at conversation boundary",
                "passed": "sub" not in data.get("stdout", "") or "inside.txt" not in data.get("stdout", ""),
                "details": json.dumps(data, ensure_ascii=False)[:120],
            })
        finally:
            fs.set_session_cwd("")
            fs.set_file_access_level("workspace")
        return results

    return asyncio.run(run())


def run():
    report = EvalReport()

    print("=== L0/L3(red): bash 白名单/危险命令 ===")
    for r in test_whitelist_and_dangerous():
        report.add(f"bash.wl: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0/L3(red): bash 注入/逃逸 ===")
    for r in test_injection_and_escape():
        report.add(f"bash.inj: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0/L3(red): bash 超时/截断 ===")
    for r in test_timeout_and_truncation():
        report.add(f"bash.lim: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0: 三档访问开关 ===")
    for r in test_access_levels():
        report.add(f"bash.access: {r['name']}", r["passed"], r.get("details", ""))
    print("=== L0: bash 会话 cwd (pi 同款) ===")
    for r in test_session_cwd():
        report.add(f"bash.cwd: {r['name']}", r["passed"], r.get("details", ""))

    print(report.summary())
    return report


if __name__ == "__main__":
    run()
