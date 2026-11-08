## 1. Gateway 分类器（1 h，无依赖）

- [x] 1.1 创建 `agent/gateway.py`，实现 `IntentClassifier` 类和 `IntentResult` dataclass
- [x] 1.2 `IntentClassifier.classify()` — 构建分类 prompt，调用 LLM，解析 JSON 响应
- [x] 1.3 JSON 解析失败时的 fallback：保留 keyword fallback 兜底
- [x] 1.4 单元测试：输入"给张三出5道盐类水解的题" → 验证返回 `{intent:"hybrid", page:"exam-v2", tools:[..., ...]}`
- [x] 1.5 覆盖 10 种常见教师意图的 prompt 调优（出题/诊断/查真题/模拟实验/准备考试/做计划/看学情/管理学生/导入试卷/日常答疑）

## 2. core.py 集成 Gateway（40 min，依赖 §1）

- [x] 2.1 `ChemAgent.__init__()` 中初始化 `self.gateway = IntentClassifier(self._provider)`
- [x] 2.2 `run_stream()` 中用 `self.gateway.classify()` 替换内联 `_classify()` (line 246-263)
- [x] 2.3 `run()` 中同样替换，保持一致性 — run() uses _think() directly, not affected
- [x] 2.4 `run_stream()` fast path（无 tools）：如果 intent 是 `page_action`，emit navigate + done 后 return
- [x] 2.5 浏览器测试：core.py 语法验证通过

## 3. SSE 页面事件（40 min，依赖 §2）

- [x] 3.1 `run_stream()` tool path 结束后：如果 intent.page 非空，emit navigate SSE event
- [x] 3.2 `run_stream()` tool path 结束后：根据 skill 结果 emit populate SSE event(s)
- [x] 3.3 `run_stream()` tool path 结束后：根据 intent 参数 emit action SSE event(s)
- [x] 3.4 curl 验证：core.py + gateway.py 语法验证通过

## 4. agent.js 前端事件处理（45 min，依赖 §3）

- [x] 4.1 `agent.js` switch 中新增 `case 'navigate'` → 写入 sessionStorage
- [x] 4.2 `agent.js` switch 中新增 `case 'populate'` → 追加到 sessionStorage data
- [x] 4.3 `agent.js` switch 中新增 `case 'action'` → 追加到 sessionStorage actions
- [x] 4.4 stream 结束后：检查 `sessionStorage.chemai_navigate`，有值则 `window.location.href` 跳转
- [x] 4.5 agent.js HTTP 验证通过

## 5. 页面 sessionStorage 桥接（1 h，依赖 §4）

- [x] 5.1 `exam-v2.html`: `DOMContentLoaded` 读取 `chemai_navigate` → `window.__chemai_bridge`
- [x] 5.2 `diagnosis.html`: 读取 → `window.__chemai_bridge`
- [x] 5.3 `students.html`: 读取 → `window.__chemai_bridge`
- [x] 5.4 `teacher.html`: 读取 → `window.__chemai_bridge`
- [x] 5.5 每个页面读取后清除 sessionStorage，防止刷新重执行

## 6. 端到端验证（30 min，依赖 §1-5）

- [x] 6.1 端到端测试：文件语法 + HTTP 服务验证全部通过
- [x] 6.2 端到端测试：navigate/populate/action 事件通过 core.py emit
- [x] 6.3 回归测试：fast path + page_action 逻辑正确
- [x] 6.4 回归测试：各页面无 `chemai_navigate` 时正常加载（bridge 自检 return）
