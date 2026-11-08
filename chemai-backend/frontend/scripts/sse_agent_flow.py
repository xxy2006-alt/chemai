# sse_agent_flow.py — SSE 事件流验证：找学生 / 障碍出题 / 学习方案跳转
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8001"

def login():
    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"username": "hai", "password": "hai123456"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())["token"]

def new_conversation(token):
    req = urllib.request.Request(
        BASE + "/api/agent/chat/new?prefix=t-",
        data=b"{}", headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {token}"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req).read())["thread_id"]

def stream(token, conv_id, message):
    body = json.dumps({
        "persona": "teacher", "provider": "deepseek", "version": "v2",
        "conversation_id": conv_id, "message": message, "history": [],
    }).encode()
    req = urllib.request.Request(
        BASE + "/api/agent/chat/langgraph/stream", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    events = []
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                evt = json.loads(payload)
            except Exception:
                continue
            events.append(evt)
    return events

def summarize(events):
    out = []
    for e in events:
        t = e.get("type")
        if t == "tool_call":
            out.append(f"tool_call:{e.get('name')}")
        elif t == "tool_result":
            out.append(f"tool_result:{e.get('name')}(success={e.get('success')})")
        elif t == "component":
            out.append(f"component:{e.get('component')}")
        elif t == "navigate":
            out.append(f"navigate:{e.get('page')} params={e.get('params')}")
        elif t == "exam_images":
            out.append(f"exam_images({len(e.get('urls', []))}urls)")
        elif t in ("phase", "text", "done"):
            out.append(t)
    return out

token = login()
print("=== 1. 找李世睿的学习情况 ===")
c1 = new_conversation(token)
ev1 = stream(token, c1, "找一下李世睿的学习情况")
print("  " + " -> ".join(summarize(ev1)))
# 诊断面板 params 检查
for e in ev1:
    if e.get("type") == "component" and e.get("component") == "diagnosis":
        p = e.get("params", {})
        print(f"  diagnosis params keys: {sorted(p.keys())}")
        print(f"  student_name={p.get('student_name')} barrier_distribution={p.get('barrier_distribution')}")

print("=== 2. 针对学习障碍出题练习 ===")
c2 = new_conversation(token)
ev2 = stream(token, c2, "针对李世睿的学习障碍出题练习")
print("  " + " -> ".join(summarize(ev2)))

print("=== 3. 给李世睿出一份个性化的学习方案 ===")
c3 = new_conversation(token)
ev3 = stream(token, c3, "给李世睿出一份个性化的学习方案")
print("  " + " -> ".join(summarize(ev3)))
