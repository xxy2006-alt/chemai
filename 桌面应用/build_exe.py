"""ChemAI 桌面启动器 — 打包为独立 .exe (嵌入式桌面窗口)

使用 pywebview 创建原生窗口承载 Web 应用，不再打开浏览器。
端口: 8000
"""

import PyInstaller.__main__
import os
import shutil

SRC = r"D:\\化学\\chemai-backend"
OUT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(OUT, "_build_tmp")
shutil.rmtree(BUILD, ignore_errors=True)
os.makedirs(BUILD, exist_ok=True)

# 教师端启动入口
teacher_py = os.path.join(BUILD, "teacher_launcher.py")
with open(teacher_py, "w", encoding="utf-8") as f:
    f.write(r'''
import sys, os, threading, time
SRC = r"D:\\化学\\chemai-backend"
sys.path.insert(0, SRC)
os.chdir(SRC)

def start_server():
    from uvicorn import run
    run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")

threading.Thread(target=start_server, daemon=True).start()

# 等待服务器就绪
import urllib.request
for _ in range(30):
    try:
        urllib.request.urlopen("http://localhost:8000/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

import webview
webview.create_window("智辅化学 · 教师端", "http://localhost:8000/", width=1200, height=800, min_size=(800, 600))
webview.start()
''')

# 学生端启动入口
student_py = os.path.join(BUILD, "student_launcher.py")
with open(student_py, "w", encoding="utf-8") as f:
    f.write(r'''
import sys, os, threading, time
SRC = r"D:\\化学\\chemai-backend"
sys.path.insert(0, SRC)
os.chdir(SRC)

def start_server():
    from uvicorn import run
    run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")

threading.Thread(target=start_server, daemon=True).start()

import urllib.request
for _ in range(30):
    try:
        urllib.request.urlopen("http://localhost:8000/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

import webview
webview.create_window("智辅化学 · 学生端", "http://localhost:8000/m/index.html", width=430, height=900, min_size=(380, 600))
webview.start()
''')

COMMON = [
    "--onefile", "--noconsole", "--clean",
    "--distpath", OUT, "--workpath", BUILD, "--specpath", BUILD,
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "starlette",
    "--hidden-import", "webview",
    "--hidden-import", "webview.platforms.winforms",
    "--collect-all", "webview",
]

# 家长端
parent_py = os.path.join(BUILD, "parent_launcher.py")
with open(parent_py, "w", encoding="utf-8") as f:
    f.write(r'''
import sys, os, threading, time
SRC = r"D:\\化学\\chemai-backend"
sys.path.insert(0, SRC)
os.chdir(SRC)

def start_server():
    from uvicorn import run
    run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")

threading.Thread(target=start_server, daemon=True).start()

import urllib.request
for _ in range(30):
    try:
        urllib.request.urlopen("http://localhost:8000/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

import webview
webview.create_window("智辅化学 · 家长端", "http://localhost:8000/m/parent-login.html", width=430, height=900, min_size=(380, 600))
webview.start()
''')

for name, entry in [("ChemAI-Teacher", teacher_py), ("ChemAI-Student", student_py), ("ChemAI-Parent", parent_py)]:
    print(f"Building {name}...")
    PyInstaller.__main__.run([entry, "--name", name] + COMMON)

# 重命名
for en, cn in [("ChemAI-Teacher", "智辅化学-教师端"), ("ChemAI-Student", "智辅化学-学生端"), ("ChemAI-Parent", "智辅化学-家长端")]:
    src = os.path.join(OUT, en + ".exe")
    dst = os.path.join(OUT, cn + ".exe")
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(src, dst)

shutil.rmtree(BUILD, ignore_errors=True)
print("Done")
