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
