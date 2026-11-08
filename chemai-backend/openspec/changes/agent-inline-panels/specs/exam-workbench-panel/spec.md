## ADDED Requirements

### Requirement: Panel renders full interactive controls
系统 SHALL 在 `show_exam_workbench` 触发时渲染完整交互面板，包含知识点选择、题型配置、难度、变种蓝本、文件夹选择等控件。

#### Scenario: Knowledge point chips are interactive
- **WHEN** 面板渲染且加载了知识点列表
- **THEN** 用户可输入关键词过滤知识点
- **AND** 用户可点击 chip 切换选中/取消
- **AND** 选中的知识点显示在已选区域

#### Scenario: Question type chips with quantity input
- **WHEN** 面板渲染
- **THEN** 5 种题型（选择题/填空题/计算题/实验题/推断题）以 chip 形式展示
- **AND** 点击 chip 切换激活/非激活状态
- **AND** 激活时显示数量输入框（min=1, max=10）

#### Scenario: Difficulty dropdown works
- **WHEN** 用户从难度下拉中选择
- **THEN** 面板内部 `difficulty` 状态更新为所选值

### Requirement: Generate button calls question API
系统 SHALL 在用户点击"AI 出题"按钮时，按面板当前配置调用 `POST /api/question/generate`。

#### Scenario: Questions generated per type
- **WHEN** 用户配置选择题×3 + 填空题×2 并点击"AI 出题"
- **THEN** 面板对每种题型分别调用 API
- **AND** 所有 API 完成后题目合并展示在面板中

### Requirement: Questions display with edit/save/delete
系统 SHALL 在面板中展示生成的题目，每道题有编辑、保存、删除操作。

#### Scenario: Save question to bank
- **WHEN** 用户点击某道题的"保存"按钮
- **THEN** 面板调用 `POST /api/exam-bank/import-questions`
- **AND** 保存成功后按钮变为"已保存"并禁用
