from types import SimpleNamespace
from unittest.mock import MagicMock

from graphon.enums import WorkflowExecutionStatus
from models.tools import GeneratedFile
from services.generated_asset_discovery import GeneratedAssetCandidate
from services.generated_file_service import (
    _enrich_existing_asset,
    _owner_display_name,
    build_generated_file_preview_config,
    build_workflow_tool_file_candidates,
    classify_file_type,
    get_generated_file_for_end_user,
    serialize_generated_asset,
)


def test_owner_display_name_prefers_console_account_name():
    assert (
        _owner_display_name(
            owner_id="owner-1",
            account_name="Admin",
            end_user_session_id="feishu-session",
            end_user_type="service-api",
            end_user_name=None,
        )
        == "Admin"
    )


def test_owner_display_name_labels_service_api_without_guessing_channel():
    assert (
        _owner_display_name(
            owner_id="owner-1",
            account_name=None,
            end_user_session_id="feishu-user-session-123",
            end_user_type="service-api",
            end_user_name=None,
        )
        == "Service API 用户 · feis...-123"
    )


def test_owner_display_name_preserves_namespaced_channel_and_unique_suffix():
    assert (
        _owner_display_name(
            owner_id="owner-1",
            account_name=None,
            end_user_session_id="feishu:ou_abcdef123456",
            end_user_type="service-api",
            end_user_name=None,
        )
        == "feishu · ou_a...3456"
    )


def test_owner_display_name_labels_web_app_user_separately():
    assert (
        _owner_display_name(
            owner_id="owner-1",
            account_name=None,
            end_user_session_id="web-session-123",
            end_user_type="web-app",
            end_user_name=None,
        )
        == "WebApp 用户 · web-...-123"
    )


def test_classify_generated_asset_categories():
    assert classify_file_type("video/mp4", "clip.mp4") == "video"
    assert classify_file_type("audio/mpeg", "voice.mp3") == "audio"
    assert classify_file_type("application/octet-stream", "deck.pptx") == "presentation"
    assert classify_file_type("application/octet-stream", "bundle.zip") == "archive"


def test_service_asset_lookup_contains_tenant_app_and_end_user_scope():
    session = MagicMock()
    session.scalar.return_value = None

    get_generated_file_for_end_user(
        session,
        generated_file_id="asset-id",
        tenant_id="tenant-id",
        app_id="app-id",
        end_user_id="end-user-id",
    )

    statement = session.scalar.call_args.args[0]
    assert {
        "asset-id",
        "tenant-id",
        "app-id",
        "end-user-id",
    }.issubset(set(statement.compile().params.values()))


def test_remote_video_preview_keeps_asset_category_and_supporting_metadata():
    asset = GeneratedFile(
        tenant_id="00000000-0000-0000-0000-000000000001",
        owner_user_id="00000000-0000-0000-0000-000000000002",
        storage_type="remote_url",
        source_url="https://vidgen.x.ai/videos/final.mp4",
        thumbnail_url="https://ai.meinmalzebier.shop/images/scene.jpg",
        source_kind="workflow_video",
        source_key="remote:video:test",
        asset_metadata={"scene_image_url": "https://ai.meinmalzebier.shop/images/scene.jpg"},
        name="Launch video.mp4",
        mime_type="video/mp4",
        file_type="video",
        size=-1,
    )

    preview = build_generated_file_preview_config(asset)

    assert preview["file_type"] == "video"
    assert preview["extension"] == "mp4"
    assert preview["preview_kind"] == "native"
    assert preview["thumbnail_url"] == asset.thumbnail_url
    assert preview["asset_metadata"] == asset.asset_metadata

    serialized = serialize_generated_asset(asset, source_app_name="Video Studio", owner_name="Owner")
    assert serialized["mode"] == "remote"


def test_message_file_enrichment_repairs_verified_tool_file_owner():
    tool_file_id = "00000000-0000-0000-0000-000000000003"
    asset = GeneratedFile(
        tenant_id="00000000-0000-0000-0000-000000000001",
        owner_user_id="00000000-0000-0000-0000-000000000002",
        tool_file_id=tool_file_id,
        storage_type="tool_file",
        source_kind="message_file",
        source_key=None,
        name="report.pdf",
        mime_type="application/pdf",
        file_type="document",
        size=100,
    )
    candidate = GeneratedAssetCandidate(
        tenant_id=asset.tenant_id,
        owner_user_id="00000000-0000-0000-0000-000000000004",
        tool_file_id=tool_file_id,
        storage_type="tool_file",
        source_kind="message_file",
        source_key=f"tool-file:{tool_file_id}",
        source_message_id="00000000-0000-0000-0000-000000000005",
        name=asset.name,
        mime_type=asset.mime_type,
        file_type=asset.file_type,
    )

    _enrich_existing_asset(asset, candidate)

    assert asset.owner_user_id == candidate.owner_user_id


def test_non_message_enrichment_does_not_reassign_owner():
    original_owner_id = "00000000-0000-0000-0000-000000000002"
    asset = GeneratedFile(
        tenant_id="00000000-0000-0000-0000-000000000001",
        owner_user_id=original_owner_id,
        storage_type="remote_url",
        source_url="https://vidgen.x.ai/videos/final.mp4?token=old",
        source_kind="workflow_video",
        source_key="remote:video:test",
        asset_metadata={"character_image_url": "https://ai.meinmalzebier.shop/character.jpg?token=old"},
        name="clip.mp4",
        mime_type="video/mp4",
        file_type="video",
        size=-1,
    )
    candidate = GeneratedAssetCandidate(
        tenant_id=asset.tenant_id,
        owner_user_id="00000000-0000-0000-0000-000000000004",
        storage_type="remote_url",
        source_url="https://vidgen.x.ai/videos/final.mp4?token=new",
        source_kind="workflow_video",
        source_key=asset.source_key,
        asset_metadata={"character_image_url": "https://ai.meinmalzebier.shop/character.jpg?token=new"},
        name=asset.name,
        mime_type=asset.mime_type,
        file_type=asset.file_type,
    )

    _enrich_existing_asset(asset, candidate)

    assert asset.owner_user_id == original_owner_id
    assert asset.source_url == "https://vidgen.x.ai/videos/final.mp4?token=new"
    assert asset.asset_metadata == candidate.asset_metadata


def test_workflow_tool_file_candidate_requires_matching_tenant_and_owner():
    tenant_id = "00000000-0000-0000-0000-000000000001"
    owner_id = "00000000-0000-0000-0000-000000000002"
    tool_file_id = "00000000-0000-0000-0000-000000000003"
    session = MagicMock()
    session.get.return_value = SimpleNamespace(
        id=tool_file_id,
        tenant_id=tenant_id,
        user_id=owner_id,
        conversation_id=None,
        name="workflow-report.pdf",
        mimetype="application/pdf",
        size=100,
    )
    workflow_run = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000004",
        tenant_id=tenant_id,
        app_id="00000000-0000-0000-0000-000000000005",
        created_by=owner_id,
        created_at=None,
        status=WorkflowExecutionStatus.SUCCEEDED,
        outputs={
            "file": {
                "dify_model_identity": "__dify__file__",
                "transfer_method": "tool_file",
                "related_id": tool_file_id,
            }
        },
    )

    candidates = build_workflow_tool_file_candidates(session, workflow_run)

    assert len(candidates) == 1
    assert candidates[0].tool_file_id == tool_file_id
    assert candidates[0].source_kind == "workflow_tool_file"
    assert candidates[0].source_workflow_run_id == workflow_run.id

    session.get.return_value.tenant_id = "00000000-0000-0000-0000-000000000099"
    assert build_workflow_tool_file_candidates(session, workflow_run) == []
