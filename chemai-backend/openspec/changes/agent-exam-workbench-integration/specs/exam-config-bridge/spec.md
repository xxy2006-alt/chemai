## ADDED Requirements

### Requirement: exam-v2 receives and applies exam-config populate data
系统 SHALL 在 `exam-v2.html` 的 bridge handler 中处理 `populate.target === "exam-config"`，预填所有考试工作台字段并自动调用 `aiGenerate()`。

#### Scenario: All fields pre-filled from bridge data
- **WHEN** bridge 收到 `populate.target="exam-config"`，data 包含 `knowledge_points: ["氧化还原"]`, `difficulty: "hard"`, `types: [{val: "single_choice", active: true, qty: 3}]`, `variant_source_id: "q_2024_001"`, `selectedFolder: "qset_001"`
- **THEN** `this.kps` 中"氧化还原"被激活
- **AND** `this.difficulty` 设为 `"hard"`
- **AND** `this.types` 中选择题被激活且数量设为 3
- **AND** `this.variantQid` 设为 `"q_2024_001"`，`this.useVariant` 设为 `true`
- **AND** `this.selectedFolder` 设为 `"qset_001"`
- **AND** `this.tab` 切换到 `"workbench"`，`this.sourceMode` 切换到 `"ai"`

#### Scenario: Auto-trigger generation after pre-fill
- **WHEN** bridge `exam-config` 处理完成
- **THEN** `this.aiGenerate()` 在 `$nextTick` 中被自动调用
- **AND** 页面显示生成 loading 状态
- **AND** 生成完成后题目展示在页面上

#### Scenario: Unknown fields are silently ignored
- **WHEN** bridge data 包含未定义的字段
- **THEN** 已定义字段正常预填，未定义字段被忽略，不抛出异常

### Requirement: Agent JS persists conversation_id across pages
系统 SHALL 在 `agent.js` 中将当前 `conversation_id` 存入 `sessionStorage`，在聊天页加载时恢复。

#### Scenario: cid saved before navigation
- **WHEN** Agent 发送 `navigate` SSE 事件导致页面跳转
- **THEN** 跳转前 `sessionStorage.setItem('chemai_active_cid', currentCid)` 被调用

#### Scenario: cid restored on chat page load
- **WHEN** 用户从考试工作台返回聊天页
- **THEN** 聊天页从 `sessionStorage.getItem('chemai_active_cid')` 读取 `cid`
- **AND** 后续 API 请求使用该 `cid`
