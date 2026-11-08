# ChemAI ChemAI Agent 集成测试指南

> 本文档描述如何验证 Phase 1-3 的实施结果

---

## 前置条件

### 1. 启动服务

**终端 1: 启动 FastAPI Backend**
```bash
cd D:\化学\chemai-backend
python -m app.main
# 预期输出: Uvicorn running on http://0.0.0.0:8001
```

**终端 2: 启动 ChemAI Agent API Server**
```bash
cd D:\化学\hermes-agent-main
python -m gateway.run --platform api_server
# 预期输出: API server listening on http://127.0.0.1:8642
```

---

## 测试步骤

### Step 1: 验证 ChemAI Agent 启动成功

```bash
curl http://localhost:8642/health
```

**预期输出**:
```json
{"status": "ok", "platform": "hermes-agent"}
```

---

### Step 2: 验证 Tools 注册

```bash
curl http://localhost:8642/v1/models
```

**预期输出**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "hermes-agent",
      "object": "model",
      ...
    }
  ]
}
```

**验证 chemistry tools 是否可用**: 发送一个测试请求

```bash
curl -X POST http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "你好，请简单介绍一下自己"}],
    "stream": false
  }'
```

**预期**: 返回 JSON 格式的聊天回复（因为 `stream: false`）

---

### Step 3: 验证 chemistry_tools.py 导入

在 **终端 2** (ChemAI Agent) 中查看启动日志，应该看到:

```
Registered 22 chemistry tools to ChemAI Agent
```

如果看到警告信息如 `Could not import chem_skills`，检查:
1. `D:\化学\chemai-backend` 是否存在
2. Python 路径是否正确

---

### Step 4: 验证 SSE 流式输出

```bash
curl -X POST http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

**观察**:
- 应该看到 SSE 格式的输出（带 `data: ` 前缀）
- 应该能看到 `chat.completion.chunk` 格式的事件

---

### Step 5: 验证 Tool Calling

```bash
curl -X POST http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "请检查化学公式 Ca(OH)2 的标准化"}],
    "stream": true
  }'
```

**观察**:
- 应该看到 `chat.completion.chunk` 事件
- 如果 LLM 决定调用 tool，应该看到 `tool_calls` 在 delta 中
- 结束时应该看到 `finish_reason: "stop"` 或 `finish_reason: "tool_calls"`

---

### Step 6: 前端集成测试

启动前端开发服务器：
```bash
cd D:\化学\chemai-backend\frontend
npm run dev
```

访问 `http://localhost:5173` (或配置的端口)

#### 6.1 打开浏览器开发者工具 (F12)

#### 6.2 切换到 Network 标签

#### 6.3 登录并执行一个 Hermes Task（如 OCR 识别）

观察 Network 请求:
- 应该看到请求发送到 `http://localhost:8642/v1/chat/completions`
- SSE 流应该返回 `chat.completion.chunk` 格式

#### 6.4 切换到 Console 标签

观察日志:
- 应该看到 HermesThinking 组件的日志
- 应该看到 `tool_call` 事件
- 应该看到 `tool_result` 事件

---

## 常见问题排查

### Q1: ChemAI Agent 启动失败，提示 "aiohttp not installed"

**解决**:
```bash
pip install aiohttp
```

### Q2: chem_skills 导入失败

**检查**:
1. `D:\化学\chemai-backend` 目录存在
2. `D:\化学\chemai-backend\chem_skills` 目录存在
3. Python 路径正确

**解决**: 在 `chemistry_tools.py` 中已添加路径:
```python
CHEMAI_BACKEND_PATH = r"D:\化学\chemai-backend"
if CHEMAI_BACKEND_PATH not in sys.path:
    sys.path.insert(0, CHEMAI_BACKEND_PATH)
```

### Q3: 前端 SSE 事件不解析

**检查**:
1. 确认 hermes.js 已更新（检查文件修改时间）
2. 清除浏览器缓存
3. 确认 Vite dev server 已重启

### Q4: Tool 不被调用

可能原因:
1. LLM 决定不调用 tool，直接回答
2. system prompt 没有正确引导 tool calling

**解决**: 检查 `_buildPrompt()` 中的指令是否足够明确

---

## Python 单元测试

创建一个快速测试脚本来验证 chemistry_tools.py:

```python
# test_chemistry_tools.py
import sys
sys.path.insert(0, r"D:\化学\chemai-backend")
sys.path.insert(0, r"D:\化学\hermes-agent-main")

# 测试导入
print("Testing imports...")
try:
    from chem_skills.chemistry_parser.handler import ParserHandler
    from chem_skills.chemistry_exam.handler import ExamHandler
    from chem_skills.chemistry_diagnosis.handler import DiagnosisHandler
    print("✓ chem_skills imported successfully")
except ImportError as e:
    print(f"✗ chem_skills import failed: {e}")

# 测试 chemistry_tools
try:
    from tools.chemistry_tools import SKILLS_AVAILABLE, REGISTRY_AVAILABLE
    print(f"✓ chemistry_tools imported")
    print(f"  SKILLS_AVAILABLE: {SKILLS_AVAILABLE}")
    print(f"  REGISTRY_AVAILABLE: {REGISTRY_AVAILABLE}")
except ImportError as e:
    print(f"✗ chemistry_tools import failed: {e}")

# 测试 Handler 创建
if SKILLS_AVAILABLE:
    try:
        parser = ParserHandler()
        print(f"✓ ParserHandler created (mineru_available={parser.mineru_available})")
    except Exception as e:
        print(f"✗ ParserHandler creation failed: {e}")
```

运行测试:
```bash
cd D:\化学\hermes-agent-main
python test_chemistry_tools.py
```

---

## 验证清单

- [ ] Step 1: ChemAI Agent 健康检查通过
- [ ] Step 2: /v1/models 返回成功
- [ ] Step 3: chemistry_tools.py 导入成功，日志显示 "Registered 22 chemistry tools"
- [ ] Step 4: SSE 流式输出正常
- [ ] Step 5: Tool calling 格式正确
- [ ] Step 6: 前端 HermesThinking 组件正常工作

---

## 预期结果

### 成功的标志

1. **ChemAI Agent 日志**:
   ```
   Registered 22 chemistry tools to ChemAI Agent
   API server listening on http://127.0.0.1:8642
   ```

2. **curl 测试**:
   - 健康检查返回 `{"status": "ok"}`
   - 流式输出包含 `chat.completion.chunk` 格式事件

3. **前端 Console**:
   - 无 JavaScript 错误
   - 看到 SSE 事件被正确解析
   - HermesThinking 组件正确显示

---

## 联系支持

如果遇到问题，请提供:
1. ChemAI Agent 启动日志
2. curl 测试的完整输出
3. 浏览器 Console 的错误信息
4. Network 标签中失败的请求详情
