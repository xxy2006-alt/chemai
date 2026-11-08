# 智辅化学（ChemAI）

面向中学化学教学的 AI 辅助平台：智能出题、答题卡 OCR 批改、学情诊断、个性化练习与家校协同。

## 目录结构

```
.
├── chemai-backend/          # 主应用（FastAPI 后端 + React 前端 + LangGraph Agent）
│   ├── app/                 #   后端 API / 服务 / 模型
│   ├── agent/               #   LangGraph Agent（v2 单 Agent 推荐）
│   ├── frontend/            #   React 前端（三端同一 SPA）
│   ├── chem_skills/         #   化学领域技能（出题 / 解析 / 批改）
│   ├── evals/               #   评测与回归测试
│   ├── tests/               #   pytest 测试
│   ├── scripts/             #   一次性脚本（数据导入 / 架构图生成 / 回滚）
│   ├── design/              #   设计三端分册（学生 / 教师 / 家长），总册 DESIGN.md 在 backend 根
│   ├── design-upgrade/      #   2026-09 界面升级工作区（提案 / 备选 / 归档）
│   ├── openspec/            #   OpenSpec 变更提案与规格（全仓库唯一实例）
│   ├── docs/adr/            #   ADR 架构决策记录（0001-0017）
│   └── data/                #   运行时数据（chromadb / 题库 / 审计，不入库）
├── UI组件/                   # 设计系统 HTML deck 原型
├── curriculum/              # 课程资料（需求调研归档 / 草稿）
├── docs/                    # 项目级文档（PRD / 架构图 / 评测框架 / 历史归档）
├── third_party/             # 第三方源码（mineru：PDF 解析工具，源码运行方式）
├── 桌面应用/                 # 桌面端打包脚本（build_exe.py，exe 产物不入库）
└── .archive/                # 旧仓库历史归档（git bundle，见下）
```

## 快速开始

后端（FastAPI + Agent）说明见 [`chemai-backend/README.md`](chemai-backend/README.md)。

## Git 说明

- 本仓库为 2026-07 整理后的**统一仓库**，默认分支 `main`。
- 整理前的历史（187 个提交、5 分支、2 标签）已打包为
  `.archive/chemai-backend-history.bundle`，需要查看/恢复旧历史时：

  ```bash
  # 查看 bundle 内容
  git bundle list-heads .archive/chemai-backend-history.bundle
  # 恢复到本地仓库（目录内即旧仓库的全部历史）
  git clone .archive/chemai-backend-history.bundle chemai-backend-history
  ```

- 不入库的目录：`node_modules`、`.gstack/`、`.workbuddy/`、`桌面应用/*.exe`、
  各类缓存与日志、`chemai-backend/data/` 下的运行时数据。
- `chemai.db`（后端主库）被 git 跟踪，但它是 WAL 模式的活库：**提交或切换
  分支涉及它之前，先跑 `python scripts/db_checkpoint.py`**（在
  `chemai-backend/` 下）把 WAL 落盘，否则提交到的可能不是最新状态。
