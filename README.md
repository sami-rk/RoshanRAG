# RoshanRAG

**A RAG-based Document Q&A system.** Upload your text documents (DOCX/TXT), ask questions in natural language, and get accurate answers grounded in your documents, with cited sources. Built with Django, LangChain, and ChromaDB, powered by free OpenRouter LLMs with automatic fallback — fully containerized with Docker.

## Features

- Document CRUD (`docx` + `txt`), full-text storage
- Automatic text extraction → chunking → vector indexing
- RAG question answering with citation of used documents (MMR retrieval for diverse chunks)
- Full Q&A history (question, answer, status, sources)
- Free OpenRouter LLMs with an automatic fallback chain + readable error messages
- Admin retry actions (re-index / re-answer) and automatic stuck-task recovery
- API rate limiting and a health-check endpoint for Docker healthchecks
- Multilingual embedding model `BAAI/bge-m3` (Persian + English), GPU-aware
- Django Admin UI (Persian) + token-authenticated REST API with OpenAPI schema
- Public Persian landing page (dark/light) with home, about, pricing, contact and a styled 404, including scroll reveals, tilt/spotlight cards, magnetic CTAs and a tech-stack marquee
- Docker Compose with optional GPU override

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  web (Django + DRF + gunicorn)                           │
│   ┌──────────────┐   ┌───────────────────────────────┐   │
│   │ Django Admin │   │ REST API (Token auth)         │   │
│   └──────┬───────┘   └──────┬────────────────────────┘   │
│          │                  │                            │
│   ┌──────▼──────────────────▼────────────────────────┐   │
│   │  Background (threads + status fields)            │   │
│   │  extract → chunk → embed → Chroma                │   │
│   │  retrieve → LLM (OpenRouter + fallback)          │   │
│   └──────┬────────────────────────────┬──────────────┘   │
│          │                           │                   │
└──────────┼───────────────────────────┼───────────────────┘
           │                           │
   ┌───────▼─────────┐         ┌───────▼──────────┐
   │  SQLite (volume) │         │  ChromaDB container │
   └─────────────────┘         └──────────────────┘
```

RAG flow: `user question → embed → MMR retrieval (top-4 of 20, diverse) → dedupe (max 3 docs) → prompt (answer in the question's language, cite sources) → LLM → save answer + sources`.

Stuck-task safety: background tasks run in threads, so a killed worker can leave an item in `pending`/`generating`. `recover_stuck_tasks` (run automatically on container start) marks such items `failed` after 30 minutes, and the admin offers **re-index** / **re-answer** actions to retry them.

## Getting Started

### Prerequisites

1. Docker + Docker Compose
2. An API key from [openrouter.ai](https://openrouter.ai) (free models are used)
3. Optional, for GPU: [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

### Run

```bash
cp .env.example .env          # then set OPENROUTER_API_KEY in .env
docker compose up --build     # CPU mode

# GPU mode (requires nvidia-container-toolkit):
docker compose -f compose.yaml -f compose.gpu.yaml up --build

# Load the bundled sample documents:
docker compose exec web python manage.py load_sample_data
```

Then:

- Landing page: <http://localhost:8000/>
- Admin: <http://localhost:8000/admin/> (superuser from `.env`, default `admin` / `admin`)
- Swagger docs: <http://localhost:8000/api/schema/docs/>
- OpenAPI schema: <http://localhost:8000/api/schema/>

> On first run the embedding model (~2.3 GB) is downloaded and cached in a Docker volume.

### Configuration

Everything is driven by environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required. OpenRouter key for the LLM |
| `LLM_MODEL` | `poolside/laguna-s-2.1:free` | Primary LLM |
| `LLM_FALLBACK_MODELS` | `openai/gpt-oss-20b:free,nvidia/nemotron-nano-9b-v2:free` | Comma-separated fallbacks tried in order on error |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model (single multilingual model) |
| `CHROMA_HOST` / `CHROMA_PORT` | `localhost` / `8000` | ChromaDB connection (`chroma` / `8000` in Docker) |
| `CHROMA_COLLECTION` | `roshan_documents` | Chroma collection name |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `200` | RecursiveCharacterTextSplitter settings |
| `RETRIEVAL_TOP_K` / `RETRIEVAL_FETCH_K` / `RETRIEVAL_MAX_DOCS` | `4` / `20` / `3` | MMR: fetch top-20 chunks, return 4 diverse ones, dedupe to max 3 documents |
| `THROTTLE_USER_RATE` / `THROTTLE_ANON_RATE` | `300/minute` / `30/minute` | DRF API rate limits |
| `MAX_UPLOAD_SIZE_MB` | `25` | Max document upload size |
| `DJANGO_SUPERUSER_*` | `admin` / `admin` | Auto-created superuser in Docker |
| `SQLITE_PATH` / `MEDIA_ROOT` | — | Set by docker-compose (persistent volumes) |
| `HF_HUB_DISABLE_XET` | `1` | Disables the flaky Hugging Face xet download backend |
| `HF_TOKEN` | — | Optional; speeds up Hugging Face downloads |

### Useful commands

```bash
# Create an API token for the admin user:
docker compose exec web python manage.py shell -c \
  "from rest_framework.authtoken.models import Token; from django.contrib.auth import get_user_model; t,_=Token.objects.get_or_create(user=get_user_model().objects.get(username='admin')); print(t.key)"

# Open a shell inside the container:
docker compose exec web python manage.py shell
```

## API Overview

All endpoints require `Authorization: Token <token>`. Get a token with:

```bash
curl -X POST http://localhost:8000/api/token/ -d 'username=admin&password=admin'
```

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/` | Upload a document (multipart: `file` required, `title` optional) |
| `GET` | `/api/documents/` | List documents (`?q=<text>` searches title + full text) |
| `GET` / `PATCH` / `DELETE` | `/api/documents/{id}/` | Detail / edit / delete (removes vector chunks too) |
| `POST` | `/api/questions/` | Ask a question (`{"question": "..."}`) |
| `GET` | `/api/questions/` | Q&A history |
| `GET` | `/api/questions/{id}/` | Poll for status / answer / sources |
| `DELETE` | `/api/questions/{id}/` | Delete a question from the history |
| `GET` | `/api/health/` | Health check (DB + Chroma), used by the container healthcheck |

Document status: `pending → ready | failed`. Question status: `pending → generating → done | failed`. After creating a question, poll `GET /api/questions/{id}/` for the result.

Example question response:

```json
{
  "id": 1,
  "question": "میزان کل فروش در سه ماهه اول چقدر بوده است؟",
  "answer": "بر اساس گزارش، میزان کل فروش در سه ماهه اول ۱۲.۵ میلیارد تومان بوده است...\n\nمنابع:\n- گزارش فروش سه ماهه اول ۱۴۰۳",
  "status": "done",
  "sources": [
    {"document_id": 1, "title": "گزارش فروش سه ماهه اول ۱۴۰۳", "excerpt": "..."}
  ],
  "created_at": "2026-08-16T12:00:00Z",
  "answered_at": "2026-08-16T12:00:05Z"
}
```

## Screenshots

| | |
| --- | --- |
| Admin login | Admin dashboard |
| ![login](docs/screenshots/1-admin-login.png) | ![dashboard](docs/screenshots/2-admin-dashboard.png) |
| Documents list | Document detail |
| ![documents](docs/screenshots/3-documents-list.png) | ![document](docs/screenshots/4-document-detail.png) |
| Questions list | Question answer with sources |
| ![questions](docs/screenshots/5-questions-list.png) | ![answer](docs/screenshots/6-question-answer.png) |
| Swagger UI | |
| ![api docs](docs/screenshots/7-api-docs.png) | |
| Dark mode | Mobile |
| ![dark](docs/screenshots/8-admin-dark.png) | ![mobile](docs/screenshots/9-admin-mobile.png) |
| Landing page | Landing dark mode |
| ![landing](docs/screenshots/10-landing.png) | ![landing dark](docs/screenshots/11-landing-dark.png) |
| Landing mobile | Styled 404 |
| ![landing mobile](docs/screenshots/12-landing-mobile.png) | ![404](docs/screenshots/13-landing-404.png) |
| Admin login (light) | Admin login (dark) |
| ![login light](docs/screenshots/14-admin-login.png) | ![login dark](docs/screenshots/15-admin-login-dark.png) |
| Admin dashboard (light) | Admin dashboard (dark) |
| ![dashboard light](docs/screenshots/16-admin-dashboard.png) | ![dashboard dark](docs/screenshots/17-admin-dashboard-dark.png) |
| Documents list | Document detail |
| ![documents](docs/screenshots/18-documents-list.png) | ![document](docs/screenshots/19-document-detail.png) |

## Project Structure

```
config/            Django settings and URLs
core/              Shared services (embeddings, chroma_client, llm_client, workers)
documents/         Document model, services (extraction/chunking/indexing), signals, API
qa/                Question model, RAG answering service, API
templates/landing/ Public landing pages (home, about, pricing, contact, base)
static/landing/    Landing CSS/JS (dark-light theme, mobile nav, count-up, scroll reveals, tilt, magnetic CTAs, marquee)
sample_data/       Four Persian sample documents (3 DOCX + 1 TXT)
Dockerfile         python:3.12-slim; CPU torch by default, CUDA torch via GPU build arg
compose.yaml       web + chroma services
compose.gpu.yaml   GPU override (adds CUDA torch + nvidia device reservation)
entrypoint.sh      Migrate, recover stuck tasks, create superuser, run gunicorn
.env.example       Configuration template
```

## Technical Decisions

- **Embedding model — `BAAI/bge-m3` (MIT).** Strong on Persian (~61% FaMTEB), multilingual (one model for Farsi + English in a single vector space), and permissively licensed. jina-embeddings-v3 was dropped because its license is non-commercial CC BY-NC.
- **GPU-aware, CPU-portable.** The app auto-detects CUDA. `compose.yaml` is CPU-only; `compose.gpu.yaml` builds the image with CUDA torch and requests the GPU. Note: bge-m3 ships `.bin` weights only, so torch ≥ 2.6 is required (modern transformers refuses `torch.load` below it).
- **Background work via Python threads + status fields** (`pending/ready/failed`), per the project's simplicity-first requirement — no Celery/Redis. Stuck tasks are recovered automatically on container start (`recover_stuck_tasks`).
- **Free OpenRouter models with `with_fallbacks`.** Free models get rate-limited, so on error LangChain tries the next model in the chain. Stored errors are unwrapped to the provider's actual message.
- **MMR retrieval.** Retrieval uses maximal marginal relevance (`fetch_k=20`, `k=4`) to balance relevance with diversity, then dedupes to at most 3 documents.
- **Answers are cited.** Every answer returns the source documents used, keeping RAG transparent; answers follow the language of the question.
- **Separate ChromaDB container** keeps the vector store isolated from the app (pinned to `chromadb/chroma:1.5.9` with a healthcheck).
- **SQLite** for simplicity and persistence via a Docker volume; chunking at 800/200 via `RecursiveCharacterTextSplitter`.
- **Hugging Face xet backend disabled** — it can hang on some networks; downloads fall back to plain HTTP.
- **Custom Persian admin theme** — Django Admin is restyled with a Persian-first design system (bundled Vazirmatn font, RTL, light/dark mode, dashboard stat cards, status pills) via a custom `AdminSite` and template overrides, no third-party admin package. Dashboard and app cards are 3D-interactive (mouse-tracked perspective tilt, glassmorphism, layered depth, count-up stats, cursor-tracking spotlight) with `prefers-reduced-motion` respected, and bulk actions render as explicit buttons instead of a dropdown. Movement is layered across every page: header slide-down, staggered card entrance, IntersectionObserver scroll reveals, a pulsing amber "pending" pill, and press/scale on buttons. Dark mode adds an elegant layered background (radial gradient base, drifting skewed cyan light streaks, dot grid, and fractal-noise texture — ported from the `elegant-dark-pattern` component, with the texture inlined as an SVG data URI). The login page gets its own card entrance and a gently floating logo; the theme toggle there shares its `roshan-theme` storage key with the landing page, so a visitor's preference carries over. Changelists and forms are fully scrollable on phones (no horizontal page overflow).
- **Public landing page** — a bespoke Persian landing (home with hero + bento features + how-it-works + FAQ, plus about, pricing, contact and a styled 404) built in plain Django templates and vanilla CSS, RTL with the bundled Vazirmatn font, dark/light via a shared `data-theme` attribute and `roshan-theme` key. Motion is vanilla JS + CSS only: staggered hero entrance, IntersectionObserver scroll reveals (with a debounced fallback so fast scrolls never skip a reveal), 3D-tilt bento cards with cursor spotlight, magnetic CTA buttons, an infinite tech-stack marquee (bge-m3 · ChromaDB · OpenRouter · LangChain · Django · Persian), smooth FAQ open/close, a rotating/cross-fading theme icon, sliding nav underlines, a hamburger-to-X mobile menu with staggered links, count-up stats, and a drifting streak background — all disabled under `prefers-reduced-motion` and for no-JS visitors. It doubles as the destination for the admin's "View site" link (`AdminSite.site_url = "/"`). Because the home page root is now routed, the admin "View site" link works.
- **Custom 404 page** — served through `handler404` when `DEBUG = false`. In dev (`DEBUG = true`) Django intentionally shows its technical 404 page instead; the styled page is what visitors see in production.
- **WhiteNoise serves static files** — installed in a dedicated Docker layer (keeps the torch layer cached) so gunicorn serves the admin's collected assets.
