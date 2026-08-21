# Submission Contents

Everything required by the assignment brief, and where to find it:

| # | Requirement | Location |
|---|-------------|----------|
| 1 | Project source code | `config/`, `core/`, `qa/`, `documents/`, `templates/`, `static/`, `locale/`, `manage.py` |
| 2 | Docker & docker-compose files | `Dockerfile`, `compose.yaml` (+ GPU variant `compose.gpu.yaml`), `entrypoint.sh`, `.dockerignore` |
| 3 | README with setup steps | `README.md` — see "Quick Start" |
| 4 | Admin panel screenshots | `docs/screenshots/` (19 images: login, dashboard, documents, questions, dark/mobile variants) |
| 5 | API documentation | `docs/api.md`; interactive Swagger UI served live at `/api/schema/docs/` |
| 6 | Sample data for testing | `sample_data/` — five Persian documents (3 DOCX + 1 PDF + 1 TXT) |

## Testing the system with the sample documents

After the stack is up (`docker compose up --build`, admin/admin):

```bash
# Index all bundled sample documents in one command:
docker compose exec web python manage.py load_sample_data
```

Then open <http://localhost:8000/chat/> and ask questions grounded in those
documents, e.g. «میزان فروش سه ماهه اول چقدر بود؟». Answers stream word by
word and cite the matching source documents.
