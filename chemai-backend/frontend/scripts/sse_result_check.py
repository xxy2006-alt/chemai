# sse_result_check.py — 验证 diagnose_barrier 的 tool_result 是可解析干净 JSON
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

def stream(token, conv, msg):
    body = json.dumps({"persona": "teacher", "provider": "deepseek", "version": "v2",
                       "conversation_id": conv, "message": msg, "history": []}).encode()
    req = urllib.request.Request(BASE + "/api/agent/chat/langgraph/stream", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                                 method="POST")
    out = []
    with urllib.request.urlopen(req, timeout=180) as resp:
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

token = login()
conv = new_conv(token)
evts = stream(token, conv, "找一下李世睿的学习情况")
found = 0
for e in evts:
    if e.get("type") == "tool_result" and e.get("name") == "diagnose_barrier":
        found += 1
        r = e.get("result", "")
        try:
            parsed = json.loads(r)
            print(f"diagnose_barrier tool_result: 干净JSON ✓ student_name={parsed.get('student_name')} "
                  f"barrier={parsed.get('barrier_distribution')} len={len(r)}")
        except Exception as ex:
            print(f"diagnose_barrier tool_result: 解析失败 ✗ {ex} head={r[:120]}")
    if e.get("type") == "tool_result" and e.get("name") == "show_diagnosis":
        r = e.get("result", "")
        try:
            parsed = json.loads(r)
            print(f"show_diagnosis tool_result: 干净JSON ✓ message={parsed.get('message', '')[:40]} len={len(r)}")
        except Exception as ex:
            print(f"show_diagnosis tool_result: 解析失败 ✗ {ex} head={r[:120]}")
print("diagnose_barrier tool_result 事件数:", found)
