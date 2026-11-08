# Tasks: infra-foundation

## T1: 安装 MinerU Python 依赖

**估时**: 1h
**风险**: Windows 上 opencv-python 可能有兼容问题
**验证**: `python -c "from mineru.cli.client import plan_tasks"` 成功

- [x] 1.1 进入 `D:\化学\MinerU-master\MinerU-master`
- [x] 1.2 执行 `pip install -e .` 安装所有依赖 → mineru-3.0.9 成功
- [x] 1.3 如果某个包安装失败（如 opencv），记录并尝试 `pip install opencv-python-headless` → opencv-python-4.13.0.92 正常安装，无需 headless
- [x] 1.4 验证：`python -c "from mineru.cli.client import collect_input_documents, plan_tasks"` → 全部通过
- [x] 1.5 记录最终安装结果（成功/部分成功/失败）→ 保存到 memory

---

## T2: LLM 调用方式现代化 (curl → httpx)

**估时**: 1.5h
**涉及文件**: `app/services/llm_service.py`
**验证**: 调用 `generate_text("你好")` 返回非 mock 内容

- [x] 2.1 `generate_text()` 中删除 subprocess curl 代码块
- [x] 2.2 替换为 `httpx.post()` 调用 DashScope compatible-mode 端点
- [x] 2.3 添加重试机制：3 次，指数退避 (1s/2s/4s) → `_call_with_retry()`
- [x] 2.4 添加超时分层级：普通 30s，vision 120s
- [x] 2.5 同样改造 `analyze_paper_with_vision()` 的智谱 API 调用 → httpx + retry
- [x] 2.6 接入 DeepSeek 作为备选 Provider → auto 模式 DashScope优先/DeepSeek备选
- [x] 2.7 验证：DashScope + DeepSeek 两个 Provider 真实调用均返回 "好"

---

## T3: OCR 端点验证 + 降级链完善

**估时**: 1h
**涉及文件**: `app/services/ocr_service.py`
**验证**: POST `/api/ocr/preview` 返回真实识别结果（或明确的降级信息）

- [x] 3.1 准备一张测试图片（纯文字/数字表格），转 base64 → Pillow 生成测试图
- [x] 3.2 测试智谱 OCR 端点 → 成功识别学号+8题答案，准确率100%
- [x] 3.3 如果端点不可用/返回格式变化，改为调用 GLM-4V vision → 已实现 fallback
- [x] 3.4 实现 triage 策略 → 智谱OCR → GLM-4V Vision → 提示手动输入
- [x] 3.5 每个降级路径记录日志 → print() 日志标记 [OCR]
- [x] 3.6 更新 `.env` 加 `OCR_PROVIDER=auto` 配置项

---

## T4: 修复启动时错误

**估时**: 0.5h
**涉及文件**: `app/main.py`, `app/scheduler/__init__.py`

- [x] 4.1 APScheduler ReviewTask 导入错误 → 修复了 `daily_practice.py` 中的 import 路径
- [x] 4.2 ChromaDB telemetry → posthog mock 在 main.py 生效，telemetry 警告无害
- [x] 4.3 验证 → 启动服务，APScheduler 正常运行，无 error/exception
