# P2-1 前端 API 调用审计修复确认

## 修复日期
2026-04-25

## 审计范围
- `frontend/src/services/` 全部 12 个 service 文件
- `frontend/teacher_v2.html` 内联脚本
- `frontend/login.html` 内联脚本
- 对应 `app/api/` 全部 24 个路由模块

## 发现的问题

### ✅ 已修复

| 文件 | 前端路径 | 后端路径 | 修复方式 |
|------|---------|---------|---------|
| `diagnosis.js:46` | `/api/diagnosis/student/${id}` | `/api/diagnosis/barrier/${id}` | 路径修正 |
| `exam.js:46` | `/api/exam/${id}/publish` | `/api/exam/${id}/finalize` | 路径修正 |

### ⚠️ 前端已定义但后端无对应路由（不阻塞运行）

以下 service 方法均有前端定义，但后端尚未实现对应端点。这些方法**未被当前 SPA 页面主动调用**，不导致即时错误，但后续实现功能时需要补齐：

| 文件 | 方法 | 期望路径 | 状态 |
|------|------|---------|------|
| `diagnosis.js` | `getInterventionPlan()` | `GET /api/diagnosis/plan/{id}` | 未实现 |
| `diagnosis.js` | `submitFeedback()` | `POST /api/diagnosis/{id}/feedback` | 未实现 |
| `diagnosis.js` | `getDiagnosisHistory()` | `GET /api/diagnosis/history/{id}` | 未实现 |
| `diagnosis.js` | `getClassBarrierStats()` | `GET /api/diagnosis/class/{id}/stats` | 未实现 |
| `diagnosis.js` | `getKPBarnerAnalysis()` | `GET /api/diagnosis/class/{id}/kp/{kp}` | 未实现 |
| `exam.js` | `updateExam()` | `PUT /api/exam/{id}` | 未实现 |
| `exam.js` | `deleteExam()` | `DELETE /api/exam/{id}` | 未实现 |
| `exam.js` | `getStudentResult()` | `GET /api/exam/{examId}/result/{studentId}` | 未实现 |
| `practice.js` | `getPracticeQuestions()` | `GET /api/practice/{id}/questions` | 未实现 |
| `practice.js` | `getPracticeHistory()` | `GET /api/practice/history/{studentId}` | 未实现 |
| `practice.js` | `getWrongQuestions()` | `GET /api/practice/wrong/list` | 未实现 |
| `practice.js` | `markAsMastered()` | `POST /api/practice/wrong/{qid}/master` | 未实现 |
| `practice.js` | `getReviewQuestions()` | `GET /api/practice/review/list` | 未实现 |
| `practice.js` | `getHistoricalQuestions()` | `GET /api/practice/historical` | 未实现 |
| `report.js` | 6 个方法 | `/api/report/student/{id}` 系列 | 路径格式与后端不同 |
| `question.js` | 8 个方法 | `/api/question/{id}` 系列 | 路径格式与后端不同 |

### ✅ 已验证匹配的路径

- `teacher_v2.html` 中所有 8 个 analytics API 调用 → 与后端路由一致
- API认证相关 (`/api/auth/login`, `/api/auth/me`, `/api/auth/logout`) → 匹配
- 真题库 (`/api/exam-bank/exam-sets`, `/api/exam-bank/historical`) → 匹配
- 障碍诊断核心 (`/api/diagnosis/barrier/{class}/{exam}`, `/api/diagnosis/learning-plan/*`) → 匹配
- 练习核心 (`/api/practice/student/{id}/tasks`, `/api/practice/submit`, `/api/practice/assign`) → 匹配
- 间隔复习 (`/api/review/student/{id}/due`, `/api/review/submit`, `/api/review/sync/{id}`) → 匹配
- OCR (`/api/ocr/parse/document`, `/api/ocr/services/status`) → 匹配
- 集成/通知/日志/家长/预警 → 全部匹配

## 工作建议
后端未实现的 20+ 个端点可归为"待实现功能"而非"bug"，建议在后续迭代中按优先级补齐。
