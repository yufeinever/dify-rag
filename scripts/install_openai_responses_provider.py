from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app import app
from core.plugin.plugin_service import PluginService

DEFAULT_TENANT_ID = "60630e96-a41c-481d-92e2-c6f83c9e4749"
TERMINAL_STATUSES = {"success", "failed", "partial_success", "completed"}


def main() -> None:
    tenant_id = os.environ.get("DIFY_TENANT_ID", DEFAULT_TENANT_ID)
    pkg_path = Path(os.environ.get("PLUGIN_PKG", "/tmp/openai_responses_provider-0.1.0.pkg"))
    if not pkg_path.exists():
        raise FileNotFoundError(f"Plugin package not found: {pkg_path}")

    with app.app_context():
        response = PluginService.upload_pkg(tenant_id, pkg_path.read_bytes(), verify_signature=False)
        identifier = response.unique_identifier
        task = PluginService.install_from_local_pkg(tenant_id, [identifier])
        task_id = getattr(task, "id", None) or getattr(task, "task_id", None)
        print(json.dumps({"uploaded_identifier": identifier, "install_task": str(task_id)}, ensure_ascii=False), flush=True)

        final_payload = None
        for i in range(90):
            status = PluginService.fetch_install_task(tenant_id, str(task_id))
            payload = {
                "i": i,
                "status": str(getattr(status, "status", "")),
                "message": str(getattr(status, "message", "")),
            }
            print(json.dumps(payload, ensure_ascii=False), flush=True)
            final_payload = payload
            if payload["status"].lower() in TERMINAL_STATUSES:
                break
            time.sleep(2)

        PluginService.invalidate_plugin_model_providers_cache(tenant_id)
        if not final_payload or final_payload["status"].lower() not in {"success", "completed"}:
            raise RuntimeError(f"Plugin install did not complete successfully: {final_payload}")


if __name__ == "__main__":
    main()
