## 1. Skill Registry

- [ ] 1.1 实现 `skill_registry.py` — `SkillRegistry` 类 + `register()` 装饰器
- [ ] 1.2 实现 `to_openai_tools()` — 生成 function calling 格式
- [ ] 1.3 实现 `execute()` — 按 name 查找并调用 Skill
- [ ] 1.4 验证：注册一个 mock Skill，执行并检查 tools 格式

## 2. Memory Stack

- [ ] 2.1 实现 `memory.py` — `MemoryStack` 类（working + episodic + profile）
- [ ] 2.2 实现 `build_context()` — 组装发送给 LLM 的完整消息列表
- [ ] 2.3 实现 `load_student()` — 从 DB 加载学生画像
- [ ] 2.4 验证：20 轮后旧消息被淘汰，学生画像正确注入

## 3. Persona 配置

- [ ] 3.1 创建 `personas/tutor.yaml` — 学生端 AI 助教 prompt
- [ ] 3.2 创建 `personas/teacher.yaml` — 教师端教研助手 prompt
- [ ] 3.3 创建 `personas/parent.yaml` — 家长端周报助手 prompt
- [ ] 3.4 实现 Persona 加载函数（读 yaml → dict）

## 4. Agent Core

- [ ] 4.1 实现 `core.py` — `AgentConfig` + `ChemAgent` 类
- [ ] 4.2 实现 Think — 组装 messages → LLM 决策（reply 或 use_skill）
- [ ] 4.3 实现 Route + Execute — 解析 LLM 决定 → 调用 Skill → 观察结果
- [ ] 4.4 实现 `run()` — 完整循环（非流式）
- [ ] 4.5 实现 `run_stream()` — 流式循环（SSE 输出）
- [ ] 4.6 实现 max_turns 保护（默认 5 轮）
- [ ] 4.7 验证：Agent 回答不需要工具的问题
- [ ] 4.8 验证：Agent 调用 Skill 后给出友好回复
