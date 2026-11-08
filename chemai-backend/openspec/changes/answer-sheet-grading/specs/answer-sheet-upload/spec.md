# Answer Sheet Upload

教师批量上传答题卡图片的前端页面和后端 API。

## ADDED Requirements

### REQ-UPLOAD-001: Drag-and-drop Upload
教师可以将多张答题卡图片（JPG/PNG/PDF）拖入上传区域，或通过文件选择器选择。

**Acceptance:**
- 支持一次选择 1-10 张图片
- 显示缩略图预览，可删除单张
- 每张可编辑标题（默认"答题卡_01"）

### REQ-UPLOAD-002: Batch Submit
提交时所有图片作为一批上传，返回 `batch_id`。

**Acceptance:**
- POST `/api/ocr/tasks/batch` 接受 multipart/form-data
- 响应包含 `{batch_id, task_ids: [...]}`
- 前端显示"识别已提交"状态

### REQ-UPLOAD-003: Progress Display
前端轮询 `/api/ocr/tasks/batch/{batch_id}` 获取进度，每张答题卡显示进度条。

**Acceptance:**
- 进度条显示百分比（OCR 识别完成后 = 100%）
- 失败任务显示红色标记和重试按钮
- 每张答题卡显示缩略图 + 标题 + 状态标签

### REQ-UPLOAD-004: Batch Upload Retry
失败的任务可单独重试，不影响已完成的任务。

**Acceptance:**
- POST `/api/ocr/tasks/{task_id}/retry` 重置状态为 pending
- 重试后更新进度

### REQ-UPLOAD-005: Pagination
支持多批次——第一批完成后再传第二批，独立 `batch_id`。

**Acceptance:**
- 不同 batch 的任务互不干扰
- 页面显示历史批次列表
