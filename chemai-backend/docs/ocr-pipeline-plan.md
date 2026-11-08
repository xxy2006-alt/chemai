# ChemAI OCR Pipeline — Implementation Plan

**Date**: 2026-06-25
**ADR**: 0001-single-pass-routing, 0002-baidu-ocr-pipeline

## Post-Review Revisions

1. **Full async**: OCRService + all three clients use `httpx.AsyncClient` + `asyncio.sleep`. Not sync.
2. **BLOB storage**: Raw file bytes go in `upload_sessions.file_data` column. Not `/tmp/`.
3. **Background tasks**: `asyncio.create_task()` for long-running imports/grading.
4. **ERROR return paths**: `ERROR → READY` (retry) and `ERROR → UPLOADED` (re-upload).
5. **24h cleanup**: APScheduler daily job cleans stale UPLOADED/PREVIEWING sessions.
6. **Remove old import_exam_paper tool**: Delete the broken MinerU-based path.
7. **recognize() moved to Slice 1**: It's independent, no reason to delay.
8. **Concurrency**: Optimistic locking via `version` column on `upload_sessions`.
9. **Path sanitization**: Region/year values validated before use in file paths.
10. **Degraded flag**: `upload_sessions.degraded` column for fallback tracking.
11. **File size validation**: 10MB check in both frontend and API.
12. **Cancel endpoint**: `POST /api/ocr/tasks/{id}/cancel`.

## Execution Order

Three vertical slices, each independently testable:

```
Slice 1: 基础能力
  baidu_auth → exam_import_client → upload_sessions table → ocr_service.import_exam()
  → ocr_service.recognize() (doc_analysis preview)
  ✅ 预览 + 导入全通

Slice 2: 判卷
  grading_client → student_submissions table → ocr_service.grade()

Slice 3: 统一入口 + Agent + 前端
  document_parse_service routing → API endpoints → Agent upload → frontend UI
```

---

## Slice 1: Exam Import (建题库)

### 1.1 `app/services/baidu_auth.py`

Shared token manager used by all three Baidu API clients.

```python
class BaiduAuth:
    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"

    def get_token() -> str
        # Returns cached token if valid (>5min remaining)
        # Otherwise fetches new token via OAuth client_credentials
        # Stores in memory: {token, expires_at}

    # Reads BAIDU_OCR_API_KEY / BAIDU_OCR_SECRET_KEY from env
```

Interface: one method `get_token()`. No state on disk, just in-memory cache.

### 1.2 `app/services/exam_import_client.py`

Wrapper around Baidu `paper_cut_edu_vlm` async API.

```python
class ExamImportClient:
    CREATE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/paper_cut_edu_vlm/create_task"
    GET_URL    = "https://aip.baidubce.com/rest/2.0/ocr/v1/paper_cut_edu_vlm/get_result"

    async def submit_page(image_base64: str, page_num: int) -> str
        # POST create_task with scene_type="paper"
        # Returns baidu_task_id
        # Content-Type: application/json
        # Body: {image, scene_type: "paper"}

    async def poll_result(baidu_task_id: str, timeout: float = 60.0) -> dict | None
        # Poll get_result every 3s until isAllFinished=true or timeout
        # Returns raw Baidu response or None on timeout
        # Body: {task_id}

    async def import_pages(pages: list[bytes], on_progress=None) -> ImportResult
        # Batch of 2 concurrent:
        #   1. Submit pages 1-2 → poll both → collect results
        #   2. Submit pages 3-4 → poll both → collect results
        #   ...
        # Calls on_progress(current, total) for frontend polling
        # Returns ImportResult with all question data

@dataclass
class ImportResult:
    success: bool
    questions: list[ExtractedQuestion]  # from qus_words
    figures: list[FigureRef]            # from pic_location + enhance_url
    raw_response: dict                  # for debugging

@dataclass
class ExtractedQuestion:
    number: str          # from seqence
    content: str         # from qus_words
    question_type: str   # from qus_type
    bbox: list[int]      # from qus_location [x,y,w,h]

@dataclass
class FigureRef:
    page_num: int
    bbox: list[int]      # from pic_location [x,y,w,h]
    enhance_url: str     # downloaded and stored locally
```

### 1.3 `upload_sessions` table (SQLite)

Tracks file uploads through the state machine.

```sql
CREATE TABLE upload_sessions (
    id              TEXT PRIMARY KEY,        -- UUID
    file_data       BLOB,                    -- raw file bytes
    file_name       TEXT,                    -- original filename
    mime_type       TEXT,                    -- e.g. "application/pdf"
    status          TEXT DEFAULT 'uploaded', -- state machine status
    preview_text    TEXT,                    -- doc_analysis output
    formula_result  TEXT,                    -- LaTeX formulas JSON
    detected_type   TEXT,                    -- "exam"/"answer_sheet"/"other"
    baidu_task_id   TEXT,                    -- for async APIs
    page_count      INTEGER,                -- total pages
    pages_completed INTEGER DEFAULT 0,       -- progress
    result_json     TEXT,                    -- final structured output
    error_msg       TEXT,                    -- last error
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

States: `uploaded → previewing → ready → importing → imported → done`
                                     ↘ grading   → graded   → done
                                     ↘ discarded
               Any state → error

### 1.4 `ocr_service.import_exam()` (add to existing OCRService)

```python
def import_exam(upload_id: str) -> dict:
    # 1. Load session from upload_sessions
    # 2. Read file_data, convert to page images (PyMuPDF for PDF, PIL for images)
    # 3. Set status="importing"
    # 4. Call exam_import_client.import_pages(), update pages_completed
    # 5. Collect all ExtractedQuestion across pages
    # 6. If formula_result exists in session, pass to LLM as hints
    # 7. LLM structures questions (HistoricalQuestion format)
    # 8. Save JSON + figures to data/exam_questions/{region}/{year}/
    # 9. Save questions to DB (questions + question_sets tables)
    # 10. Set status="imported", store result_json
```

### 1.5 Verification

After slice 1, this works:
```bash
python scripts/import_exam_papers.py --year 2020
# → 2020 national exam imported, questions in DB, figures on disk
```

---

## Slice 2: Grading (判卷)

### 2.1 `app/services/grading_client.py`

```python
class GradingClient:
    CREATE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/correct_edu/create_task"
    GET_URL    = "https://aip.baidubce.com/rest/2.0/ocr/v1/correct_edu/get_result"

    async def submit(image_base64: str) -> str
        # POST create_task with paperSubject="chemistry"
        # Content-Type: application/json
        # Body: {image, paperSubject: "chemistry"}

    async def poll_result(baidu_task_id: str, timeout: float = 60.0) -> dict | None

    async def grade(image_base64: str) -> GradingResult

@dataclass
class GradingResult:
    success: bool
    questions: list[GradedQuestion]
    stat_result: dict   # {all, corrected, correcting}

@dataclass
class GradedQuestion:
    question_id: str
    seqence: int
    type: int           # 2=choice, 4=fill, etc.
    correct_result: int # 0=unprocessed, 1=correct, 2=wrong, 3=unanswered
    reason: str         # grading reason / error analysis
    crop_url: str       # graded question image URL (downloaded locally)
    crop_local_path: str
```

### 2.2 `app/models/student_submission.py`

```python
class StudentSubmission(Base):
    __tablename__ = "student_submissions"

    submission_id   = Column(String, primary_key=True)
    exam_id         = Column(String, ForeignKey("exam_records.record_id"))
    class_id        = Column(String)  # redundant for fast queries
    student_name    = Column(String)
    original_image  = Column(String)      # path to raw answer sheet
    graded_image    = Column(String)      # path to annotated image
    answers_json    = Column(Text)        # [{q_number, answer, correct, score, reason}]
    total_score     = Column(Integer)
    submitted_at    = Column(DateTime)
    graded_at       = Column(DateTime)
```

### 2.3 `ocr_service.grade()` (add to OCRService)

```python
def grade(upload_id: str, exam_id: str = None) -> dict:
    # 1. Load session from upload_sessions
    # 2. Set status="grading"
    # 3. Call grading_client.grade()
    # 4. Download crop images to data/submissions/{submission_id}/
    # 5. Save to student_submissions table
    # 6. Set status="graded"
```

---

## Slice 3: Unified Entry + Agent + Frontend

### 3.1 `ocr_service.recognize()` — unified preview

```python
def recognize(file_data: bytes, mime_type: str) -> PreviewResult:
    # Route by file type:
    #   image/* → doc_analysis (sync OCR)
    #   application/pdf → doc_analysis page 1
    #   text/* → direct text read
    # Returns: {preview_text, formula_result, detected_type, page_count}
```

### 3.2 `document_parse_service.py` — routing

```python
class DocumentParseService:
    def route(file_data, mime_type, user_intent=None) -> str:
        # Returns: "preview" | "import" | "grade"
        # If user_intent set: use it
        # Otherwise: doc_analysis preview → LLM detect type → suggest action
```

### 3.3 API Endpoints (add to `app/api/ocr.py`)

```
POST /api/ocr/upload
  Body: multipart file
  → Creates upload_session
  → Calls OCRService.recognize() for preview
  → Returns {upload_id, preview_text, detected_type, suggestions: ["import","grade","search"]}

GET /api/ocr/tasks/{upload_id}/status
  → Returns {status, progress: {current, total}, result (if done)}

POST /api/ocr/tasks/{upload_id}/import
  → Triggers OCRService.import_exam() in background
  → Returns immediately, client polls /status

POST /api/ocr/tasks/{upload_id}/grade
  → Triggers OCRService.grade() in background
  → Returns immediately, client polls /status
```

### 3.4 Agent Upload (`agent/channel/langgraph_channel.py`)

```
POST /api/agent/upload
  Body: multipart file
  → Calls OCRService.recognize() for preview
  → Returns {upload_id, preview_text, detected_type, actions: [
       {id:"import", label:"导入题库"},
       {id:"grade", label:"批改判卷"},
       {id:"search", label:"搜题解析"}
     ]}

When user sends chat message with {action: "import", upload_id: "..."}:
  → Agent routes to exam_expert
  → exam_expert calls import_exam tool
  → Tool triggers OCRService.import_exam()
  → Result: structured questions displayed in chat
```

### 3.5 Frontend Changes

#### 3.5.1 Agent Chat (`index.html` + `js/agent.js`)

Add 📎 button below chat input:
- Click → file picker (accept: image/*, .pdf, .doc, .docx, .xlsx, .pptx)
- On select → upload to `/api/agent/upload`
- Show preview card in chat:
  ```
  ┌─────────────────────────────────────┐
  │ 📄 2020全国卷化学.pdf (22页)        │
  │ 预览: 选择题1-7，非选择题8-10...    │
  │ [📥 导入题库] [🖊️ 批改] [🔍 搜题] │
  └─────────────────────────────────────┘
  ```
- User clicks action → send as chat message with {action, upload_id}
- During async processing: show spinner + progress updates (poll `/status`)

#### 3.5.2 Exam Workbench (`pages/exam-v2.html`)

After import completes, redirect or show inline:
- List of extracted questions with type/content/answer
- Editable fields (content, answer, knowledge_points)
- "确认入库" button → final save to DB

#### 3.5.3 Grading Results (new section in `pages/teacher.html`)

After grading completes:
- Summary card: "14/14 correct, 85/100 points"
- Per-question breakdown with graded crop images
- "查看原始答题卡" link

#### 3.5.4 Student Submissions (new section in `pages/students.html`)

Class detail page, add "考试记录" tab:
```
Class: 2419班
  Exams:
    ├─ 2024期中考试 (14 submissions, avg: 78)
    ├─ 2024期末考试 (12 submissions, avg: 82)
    └─ ...

Click exam → submission list:
  ├─ 张三  85分  ✅
  ├─ 李四  62分  ⚠️
  └─ ...

Click student → detail:
  ├─ Original answer sheet image
  ├─ Graded image with annotations
  └─ Per-question: correct/wrong + reason
```

---

## File Summary

| # | File | Action | Slice |
|---|------|--------|-------|
| 1 | `app/services/baidu_auth.py` | New | 1 |
| 2 | `app/services/exam_import_client.py` | New | 1 |
| 3 | DB: `upload_sessions` table | New | 1 |
| 4 | `app/services/ocr_service.py` | Edit: `import_exam()` | 1 |
| 5 | `app/services/grading_client.py` | New | 2 |
| 6 | `app/models/student_submission.py` | New | 2 |
| 7 | `app/services/ocr_service.py` | Edit: `grade()` | 2 |
| 8 | `app/services/ocr_service.py` | Edit: `recognize()` | 3 |
| 9 | `app/services/document_parse_service.py` | Edit: routing | 3 |
| 10 | `app/api/ocr.py` | Edit: `/upload`, `/tasks/`, `/grade` | 3 |
| 11 | `agent/channel/langgraph_channel.py` | Edit: `/agent/upload` | 3 |
| 12 | `frontend/index.html` + `js/agent.js` | Edit: upload UI | 3 |
| 13 | `frontend/pages/exam-v2.html` | Edit: import preview | 3 |
| 14 | `frontend/pages/teacher.html` | Edit: grading results | 3 |
| 15 | `frontend/pages/students.html` | Edit: submission drilldown | 3 |

## Verification

After each slice:
- **Slice 1**: `python scripts/import_exam_papers.py --year 2020` → questions in DB
- **Slice 2**: Upload answer sheet → graded result with images
- **Slice 3**: Agent chat upload → preview → import → questions in bank
