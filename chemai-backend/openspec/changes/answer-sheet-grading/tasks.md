# Tasks: Answer Sheet Grading

## 1. Database & Model

- [x] 1.1 Create `ocr_tasks` model
- [x] 1.2 Alembic migration
- [x] 1.3 Add OCR provider config

## 2. Upload API & Frontend

- [x] 2.1 Create `app/api/ocr_sheets.py` with endpoints:
  - `POST /api/ocr/tasks/batch` — multipart upload, returns batch_id + task_ids
  - `GET /api/ocr/tasks/batch/{batch_id}` — batch status + per-task progress
  - `POST /api/ocr/tasks/{task_id}/retry` — retry failed task
  - `GET /api/ocr/tasks?teacher_id=xxx` — teacher's task list
- [x] 2.2 Register router in `app/main.py`
- [x] 2.3 Create `frontend/pages/ocr-sheets.html` — drag-drop upload page with:
  - Drop zone + file picker
  - Thumbnail previews with delete button
  - Editable task titles
  - "开始识别" button → submit batch
  - Real-time progress bars (polling)
  - History batches list
  - Retry buttons on failed tasks

## 3. OCR Pipeline

- [x] 3.1 Create `app/services/ocr_mineru.py` — MinerU OCR wrapper:
  - Extract student info (学号 name regex + 姓名)
  - Extract answer content (per-question answer + confidence)
  - Return structured JSON
- [x] 3.2 Create `app/scheduler/ocr_scheduler.py` — APScheduler job:
  - Poll `ocr_tasks` every 5s for pending tasks
  - Process one at a time
  - Update status + progress + result
- [x] 3.3 Register scheduler in app startup

## 4. LLM Grading

- [x] 4.1 Create `app/services/llm_grading.py`:
  - `grade_batch(tasks, answer_source)` — batch call LLM
  - Per-card prompt: correct answers + student answers → per-question judgment
  - Returns per-card grading results
- [x] 4.2 Create `app/api/grading.py`:
  - `POST /api/grading/run` — trigger LLM grading for batch
  - `POST /api/grading/save` — save confirmed results + trigger diagnosis
  - `GET /api/grading/results/{batch_id}` — get grading results per batch

## 5. Agent Tools

- [x] 5.1 Add to `agent/tools_core.py`:
  - `query_ocr_progress(teacher_id, batch_id)` — query ocr_tasks table, return per-task status
  - `grade_answer_sheets(teacher_id, batch_id)` — trigger LLM grading, return result cards
  - `save_grading_results(teacher_id, batch_id)` — save to StudentAnswer, trigger diagnosis, return class stats
- [x] 5.2 Add to `TOOL_META`: `{"personas": ["teacher"], "call_limit": 3}` for each
- [x] 5.3 Verify: `test_tool_filtering.py` confirms teacher has 3 new tools

## 6. Tests

- [x] 6.1 `tests/test_ocr_pipeline.py`:
  - Test task creation and status transitions
  - Test teacher isolation (teacher A can't see teacher B's tasks)
  - Test retry logic
- [x] 6.2 `tests/test_llm_grading.py`:
  - Test answer source resolution (exam match / teacher input / LLM auto)
  - Test semantic comparison (same equation, different format)
  - Test result card generation
- [x] 6.3 `tests/test_ocr_agent_tools.py`:
  - Test query_ocr_progress returns correct status
  - Test grade_answer_sheets triggers grading pipeline
  - Test teacher persona includes all 3 tools

## 7. Integration

- [x] 7.1 Wire grading save → barrier diagnosis (existing run-llm pipeline)
- [x] 7.2 Wire grading save → exam-analytics endpoint
- [x] 7.3 Manual E2E test: upload 3 answer sheets → OCR → grade → confirm → verify diagnosis + analytics
