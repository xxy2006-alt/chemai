## ADDED Requirements

### Requirement: Agent 聊天主界面
系统 SHALL 将首页替换为 Agent 聊天界面，包含消息流、输入区、快捷提问、状态栏和侧边栏。

#### Scenario: 发送消息并接收回复
- **WHEN** 用户在输入框输入"你好"并点击发送
- **THEN** 消息流显示用户消息气泡，Agent 流式回复逐字显示

#### Scenario: 快捷提问
- **WHEN** 首页无聊天记录时
- **THEN** 显示 6 个快捷提问芯片：配平方程式、出3道题、模拟实验、讲概念、查真题、错题诊断

#### Scenario: 工具调用可视化
- **WHEN** Agent 调用 Skill（如 balance_equation）
- **THEN** 显示 ToolResultCard（可折叠卡片，左侧彩色边框，展示工具名、耗时、结果）

#### Scenario: AgentStatusBar
- **WHEN** Agent 正在处理请求
- **THEN** 底部显示状态栏：当前阶段（思考中/执行中/回复中）+ 工具名 + 耗时

### Requirement: 侧边栏功能入口
侧边栏 SHALL 保留现有功能入口（题库管理、学情面板、考试管理、学生管理），点击后跳转到对应功能页面。

#### Scenario: 从聊天切换到题库
- **WHEN** 用户点击侧边栏"题库管理"
- **THEN** 主区域切换为题目库页面，保留侧边栏
