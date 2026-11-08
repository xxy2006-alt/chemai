# P5 后端未实现端点补齐确认

## 修复日期
2026-04-25

## 架构说明
本系统集成 ChemAI Agent，AI 分析类功能（障碍诊断、学习计划生成、报告生成、出题等）通过 `hermesService.execute(TaskType.xxx)` → Hermes Gateway 处理。本计划只补齐前端直接调用的 REST 数据 CRUD/检索端点。

## 修改内容

### P5-1：诊断模块 (`app/api/diagnosis.py`)
新增 5 个端点：
| 端点 | 功能 | 实现方式 |
|------|------|---------|
| `GET /api/diagnosis/plan/{student_id}` | 获取学生已有学习计划 | 从 Student.barrier_type + 答题记录查询 |
| `POST /api/diagnosis/{diagnosis_id}/feedback` | 提交诊断反馈 | 写入 OperationLog |
| `GET /api/diagnosis/history/{student_id}` | 诊断历史记录 | 按考试分组统计 barrier 分布 |
| `GET /api/diagnosis/class/{class_id}/stats` | 班级障碍分布统计 | 聚合全班 Student.barrier_type |
| `GET /api/diagnosis/class/{class_id}/kp/{kp}` | 知识点障碍分析 | 按知识点筛选 StudentAnswer + Question |

### P5-2：考试管理 (`app/api/exam.py`)
新增 3 个端点：
| 端点 | 功能 |
|------|------|
| `PUT /api/exam/{exam_id}` | 更新考试信息 |
| `DELETE /api/exam/{exam_id}` | 删除考试及关联数据 |
| `GET /api/exam/{exam_id}/result/{student_id}` | 获取学生考试结果 |

### P5-3：练习模块 (`app/api/practice.py`)
新增 6 个端点：
| 端点 | 功能 |
|------|------|
| `GET /api/practice/{practice_id}/questions` | 获取练习题目列表 |
| `GET /api/practice/history/{student_id}` | 学生练习历史 |
| `GET /api/practice/wrong/list` | 全局错题列表 |
| `POST /api/practice/wrong/{question_id}/master` | 标记错题已掌握 |
| `GET /api/practice/review/list` | 待复习题目列表 |
| `GET /api/practice/historical` | 历史真题（委托 exam_bank_service） |

### P5-4：报告模块 (`app/api/report.py`)
修改 1 个现有端点，新增 6 个端点：

**修改：** `GET /api/report/teacher/{record_or_teacher_id}`
- 同时支持 exam_record_id（返回考试报告）和 teacher_id（返回教师总览）

**新增：**
| 端点 | 功能 |
|------|------|
| `GET /api/report/student/{student_id}` | 学生报告概览 |
| `GET /api/report/class/{class_id}` | 班级报告概览 |
| `GET /api/report/student/{student_id}/kp-mastery` | 知识点掌握报告 |
| `GET /api/report/student/{student_id}/barrier-change` | 障碍变化报告 |
| `GET /api/report/student/{student_id}/trend` | 学习趋势报告 |

### P5-5：题目管理 (`app/api/question.py`)
新增 7 个端点：
| 端点 | 功能 |
|------|------|
| `GET /api/question/categories` | 题库分类列表 |
| `GET /api/question/kps` | 知识点列表 |
| `GET /api/question/similar/{question_id}` | 相似题目（委托 exam_bank_service） |
| `POST /api/question/search` | 搜索题目（多条件筛选） |
| `GET /api/question/{question_id}` | 题目详情 |
| `POST /api/question/{question_id}/approve` | 审核通过 |
| `POST /api/question/{question_id}/reject` | 审核拒绝 |

### P5-6：家长账号 (`app/utils/init_db.py` + `app/api/auth.py`)
- **init_db.py**: 创建家长「李国华」(13800138000/123456)，绑定学生 202610101（李世睿）
- **auth.py**: `get_user_info()` 增加 parent 角色处理，返回绑定学生信息
- **login.html**: 快速登录家长凭证改为 `13800138000`

## 修改文件清单
| 文件 | 端点数 |
|------|--------|
| `app/api/diagnosis.py` | 5 |
| `app/api/exam.py` | 3 |
| `app/api/practice.py` | 6 |
| `app/api/report.py` | 6 (含 1 个修改) |
| `app/api/question.py` | 7 |
| `app/utils/init_db.py` | 家长账号创建 |
| `app/api/auth.py` | parent 角色支持 |
| `frontend/login.html` | 更新家长凭证 |

## 验证方式
1. 启动服务 → 访问各新端点确认返回 200
2. 家长账号 `13800138000 / 123456` 可正常登录
3. 前端各功能操作正常，不报 404
