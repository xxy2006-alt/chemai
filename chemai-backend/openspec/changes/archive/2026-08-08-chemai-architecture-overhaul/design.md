## Context

ChemAI当前使用三层存储（SQLite业务数据 + ChromaDB向量 + LangGraph checkpoint），但三层之间存在断裂：AI生成的题目只存SQLite不入ChromaDB、向量搜索未接入真题检索、对话上下文硬截断、记忆系统碎片化。LangGraph 1.2.5已支持SqliteStore原生长期记忆后端，Delta Channels默认开启。

## Goals / Non-Goals

**Goals:**
- ChromaDB嵌入从MD5伪向量迁移到dashscope text-embedding-v3 API
- 真题搜索链路接入ChromaDB语义召回
- AI生成题目保存时同步写入exam_bank内存列表和ChromaDB
- 上下文管理从硬截断30条升级为TrimMessages + 15轮LLM摘要
- 引入LangGraph SqliteStore作为长期记忆后端（诊断/学习计划/教师偏好）
- 记忆工具注册到Agent（memory_student_get, memory_teacher_get）
- 诊断结果自动写回SqliteStore
- 删除pydantic_ai残余（_conversations消息历史、MemoryStack死代码）

**Non-Goals:**
- 不迁移到PostgreSQL（SQLite足以支撑当前规模）
- 不在ChromaDB新建student_memories collection（记忆全走SqliteStore）
- 不修改旧/api/agent/chat/stream端点（标记废弃但保留）
- 不重建丢失的238道真题（质量差，已废弃）

## Decisions

### D1: 嵌入模型用dashscope API而非本地sentence-transformers
- **选dashscope**: 你已有dashscope SDK（1.20.0），零新增依赖，零本地内存开销，中文embedding效果好
- **拒绝sentence-transformers**: 120MB本地模型，30秒首次加载，增加部署复杂度
- **回退**: dashscope调用失败时回退到MD5伪嵌入

### D2: 长期记忆用LangGraph SqliteStore而非自建SQLite表 + ChromaDB双写
- **选SqliteStore**: LangGraph原生支持，内置sqlite-vec语义搜索，与checkpointer统一编译，agent节点通过runtime.store自动获取
- **拒绝双写方案**: 维护两套同步逻辑，ChromaDB API与LangGraph不一致，增加复杂度

### D3: ChromaDB只做真题搜索
- ChromaDB保留exam_questions collection用于真题和AI生成题的向量搜索
- 记忆语义搜索走SqliteStore内置索引
- 职责边界清晰，不互相侵入

### D4: 上下文管理用TrimMessages而非全量摘要
- **先Trim后摘要**: 保留最近6条消息 + 条件保留含学生/诊断/考试数据的消息 + 30条消息触发LLM摘要
- **拒绝全量摘要**: 教师对话主题跳跃大，全量摘要混入无关话题

### D5: _conversations dict直接删除
- student_id从前端ChatRequest.student_id取
- Gateway分类器上下文从checkpointer提取
- /reset端点同步清checkpoint
- 不建替代方案

## Risks / Trade-offs

- [dashscope API依赖] → 网络不可用时embedding回退到MD5伪向量，语义搜索降级为无意义排序。启动自动索引时检测API可用性并告警
- [SqliteStore版本兼容] → langgraph 1.2.5 + checkpoint-sqlite 3.1.0经验证支持AsyncSqliteStore。锁定版本避免breaking change
- [_conversations删除影响Gateway] → Gateway分类器改用checkpointer提取最近2轮文本。需验证`_classify_and_narrow`在无message_history参数时正常工作
- [摘要LLM调用成本] → 每15轮触发一次，DeepSeek约$0.001/次，可忽略
- [ChromaDB collection重建] → 嵌入维度从768→1024，需删除旧collection重建。已有188KB数据量小，重建<1秒

## Migration Plan

1. Phase 1先部署（嵌入+向量搜索+保存即索引），验证搜索质量提升
2. Phase 2部署（上下文管理+pydantic_ai清理），验证多轮对话连续性
3. Phase 3部署（SqliteStore+记忆工具+写回），验证长期记忆功能
4. 每阶段独立可回滚，不互相阻塞
5. 旧chemai_checkpoints.db和chemai.db保留不删除

## Open Questions

- 无
