# Plan: Phase 5 - Document Upload and Extraction

## 1. Goal
Implement secure document upload, validation, persistent storage behind an interface, text extraction (PDF, TXT, Markdown, JSON), and project-scoped management endpoints and UI dropzone.

## 2. Requirements & Constraints
- Models: `Document` table with `id` (UUID), `project_id` (UUID, FK projects.id ON DELETE CASCADE), `original_name` (str), `stored_name` (str - UUID based, safe), `file_type` (str: pdf, txt, md, json), `size_bytes` (int), `extraction_status` (str: PENDING, SUCCESS, FAILED), `extracted_text` (Text, nullable), `created_at` (timestamptz).
- Storage: `backend/app/services/storage.py` - LocalStorageProvider with interface `StorageProvider`. Stored in `storage/uploads/` with UUID filename. Never user-controlled paths.
- Validation:
  - Allowed types: PDF, TXT, MD, JSON.
  - Extension and content validation (PDF magic bytes `%PDF`, JSON parseable, UTF-8 text).
  - Max upload size: `settings.MAX_UPLOAD_MB` (default 10 MB). Empty files rejected.
- Extractors:
  - PDF: PyMuPDF (`fitz`), text extracted per page. Size/timeout safety.
  - TXT / Markdown: UTF-8 decode.
  - JSON: JSON parse, serialized pretty text or structured representation.
- Endpoints:
  - `POST /projects/{id}/documents` - Upload multipart file, validate, store, extract, return DocumentResponse.
  - `GET /projects/{id}/documents` - List project documents (owner scoped, 404 for non-owners).
  - `DELETE /documents/{id}` - Delete document (removes file from storage and row from DB, owner scoped).
- Frontend:
  - Dropzone in `ProjectPage.jsx` supporting drag-and-drop & file picker.
  - Upload progress / status indicator.
  - List uploaded documents with status badge (SUCCESS/FAILED/PENDING), size, and delete button.
  - Enable "Start Test Run" button when >= 1 document exists.

## 3. Files to Create / Modify
- `backend/app/models/document.py` (New model)
- `backend/app/models/__init__.py` (Export Document)
- `backend/app/schemas/document.py` (DocumentResponse)
- `backend/app/services/storage.py` (Storage interface and local filesystem provider)
- `backend/app/services/extractor.py` (Text extraction logic)
- `backend/app/services/document_service.py` (Document business logic)
- `backend/app/api/documents.py` (Document endpoints)
- `backend/app/main.py` (Include documents router)
- Alembic migration for `documents` table
- `backend/tests/test_documents.py` (T5.1 - T5.4 tests)
- `frontend/src/api/client.js` (Add documents API methods)
- `frontend/src/pages/ProjectPage.jsx` (Add dropzone and documents list)
- `frontend/src/__tests__/auth_and_projects.test.jsx` / `documents.test.jsx` (Frontend dropzone test)

## 4. Verification Plan
- Backend tests: T5.1 (extraction of PDF, TXT, MD, JSON), T5.2 (reject empty, oversize, wrong/spoofed type), T5.3 (UUID stored name), T5.4 (delete cleans storage and DB, cross-user 404).
- Full backend suite: `uv run pytest`.
- Lint: `uv run ruff check .` and frontend `npm.cmd run lint`.
- Frontend tests: `npm.cmd test`.
