# RoshanRAG — روشن‌RAG

**سامانه پرسش از اسناد (Document Q&A System)**

RoshanRAG یک سامانه مبتنی بر RAG است که به شما امکان می‌دهد اسناد متنی خود (DOCX و TXT) را بارگذاری کنید، به زبان طبیعی از آن‌ها بپرسید و پاسخی دقیق مبتنی بر محتوای اسناد دریافت کنید. رابط کاربری پنل مدیریت با Django Admin پیاده‌سازی شده و تمام قابلیت‌ها از طریق یک API کامل REST در دسترس است.

> RoshanRAG — a RAG-based Document Q&A system: ask questions in natural language and get answers grounded in your documents. Built with Django, LangChain, and ChromaDB, powered by free OpenRouter LLMs with automatic fallback, fully containerized with Docker.

---

## فهرست مطالب

- [امکانات](#امکانات)
- [معماری](#معماری)
- [تکنولوژی‌ها](#تکنولوژی‌ها)
- [راه‌اندازی با Docker](#راه‌اندازی-با-docker)
- [اجرای بدون GPU](#اجرای-بدون-gpu)
- [داده نمونه](#داده-نمونه)
- [مستندات API](#مستندات-api)
- [ساختار پروژه](#ساختار-پروژه)
- [تصمیمات فنی](#تصمیمات-فنی)
- [English](#english)

---

## امکانات

- ثبت، ویرایش و حذف اسناد (فرمت‌های `docx` و `txt`)
- ذخیره متن کامل هر سند
- استخراج متن و تبدیل خودکار سند به بخش‌های قابل بازیابی (Chunking)
- نمایه‌سازی برداری با مدل embedding چندزبانه **BAAI/bge-m3**
- ثبت پرسش و پاسخ‌گویی خودکار بر اساس محتوای اسناد (RAG)
- جست‌وجوی پیشرفته (بازیابی ۴ بخش مرتبط و پاسخ دقیق با ذکر منابع)
- ذخیره تاریخچه کامل پرسش‌ها، پاسخ‌ها و منابع استفاده‌شده
- API کامل REST با احراز هویت مبتنی بر Token
- اجرای ساده با Docker و پشتیبانی اختیاری GPU
- زنجیره مدل‌های رایگان OpenRouter با fallback خودکار

## معماری

```
┌─────────────────────────────────────────────────────────┐
│  web (Django + DRF + gunicorn)                          │
│   ┌──────────────┐   ┌───────────────────────────────┐  │
│   │ Django Admin │   │ API (REST, Token auth)        │  │
│   └──────┬───────┘   └──────┬────────────────────────┘  │
│          │                  │                            │
│   ┌──────▼──────────────────▼────────────────────────┐  │
│   │  پردازش پس‌زمینه (Thread + وضعیت)                │  │
│   │   استخراج متن → تقسیم به بخش → embedding → Chroma│  │
│   │   بازیابی بخش‌ها → LLM (OpenRouter + fallback)   │  │
│   └──────┬────────────────────────────┬──────────────┘  │
│          │                           │                  │
└──────────┼───────────────────────────┼──────────────────┘
           │                           │
   ┌───────▼─────────┐         ┌───────▼──────────┐
   │  SQLite (volume) │         │  ChromaDB (کانتینر)│
   └─────────────────┘         └──────────────────┘
```

جریان RAG:

```
پرسش کاربر → embedding پرسش → جست‌وجوی شباهت (top-4) → dedupe (حداکثر ۳ سند)
→ ساخت prompt (پاسخ به زبان پرسش + ذکر منابع) → LLM → ذخیره پاسخ + منابع
```

## تکنولوژی‌ها

| بخش | انتخاب |
|---|---|
| وب‌فریمورک | Django 6.1 |
| API | Django REST Framework + drf-spectacular (OpenAPI) |
| ارکستراسیون RAG | LangChain (text-splitters, chroma, openrouter, huggingface) |
| مدل embedding | BAAI/bge-m3 (چندزبانه، MIT، GPU/CPU) |
| پایگاه برداری | ChromaDB (کانتینر جداگانه) |
| مدل زبانی | OpenRouter مدل رایگان با fallback: `poolside/laguna-s-2.1:free` → `deepseek-chat:free` → `qwen-2.5-72b-instruct:free` |
| پایگاه داده | SQLite |
| استخراج متن | python-docx |
| پردازش پس‌زمینه | نخ‌های Python + فیلد وضعیت (بدون Celery) |
| کانتینر | Docker + Docker Compose |

## راه‌اندازی با Docker

### پیش‌نیازها

1. **Docker** و **Docker Compose** نصب باشد.
2. یک API Key از [openrouter.ai](https://openrouter.ai) بسازید (از مدل‌های رایگان استفاده می‌شود).
3. برای استفاده از **GPU** (توصیه‌شده): [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) را نصب کنید.

### مراحل

```bash
# ۱. ساخت فایل .env از روی نمونه
cp .env.example .env
# ۲. کلید OpenRouter خود را در .env قرار دهید (OPENROUTER_API_KEY)

# ۳. اجرا (پیش‌فرض CPU)
docker compose up --build

# ۳-ب. اجرا با GPU (در صورت وجود nvidia-container-toolkit)
docker compose -f compose.yaml -f compose.gpu.yaml up --build
```

پس از اجرا:

- پنل مدیریت: <http://localhost:8000/admin/>
- مستندات تعاملی API (Swagger): <http://localhost:8000/api/schema/docs/>
- اسکیمای OpenAPI: <http://localhost:8000/api/schema/>
- کاربر ادمین به صورت خودکار از متغیرهای `.env` ساخته می‌شود (پیش‌فرض: `admin` / `admin`)

> نکته: در اولین اجرا مدل embedding (~۲٫۳GB) دانلود می‌شود؛ این دانلود در volume ذخیره شده و فقط یک بار انجام می‌شود.

### دستورات مفید

```bash
# بارگذاری داده نمونه
docker compose exec web python manage.py load_sample_data

# ساخت token برای دسترسی API (خروجی: کلید مربوط به کاربر)
docker compose exec web python manage.py shell -c "from rest_framework.authtoken.models import Token; from django.contrib.auth import get_user_model; t, _ = Token.objects.get_or_create(user=get_user_model().objects.get(username='admin')); print(t.key)"

# اجرای دستورات دلخواه
docker compose exec web python manage.py shell
```

## اجرای بدون GPU

همه‌چیز بدون تغییر کار می‌کند؛ سیستم به صورت خودکار وجود CUDA را تشخیص می‌دهد و در صورت نبود GPU از CPU استفاده می‌کند (`compose.yaml` اصلی به GPU وابسته نیست). فقط سرعت embedding کمتر خواهد بود.

## داده نمونه

در پوشه `sample_data/` چهار سند نمونه (سه فایل DOCX و یک TXT) به زبان فارسی قرار دارد:

- گزارش فروش سه ماهه اول ۱۴۰۳
- دستورالعمل فرآیند استخدام
- سیاست حریم خصوصی
- سوالات متداول

با دستور زیر می‌توانید آن‌ها را بارگذاری کنید:

```bash
docker compose exec web python manage.py load_sample_data
```

## مستندات API

تمام endpointها با **Token Authentication** محافظت می‌شوند. ابتدا توکن را در پنل مدیریت یا با دستور بالا بسازید و در هدر هر درخواست ارسال کنید:

```
Authorization: Token <YOUR_TOKEN>
```

### دریافت توکن

```bash
curl -X POST http://localhost:8000/api/token/ \
  -d 'username=admin&password=admin'
```

### اسناد

| متد | مسیر | توضیح |
|---|---|---|
| `POST` | `/api/documents/` | بارگذاری سند (multipart: `title` اختیاری، `file` الزامی) |
| `GET` | `/api/documents/` | فهرست اسناد |
| `GET` | `/api/documents/?q=<متن>` | جست‌وجو در عنوان و متن کامل اسناد |
| `GET` | `/api/documents/{id}/` | جزئیات سند (شامل متن کامل) |
| `PATCH` | `/api/documents/{id}/` | ویرایش (عنوان یا فایل) |
| `DELETE` | `/api/documents/{id}/` | حذف سند (به همراه بخش‌های برداری) |

نمونه بارگذاری سند:

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -H "Authorization: Token <YOUR_TOKEN>" \
  -F "title=گزارش فروش" \
  -F "file=@sample_data/گزارش-فروش-سه-ماهه-اول-1403.docx"
```

فیلد `status` وضعیت پردازش سند را نشان می‌دهد: `pending` → `ready` یا `failed`.

### پرسش‌ها

| متد | مسیر | توضیح |
|---|---|---|
| `POST` | `/api/questions/` | ثبت پرسش جدید (بدنه: `{"question": "..."}`) |
| `GET` | `/api/questions/` | تاریخچه پرسش‌ها و پاسخ‌ها |
| `GET` | `/api/questions/{id}/` | وضعیت، پاسخ و منابع یک پرسش (برای polling) |

نمونه ثبت پرسش:

```bash
curl -X POST http://localhost:8000/api/questions/ \
  -H "Authorization: Token <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"question": "میزان کل فروش در سه ماهه اول چقدر بوده است؟"}'
```

پاسخ شامل فیلدهای زیر است:

```json
{
  "id": 1,
  "question": "میزان کل فروش در سه ماهه اول چقدر بوده است؟",
  "answer": "بر اساس گزارش، میزان کل فروش در سه ماهه اول ۱۲.۵ میلیارد تومان بوده است...\n\nمنابع:\n- گزارش فروش سه ماهه اول ۱۴۰۳",
  "status": "done",
  "sources": [
    {
      "document_id": 1,
      "title": "گزارش فروش سه ماهه اول ۱۴۰۳",
      "excerpt": "گزارش فروش سه ماهه اول سال ۱۴۰۳ شرکت..."
    }
  ],
  "created_at": "2026-08-16T12:00:00Z",
  "answered_at": "2026-08-16T12:00:05Z"
}
```

وضعیت‌ها: `pending` → `generating` → `done` یا `failed`. برای دریافت نتیجه، پس از ثبت پرسش روی `GET /api/questions/{id}/` polling کنید.

### اسکیمای OpenAPI

اسکیمای کامل API در `GET /api/schema/` و مستندات تعاملی در `GET /api/schema/docs/` در دسترس است.

## ساختار پروژه

```
.
├── config/               # تنظیمات و مسیریابی Django
│   ├── settings.py
│   └── urls.py
├── core/                 # سرویس‌های مشترک
│   ├── embeddings.py     # مدل embedding (bge-m3) با تشخیص GPU/CPU
│   ├── chroma_client.py  # اتصال و عملیات ChromaDB
│   ├── llm_client.py     # مدل OpenRouter + زنجیره fallback
│   └── workers.py        # اجرای وظایف پس‌زمینه با نخ
├── documents/            # اپ اسناد
│   ├── models.py         # مدل Document
│   ├── services/         # استخراج متن، chunking، نمایه‌سازی
│   ├── signals.py        # پردازش خودکار پس از ذخیره/حذف سند
│   ├── serializers.py
│   ├── views.py          # CRUD + جست‌وجو
│   └── management/commands/load_sample_data.py
├── qa/                   # اپ پرسش‌وپاسخ
│   ├── models.py         # مدل Question
│   ├── services/         # سرویس پاسخ‌گویی RAG
│   ├── serializers.py
│   └── views.py          # ثبت پرسش، تاریخچه، polling
├── sample_data/          # اسناد نمونه
├── Dockerfile
├── compose.yaml
├── compose.gpu.yaml      # فعال‌سازی GPU
├── entrypoint.sh
└── .env.example
```

## تصمیمات فنی

- **مدل embedding**: `BAAI/bge-m3` به دلیل کیفیت بالا روی فارسی (≈۶۱٪ FaMTEB)، چندزبانه بودن (فارسی + انگلیسی در یک فضای برداری)، و مجوز آزاد MIT انتخاب شد. گزینه «جینا» (jina-embeddings-v3) کیفیت بالاتری داشت اما مجوز آن CC BY-NC (غیرتجاری) بود، بنابراین کنار گذاشته شد.
- **ChromaDB به‌صورت کانتینر جداگانه**: جداسازی پایگاه برداری از برنامه اصلی.
- **پردازش پس‌زمینه با نخ**: به‌دلیل تأکید پروژه بر سادگی، به‌جای Celery/Redis از نخ‌های Python و فیلد وضعیت (`pending/ready/failed`) استفاده شده است.
- **زنجیره fallback مدل زبانی**: مدل‌های رایگان OpenRouter گاه rate-limit می‌شوند؛ با `with_fallbacks` لنگچین، در صورت خطا مدل بعدی به‌کار می‌رود.
- **پاسخ + منابع**: هر پاسخ فهرست اسناد استفاده‌شده را بازمی‌گرداند تا شفافیت RAG حفظ شود.
- **SQLite**: سادگی و عدم نیاز به سرویس جداگانه؛ با volume در Docker ماندگار است.

---

## English

**RoshanRAG** is a RAG-based Document Q&A system. Upload your text documents (DOCX/TXT), ask questions in natural language, and get accurate answers grounded in your documents, with cited sources.

### Features

- Document CRUD with `docx` and `txt` support and full-text storage
- Automatic text extraction, chunking (800/200), and vector indexing
- Multilingual embedding model `BAAI/bge-m3` (Persian + English), GPU-aware
- RAG question answering with top-4 retrieval (max 3 documents) via LangChain
- Free OpenRouter LLM with an automatic fallback chain
- Full Q&A history with sources; Django Admin UI (Persian labels)
- Token-authenticated REST API with OpenAPI schema
- Docker Compose setup with optional GPU override

### Quick start

```bash
cp .env.example .env          # set OPENROUTER_API_KEY
docker compose up --build     # CPU; add -f compose.gpu.yaml for GPU

# Admin: http://localhost:8000/admin/  (admin / admin by default)
# Swagger: http://localhost:8000/api/schema/docs/
docker compose exec web python manage.py load_sample_data
```

### API overview

All endpoints require `Authorization: Token <token>` (get a token via `POST /api/token/`).

- Documents: `POST/GET /api/documents/`, `GET/PATCH/DELETE /api/documents/{id}/`, search with `?q=`
- Questions: `POST /api/questions/`, `GET /api/questions/`, `GET /api/questions/{id}/` (poll for status)
- Schema: `GET /api/schema/`, interactive docs at `GET /api/schema/docs/`

### Technical decisions

- **Embedding**: `BAAI/bge-m3` (MIT, multilingual incl. Farsi). jina-embeddings-v3 was dropped due to its non-commercial CC BY-NC license.
- **Background work**: Python threads + status fields (per the project's simplicity-first requirement, no Celery/Redis).
- **LLM**: free OpenRouter models with LangChain `with_fallbacks` to survive rate limits.
- **Database**: SQLite (persistent via Docker volume). **Vector store**: separate ChromaDB container.