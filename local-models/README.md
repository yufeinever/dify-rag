# Local Dify Models

This service exposes local CPU models for Dify's OpenAI-compatible provider:

- Embedding: `bge-small-zh-v1.5`
- Rerank: `bge-reranker-base`

On this machine the models are cached under `docker/volumes/local-models/huggingface`.

Start the Windows background service:

```powershell
powershell -ExecutionPolicy Bypass -File D:\dify-rag\local-models\start-local-models.ps1
```

Dify containers should use:

```text
http://host.docker.internal:8008/v1
```

Use `LOCAL_MODELS_API_KEY` to change the bearer token if needed.
