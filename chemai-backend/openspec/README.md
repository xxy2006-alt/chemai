# ChemAI 补全计划

## 6 个 Change 总览

```
infra-foundation          mineru-pipeline         adaptive-diagnosis-engine
    │                          │                          │
    │ 0.5天 / 4 tasks          │ 1天 / 4 tasks            │ 2天 / 4 tasks
    │                          │                          │
    │ 装依赖 修LLM 验OCR       │ PDF→题目入库全链路       │ F4诊断 F5自适应 全题型
    │                          │                          │
    └──────────┬───────────────┘──────────────┬───────────┘
               │                              │
               ▼                              ▼
        export-and-dashboard           agent-activation
               │                              │
               │ 1.5天 / 4 tasks              │ 1天 / 3 tasks
               │                              │
               │ 导出Word/PDF + 前端面板       │ 6 Skills联通 + 决策链
               │                              │
               └──────────────┬───────────────┘
                              │
                              ▼
                      production-readiness
                              │
                              │ 1.5天 / 6 tasks
                              │
                              │ 加固 + 性能 + 安全 + 评测
```

## 执行顺序

```
1. infra-foundation          ← 先做, 不依赖其他
2. mineru-pipeline           ← 依赖 1 的 MinerU 装完
3. adaptive-diagnosis-engine ← 依赖 1 的 LLM httpx 改造完
4. export-and-dashboard      ← 依赖 3 的诊断/出题真实数据就绪
5. agent-activation          ← 依赖 1,2,3 的服务层就绪
6. production-readiness      ← 全部做完后加固
7. gateway-router-refactor   ← 独立执行，不依赖其他 change
```

## 各 Change 范围

| Change | 估时 | Tasks | 核心交付 |
|--------|------|-------|---------|
| infra-foundation | 0.5天 | 4 | 所有组件正常启动, 零 error |
| mineru-pipeline | 1天 | 4 | PDF→题目自动入库, LaTeX化学式 |
| adaptive-diagnosis-engine | 2天 | 4 | 个性化诊断+自适应出题, 非mock |
| export-and-dashboard | 1.5天 | 4 | Word/PDF导出 + 面板可视化 |
| agent-activation | 1天 | 3 | Agent自然语言→完成任务 |
| production-readiness | 1.5天 | 6 | 加固/安全/评测全部通过 |

| vue-migration | 1天 | 6 | Vue 3 迁移 + CSS 抽离 + Chips + 学情面板 |
| bugfix-bank-save | done | - | 题库 localStorage→API, 保存/删除按钮 |
| gateway-router-refactor | 0 | 6 | Gateway 两分类 + tool 自路由 |
| langgraph-migration | done | 34 | ReAct agent (create_react_agent + interrupt + SSE 适配 + D8/D9 护栏) |

**总计: 8.5 个工作日** (含新增 vue-migration)
