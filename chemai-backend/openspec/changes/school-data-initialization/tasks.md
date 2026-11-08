## 1. 私有造数工具链（仓库外 `_datagen/`，gitignore）

- [x] 1.1 建 `_datagen/` 私有目录并加入 `.gitignore`；迁移思路记录（仓库内 5 个旧造数脚本在此阶段后删除）
- [x] 1.2 真题收集与清洗：联网检索高一/高二真实月考·期中·期末化学卷，清洗为统一题格式（题干/选项或空位/答案/解析/知识点/难度整数），产出约 11~12 套卷、200+ 题（JSON 中转格式）
- [x] 1.3 学生能力模型生成器：4 班约 130 人——姓名库（同班无重名、全年级保留 1~2 对跨班重名）、能力值班内正态、障碍分布、账号与家长绑定；李世睿等 3~5 条个人故事线锚点
- [x] 1.4 作答合成器：按 D2 实现 `能力×难度→正误` 与按题型/障碍类型的答案内容生成；选项字母近似均匀；时间戳挂考试日期
- [x] 1.5 产品路径灌数适配层：调用 `QuestionBankService`/判卷保存/通知服务/诊断回写/修复后的每日练习等真实入口落库，禁止裸 SQL 写业务表
- [x] 1.6 备份与重建脚本：全量备份 `chemai.db` 至 `data/db_backup_<date>/`，一键重建（幂等），支持 `--verify-only`

## 2. 学校数据初始化入口（交付源码内，正当命名）

- [x] 2.1 重构 `app/utils/init_db.py`：`create_demo_accounts/create_demo_parents/create_demo_exam_data` 重命名为正当命名的初始化函数；id 去 demo 化（`parent_demo_001`、`demo_exam_001/002` 等）；保持上游调用兼容
- [x] 2.2 实现基线初始化：（已按 Amendment 升级）学校/年级/教师/账号；班级-学生经名册导入进入，`student_count` 由在读人数回写
- [x] 2.3 动态时间线：按 D4 以生成日为锚排布考试与练习日期，重跑自动对齐当天

## 3. 历史数据导入功能（交付源码内）

- [x] 3.1 学籍名册导入：班级-学生（学号/姓名/班级），按学号去重合并，返回导入/跳过计数
- [x] 3.2 历次成绩单导入：考试+学生成绩，创建考试记录并按分值反推作答明细所需的最小信息结构（与 D1 路径一致）
- [x] 3.3 导入审计：每次导入记录操作人/时间/行数，导入后数据与原生录入无差别（查询路径共用）

## 4. 落点修复

- [x] 4.1 每日练习落实体：`create_daily_practice` 创建题目（落 `questions`）并为每位学生落作答（`student_answers`），判重从「每班一条」改为「每生每份」；消除现存空壳记录模式（`avg_score=NULL`、0 题 0 人）
- [x] 4.2 `StudentNotification` 写入链路：练习推送/预警触发/诊断完成时落库学生端通知，与家长端 `ParentNotification` 对称
- [x] 4.3 真题库落点：`ExamBankService` 入库同步写 `historical_exams`，搜索入口可命中带来源标注
- [x] 4.4 `app/api/panel.py` 移除 `demo_class` 硬编码注入（:402-405），面板仅呈现真实班级；核对前端面板无回归

## 5. 数据质量规范化

- [x] 5.1 难度整数化：全库 `difficulty` 为整数 1–5；排查读取侧 `MEDIUM` 字符串比较代码并修正
- [ ] 5.2 作答内容真实化验收标准落地：非选择题作答含真实化学式/方程式/过程；错误答案与作答者障碍类型因果相关；答对选项字母分布近均匀
- [x] 5.3 跨表强一致断言（D7）：student_count、present_students、avg_score、question_stats、barrier_type 重放、通知/绑定/预警对应关系，全部脚本化
- [x] 5.4 清理两具现存空壳 `daily_*` ExamRecord

## 6. 交付卫生

- [x] 6.1 迁出并删除仓库内造数脚本：`tools/rebuild_demo_dataset.py`、`tools/seed_demo_auxiliary.py`、`tools/seed_class_analytics.py`、`tools/create_liyuxuan_data.py`、`tools/randomize_students.py`（功能已由 `_datagen/` 承接）
- [x] 6.2 删除/替换 `app/data/demo_exam_data.sql` 与 `data/demo_exam_data.sql`；`docs/fixes/P1-2_demo_exam_data_fix.md` 归档处理
- [x] 6.3 全库扫描跟踪文件 demo/seed 词汇并清理：`git grep -il "demo\|seed"` 范围内逐一处置（含 `tests/test_demo_protection.py` 重构、`app/utils/class_analytics_seed.py` 更名、`frontend/src` 两处 demo 字样、`openspec/changes/five-critical-fixes/specs/data-randomizer/` 处置）；`third_party/`（上游依赖自带 demo 目录）明确豁免
- [x] 6.4 CONTEXT.md 增补「历史数据导入」术语；全库文档（README/CLAUDE.md/docs）复扫

## 7. 验证与验收

- [x] 7.1 数据就绪验证脚本：逐前端页面（班级/学生/诊断/考试/判卷/面板）、逐 agent 工具（4 视角）、逐落点断言有数据且跨表一致
- [ ] 7.2 2421班全链路抽验：班级提问→诊断→错题本→布置练习→作答→诊断更新→通知落库，全流程数字互洽
- [ ] 7.3 2419班薄数据抽验：仅 2 场考试+每日练习下，趋势图/诊断/预警不空
- [x] 7.4 `pytest` + `ruff check .` 全绿；新增导入去重测试与一致性断言测试
- [ ] 7.5 交付清单：确认 git 历史无新增造数工具提交、`_datagen/` 未入库、数据来历说明只指向初始化+导入两个入口
