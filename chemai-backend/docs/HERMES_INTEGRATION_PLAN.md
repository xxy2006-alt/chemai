# ChemAI × ChemAI Agent 集成方案

## 一、集成背景

### ChemAI Agent 核心能力

| 能力 | 说明 |
|------|------|
| **自改进学习循环** | 从经验创建技能、使用中自我改进、跨会话记忆 |
| **Skills系统** | 过程性记忆、技能市场、技能自改进 |
| **Cron定时任务** | 自然语言调度、任意平台推送 |
| **MCP集成** | 连接任何MCP服务器扩展能力 |
| **消息网关** | Telegram/Discord/Slack/WhatsApp/Signal/Email |
| **子Agent委托** | 并行工作流、RPC工具调用 |
| **多模型支持** | Nous Portal/OpenRouter/GLM/Kimi/MiniMax等 |

### ChemAI 可集成模块

| 模块 | 功能 | 集成价值 |
|------|------|----------|
| OCR识别 | 答题卡/文档识别 | Agent可调用识别任务 |
| 错题强化 | 变式题生成 | Agent可为学生生成个性化练习 |
| 学情预警 | 异常检测 | Agent自动推送预警通知 |
| 间隔复习 | 艾宾浩斯复习 | Agent调度复习提醒 |
| 每日推送 | 练习推送 | Agent执行定时推送 |
| 家长通知 | 周报/成绩通知 | Agent推送到家长端 |
| 智能出题 | AI生成题目 | Agent可调用出题 |

---

## 二、集成方案

### 方案A: MCP协议集成（推荐）

**原理**: ChemAI作为MCP Server，ChemAI Agent通过MCP协议调用ChemAI功能

```
ChemAI Agent ←→ MCP Protocol ←→ ChemAI MCP Server
```

**优势**:
- 标准化协议，开箱即用
- 无需修改ChemAI Agent源码
- 解耦设计，各自独立演进

**MCP Server能力**:

| 工具 | 功能 | 参数 |
|------|------|------|
| `ocr_recognize` | OCR识别 | image_data, type |
| `generate_questions` | 智能出题 | knowledge_points, difficulty, quantity |
| `generate_variant` | 变式题生成 | original_question_id, quantity |
| `get_wrong_questions` | 获取错题 | student_id, limit |
| `create_training` | 创建训练 | student_id, question_ids |
| `submit_training` | 提交训练 | session_id, answers |
| `get_review_tasks` | 获取复习任务 | student_id |
| `complete_review` | 完成复习 | task_id, is_correct |
| `get_class_overview` | 班级概览 | class_id |
| `get_student_stats` | 学生统计 | student_id |
| `trigger_warning_check` | 触发预警检测 | class_id |

**工作量**: 约2-3天

---

### 方案B: 直接API集成

**原理**: ChemAI Agent通过HTTP调用ChemAI REST API

```
ChemAI Agent → REST API → ChemAI Backend
```

**优势**:
- 实现简单
- 兼容性最广

**配置示例**:
```bash
# Hermes配置ChemAI API
hermes config set chemai.api_url http://localhost:8001
hermes config set chemai.api_key xxx
```

**工作量**: 约1天

---

### 方案C: Skill技能封装

**原理**: 为ChemAI功能创建Chem Skill技能包

```
ChemAI Agent → Skill → ChemAI
```

**示例Skill**: `chemai-tutor.skill.md`

```markdown
# ChemAI Tutor Skill

## Description
高中化学AI助教，处理学生问题、生成练习、诊断障碍

## Triggers
- "出一道氧化还原题"
- "帮我看看这道题"
- "生成10道盐类水解练习"

## Actions
1. 识别学生问题类型
2. 调用ChemAI API生成响应
3. 返回结构化答案

## Tools
- ocr_recognize
- generate_questions
- get_diagnosis
```

**工作量**: 约3-4天

---

## 三、场景化集成方案

### 场景1: 智能助教对话

**描述**: 学生通过Telegram/Discord向ChemAI Agent提问化学问题

```
学生(Telegram) → ChemAI Agent → ChemAI(OCR/诊断/出题) → 回复学生
```

**功能点**:
- 学生拍照发题 → Hermes调用`ocr_recognize`识别
- 识别后调用`get_diagnosis`获取障碍分析
- 根据诊断调用`generate_variant`生成变式练习

**指令示例**:
```
/ask 这道题怎么做
[上传图片]
```

---

### 场景2: 自动学情监控

**描述**: ChemAI Agent定时检查学生学情，异常时通知

```
Hermes Cron(每日8:00) → ChemAI预警检测 → 通知教师/家长
```

**功能点**:
- `trigger_warning_check`检测异常
- 根据预警级别推送到不同渠道
- Telegram通知教师: "3班张三连续3天未登录"

**Cron配置**:
```bash
hermes cron add "每天8点检查学生学情" \
  --action "call chemai.check_warnings" \
  --platform telegram
```

---

### 场景3: 家长周报推送

**描述**: 每周五ChemAI Agent汇总学生周报推送给家长

```
Hermes Cron(周五18:00) → ChemAI获取周报 → 推送家长
```

**功能点**:
- 批量获取学生周报
- 生成自然语言总结
- 通过Telegram/Email推送

**Cron配置**:
```bash
hermes cron add "每周五18点推送家长周报" \
  --action "call chemai.send_weekly_reports" \
  --platform telegram
```

---

### 场景4: 自适应复习调度

**描述**: ChemAI Agent管理复习任务，适时提醒学生

```
Hermes Cron → ChemAI获取到期复习 → 提醒学生 → 收集结果 → 更新复习计划
```

**功能点**:
- 每日检查复习任务
- 按时提醒学生
- 收集完成结果
- 更新复习间隔(艾宾浩斯)

**Cron配置**:
```bash
hermes cron add "每天20点复习提醒" \
  --action "call chemai.review_reminder" \
  --platform telegram
```

---

### 场景5: 错题强化训练

**描述**: 学生错题被标记后，Hermes自动生成强化计划

```
错题标记 → Hermes生成变式题 → 推送给学生 → 完成后更新状态
```

**功能点**:
- `get_wrong_questions`获取错题
- `generate_variant`生成变式
- `create_training`创建训练
- 追踪训练效果

---

## 四、实施计划

### Phase 1: MCP Server基础 (2天)

**目标**: 将ChemAI核心功能暴露为MCP工具

**任务**:
1. [ ] 创建`app/mcp/`目录结构
2. [ ] 实现`mcp_server.py` - FastMCP服务器
3. [ ] 注册OCR/出题/诊断/预警等工具
4. [ ] 本地测试MCP连接

**文件**:
```
app/mcp/
├── __init__.py
├── server.py          # MCP服务器
├── tools/            # 工具定义
│   ├── __init__.py
│   ├── ocr.py
│   ├── question.py
│   ├── diagnosis.py
│   ├── warning.py
│   └── review.py
└── utils.py
```

---

### Phase 2: Chem Skill封装 (2天)

**目标**: 创建ChemAI Tutor技能包

**任务**:
1. [ ] 创建`~/.hermes/skills/chemai-tutor/`
2. [ ] 编写`SKILL.md`
3. [ ] 定义触发词和响应模板
4. [ ] 配置工具映射

**文件**:
```
~/.hermes/skills/chemai-tutor/
├── SKILL.md
├── prompts/
│   ├── diagnose.md
│   ├── question.md
│   └── review.md
└── examples/
```

---

### Phase 3: Cron任务配置 (1天)

**目标**: 配置定时任务实现自动化

**任务**:
1. [ ] 配置每日学情检查
2. [ ] 配置复习提醒
3. [ ] 配置周报推送
4. [ ] 测试各渠道推送

---

### Phase 4: 对话集成 (1天)

**目标**: 实现学生对话交互

**任务**:
1. [ ] 配置Telegram/Discord Bot
2. [ ] 集成ChemAI Skill到消息流
3. [ ] 测试拍照识别对话
4. [ ] 测试问答对话

---

## 五、推荐实施路径

### 快速验证 (方案B - 1天)

如果想快速验证效果，建议先采用**方案B直接API集成**:

```bash
# 1. 在ChemAI后端添加API Key认证
# 2. 在Hermes配置API调用
hermes tools add http-request \
  --name "chemai-ocr" \
  --url "http://localhost:8001/api/ocr/recognize/base64"
```

### 完整方案 (方案A+场景1 - 3天)

**推荐**:

1. **Day 1**: 实现MCP Server基础
2. **Day 2**: 封装Skill + Telegram集成
3. **Day 3**: Cron配置 + 完整测试

---

## 六、注意事项

1. **API认证**: 所有调用需认证，建议使用JWT或API Key
2. **错误处理**: MCP调用需有超时和重试机制
3. **数据隔离**: 学生敏感数据需加密传输
4. **消息网关**: Telegram在大陆需代理，Discord/Email更稳定
5. **成本控制**: LLM调用需计量，避免过度使用

---

## 七、决策点

请确认:

1. **集成方案选择**:
   - A: MCP协议（推荐，2-3天）
   - B: 直接API（快速，1天）
   - C: Skill封装（完整，3-4天）

2. **优先场景**:
   - 场景1: 智能助教对话
   - 场景2: 自动学情监控
   - 场景3: 家长周报推送
   - 场景4: 自适应复习调度
   - 场景5: 错题强化训练

3. **消息平台**:
   - Telegram（功能强，需代理）
   - Discord（稳定，需科学上网）
   - Email（简单，但即时性差）

---

*文档版本: V1.0*
*创建日期: 2026-04-24*
