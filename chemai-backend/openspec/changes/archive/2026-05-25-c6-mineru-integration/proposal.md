## Why

MinerU 是 PDF 解析工具，已在项目中使用（一次性提取了 250 道真题）。但当前是手动命令行操作，需要集成到产品中：老师上传试卷 PDF → MinerU 自动解析 → 化学审核 → 入库。闭环为 Skill。

## What Changes

- 新增 `app/services/mineru_service.py` — MinerU HTTP 客户端封装
- 新增 `docker/docker-compose.yml` — MinerU 容器 + ChemAI 编排
- 新增 `docker/mineru/Dockerfile` — MinerU 独立容器（基于官方镜像）
- MinerU 作为 `import_exam_paper` Skill 的一部分（C4 实现）

## Capabilities

### New Capabilities
- `mineru-service`: MinerU 试卷解析 HTTP 服务封装，提取结构化题目

### Modified Capabilities
- (无)

## Impact

- `app/services/mineru_service.py` — 新增
- `docker/` — 新增 Docker 配置
- 依赖：MinerU Docker 容器独立运行
