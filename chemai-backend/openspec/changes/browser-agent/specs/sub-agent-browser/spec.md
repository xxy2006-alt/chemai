## ADDED Requirements

### Requirement: Browser expert navigates and reads web pages
The browser_expert sub-agent SHALL have access to browse_navigate, browse_read, browse_click, browse_input, and browse_screenshot tools.

#### Scenario: Navigate to URL and read content
- **WHEN** browser_expert is queried with "打开 example.com 读取内容"
- **THEN** it invokes browse_navigate then browse_read, returning page title and text

#### Scenario: Click element on page
- **WHEN** browser_expert is queried with "点击'下一页'按钮"
- **THEN** it invokes browse_click with appropriate selector

#### Scenario: Input text into form field
- **WHEN** browser_expert is queried with "在搜索框输入'氧化还原'"
- **THEN** it invokes browse_input with selector and text

#### Scenario: Take page screenshot
- **WHEN** browser_expert is queried with "截取当前页面"
- **THEN** it invokes browse_screenshot and returns base64 PNG

### Requirement: Coordinator routes browser requests
The coordinator SHALL route browser-related user intents to browser_expert.

#### Scenario: Browser intent routed
- **WHEN** user says "帮我看一下这个网页的内容"
- **THEN** coordinator routes to browser_expert
