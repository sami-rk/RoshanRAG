# RoshanRAG API Documentation

سامانه پرسش از اسناد (RoshanRAG) یک REST API کامل برای مدیریت اسناد، پرسش و پاسخ مبتنی بر RAG و تاریخچه پرسش‌ها ارائه می‌دهد.

- Interactive docs (Swagger UI): `GET /api/schema/docs/`
- OpenAPI schema: `GET /api/schema/`
- Base URL: `http://localhost:8000`

## Authentication

All endpoints require a token. Obtain one with a superuser's credentials:

```bash
curl -X POST http://localhost:8000/api/token/ \
  -d 'username=admin&password=admin'
```

Response:

```json
{ "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" }
```

Send the token on every request:

```
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

Requests without a valid token receive `403 Forbidden`. An unauthenticated client is limited by `THROTTLE_ANON_RATE`; authenticated clients by `THROTTLE_USER_RATE` (default `300/minute`).

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/` | Upload a document (multipart: `file` required, `title` optional) |
| `GET` | `/api/documents/` | List documents (`?q=<text>` searches title + full text, `?status=pending\|ready\|failed` filters) |
| `GET` | `/api/documents/{id}/` | Document detail (includes full text and status) |
| `PATCH` | `/api/documents/{id}/` | Edit a document (e.g. rename, or replace `file` to re-index) |
| `DELETE` | `/api/documents/{id}/` | Delete a document (removes vector chunks and the stored file) |
| `POST` | `/api/questions/` | Ask a question (`{"question": "..."}`) — starts background answering |
| `GET` | `/api/questions/` | Q&A history (`?status=pending\|generating\|done\|failed` filters, paginated, 20/page) |
| `GET` | `/api/questions/{id}/` | Poll for status / answer / sources |
| `DELETE` | `/api/questions/{id}/` | Delete a question from the history |
| `GET` | `/api/health/` | Health check (DB + Chroma), no authentication required |

## Uploading a document

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -H "Authorization: Token <token>" \
  -F "file=@sample_data/سوالات-متداول.txt" \
  -F "title=سوالات متداول"
```

- Supported formats: `docx`, `txt` (max `MAX_UPLOAD_SIZE_MB`, default 25 MB).
- `title` defaults to the file name if omitted.
- The document is created with status `pending`; text extraction, chunking and vector indexing run in the background. Poll the detail endpoint until `status` becomes `ready` or `failed`.

Response (`201 Created`):

```json
{
  "id": 1,
  "title": "سوالات متداول",
  "file": "http://localhost:8000/media/documents/2026/08/سوالات-متداول.txt",
  "full_text": "متن کامل استخراج‌شده...",
  "status": "pending",
  "error_message": "",
  "created_at": "2026-08-16T12:00:00Z",
  "updated_at": "2026-08-16T12:00:00Z"
}
```

> The `file` URL points to protected media — a session login or the same `Authorization: Token` header is required to download it.

## Asking a question

```bash
curl -X POST http://localhost:8000/api/questions/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "میزان کل فروش در سه ماهه اول چقدر بوده است؟"}'
```

The question is created with status `pending` and answering starts in the background. Poll `GET /api/questions/{id}/` until it finishes.

Question lifecycle: `pending → generating → done | failed`.

```bash
curl -X GET http://localhost:8000/api/questions/1/ \
  -H "Authorization: Token <token>"
```

Response (`200 OK`) when done:

```json
{
  "id": 1,
  "question": "میزان کل فروش در سه ماهه اول چقدر بوده است؟",
  "answer": "بر اساس گزارش، میزان کل فروش در سه ماهه اول ۱۲.۵ میلیارد تومان بوده است.\n\nمنابع:\n- گزارش فروش سه ماهه اول ۱۴۰۳",
  "status": "done",
  "sources": [
    {
      "document_id": 4,
      "title": "گزارش فروش سه ماهه اول ۱۴۰۳",
      "excerpt": "گزارش فروش سه ماهه اول ۱۴۰۳..."
    }
  ],
  "error_message": "",
  "created_at": "2026-08-16T12:00:00Z",
  "answered_at": "2026-08-16T12:00:05Z"
}
```

Notes:

- Answers are generated only from the indexed documents (RAG); every answer carries its `sources`.
- If no document has been indexed yet, the answer is a deterministic "no documents yet" message without calling the LLM.
- If no relevant content is retrieved for the question, the answer explains that no matching content was found.
- On LLM/provider failure the question is marked `failed` and `error_message` holds the readable provider error; the admin offers a "پاسخ‌دهی مجدد" (re-answer) action.

## Status reference

Document status: `pending` (extracting/indexing), `ready` (searchable), `failed` (extraction error — see `error_message`; retry via admin action).

Question status: `pending` (queued), `generating` (LLM answering), `done` (answer + sources saved), `failed` (provider/retrieval error).

## Rate limiting

- `THROTTLE_USER_RATE` (default `300/minute`) — authenticated requests.
- `THROTTLE_ANON_RATE` (default `30/minute`) — anonymous requests.

Exceeding a limit returns `429 Too Many Requests`.