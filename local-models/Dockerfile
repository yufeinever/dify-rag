FROM langgenius/dify-api:1.14.2

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/models/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence-transformers

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.2.2+cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8008
ENTRYPOINT []
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8008"]
