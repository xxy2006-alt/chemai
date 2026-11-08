# sse_approval_flow.py — SSE 直测批准流程：数 awaiting_approval 出现次数
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8001"

def login():
    req = urllib.request.Request(BASE + "/api/auth/login",
                                 data=json.dumps({"username": "hai", "password": "hai123456"}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["token"]

def new_conv(token):
    req = urllib.request.Request(BASE + "/api/agent/chat/new?prefix=t-", data=b"{}",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                                 method="POST")
    return json.loads(urllib.request.urlopen(req).read())["thread_id"]

def stream(token, conv, msg, resume=False):
    body = json.dumps({
        "persona": "teacher", "provider": "deepseek", "version": "v2",
        "conversation_id": conv, "message": msg, "history": [],
        **({"resume": True} if resume else {}),
    }).encode()
    req = urllib.request.Request(BASE + "/api/agent/chat/langgraph/stream" if not resume
                                 else BASE + "/api/agent/chat/langgraph/resume",
                                 data=body,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                                 method="POST")
    out = []
    with urllib.request.urlopen(req, timeout=240) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                out.append(json.loads(payload))
            except Exception:
                pass
    return out

def summarize(events):
    counts = {}
    for e in events:
        t = e.get("type")
        counts[t] = counts.get(t, 0) + 1
    return counts

token = login()
conv = new_conv(token)
print("=== 1. 首次对话（应出现 1 次 awaiting_approval 后中断） ===")
ev1 = stream(token, conv, "给李世睿布置针对性练习")
print("事件统计:", summarize(ev1))
approvals = [e for e in ev1 if e.get("phase") == "awaiting_approval"]
print("awaiting_approval 次数:", len(approvals))

print("=== 2. 批准后 resume（不应再出现 awaiting_approval） ===")
ev2 = stream(token, conv, "approved", resume=True)
print("事件统计:", summarize(ev2))
approvals2 = [e for e in ev2 if e.get("phase") == "awaiting_approval"]
print("awaiting_approval 次数:", len(approvals2))
for e in ev2:
    t = e.get("type")
    if t == "tool_call":
        print("  tool_call:", e.get("name"))
    if t == "tool_result":
        print("  tool_result:", e.get("name"), "success=", e.get("success"))
    if t == "phase":
        print("  phase:", e.get("phase"), "msg:", str(e.get("message"))[:60])
    if t == "component":
        print("  component:", e.get("component"))
has_result = any(e.get("type") == "tool_result" and e.get("name") == "assign_adaptive_practice" for e in ev2)
print("assign_adaptive_practice 结果到达:", has_result)
