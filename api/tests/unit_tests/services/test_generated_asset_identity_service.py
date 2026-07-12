from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from models.tools import GeneratedFile
from services.generated_asset_identity_service import channel_type_for_end_user, identity_display_name
from services.generated_file_service import list_generated_files, serialize_generated_asset


def test_channel_type_detects_namespaced_service_identity():
    assert channel_type_for_end_user(SimpleNamespace(type="service-api", session_id="feishu:ou_123")) == "feishu"
    assert channel_type_for_end_user(SimpleNamespace(type="service-api", session_id="openclaw:user-1")) == "openclaw"
    assert channel_type_for_end_user(SimpleNamespace(type="web-app", session_id="session")) == "webapp"


def test_identity_display_name_uses_channel_and_masks_external_id():
    end_user = SimpleNamespace(id="end-user", type="service-api", session_id="feishu:ou_abcdefgh1234")
    assert identity_display_name(end_user) == "飞书 · ou_a...1234"


def test_serialized_asset_exposes_person_and_identity_without_changing_owner():
    owner_id = "00000000-0000-0000-0000-000000000002"
    asset = GeneratedFile(
        tenant_id="00000000-0000-0000-0000-000000000001",
        owner_user_id=owner_id,
        storage_type="remote_url",
        source_url="https://vidgen.x.ai/videos/final.mp4",
        source_kind="workflow_video",
        source_key="identity:test",
        asset_metadata={},
        name="clip.mp4",
        mime_type="video/mp4",
        file_type="video",
        size=-1,
    )
    serialized = serialize_generated_asset(
        asset,
        source_app_name="Video",
        owner_name="飞书 · 1234",
        person_name="mmbadmin",
        identity_name="飞书 · 1234",
        channel_type="feishu",
        identity_bound=True,
    )
    assert serialized["owner_user_id"] == owner_id
    assert serialized["person_name"] == "mmbadmin"
    assert serialized["channel_type"] == "feishu"
    assert serialized["identity_bound"] is True


def _compiled_values(filters):
    values = set()
    for condition in filters:
        for value in condition.compile().params.values():
            if isinstance(value, list):
                values.update(value)
            else:
                values.add(value)
    return values


@patch("services.generated_file_service._execute_asset_list")
@patch("services.generated_file_service.bound_identity_ids", return_value=["00000000-0000-0000-0000-000000000003"])
def test_my_scope_includes_account_and_bound_identity(mock_bound, mock_execute):
    mock_execute.return_value = {"data": []}
    session = MagicMock()
    user = SimpleNamespace(id="00000000-0000-0000-0000-000000000002", is_admin_or_owner=True)
    list_generated_files(
        session,
        tenant_id="00000000-0000-0000-0000-000000000001",
        current_user=user,
        page=1,
        limit=20,
        scope="my",
    )
    filters = mock_execute.call_args.kwargs["filters"]
    assert {user.id, "00000000-0000-0000-0000-000000000003"}.issubset(_compiled_values(filters))
    mock_bound.assert_called_once()


@patch("services.generated_file_service._execute_asset_list")
@patch("services.generated_file_service.bound_identity_ids", return_value=[])
def test_normal_member_cannot_expand_scope_to_all(mock_bound, mock_execute):
    mock_execute.return_value = {"data": []}
    session = MagicMock()
    user = SimpleNamespace(id="00000000-0000-0000-0000-000000000002", is_admin_or_owner=False)
    list_generated_files(
        session,
        tenant_id="00000000-0000-0000-0000-000000000001",
        current_user=user,
        page=1,
        limit=20,
        scope="all",
    )
    filters = mock_execute.call_args.kwargs["filters"]
    assert user.id in _compiled_values(filters)
    mock_bound.assert_called_once()
