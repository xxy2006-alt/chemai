## 1. MinerU 服务封装

- [ ] 1.1 实现 `mineru_service.py` — `MinerUClient` 类（httpx HTTP 客户端）
- [ ] 1.2 实现 `extract_questions()` — 上传 PDF，解析为结构化题目
- [ ] 1.3 实现错误处理 — 超时、连接失败、非试卷 PDF
- [ ] 1.4 验证：启动 MinerU Docker，调 extract_questions 获取题目

## 2. Docker 编排

- [ ] 2.1 创建 `docker/docker-compose.yml` — MinerU + ChemAI 服务编排
- [ ] 2.2 创建 `docker/mineru/Dockerfile` — 基于官方 MinerU 镜像
- [ ] 2.3 验证：`docker-compose up` 两个服务正常启动
