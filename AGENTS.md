# AGENTS.md

## Project Overview

Dify is an open-source platform for developing LLM applications with an intuitive interface combining agentic AI workflows, RAG pipelines, agent capabilities, and model management.

The codebase is split into:

- **Backend API** (`/api`): Python Flask application organized with Domain-Driven Design
- **Frontend Web** (`/web`): Next.js application using TypeScript and React
- **Docker deployment** (`/docker`): Containerized deployment configurations
- **Dify Agent Backend** (`/dify-agent`): Backend services for managing and executing agent

## Development Location

- Canonical MMB-Dify development happens on the 150 production host at `/opt/mmb-dify/current`.
- `/opt/mmb-dify/current` is the only development baseline for this project unless the user explicitly says otherwise.
- Do not make MMB-Dify feature or product changes in the Windows local mirror `C:\Users\86150\Documents\RAG_for_dify` or the historical T1000 tree `/home/yu/projects/dify-rag`; treat them as historical references or patch-transfer locations only.
- When Codex needs to change this project, SSH to the 150 production host with `ssh mmb-dify-150` or `ssh root@150.5.132.104`, work in `/opt/mmb-dify/current`, then commit and push from that repository.

## Production Deployment: 150.5.132.104

- The public MMB-Dify production node is hosted on the 150 production machine. Do not assume a source commit is visible to users until the production-equivalent Docker build/restart path has been completed on that machine.
- Production source path: `/opt/mmb-dify/current`.
- Production Docker Compose project: `mmb-dify-v010`. Always include `-p mmb-dify-v010` in compose commands on 150 to avoid touching a default project by mistake.
- Build and restart from the repository root with the production compose file and env file, for example:
  - `docker compose -p mmb-dify-v010 -f docker/docker-compose.yaml --env-file docker/.env build web`
  - `docker compose -p mmb-dify-v010 -f docker/docker-compose.yaml --env-file docker/.env up -d web`
- For API, worker, migration, nginx, plugin daemon, or database changes, state the affected services, database impact, verification commands, and rollback path before deployment.
- After every production release, update `VERSION`, `DEPLOYMENT_VERSION`, and `版本迭代说明.md` with the next sequential version number, deployment time, image tags, restarted services, database impact, verification, and rollback instructions.
- Before reporting completion, verify the relevant production UI/API entrypoints and inspect service status/logs as needed with the `mmb-dify-v010` compose project.


## Related Windows Upload Client

- The Windows local file upload/ingestion client is a separate project at T1000 `/home/yu/projects/dify-file-ingestor`.
- It is a Windows-only WPF tray app for scanning local files, helping users choose approved work documents, and uploading them to a Dify knowledge base.
- Do not look for or implement this client inside this MMB-Dify repository.

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
