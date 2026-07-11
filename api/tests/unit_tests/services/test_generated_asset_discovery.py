from datetime import datetime
from types import SimpleNamespace

from graphon.enums import WorkflowExecutionStatus
from services.generated_asset_discovery import (
    extract_workflow_asset_candidates,
    extract_workflow_tool_file_ids,
    remote_source_key,
    trusted_remote_asset_url,
)

POSTER_APP_ID = "13f7a06c-769d-474c-8863-613e9aeb25cb"
OTHER_APP_ID = "00000000-0000-0000-0000-000000000999"


def _run(*, app_id: str = OTHER_APP_ID, outputs: dict, run_id: str = "run-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=run_id,
        tenant_id="tenant-1",
        app_id=app_id,
        created_by="user-1",
        created_at=datetime(2026, 7, 1, 8, 30),
        status=WorkflowExecutionStatus.SUCCEEDED,
        inputs='{"video_request":"Make a launch video"}',
        outputs=outputs,
    )


def test_extracts_one_video_with_readable_title_and_image_attachments():
    run = _run(
        outputs={
            "status": "done",
            "result": "# Product launch\nDetails",
            "video_url": "https://vidgen.x.ai/videos/final.mp4?token=secret",
            "character_image_url": "https://ai.meinmalzebier.shop/images/character.png",
            "scene_image_url": "https://ai.meinmalzebier.shop/images/scene.jpg",
        }
    )

    candidates = extract_workflow_asset_candidates(run)

    assert len(candidates) == 1
    video = candidates[0]
    assert video.name == "Product launch.mp4"
    assert video.thumbnail_url.endswith("scene.jpg")
    assert len(video.asset_metadata["attachments"]) == 2
    assert video.created_at == run.created_at
    assert "token=secret" not in video.source_key


def test_rejects_business_failure_and_untrusted_video_url():
    failed = _run(outputs={"status": "failed", "video_url": "https://vidgen.x.ai/videos/final.mp4"})
    untrusted = _run(outputs={"status": "done", "video_url": "https://example.com/final.mp4"})

    assert extract_workflow_asset_candidates(failed) == []
    assert extract_workflow_asset_candidates(untrusted) == []
    assert trusted_remote_asset_url("http://vidgen.x.ai/final.mp4") is None


def test_poster_is_limited_to_known_apps_and_requires_high_resolution_source():
    poster_id = "12345678-1234-1234-1234-123456789abc"
    answer = (
        f"![full](https://ai.meinmalzebier.shop/poster-files/files/poster-{poster_id}.png)\n"
        f"![thumb](https://ai.meinmalzebier.shop/poster-files/files/poster-{poster_id}-thumb.jpg)"
    )

    assert extract_workflow_asset_candidates(_run(outputs={"answer": answer})) == []
    candidates = extract_workflow_asset_candidates(_run(app_id=POSTER_APP_ID, outputs={"answer": answer}))

    assert len(candidates) == 1
    assert candidates[0].source_url.endswith(f"poster-{poster_id}.png")
    assert candidates[0].thumbnail_url.endswith(f"poster-{poster_id}-thumb.jpg")


def test_legacy_poster_is_canonicalized_and_deduplicated_with_cdn_url():
    poster_id = "abcdefab-1234-5678-90ab-abcdefabcdef"
    legacy = f"http://150.5.132.104:8088/files/poster-{poster_id}.png"
    current = f"https://ai.meinmalzebier.shop/poster-files/files/poster-{poster_id}.png"

    legacy_candidate = extract_workflow_asset_candidates(
        _run(app_id=POSTER_APP_ID, outputs={"answer": legacy}, run_id="run-legacy")
    )[0]
    current_candidate = extract_workflow_asset_candidates(
        _run(app_id=POSTER_APP_ID, outputs={"answer": current}, run_id="run-current")
    )[0]

    assert legacy_candidate.source_url == current
    assert legacy_candidate.source_key == current_candidate.source_key


def test_remote_source_key_ignores_query_and_fragment():
    plain = remote_source_key("video", "https://vidgen.x.ai/video/final.mp4")
    signed = remote_source_key("video", "https://vidgen.x.ai/video/final.mp4?token=x#preview")
    assert plain == signed


def test_remote_source_key_is_scoped_to_owner_and_app():
    url = "https://vidgen.x.ai/video/final.mp4"

    first = remote_source_key("video", url, owner_user_id="user-1", source_app_id="app-1")
    other_user = remote_source_key("video", url, owner_user_id="user-2", source_app_id="app-1")
    other_app = remote_source_key("video", url, owner_user_id="user-1", source_app_id="app-2")

    assert len({first, other_user, other_app}) == 3


def test_extracts_only_native_tool_files_from_final_outputs():
    tool_file_id = "00000000-0000-0000-0000-000000000010"
    run = _run(
        outputs={
            "files": [
                {
                    "dify_model_identity": "__dify__file__",
                    "transfer_method": "tool_file",
                    "related_id": tool_file_id,
                },
                {
                    "dify_model_identity": "__dify__file__",
                    "transfer_method": "remote_url",
                    "related_id": "00000000-0000-0000-0000-000000000011",
                },
            ],
            "untrusted": {"tool_file_id": "00000000-0000-0000-0000-000000000012"},
        }
    )

    assert extract_workflow_tool_file_ids(run) == [tool_file_id]
