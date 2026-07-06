from services.generated_file_service import _owner_display_name


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


def test_owner_display_name_labels_service_api_as_feishu_hermes_user():
    assert (
        _owner_display_name(
            owner_id="owner-1",
            account_name=None,
            end_user_session_id="feishu-user-session-123",
            end_user_type="service-api",
            end_user_name=None,
        )
        == "飞书/Hermes 用户 · feishu-u"
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
        == "WebApp 用户 · web-sess"
    )
