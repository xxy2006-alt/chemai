# ADR-0002: Baidu Education OCR Pipeline

**Date**: 2026-06-25
**Status**: Accepted

## Context

ChemAI's OCR was powered by ZhiPu GLM-OCR with a single fire-and-forget call from `OCRService.recognize_answer_sheet()`. The migration to Baidu's education OCR suite introduces three APIs with different capabilities, call patterns, and failure modes. The existing architecture has no concept of multi-step workflows, async polling, state persistence, or API composition.

## Decision

### 1. Three-API Architecture

| API | Role | Mode | Endpoint |
|-----|------|------|----------|
| `doc_analysis` | Preview + formula extraction + fallback | Sync | `/rest/2.0/ocr/v1/doc_analysis` |
| `paper_cut_edu_vlm` | Exam question import (primary) | Async | `/rest/2.0/ocr/v1/paper_cut_edu_vlm/create_task` + `/get_result` |
| `correct_edu` | Answer sheet grading (primary) | Async | `/rest/2.0/ocr/v1/correct_edu/create_task` + `/get_result` |

### 2. Upload Session State Machine (SQLite)

All file uploads are tracked in an `upload_sessions` table with states:

```
UPLOADED → PREVIEWING → READY → IMPORTING → IMPORTED → DONE
                            ↘ GRADING   → GRADED   → DONE
                            ↘ DISCARDED
Any state → ERROR (retryable)
```

The user must explicitly choose an action before the system invokes an expensive async API.

### 3. Client-Side Task Polling

Async operations return a `task_id` immediately. The frontend polls `GET /api/ocr/tasks/{upload_id}/status` every 2 seconds. The server proxies to Baidu's `get_result` on each poll. This gives the frontend a progress indicator (e.g. "processing page 3/22") and avoids long-lived HTTP connections.

### 4. API Composition and Fallback

| User action | Primary API | On success | On failure |
|------------|-------------|-----------|------------|
| Import to bank | `paper_cut_edu_vlm` | Structured questions saved to JSON + DB | Fallback to `doc_analysis` → LLM structuring, marked "degraded quality" |
| Grade answers | `correct_edu` | Results saved to `student_submissions` | Show error, no automatic fallback (grading requires accuracy) |
| Preview | `doc_analysis` | Text + formula_result shown to user | Show raw image, "unable to recognize" |

`formula_result` (LaTeX chemical formulas) from the preview step is passed as hints to the LLM during import structuring for higher accuracy.

### 5. PDF Multi-Page Strategy

Batch of 2 concurrent pages (respecting Baidu's QPS=2 limit on `create_task`). After each batch completes, start the next. For a 22-page exam: ~110 seconds. Progress reported to frontend via the task status endpoint.

### 6. File Lifecycle

```
Upload   → /tmp/uploads/{upload_id}.{ext}
Preview  → Read from temp, call doc_analysis
Import   → Read from temp, call paper_cut_edu_vlm
Success  → Move to data/exam_questions/{region}/{year}/
            Download Baidu crop/enhanced images to same directory
Fail     → Keep in /tmp for retry
Discard  → Cleanup after 24 hours (scheduled job)
```

Imported papers are stored with their companion images:

```
data/exam_questions/{region}/{year}/
  ├── {paper_name}.json
  └── figures/
      ├── page_01.png
      ├── page_01_enhanced.png
      ├── q1_crop.png
      └── ...
```

### 7. Storage: Student Submissions

A new `student_submissions` table links graded answer sheets to exams and classes:

```
student_submissions
  submission_id   PK
  exam_id         FK → exam_records
  class_id        FK → classes
  student_name    string
  original_image  path to raw answer sheet
  graded_image    path to annotated image
  answers_json    [{q_number, student_answer, correct_result, reason, score}]
  total_score     int
  submitted_at    datetime
  graded_at       datetime
```

Frontend navigation: Class → Exam list → Single exam → Student submission list → Single submission detail (original image + graded image + per-question breakdown).

## Alternatives Considered

### In-memory state (vs SQLite)
Rejected. Teachers may close the browser mid-workflow. SQLite survives restarts.

### Server-side polling (vs client-side)
Rejected. Would block FastAPI workers or require background task infrastructure. Client-side polling is simpler and gives the frontend progress visibility.

### Serial page processing (vs batch of 2)
Rejected. Too slow for multi-page PDFs. Full parallel rejected due to Baidu QPS=2 limit.

### VLM-only import (vs VLM + doc_analysis formula merge)
Rejected. doc_analysis produces more precise LaTeX formulas than VLM plain text. Merging both improves downstream question generation quality.

## Consequences

- **Positive**: Multi-step workflows with user-in-the-loop confirmation prevent expensive API calls on wrong inputs.
- **Positive**: Fallback to sync OCR ensures the system never returns empty results on API failure.
- **Positive**: Client-side polling gives real progress feedback for long operations.
- **Negative**: Three APIs with two async patterns increase implementation complexity vs. the single sync call before.
- **Negative**: SQLite state machine adds a new table and migration step.
