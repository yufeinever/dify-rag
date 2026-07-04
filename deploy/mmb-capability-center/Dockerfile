FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAPABILITY_DB_PATH=/app/data/capability_center.sqlite

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY openapi-dify.yaml /app/openapi-dify.yaml
RUN mkdir -p /app/data

EXPOSE 8097
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8097"]
