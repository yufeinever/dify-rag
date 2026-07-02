# MMB Poster Service

A small Dify OpenAPI tool service for generating vertical social posters with GPT-5.5 planning, OpenAI image generation, production material references, and deterministic Chinese text overlays.

## Local run

```bash
cp .env.example .env
# Set OPENAI_API_KEY and POSTER_PUBLIC_BASE_URL for production use.
docker compose up --build
```

Health check:

```bash
curl http://localhost:8088/health
```

Mock generation without OpenAI calls:

```bash
POSTER_ALLOW_MOCK_OPENAI=true docker compose up --build
```

## Dify tool import

Import `openapi-dify.yaml` as a Dify OpenAPI custom tool. In a Docker network deployment, set the server URL to `http://poster-service:8088`; for external access set it to the public HTTPS URL that fronts this service.

The service returns a JSON result with `poster_url`, `thumbnail_url`, `final_prompt`, `used_assets`, and `status`.
