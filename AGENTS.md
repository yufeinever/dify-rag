# AGENTS.md

## Project Overview

Dify is an open-source platform for developing LLM applications with an intuitive interface combining agentic AI workflows, RAG pipelines, agent capabilities, and model management.

The codebase is split into:

- **Backend API** (`/api`): Python Flask application organized with Domain-Driven Design
- **Frontend Web** (`/web`): Next.js application using TypeScript and React
- **Docker deployment** (`/docker`): Containerized deployment configurations
- **Dify Agent Backend** (`/dify-agent`): Backend services for managing and executing agent

## Development Location

- Canonical development happens on T1000 at `/home/yu/projects/dify-rag`.
- Do not make feature or product changes in the Windows local mirror `C:\Users\86150\Documents\RAG_for_dify`; treat it as historical/local artifact storage only.
- When Codex needs to change this project, first SSH to T1000 with `ssh t1000-lan` and work in `/home/yu/projects/dify-rag`, then commit and push from that remote repository.

## Production Deployment: 118.196.65.83:18088

- The public Dify node `http://118.196.65.83:18088` is the main environment the user checks. Do not assume a source commit is visible there until the Docker deployment has been rebuilt and restarted.
- Traffic path: public 118 server HAProxy `:18088` -> FRP tunnel `127.0.0.1:18087` -> T1000 Docker Compose nginx -> `web`/`api` services in `/home/yu/projects/dify-rag/docker`.
- Default to `scripts/deploy-18088.sh` for publishing after changes. Use the manual commands below only when the script is unavailable, needs debugging, or a special one-off deployment is required.
- After any backend, frontend, migration, or user-visible product change, publish to this node as part of the task unless the user explicitly says not to deploy.
- If the working tree has unrelated dirty files, create a clean deploy worktree from the intended commit, for example `git worktree add --detach /tmp/dify-rag-deploy-<sha> <sha>`, and build from that clean tree.
- Build images from the repository root of the intended source state:
  - `docker build -f api/Dockerfile -t mmbai/dify-api:local .`
  - `docker build -f web/Dockerfile -t mmbai/dify-web:local .`
- If API migrations changed, run them from `/home/yu/projects/dify-rag/docker` with `docker compose run --rm --no-deps api flask db upgrade`; verify `alembic_version` when needed.
- Recreate the runtime services from `/home/yu/projects/dify-rag/docker` with `docker compose up -d --no-build --force-recreate api api_websocket worker worker_beat web`.
- Restart nginx after recreating api or web because nginx can cache old Docker DNS upstream IPs for both upstreams: `docker compose restart nginx`.
- If `api` or `web` was recreated and the UI/API returns 502/503 while containers are healthy, restart nginx first; nginx is usually still using the old Docker upstream IP.
- Verify both the internal and public UI/API entrypoints before reporting completion:
  - On T1000: `curl -I http://127.0.0.1/admin` and `curl -I http://127.0.0.1/console/api/setup`
  - Public: `curl -I http://118.196.65.83:18088/admin` and `curl -I http://118.196.65.83:18088/console/api/setup`
  - Check logs when relevant: `docker compose logs --tail=100 api web nginx`
- If the browser still shows the old UI after deployment, tell the user to hard refresh with `Ctrl+F5` because stale Next.js chunks may be cached.
- For small visual/static-asset changes such as favicon, logo, image, or other `web/public` resource swaps, prefer a fast preview loop on T1000 before a full Docker rebuild: copy the candidate asset into the running `docker-web-1` container with `docker cp`, or otherwise replace only the needed runtime static asset for visual confirmation. After the user confirms the result, persist the same change in the repository, commit and push it, then run the build/deployment validation required by the actual change scope. Runtime-only replacement is never a final deliverable.
- For TSX/CSS behavior changes, compiled frontend code, dependencies, Dockerfile, compose, build scripts, or anything that affects built artifacts beyond static files, use the normal source-change plus production-equivalent Docker build flow. Do not treat editing built output as the final implementation.


## Related Windows Upload Client

- The Windows local file upload/ingestion client is a separate project at T1000 `/home/yu/projects/dify-file-ingestor`.
- It is a Windows-only WPF tray app for scanning local files, helping users choose approved work documents, and uploading them to a Dify knowledge base.
- Do not look for or implement this client inside `/home/yu/projects/dify-rag`.

## Backend Workflow

- Read `api/AGENTS.md` for details
- Run backend CLI commands through `uv run --project api <command>`.
- Integration tests are CI-only and are not expected to run in the local environment.

## Frontend Workflow

- Read `web/AGENTS.md` for details

## Testing & Quality Practices

- Follow TDD: red → green → refactor.
- Use `pytest` for backend tests with Arrange-Act-Assert structure.
- Enforce strong typing; avoid `Any` and prefer explicit type annotations.
- Write self-documenting code; only add comments that explain intent.

## Language Style

- **Python**: Keep type hints on functions and attributes, and implement relevant special methods (e.g., `__repr__`, `__str__`). Prefer `TypedDict` over `dict` or `Mapping` for type safety and better code documentation.
- **TypeScript**: Use the strict config, rely on ESLint (`pnpm lint:fix` preferred) plus `pnpm type-check`, and avoid `any` types.

## General Practices

- Prefer editing existing files; add new documentation only when requested.
- Inject dependencies through constructors and preserve clean architecture boundaries.
- Handle errors with domain-specific exceptions at the correct layer.

## Project Conventions

- Backend architecture adheres to DDD and Clean Architecture principles.
- Async work runs through Celery with Redis as the broker.
- Frontend user-facing strings must use `web/i18n/en-US/`; avoid hardcoded text.

## Customization Strategy

- Treat this repository as a long-lived Dify fork: prefer low-intrusion customization over deep rewrites of upstream logic.
- Prefer small extension points such as compatibility layers, new services, new APIs, additive database tables/fields, isolated admin pages, and deployment-time configuration over invasive core rewrites.
- When overriding upstream behavior is necessary, keep the change surface narrow, preserve default behavior where possible, and make upgrade impact obvious and localized.
- Production deployment should run images built from this repository or explicitly mounted compatibility files so runtime behavior stays aligned with the forked source tree.
- Optimize every customization for future upstream mergeability: fewer touched core files, clearer boundaries, and lower rework during later upgrades.

## Office Artifact Tooling Lessons

- For Agent-generated Word/PPT/Excel files, treat the work as a full artifact chain, not just file generation: tool output -> `ToolFile` row -> `MessageFile` row -> stream `message_file` event -> `message_end.files` -> signed `/files/tools` download URL -> frontend attachment card.
- Office tools should return binary/blob output with accurate metadata: original filename, extension, MIME type, and byte size. For Word, use `application/vnd.openxmlformats-officedocument.wordprocessingml.document`; for PowerPoint, use `application/vnd.openxmlformats-officedocument.presentationml.presentation`; for Excel, use `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- Do not let the LLM see or repeat raw `/files/tools/...` paths. Binary tool responses should tell the model that the file was sent as an attachment and that the user should download it from the attachment card. Raw storage or tool-file paths without a fresh signature will produce `403 Invalid request`.
- Historical and refreshed messages must re-sign tool files when serializing message files. `message_file.url` may be stored as a relative `/files/tools/{id}.ext` path, but UI-facing responses must include a signed URL with `timestamp`, `nonce`, and `sign`.
- The external `FILES_URL` must match the browser-safe public entrypoint. On 150 production use `https://ai.meinmalzebier.shop`, not `http://150.5.132.104`; otherwise Chrome may block downloads from an HTTPS page as unsafe, and users will see failed downloads even when the backend generated the file.
- If `.docx` appears as `BIN`, check the backend file serialization before changing the frontend. In this incident, the fallback path inferred the extension from `tool_file.file_key`; the durable fix was to prefer `tool_file.name`, then `tool_file.file_key`, then `mimetypes.guess_extension(tool_file.mimetype)`.
- Office MIME types must be classified as documents in `ToolEngine`; include at least `wordprocessingml`, `presentationml`, `spreadsheetml`, `msword`, and `ms-powerpoint`, not only `text` and `pdf`.
- `BINARY_LINK` must be treated like `BLOB` when extracting tool response binaries, otherwise the generated artifact may become only a text link and never appear as a downloadable attachment card.
- OpenAI Responses / proxy tool-call streams can emit partial or malformed function names such as blank names or `functions.generate_word_document`. Keep name normalization in the Agent runner and avoid executing partial streaming fragments before tool-call aggregation finishes.
- `py_compile` is not enough for import safety because it does not fully exercise application imports. After touching import paths, run a real import, targeted tests, or restart the API container and inspect logs. The correct `ToolFile` import path is `models.tools`, not always `models.model`.
- When testing this chain, verify both the stream event and the actual download: `message_file` should include `type=document`, `filename`, `.docx/.pptx/.xlsx`, MIME type, size, and an HTTPS signed URL; then download that URL and confirm `file` recognizes the Office format.
- If production needs a fast hotfix, copy only the relevant Python files into `mmb-dify-v010-api-1`, run `python -m py_compile`, restart the API container, and verify health. If the API container is recreated from compose, reapply hotfix files unless the image already contains the committed fix.
- Use the correct production compose project when recreating services: `docker compose -p mmb-dify-v010 -f /opt/mmb-dify/releases/v0.1.0/docker/docker-compose.yaml -f /opt/mmb-dify/current/docker/docker-compose.models.yaml -f /opt/mmb-dify/current/docker/docker-compose.yaml ...`. Running compose from the directory without `-p` can create an unintended `docker-*` stack.
- The successful 2026-07-04 validation query was: `帮我写一份MMB针对端午节的营销方案，大概1000字，使用word文档导入`. A passing result generated `MMB端午节营销方案.docx`, returned an HTTPS signed URL, did not expose raw `/files/tools`, and downloaded as `Microsoft Word 2007+`.
