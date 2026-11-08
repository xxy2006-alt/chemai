## Why

当前 index.html 的聊天体验已经很好——消息气泡、ToolCard、快捷提问、输入框都在。差距只有两处：
- 侧边栏是页面导航链接（考试工作台/答题卡/诊断/学生），对话历史藏在 H 书签抽屉里
- 缺少 Agent 状态栏显示当前 tool + 耗时

现在 Agent 页面驱动已实现——用户通过对话就能跳转到各个页面，侧边栏的导航链接可以替换为对话历史+小图标手动入口。

## What Changes

| 区域 | 当前 | 目标 |
|------|------|------|
| 侧边栏 | 4 个页面导航链接 + H 书签抽屉（隐藏） | 对话历史列表 + 新建对话 + 3 个小图标手动入口 |
| Agent 状态栏 | 无 | 输入框下方：当前 tool 名称 + 耗时 |
| 响应式 | 固定 240px 侧边栏 | 移动端侧边栏收起 |

### 不动的（保持现状）
- 聊天消息流（气泡 + ToolCard）——已完美
- 快捷提问 chips——已完美
- 输入框 + 发送——已完美
- agent.js SSE 事件处理——不改协议

## Tasks

- [x] 1. 侧边栏重构：删掉页面导航链接，把 H 抽屉的对话列表搬到侧边栏，底部留 3 个 Material Symbols 图标按钮作为手动入口<br>
  `edit_note` → 考试工作台 / `clinical_notes` → 障碍诊断 / `group` → 学生管理
- [x] 2. 删掉 H 书签面板的 HTML/CSS（功能已移到侧边栏）
- [x] 3. Agent 状态栏：输入框下方一行 `tool_name · X.Xs`，从 SSE tool_call/tool_result 事件提取
- [x] 4. 响应式适配：<=768px 时侧边栏默认隐藏，汉堡按钮呼出

## Impact

- **Files changed**: `frontend/index.html`, ~80 lines
- **Breaking**: 无。聊天功能完整保留，侧边栏内容替换
- **Dependencies**: 无。Material Symbols 已在 index.html L10 加载
