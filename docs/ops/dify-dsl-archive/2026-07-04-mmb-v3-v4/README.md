# MMB V3/V4 Dify DSL Archive

This directory contains official Dify DSL exports from production `150.5.132.104` for the retired MMB V3/V4 validation apps and their RAG ingestion pipelines.

Export time: `2026-07-03T17:43:18Z`.

Secrets were intentionally excluded by calling Dify export with `include_secret=false`. Plugin authorizations and model credentials must be re-bound in the target workspace after import.

## Contents

- `manifest.json`: object IDs, source names, workflow versions, and file mapping.
- `v3/app/v3-app-default-draft.yml`: draft DSL for `MMB业务助手-v3-pdf增强`.
- `v3/app/workflows/*.yml`: published workflow-version DSLs for the V3 app.
- `v3/rag-pipeline/v3-rag-pipeline.yml`: RAG pipeline DSL for `MMB统一材料知识库-v3-pdf增强`.
- `v4/app/v4-app-default-draft.yml`: draft DSL for `MMB业务助手-v4-表格增强`.
- `v4/app/workflows/*.yml`: published workflow-version DSLs for the V4 app.
- `v4/rag-pipeline/v4-rag-pipeline.yml`: RAG pipeline DSL for `MMB统一材料知识库-v4-表格增强`.

## Restore Notes

1. Import the RAG pipeline DSL first if the app should point at a restored knowledge ingestion pipeline.
2. Import the desired app DSL in Dify.
3. Re-bind knowledge base references, plugin authorizations, and model providers in the target workspace.
4. Publish the imported app before exposing it in Explore.

The `*-default-draft.yml` files represent draft state. Files under `app/workflows/` represent published workflow versions that Dify allowed exporting by explicit workflow ID.
