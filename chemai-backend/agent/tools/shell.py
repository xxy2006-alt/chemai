"""
Sandboxed bash tool — command whitelist + metachar rejection + timeout + truncation.

Spec 03 (eval-first): red tests in evals/test_shell_tools.py came first.
Doubles as the deterministic half of the L3 adversarial corpus (bash
injection / dangerous commands / sandbox escape).

Sandbox model (process-level, per Spec 03):
  - default-deny: only whitelisted first tokens run, everything else refused
  - shell metacharacters (; & | < > ` $ % ^ newline) are rejected when they
    appear OUTSIDE double quotes, so no chaining/injection surface exists
    (double quotes are the only quoting both cmd and shlex agree on)
  - ".." anywhere in the command is rejected (path-escape attempt)
  - absolute path arguments (drive letter / POSIX root) are rejected
  - runs with cwd = workspace root; timeout default 30s (cap 60s);
    output truncated to 8KB tail

Known limit (documented, honest): a whitelisted interpreter (python) can still
read outside the workspace from inside its own code — process-level sandboxing
cannot prevent that. Container-level isolation is explicitly out of scope
(Spec 03 Out of Scope).
"""
import json
import os
import re
import shlex
import subprocess

from agent.tools.filesystem import (
    _consume_elevation,
    file_access_level,
    bash_cwd,
    file_access_level,
    session_cwd_rel,
    set_session_cwd,
)

MAX_TIMEOUT_S = 60
DEFAULT_TIMEOUT_S = 30
MAX_OUTPUT_CHARS = 8000

# metacharacters that enable chaining/injection — rejected when OUTSIDE double
# quotes (double quotes are the only quoting both cmd and shlex agree on).
_METACHARS = set(";&|<>`$%\n\r^")


def _metachar_outside_quotes(command: str):
    """Return the first dangerous metachar outside double quotes, else None."""
    in_quotes = False
    for ch in command:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch in _METACHARS and not in_quotes:
            return ch
    return None


# absolute path argument check happens on the RAW command (drive letters on
# Windows) and on tokens (leading "/" on POSIX) — see bash().
_WINDOWS_WHITELIST = {"dir", "type", "echo", "where", "findstr", "python", "pip", "cd"}
_UNIX_WHITELIST = {"ls", "cat", "head", "tail", "wc", "pwd", "echo",
                   "find", "grep", "python3", "python", "pip", "cd"}

# cmd builtins need cmd /c; real executables run DIRECTLY from tokens (no shell
# at all — avoids cmd's quote-rewriting rules breaking quoted arguments).
_WINDOWS_BUILTINS = {"dir", "type", "echo", "where", "findstr", "cd"}

_DANGEROUS = {"rm", "rmdir", "del", "erase", "shutdown", "format", "taskkill",
              "curl", "wget", "chmod", "chown", "dd", "mkfs", "git", "npm",
              "powershell", "cmd", "bash", "sh"}


def _reject(reason: str) -> str:
    return json.dumps({"ok": False, "error": reason}, ensure_ascii=False)


async def bash(command: str = "", timeout: int = 0) -> str:
    """执行命令 — 在工作区内执行白名单命令（沙箱化）。

    何时用：需要运行受限命令（列目录、查文件、跑 python 脚本）时；老师要求操作
    工作区外路径（如桌面文件）时也直接尝试本工具，不要未尝试就声称无法访问。
    会发生什么：仅白名单命令可执行；注入元字符与危险命令被拒绝；超时终止；输出截断；
    工作区外路径会返回「工作区外访问需要批准」——此时调 request_approval 说明要访问
    的路径，老师批准后重试本工具（按次审批）

    已知限制：白名单内的解释器（python）自身仍可越权读文件，进程级沙箱不防这一点。

    访问档位：off=关闭；workspace=默认。白名单与元字符过滤永远生效。"""
    if file_access_level() == "off":
        return _reject("bash 已关闭（当前对话设置为「关闭」档）")
    if not command or not command.strip():
        return _reject("请提供要执行的命令")

    metachar = _metachar_outside_quotes(command)
    if metachar:
        return _reject(f"命令包含危险元字符 '{metachar}'，已拒绝（禁止管道/重定向/命令替换）")

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return _reject(f"命令解析失败: {exc}")
    if not tokens:
        return _reject("请提供要执行的命令")

    first = tokens[0].lower()
    if first in _DANGEROUS:
        return _reject(f"危险命令被拒绝: {first}")
    whitelist = _WINDOWS_WHITELIST if os.name == "nt" else _UNIX_WHITELIST
    if first not in whitelist:
        return _reject(f"命令 '{first}' 不在白名单中，已拒绝。白名单: {', '.join(sorted(whitelist))}")

    # ── cd：会话工作目录（pi agent session-cwd 同款，对话内持久、锚定工作区）──
    if first == "cd":
        if len(tokens) == 1:
            set_session_cwd("")
        elif len(tokens) == 2:
            target = tokens[1]
            if os.name == "nt" and re.match(r"^[A-Za-z]:[\\/]", target):
                return _reject("cd 不允许到工作区外（盘符路径）")
            if target.startswith("/") and os.name != "nt":
                return _reject("cd 不允许到工作区外（绝对路径）")
            cur = session_cwd_rel()
            rel = target
            if target == "..":
                rel = "/".join(cur.split("/")[:-1]) if cur else cur
            elif cur:
                rel = f"{cur}/{target}"
            new_rel = set_session_cwd(rel)
            if new_rel is None:
                return _reject(f"cd 失败：目录不存在或在工作区外: {target}")
        else:
            return _reject("cd 用法: cd [子目录]")
        return json.dumps({"ok": True, "exit_code": 0,
                           "stdout": f"当前目录: {session_cwd_rel() or '（工作区根）'}",
                           "stderr": "", "truncated": False}, ensure_ascii=False)

    if ".." in command:
        return _reject("命令包含 '..' 路径逃逸尝试，已拒绝")

    # 绝对路径参数：workspace 档请求批准后按次放行。放在危险命令/白名单检查之后，
    # 避免 URL（http://…）误触盘符启发式（L3 测试抓到的真实误判）。
    # elevation 只在真正检出绝对路径参数时消费。
    def _approval(target: str) -> str:
        return json.dumps({"approval_needed": True,
                           "message": f"工作区外访问需要批准: {target}",
                           "target": target}, ensure_ascii=False)

    if os.name == "nt" and re.search(r"[A-Za-z]:[\\/]", command):
        if file_access_level() != "full" and not _consume_elevation():
            return _approval(command)
    if os.name != "nt":
        for tok in tokens[1:]:
            if tok.startswith("/"):
                if file_access_level() != "full" and not _consume_elevation():
                    return _approval(command)
                break

    effective_timeout = max(1, min(timeout or DEFAULT_TIMEOUT_S, MAX_TIMEOUT_S))
    cwd = str(bash_cwd())  # 会话 cwd（对话内持久），锚定工作区内
    if os.name == "nt" and first in _WINDOWS_BUILTINS:
        # Windows 内建命令（dir/type/echo…）必须经 cmd；元字符已过滤，注入面不存在
        run_cmd = ["cmd", "/c", command]
    else:
        # 真实可执行文件直接按 token 执行，无 shell
        run_cmd = tokens

    try:
        proc = subprocess.run(
            run_cmd, cwd=cwd, capture_output=True, text=True, errors="replace",
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"ok": False, "timed_out": True,
                           "error": f"命令超时（{effective_timeout}s）已终止"}, ensure_ascii=False)
    except FileNotFoundError:
        return _reject(f"命令 '{first}' 在当前平台不可用")

    stdout, stderr = (proc.stdout or ""), (proc.stderr or "")
    truncated = len(stdout) + len(stderr) > MAX_OUTPUT_CHARS
    if len(stdout) > MAX_OUTPUT_CHARS:
        stdout = stdout[-MAX_OUTPUT_CHARS:]
    if len(stderr) > MAX_OUTPUT_CHARS:
        stderr = stderr[-MAX_OUTPUT_CHARS:]

    return json.dumps({
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": truncated,
    }, ensure_ascii=False)
