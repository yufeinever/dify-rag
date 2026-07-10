from io import BytesIO
import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from flask import Flask
from werkzeug.exceptions import (
    BadRequest,
    NotFound,
    RequestEntityTooLarge,
    UnsupportedMediaType,
)

from controllers.inner_api.ppt_artifacts import (
    ModelPptxArtifactUploadApi,
    PPTX_MAX_BYTES,
    _require_artifact_api_key,
    validate_pptx_upload,
)


def _pptx_bytes(*, include_slide: bool = True) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("ppt/presentation.xml", "<p:presentation />")
        if include_slide:
            archive.writestr("ppt/slides/slide1.xml", "<p:sld />")
    return output.getvalue()


def test_validate_pptx_upload_accepts_valid_package():
    assert validate_pptx_upload("演示文稿.pptx", _pptx_bytes()) == "演示文稿.pptx"


@pytest.mark.parametrize(
    "filename", ["deck.pdf", "../deck.pptx", "folder/deck.pptx", "folder\\deck.pptx"]
)
def test_validate_pptx_upload_rejects_invalid_filename(filename):
    expected = UnsupportedMediaType if filename == "deck.pdf" else BadRequest
    with pytest.raises(expected):
        validate_pptx_upload(filename, _pptx_bytes())


def test_validate_pptx_upload_rejects_corrupt_or_slideless_package():
    with pytest.raises(BadRequest):
        validate_pptx_upload("deck.pptx", b"not-a-zip")
    with pytest.raises(BadRequest):
        validate_pptx_upload("deck.pptx", _pptx_bytes(include_slide=False))


def test_validate_pptx_upload_rejects_oversized_file():
    with pytest.raises(RequestEntityTooLarge):
        validate_pptx_upload("deck.pptx", b"x" * (PPTX_MAX_BYTES + 1))


def test_artifact_api_key_is_required():
    app = Flask(__name__)
    with patch(
        "controllers.inner_api.ppt_artifacts.dify_config.PPT_ARTIFACT_API_KEY", "secret"
    ):
        with app.test_request_context(headers={"Authorization": "Bearer secret"}):
            _require_artifact_api_key()
        with app.test_request_context(headers={"Authorization": "Bearer wrong"}):
            with pytest.raises(NotFound):
                _require_artifact_api_key()


def test_upload_persists_pptx_and_returns_external_download_url():
    app = Flask(__name__)
    tool_file = SimpleNamespace(id="file-id", name="deck.pptx", size=len(_pptx_bytes()))
    manager = MagicMock()
    manager.create_file_by_raw.return_value = tool_file
    raw_post = inspect.unwrap(ModelPptxArtifactUploadApi.post)

    with (
        app.test_request_context(
            method="POST",
            data={
                "tenant_id": "tenant-id",
                "user_id": "user-id",
                "file": (BytesIO(_pptx_bytes()), "deck.pptx"),
            },
            headers={"Authorization": "Bearer secret"},
        ),
        patch(
            "controllers.inner_api.ppt_artifacts.dify_config.PPT_ARTIFACT_API_KEY",
            "secret",
        ),
        patch(
            "controllers.inner_api.ppt_artifacts.db.session.get",
            side_effect=[object(), object()],
        ),
        patch(
            "controllers.inner_api.ppt_artifacts.db.session.scalar",
            return_value="membership-id",
        ),
        patch(
            "controllers.inner_api.ppt_artifacts.ToolFileManager", return_value=manager
        ),
        patch(
            "controllers.inner_api.ppt_artifacts.sign_tool_file",
            return_value="https://example.test/file?sign=x",
        ),
    ):
        payload, status = raw_post(ModelPptxArtifactUploadApi())

    assert status == 201
    assert (
        payload["download_url"] == "https://example.test/file?sign=x&as_attachment=true"
    )
    manager.create_file_by_raw.assert_called_once()
