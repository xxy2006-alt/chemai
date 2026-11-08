## 1. Backend: SSE Adapter

- [ ] 1.1 `feed()`: 子Agent `on_chain_start` 时 emit `data: <think>\n\n`
- [ ] 1.2 `feed()`: 子Agent `on_chain_end` (depth→0) 时 emit `data: </think>\n\n`
- [ ] 1.3 `feed()`: 移除 `subagent_start`/`subagent_end` 事件 emit（保留 `subagent_tool` 在 think 块内）
- [ ] 1.4 `finalize()`: 恢复 `result_text` 流式分块（每 8 字符），作为 `text` 事件输出
- [ ] 1.5 `finalize()`: 移除 `subagent_end` 组装和 emit（已改为 feed 中 emit）

## 2. Backend: Cleanup

- [ ] 2.1 移除 `_sub_agent_start`/`_active_sub_agent`/`_tool_count` 实例变量（仅需 depth 跟踪和 think 标记 emit）

## 3. Frontend: Think Panel

- [ ] 3.1 SSE reader 新增 `<think>` 检测：`payload === '<think>'` 时创建面板 DOM，设置 `_inThink = true`
- [ ] 3.2 SSE reader 新增 `</think>` 检测：关闭面板（折叠），设置 `_inThink = false`
- [ ] 3.3 `_inThink` 状态下，`tool_call`/`tool_result`/`subagent_*` 事件渲染到面板内（复用现有 `addToolCard` 等）
- [ ] 3.4 面板 HTML：标题行"思考过程" + 折叠/展开 chevron + 内容区，默认折叠

## 4. Frontend: Cleanup

- [ ] 4.1 删除 `addSubAgentCard()` 函数
- [ ] 4.2 删除 `subAgentCards` 变量
- [ ] 4.3 删除 `subagent_start`/`subagent_tool`/`subagent_end` switch cases
- [ ] 4.4 删除 sub-agent 卡片相关 CSS

## 5. Version Bump

- [ ] 5.1 `index.html`: v=10 → v=11

## 6. Testing

- [ ] 6.1 配平方程式 → 工具卡片在折叠面板内，答案流式到对话框，无重复
- [ ] 6.2 搜索真题 → 搜索结果在面板内
- [ ] 6.3 面板点击展开/折叠正常
- [ ] 6.4 无 `text` 事件泄漏到面板内
