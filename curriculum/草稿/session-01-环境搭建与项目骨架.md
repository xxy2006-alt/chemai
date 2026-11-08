# Session 1 · 环境搭建与项目骨架

## 产出物

- `chemai-backend/` 项目目录，含完整的 FastAPI 项目骨架
- `app/main.py` — 第一个路由 `/` → `{"status":"ok"}`
- `app/core/config.py` — 环境变量管理
- `.env` — API Key 和端口配置
- `requirements.txt` — 已安装的依赖清单
- 浏览器访问 `http://127.0.0.1:8001/` 返回 `{"status":"ok"}`

## 前置条件

- Windows 10/11 操作系统（教师和学生都用的 Windows）
- Python 3.11 已安装（检查：`python --version`）
- Claude Code 已安装且在 PATH 中
- 一个可用的代码编辑器（VS Code 推荐，但记事本也行）

## 项目背景（给学生的概述）

你要做的是一个叫 **ChemAI** 的产品——给高中化学教师用的 AI 教学助手。

这个产品的起点不是技术选型，是 2026 年 1 月在湖南某重点高中一位化学教师的办公室里，开发者跟这位 18 年教龄的老教师聊了两个小时，发现了三个核心痛点：

1. **错题统计**：每次月考完花 1.5 小时手动数哪道题多少人错
2. **AI 出题不信任**：ChatGPT 出题配平错了一次，从此不信任 AI
3. **个性化缺失**：90+ 人的大班，根本没法给每个学生针对性辅导

你的任务就是用接下来 12 节课，通过 Claude Code（vibe coding），从零把这个产品做出来。

这节课先搭地基——让 FastAPI 跑起来。

---

## 操作步骤

### 步骤 1：确认 Python 环境

**目标**：确认 Python 3.11 可用

**提示词**（复制到 Claude Code）：
```
检查我的 Python 版本和 pip 是否正常工作。运行 python --version 和 pip --version。
```

**验证**：
- [ ] Python 版本显示为 3.11.x
- [ ] pip 版本显示正常，路径指向正确的 Python 环境

---

### 步骤 2：创建项目目录和虚拟环境

**目标**：在桌面创建 `chemai-backend` 目录，初始化 Python 虚拟环境

**提示词**（复制到 Claude Code）：
```
在桌面创建 chemai-backend 项目目录，然后用 venv 创建 Python 虚拟环境 venv/，并激活它（Windows PowerShell 用 venv\Scripts\Activate.ps1）。

执行以下操作：
1. mkdir 创建 C:\Users\Administrator\Desktop\chemai-backend
2. cd 进入该目录
3. python -m venv venv 创建虚拟环境
4. 激活虚拟环境
5. 确认 python --version 和 pip --version 指向 venv 内的 Python
```

**验证**：
- [ ] `chemai-backend/` 目录存在，里面有 `venv/` 文件夹
- [ ] 虚拟环境激活后，`which python`（或 `where python`）指向 `venv\Scripts\python.exe`

---

### 步骤 3：安装依赖

**目标**：安装 FastAPI 全家桶

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 目录、venv 激活状态下，安装以下依赖：

pip install fastapi uvicorn sqlalchemy python-dotenv httpx pydantic aiosqlite

安装完成后，运行 pip freeze > requirements.txt 保存依赖清单。

说明：这些包的作用——
- fastapi：Python Web 框架，高性能异步
- uvicorn：ASGI 服务器，跑 FastAPI 应用的
- sqlalchemy：ORM，操作数据库的
- python-dotenv：从 .env 文件读环境变量
- httpx：异步 HTTP 客户端，用来调 LLM API
- pydantic：数据校验，FastAPI 的依赖
- aiosqlite：异步 SQLite，后面 Agent 对话持久化用
```

**验证**：
- [ ] `pip list` 显示以上 7 个包都已安装
- [ ] `requirements.txt` 存在，包含完整依赖清单

---

### 步骤 4：创建项目文件结构

**目标**：创建 `app/main.py`、`app/core/config.py` 和项目入口 `chemai.py`

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 项目里，创建以下目录和文件结构：

chemai-backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI 应用主体
│   └── core/
│       ├── __init__.py
│       └── config.py    # 环境变量管理
├── chemai.py            # 项目入口（uvicorn 启动配置）
├── .env                 # 环境变量（API Key、端口等）
└── .gitignore           # 忽略 venv/ .env __pycache__/

具体要求：

1. app/__init__.py 和 app/core/__init__.py 留空

2. app/core/config.py — 用 pydantic 的 BaseSettings 读环境变量：
   - CHEMAI_PORT: int = 8001
   - DEEPSEEK_API_KEY: str = ""
   - 用 Config 类指定 env_file = ".env"

3. app/main.py — FastAPI 应用主体：
   - 创建 FastAPI() 实例
   - 一个路由：@app.get("/") → 返回 {"status": "ok"}
   - 配置 CORS 中间件（允许所有来源，开发阶段用）

4. chemai.py — 项目入口：
   - 如果 __name__ == "__main__"，用 uvicorn.run() 启动
   - host="127.0.0.1", port 从 config 读

5. .env 文件内容：
   CHEMAI_PORT=8001
   DEEPSEEK_API_KEY=sk-your-key-here

6. .gitignore 内容：忽略 venv/、.env、__pycache__/、*.pyc、chemai.db
```

**验证**：
- [ ] 目录结构符合上面的树形图
- [ ] 所有文件都已创建且内容正确

---

### 步骤 5：首次启动验证

**目标**：启动服务器，浏览器访问返回 200

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 目录、venv 激活状态下，运行 python chemai.py 启动服务器。

然后帮我用 curl 测试：curl http://127.0.0.1:8001/

预期响应：{"status":"ok"}

如果启动失败，根据报错信息修复。常见问题：
- 端口被占用 → 改 .env 里的 CHEMAI_PORT
- 缺少依赖 → pip install 对应的包
- import 路径不对 → 检查目录结构和 __init__.py
```

**验证**：
- [ ] `python chemai.py` 启动无报错
- [ ] `curl http://127.0.0.1:8001/` 返回 `{"status":"ok"}`
- [ ] 浏览器打开 `http://127.0.0.1:8001/` 同样看到 `{"status":"ok"}`

---

### 步骤 6：Git 初始化

**目标**：初始化 Git 仓库，做第一个提交

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 目录里初始化 git 仓库：

1. git init
2. git add -A
3. git commit -m "v1.0.0: 项目初始化 — FastAPI 骨架 + 环境配置"

注意：确保 .gitignore 生效，venv/ 和 .env 不会被提交。
运行 git status 确认没有敏感文件被跟踪。
```

**验证**：
- [ ] `git log` 显示一个提交 `v1.0.0: 项目初始化`
- [ ] `git status` 显示 clean，无未跟踪的敏感文件

---

## 发生了什么（教师参考）

### 1. 项目背景：为什么是化学教师？

ChemAI 不是一个"拍脑袋"想出来的产品。它的起点是 2026 年 1 月在湖南某重点高中一位化学教师的办公室里的对话。

**种子教师画像**（来自三轮访谈的真实数据）：

| 维度 | 数据 |
|------|------|
| 教龄 | 18 年 |
| 学校类型 | 市重点高中 |
| 任教班级 | 2 个班（高一） |
| 班额 | 90+ 人/班 |
| 周课时 | 12-14 节 |
| 技术接受度 | 中等偏低（有过 ChatGPT 出题配平错误的负面体验） |
| 可投入共创时间 | ≤2 小时/周 |
| 付费意愿 | 月付 50-100 元 / 年付 600-1200 元 |

### 2. 关键决策：这些选择不是随意的

**SQLite 而非 PostgreSQL**
- 硬约束：Windows 单机部署，没有运维人员
- 用户量 <200 人，数据量 <10MB
- 单文件备份/迁移（`chemai.db` 拷走就行）
- FastAPI + SQLAlchemy + SQLite 零配置启动

**原生 HTML 而非 Vue/React**
- 教书匠不是前端工程师，不需要学 Vue Router
- 页面间没有共享状态，不需要 Redux
- 每个页面 <500 行，小学生都能维护
- 全前端代码 1300 行——用 React 至少 3000 行起步

**端口 8001 而非 8000**
- 8000 端口经常被其他程序占用
- 选 8001 纯粹为了减少冲突的概率

### 3. 首次访谈的核心发现

Day 4-5 的第一轮用户访谈，不是用问卷做的——是角色扮演式访谈。采访者扮演"AI 教研助手"，被访者扮演"寻求帮助的教师"。

第一轮就发现了三个核心痛点：
1. "每次月考完我要花一个半小时在那数哪道题多少人错"（错题统计痛点）
2. "第一次用 ChatGPT 出题错了，从此不太信任这类工具"（信任危机）
3. "班里十几二十个学生明显跟不上，不是他们不聪明"（个性化痛点）

这些痛点直接决定了后续的功能优先级——先做错题统计 + AI 出题审核，再做其他。

### 4. 经常出现的问题

**Q：端口被占用怎么办？**
A：改 `.env` 里的 `CHEMAI_PORT=8002`，然后重启。或者 `netstat -ano | findstr :8001` 找到占用进程杀掉。

**Q：虚拟环境激活失败（PowerShell 执行策略）？**
A：PowerShell 管理员模式运行 `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Q：Python 版本不是 3.11？**
A：去 python.org 下载 3.11.x 安装。不要用 3.12——某些包可能有兼容性问题。

### 5. 真实开发记录的还原

以下是 2026 年 1 月 7 日（项目 Day 1）的真实操作记录：

```
Day 1（1月7日）
- mkdir chemai-backend && cd chemai-backend
- pip install fastapi uvicorn sqlalchemy python-dotenv httpx pydantic
- app/main.py:1-30：第一个路由 @app.get("/") → {"status": "ok"}
- app/core/config.py：环境变量 CHEMAI_PORT=8001、DEEPSEEK_API_KEY 写入 .env
- 提交 892ce30 v1.0.0: 初始版本
```

第一个提交的 hash 是 `892ce30`——每个学生的第一个提交也会有一个类似的 hash。这是项目的起点。

---

## 课后产出检查

学生应该同时具备：

- [ ] `python chemai.py` 能启动，无报错
- [ ] `curl http://127.0.0.1:8001/` 返回 `{"status":"ok"}`
- [ ] `git log` 有一个初始化提交
- [ ] `.env` 文件存在，含 `CHEMAI_PORT` 和 `DEEPSEEK_API_KEY`
- [ ] `.gitignore` 生效，`venv/` 和 `.env` 不在 Git 跟踪中

**下节课需要**：本节的 `chemai-backend` 目录完整可用。下节课将在 `app/services/llm_service.py` 中接入 DeepSeek API，让 AI 回答化学问题。
