FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system ecommerce \
    && useradd --system --gid ecommerce --create-home ecommerce

COPY pyproject.toml API_FUNCIONAMENTO.md alembic.ini ./
COPY app ./app

RUN python -m pip install .

USER ecommerce

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
