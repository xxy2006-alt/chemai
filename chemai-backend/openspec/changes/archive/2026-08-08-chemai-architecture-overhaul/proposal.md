## Why

AI生成的题目存入SQLite后搜索不到；Agent记忆系统碎片化（进程内存dict + 硬截断 + 废弃pydantic_ai格式）；ChromaDB嵌入用MD5伪向量无语义；向量搜索已实现但未接入真题检索链路。每次服务重启丢失对话上下文，教师无法跨对话获取学生历史诊断数据。

## What Changes

- **向量嵌入替换**: ChromaDB嵌入从MD5伪向量切换为dashscope text-embedding-v3 API
- **真题搜索接入向量**: `search_questions` 默认走ChromaDB语义召回，再结构化过滤
- **启动自动索引**: 服务启动时自动将真题库索引到ChromaDB
- **AI出题保存即索引**: `save_to_bank` 同步写入exam_bank内存列表 + ChromaDB向量索引
- **删除pydantic_ai残余**: 移除`_conversations` dict中的pydantic_ai消息格式，**BREAKING** `/api/agent/chat/stream`和`/api/agent/chat`旧端点标记废弃
- **智能上下文管理**: 硬截断30条消息替换为Trim（保留最近6条 + 条件保留诊断/学生数据 + 15轮LLM摘要）
- **长期记忆系统**: 引入LangGraph SqliteStore存储学生诊断历史、学习计划、教师偏好，内置sqlite-vec语义搜索
- **记忆工具注册**: `memory_student_get`、`memory_teacher_get`工具注册到Agent ReAct loop
- **诊断自动写回**: `diagnose_barrier`完成后自动将结果写入SqliteStore

## Capabilities

### New Capabilities
- `vector-search-integration`: ChromaDB dashscope嵌入替换 + search_questions向量召回 + 启动自动索引
- `question-save-indexing`: save_to_bank保存题目同步写入exam_bank内存 + ChromaDB
- `smart-context-management`: TrimMessages策略 + 15轮LLM摘要替代硬截断
- `long-term-memory`: LangGraph SqliteStore存储诊断/学习计划/教师偏好
- `memory-tools`: memory_student_get和memory_teacher_get Agent工具
- `diagnosis-writeback`: diagnose_barrier诊断结果自动持久化到Store

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

| 影响面 | 详情 |
|--------|------|
| `app/services/vector_search.py` | 嵌入函数替换为dashscope API |
| `app/services/exam_bank.py` | search_questions新增use_vector参数 |
| `agent/tools.py` | search_exam_bank默认向量搜索; save_to_bank保存即索引; 新增memory工具; diagnose_barrier写回 |
| `agent/channel/langgraph_channel.py` | 删除_conversations消息历史; 三处硬截断→trim_context; /reset同步清checkpoint |
| `agent/channel/fastapi_sse.py` | _extract_conversation_context接受通用dict; 删除pydantic_ai导入 |
| `agent/memory.py` | 删除to/from_pydantic_messages死代码 |
| `agent/context_manager.py` | **新文件** TrimMessages + LLM摘要 |
| `agent/langgraph_agent_v2.py` | create_chemai_agent接收SqliteStore参数 |
| `app/main.py` | 启动自动索引 + Store初始化/关闭钩子 |
| `requirements.txt` | 无需新增（dashscope已安装） |
