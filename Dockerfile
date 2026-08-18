FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
ARG TORCH_VERSION=2.6.0
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN sed -i '/^torch==/d' requirements.txt \
    && pip install --no-cache-dir torch==${TORCH_VERSION} --index-url ${TORCH_INDEX} \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# The image runs with DEBUG=false, which uses CompressedManifestStaticFilesStorage
# and requires staticfiles.json. Collect under DEBUG=false so the manifest is
# baked in. SECRET_KEY here is a build-time dummy, overridden at runtime.
RUN pip install --no-cache-dir "whitenoise==6.9.0" \
    && DEBUG=false SECRET_KEY=build-only-static-secret-7f3c9a2b1d4e8f0a \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["/app/entrypoint.sh"]