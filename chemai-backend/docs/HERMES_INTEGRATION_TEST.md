# ChemAI × ChemAI Agent 集成测试指南

## 测试前准备

### 1. 启动 ChemAI 后端

```bash
cd D:\化学\chemai-backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 2. 验证 MCP Server 运行

```bash
curl http://localhost:8001/api/mcp/tools
```

预期返回：
```json
{
  "success": true,
  "tools": [
    {"name": "ocr_recognize", ...},
    ...
  ]
}
```

### 3. 启动 ChemAI Agent

```bash
hermes
```

---

## 场景测试

### 场景 1: 智能出题

**测试命令**：
```
出一道关于氧化还原反应的练习题
```

**预期流程**：
1. Hermes 理解用户需求
2. 调用 `generate_questions` 工具
3. 返回格式化题目列表

**验证点**：
- [ ] 返回的题目包含氧化还原相关知识点
- [ ] 题目格式正确（选择题有 A/B/C/D 选项）
- [ ] 响应在 10 秒内完成

---

### 场景 2: OCR 识别

**测试命令**：
```
[上传一张化学题目图片]
这道题怎么做？
```

**预期流程**：
1. Hermes 收到图片
2. 调用 `ocr_recognize` 识别图片内容
3. 调用 `diagnose_question` 分析障碍类型
4. 返回诊断结果和解答思路

**验证点**：
- [ ] 图片被正确识别出文字
- [ ] 障碍类型判断正确
- [ ] 解答思路清晰

---

### 场景 3: 错题强化训练

**测试命令**：
```
我想做错题训练
```

**预期流程**：
1. Hermes 调用 `get_wrong_questions` 获取错题
2. 调用 `generate_variant` 生成变式
3. 创建训练会话
4. 逐题推送，学生作答后提交

**验证点**：
- [ ] 返回学生错题列表
- [ ] 变式题与原题有差异但同类
- [ ] 训练结果正确记录

---

### 场景 4: 复习任务

**测试命令**：
```
今天有哪些复习任务？
```

**预期流程**：
1. Hermes 调用 `get_review_tasks`
2. 返回到期复习任务列表
3. 学生完成复习后调用 `complete_review`

**验证点**：
- [ ] 返回正确的复习任务数量
- [ ] 任务包含题目内容和知识点
- [ ] 完成后更新复习间隔

---

### 场景 5: 学情查询

**测试命令**：
```
我的学习情况怎么样？
```

**预期流程**：
1. Hermes 调用 `get_student_stats`
2. 汇总关键指标
3. 用自然语言描述

**验证点**：
- [ ] 返回正确率、练习数量等数据
- [ ] 障碍分布数据准确
- [ ] 响应自然流畅

---

### 场景 6: 预警检测（需配置班级）

**测试命令**：
```
检查一下3班的学情
```

**预期流程**：
1. Hermes 调用 `trigger_warning_check`
2. 检测异常学生
3. 若有异常，推送预警通知

**验证点**：
- [ ] 能识别3天未登录学生
- [ ] 能识别成绩下降>10%学生
- [ ] 能识别错题率>50%学生

---

## Telegram 集成测试

### 1. 配置 Telegram Bot

在 Hermes 中配置 Telegram：

```bash
hermes config set telegram.bot_token YOUR_BOT_TOKEN
hermes platforms add telegram
```

### 2. 测试消息发送

```bash
hermes send "ChemAI 测试消息" --platform telegram --chat-id YOUR_CHAT_ID
```

### 3. 验证 Cron 任务推送

配置每日 8 点学情检查后，次日 8 点检查是否有推送。

---

## 调试命令

### 查看 MCP 连接状态

```bash
hermes tools list | grep chemai
```

### 手动调用 MCP 工具

```bash
hermes tools call chemai.generate_questions \
  --knowledge_points "氧化还原反应" \
  --difficulty medium \
  --quantity 5
```

### 查看 Cron 任务执行日志

```bash
hermes logs --cron --tail 100
```

---

## 常见问题

### Q: MCP 工具调用超时

**解决**：检查 ChemAI 后端是否运行在 8001 端口，确认网络连接。

### Q: Hermes 无法识别 chemai skill

**解决**：确认 SKILL.md 放在 `~/.hermes/skills/chemai-tutor/` 目录，重启 Hermes。

### Q: Telegram 消息发送失败

**解决**：确认 Bot Token 正确，Chat ID 可用，网络代理（如需要）。

### Q: LLM 返回格式错误

**解决**：MCP Server 有 JSON 解析容错，但建议检查 LLM 服务是否正常。

---

## 测试检查清单

| 功能 | 状态 | 备注 |
|------|------|------|
| MCP Server 启动 | ⬜ | |
| 工具列表获取 | ⬜ | |
| 智能出题 | ⬜ | |
| OCR 识别 | ⬜ | |
| 错题强化 | ⬜ | |
| 复习任务 | ⬜ | |
| 学情查询 | ⬜ | |
| 预警检测 | ⬜ | |
| Telegram 推送 | ⬜ | |
| Cron 定时任务 | ⬜ | |

---

*文档版本: V1.0*
*创建日期: 2026-04-24*
