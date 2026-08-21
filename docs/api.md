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

Questions and threads are scoped to their owner: every authenticated client only sees its own questions and threads (`/api/questions/` and `/api/threads/` return only the caller's records). The anonymous demo endpoints create records with no owner.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/` | Upload a document (multipart: `file` required, `title` optional) |
| `POST` | `/api/documents/batch/` | Upload several documents at once (multipart: repeat `files`) |
| `GET` | `/api/documents/` | List documents (`?q=<text>` searches title + full text, `?status=pending\|ready\|failed` filters) |
| `GET` | `/api/documents/{id}/` | Document detail (includes full text and status) |
| `PATCH` | `/api/documents/{id}/` | Edit a document (e.g. rename, or replace `file` to re-index) |
| `DELETE` | `/api/documents/{id}/` | Delete a document (removes vector chunks and the stored file) |
| `POST` | `/api/questions/` | Ask a question (`{"question": "..."}`, optional `"thread": "<uuid>"`) — starts background answering |
| `GET` | `/api/questions/` | Q&A history (`?status=...` filters, `?thread=<uuid>` scopes to a thread, paginated, 20/page) |
| `GET` | `/api/questions/{id}/` | Poll for status / answer / sources |
| `GET` | `/api/questions/{id}/stream/` | Server-Sent Events: live answer streaming (token frames + final `done` frame) |
| `PATCH` | `/api/questions/{id}/` | Record answer feedback (`{"feedback": "up"\|"down"\|"none"}`) |
| `DELETE` | `/api/questions/{id}/` | Delete a question from the history |
| `GET` | `/api/questions/export/` | Export Q&A history (`?format=csv` default, `?format=json`) |
| `POST` | `/api/questions/demo_ask/` | Anonymous demo question (no token) — returns `demo_token` for polling |
| `GET` | `/api/questions/{id}/demo/?token=...` | Poll a demo question's status (token-gated, no auth) |
| `GET` | `/api/threads/` | List conversation threads |
| `POST` | `/api/threads/` | Create a conversation thread (`{"title": "..."}`) |
| `GET` | `/api/threads/{id}/` | Thread detail including its ordered `questions` |
| `GET` | `/api/health/` | Health check (DB + Chroma), no authentication required |

## Uploading a document

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -H "Authorization: Token <token>" \
  -F "file=@sample_data/سوالات-متداول.txt" \
  -F "title=سوالات متداول"
```

- Supported formats: `docx`, `pdf`, `txt` (max `MAX_UPLOAD_SIZE_MB`, default 25 MB).
- The content is sniffed against the extension: a file whose magic bytes do not match its name (e.g. a binary renamed to `.txt`, or plain text named `.pdf`) is rejected with a `400`.
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

## Batch upload

Send several files in one multipart request; every file is validated independently and the ones that pass are created and queued for indexing in the background:

```bash
curl -X POST http://localhost:8000/api/documents/batch/ \
  -H "Authorization: Token <token>" \
  -F "files=@sample_data/سوالات-متداول.txt" \
  -F "files=@sample_data/قوانین-داخلی.txt"
```

Response (`201 Created` when at least one file passes):

```json
{
  "created": [ { "id": 1, "title": "سوالات متداول", "status": "pending" } ],
  "errors": [ { "file": "قوانین.pdf", "errors": { "file": ["فرمت فایل باید docx، pdf یا txt باشد"] } } ]
}
```

An empty request (no `files`) returns `400 Bad Request`.

## Asking a question

```bash
curl -X POST http://localhost:8000/api/questions/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "میزان کل فروش در سه ماهه اول چقدر بوده است؟"}'
```

The question is created with status `pending` and answering starts in the background. Poll `GET /api/questions/{id}/` until it finishes, or subscribe to `GET /api/questions/{id}/stream/` for live streaming.

When `thread` is omitted, the server creates a new thread titled with the question's first 60 characters, so consecutive questions naturally group into conversations.

Question lifecycle: `pending → generating → done | failed`.

## Streaming answers (Server-Sent Events)

```bash
curl -N http://localhost:8000/api/questions/1/stream/ \
  -H "Authorization: Token <token>"
```

The endpoint keeps the connection open, polling the worker's progress buffer, and emits `data:` frames:

- `{"type": "token", "text": "..."}` — an incremental chunk of the answer, emitted as soon as the worker flushes it.
- `{"type": "done", "question": {...}}` — final frame carrying the serialized question (full `answer`, `sources`, `status`).
- `{"type": "timeout"}` — after 300 seconds without completion.

While the stream is idle (no new tokens), a comment line (`: keepalive`) is emitted periodically so reverse proxies do not drop the silent connection.

A request for a question that is already finished emits a single `done` frame immediately. The chat page consumes this stream to render the answer token-by-token.

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
      "excerpt": "گزارش فروش سه ماهه اول ۱۴۰۳...",
      "citation": 1,
      "file_url": "/media/documents/2026/08/گزارش-فروش-سه-ماهه-اول-1403.docx"
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

## Answer feedback

Record whether an answer was useful (`up`), not useful (`down`), or clear it (`none`):

```bash
curl -X PATCH http://localhost:8000/api/questions/1/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"feedback": "up"}'
```

## Exporting Q&A history

```bash
curl -X GET http://localhost:8000/api/questions/export/ \
  -H "Authorization: Token <token>" > questions.csv
curl -X GET "http://localhost:8000/api/questions/export/?format=json" \
  -H "Authorization: Token <token>"
```

CSV includes a UTF-8 BOM so Excel opens Persian text correctly. The admin also offers "خروجی CSV" as a bulk action on the question list.

## Demo widget (no authentication)

The landing page's demo box uses two anonymous endpoints. They are rate-limited by `THROTTLE_DEMO_RATE` (default `10/minute`) and the poll endpoint has its own separate rate `THROTTLE_DEMO_POLL_RATE` (default `240/minute`), because the demo widget polls it every couple of seconds while an answer streams. It is also gated by a per-question token, so answers cannot be enumerated:

```bash
curl -X POST http://localhost:8000/api/questions/demo_ask/ \
  -H "Content-Type: application/json" \
  -d '{"question": "سوال دمو"}'
```

```json
{ "id": 10, "question": "سوال دمو", "status": "pending", "demo_token": "8030b871-..." }
```

Then poll with the token:

```bash
curl "http://localhost:8000/api/questions/10/demo/?token=8030b871-..."
```

Wrong or missing tokens return `404 Not Found`.

## Language

The site is Persian by default (RTL). A cookie-based language toggle is available at `GET /set-language/?lang=fa|en&next=<path>`: it sets the `django_language` cookie and redirects to `next` (off-site values are dropped). Browsers that send an English `Accept-Language` header still get Persian until the visitor toggles.

## Status reference

Document status: `pending` (extracting/indexing), `ready` (searchable), `failed` (extraction error — see `error_message`; retry via admin action).

Question status: `pending` (queued), `generating` (LLM answering), `done` (answer + sources saved), `failed` (provider/retrieval error).

## Rate limiting

- `THROTTLE_USER_RATE` (default `300/minute`) — authenticated requests.
- `THROTTLE_ANON_RATE` (default `30/minute`) — anonymous requests.
- `THROTTLE_DEMO_RATE` (default `10/minute`) — the anonymous demo widget (`demo_ask` / `demo`), which consumes LLM credits per question and so gets its own stricter limit.
- `THROTTLE_DEMO_POLL_RATE` (default `240/minute`) — the demo poll endpoint (`/demo/?token=...`), which is polled every couple of seconds while an answer streams, so it must not compete with `THROTTLE_DEMO_RATE`.

Exceeding a limit returns `429 Too Many Requests`.