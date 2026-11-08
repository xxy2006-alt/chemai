## Why

答题卡识别页面，按原型 `_5/code.html` 还原。流程：选班级→上传照片/PDF→OCR识别→预览结果→确认入库。

## What Changes

- 新建 `frontend/pages/ocr.html`
- 新建 `frontend/js/ocr.js`
- API: `POST /api/ocr/recognize`, `POST /api/ocr/confirm`, `GET /api/ocr/services/status`

## Capabilities

### New Capabilities
- `ocr-page`: 答题卡识别页面（上传+预览+确认）
