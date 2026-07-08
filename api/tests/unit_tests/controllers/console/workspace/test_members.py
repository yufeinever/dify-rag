from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from werkzeug.exceptions import HTTPException

import services
from controllers.console.auth.error import (
    CannotTransferOwnerToSelfError,
    EmailAlreadyInUseError,
    EmailCodeError,
    InvalidEmailError,
    InvalidTokenError,
    MemberNotInTenantError,
    NotOwnerError,
    OwnerTransferLimitError,
    PasswordMismatchError,
)
from controllers.console.error import EmailSendIpLimitError, WorkspaceMembersLimitExceeded
from controllers.console.workspace.members import (
    DatasetOperatorMemberListApi,
    MemberCancelInviteApi,
    MemberInviteEmailApi,
    MemberListApi,
    MemberPasswordResetApi,
    MemberUpdateRoleApi,
    OwnerTransfer,
    OwnerTransferCheckApi,
    SendOwnerTransferEmailApi,
)
from services.errors.account import AccountAlreadyInTenantError


def unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


class TestMemberListApi:
    def test_get_success(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.get)

        tenant = MagicMock()
        user = MagicMock(current_tenant=tenant)
        member = MagicMock()
        member.id = "m1"
        member.name = "Member"
        member.email = "member@test.com"
        member.avatar = "avatar.png"
        member.role = "admin"
        member.status = "active"
        members = [member]

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.get_tenant_members", return_value=members),
        ):
            result, status = method(api)

        assert status == 200
        assert len(result["accounts"]) == 1

    def test_get_no_tenant(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.get)

        user = MagicMock(current_tenant=None)

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
        ):
            with pytest.raises(ValueError):
                method(api)


    def test_post_create_normal_success_for_owner(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)

        tenant = MagicMock(id="tenant-id")
        current_user = MagicMock(id="owner-id", current_tenant=tenant, interface_language="en-US", timezone="UTC")
        features = MagicMock()
        features.workspace_members.is_available.return_value = True
        account = SimpleNamespace(
            id="new-id",
            name="Alice",
            email="alice@example.com",
            avatar=None,
            status="active",
            last_login_at=None,
            last_active_at=None,
            created_at=None,
            role="normal",
        )
        member_model = MagicMock()
        member_model.model_dump.return_value = {"id": "new-id", "email": "alice@example.com", "role": "normal"}
        payload = {
            "email": "Alice@Example.COM",
            "name": "Alice",
            "role": "normal",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "tenant-id")),
            patch("controllers.console.workspace.members.TenantService.get_user_role", return_value="owner"),
            patch("controllers.console.workspace.members.AccountService.get_account_by_email_with_case_fallback", return_value=None),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
            patch("controllers.console.workspace.members.AccountService.create_account", return_value=account) as create_mock,
            patch("controllers.console.workspace.members.TenantService.create_tenant_member") as join_mock,
            patch("controllers.console.workspace.members.TenantService.switch_tenant") as switch_mock,
            patch("controllers.console.workspace.members.AccountWithRole.model_validate", return_value=member_model),
            patch("controllers.console.workspace.members.db.session.refresh"),
            patch("controllers.console.workspace.members.db.session.add") as add_mock,
            patch("controllers.console.workspace.members.db.session.commit") as commit_mock,
        ):
            result, status = method(api)

        assert status == 201
        assert result["result"] == "success"
        create_mock.assert_called_once()
        assert create_mock.call_args.kwargs["email"] == "alice@example.com"
        assert create_mock.call_args.kwargs["is_setup"] is True
        join_mock.assert_called_once_with(tenant=tenant, account=account, role="normal")
        switch_mock.assert_called_once_with(account=account, tenant_id=tenant.id)
        audit_log = add_mock.call_args.args[0]
        assert audit_log.action == "member.direct_create"
        assert audit_log.content == {
            "target_account_id": "new-id",
            "target_email": "alice@example.com",
            "target_role": "normal",
        }
        assert "password" not in audit_log.content
        commit_mock.assert_called()

    def test_post_create_admin_success_for_owner(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)

        tenant = MagicMock(id="tenant-id")
        current_user = MagicMock(id="owner-id", current_tenant=tenant, interface_language="en-US", timezone="UTC")
        features = MagicMock()
        features.workspace_members.is_available.return_value = True
        account = SimpleNamespace(
            id="new-admin-id",
            name="Admin",
            email="admin@example.com",
            avatar=None,
            status="active",
            last_login_at=None,
            last_active_at=None,
            created_at=None,
            role="admin",
        )
        member_model = MagicMock()
        member_model.model_dump.return_value = {"id": "new-admin-id", "email": "admin@example.com", "role": "admin"}
        payload = {
            "email": "admin@example.com",
            "role": "admin",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "tenant-id")),
            patch("controllers.console.workspace.members.TenantService.get_user_role", return_value="owner"),
            patch("controllers.console.workspace.members.AccountService.get_account_by_email_with_case_fallback", return_value=None),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
            patch("controllers.console.workspace.members.AccountService.create_account", return_value=account),
            patch("controllers.console.workspace.members.TenantService.create_tenant_member") as join_mock,
            patch("controllers.console.workspace.members.TenantService.switch_tenant"),
            patch("controllers.console.workspace.members.AccountWithRole.model_validate", return_value=member_model),
            patch("controllers.console.workspace.members.db.session.refresh"),
            patch("controllers.console.workspace.members.db.session.add"),
            patch("controllers.console.workspace.members.db.session.commit"),
        ):
            _, status = method(api)

        assert status == 201
        join_mock.assert_called_once_with(tenant=tenant, account=account, role="admin")

    def test_post_create_normal_success_for_admin(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)

        tenant = MagicMock(id="tenant-id")
        current_user = MagicMock(id="admin-id", current_tenant=tenant, interface_language="en-US", timezone="UTC")
        features = MagicMock()
        features.workspace_members.is_available.return_value = True
        account = SimpleNamespace(
            id="new-id",
            name="Bob",
            email="bob@example.com",
            avatar=None,
            status="active",
            last_login_at=None,
            last_active_at=None,
            created_at=None,
            role="normal",
        )
        member_model = MagicMock()
        member_model.model_dump.return_value = {"id": "new-id", "email": "bob@example.com", "role": "normal"}
        payload = {
            "email": "bob@example.com",
            "role": "normal",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "tenant-id")),
            patch("controllers.console.workspace.members.TenantService.get_user_role", return_value="admin"),
            patch("controllers.console.workspace.members.AccountService.get_account_by_email_with_case_fallback", return_value=None),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
            patch("controllers.console.workspace.members.AccountService.create_account", return_value=account) as create_mock,
            patch("controllers.console.workspace.members.TenantService.create_tenant_member"),
            patch("controllers.console.workspace.members.TenantService.switch_tenant"),
            patch("controllers.console.workspace.members.AccountWithRole.model_validate", return_value=member_model),
            patch("controllers.console.workspace.members.db.session.refresh"),
            patch("controllers.console.workspace.members.db.session.add"),
            patch("controllers.console.workspace.members.db.session.commit"),
        ):
            _, status = method(api)

        assert status == 201
        create_mock.assert_called_once()

    def test_post_create_rejects_admin_creating_admin(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)
        tenant = MagicMock(id="tenant-id")
        current_user = MagicMock(current_tenant=tenant)
        payload = {
            "email": "admin@example.com",
            "role": "admin",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "tenant-id")),
            patch("controllers.console.workspace.members.TenantService.get_user_role", return_value="admin"),
            patch("controllers.console.workspace.members.AccountService.create_account") as create_mock,
        ):
            result, status = method(api)

        assert status == 403
        assert result["code"] == "forbidden"
        create_mock.assert_not_called()

    def test_post_create_rejects_owner_role(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)
        payload = {
            "email": "owner@example.com",
            "role": "owner",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with app.test_request_context("/", json=payload):
            result, status = method(api)

        assert status == 400
        assert result["code"] == "invalid-role"

    def test_post_create_rejects_existing_email(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)
        tenant = MagicMock(id="tenant-id")
        current_user = MagicMock(current_tenant=tenant)
        payload = {
            "email": "exists@example.com",
            "role": "normal",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "tenant-id")),
            patch("controllers.console.workspace.members.TenantService.get_user_role", return_value="owner"),
            patch("controllers.console.workspace.members.AccountService.get_account_by_email_with_case_fallback", return_value=MagicMock()),
        ):
            with pytest.raises(EmailAlreadyInUseError):
                method(api)

    def test_post_create_rejects_password_mismatch(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)
        payload = {
            "email": "mismatch@example.com",
            "role": "normal",
            "password": "newPassword123",
            "password_confirm": "otherPassword123",
        }

        with app.test_request_context("/", json=payload):
            with pytest.raises(PasswordMismatchError):
                method(api)

    def test_post_create_rejects_member_limit(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)
        tenant = MagicMock(id="tenant-id")
        current_user = MagicMock(current_tenant=tenant)
        features = MagicMock()
        features.workspace_members.is_available.return_value = False
        payload = {
            "email": "limit@example.com",
            "role": "normal",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "tenant-id")),
            patch("controllers.console.workspace.members.TenantService.get_user_role", return_value="owner"),
            patch("controllers.console.workspace.members.AccountService.get_account_by_email_with_case_fallback", return_value=None),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
        ):
            with pytest.raises(WorkspaceMembersLimitExceeded):
                method(api)

    def test_post_create_rejects_disabled_dataset_operator(self, app: Flask):
        api = MemberListApi()
        method = unwrap(api.post)
        tenant = MagicMock(id="tenant-id")
        current_user = MagicMock(current_tenant=tenant)
        features = MagicMock()
        features.dataset_operator_enabled = False
        payload = {
            "email": "dataset@example.com",
            "role": "dataset_operator",
            "password": "newPassword123",
            "password_confirm": "newPassword123",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "tenant-id")),
            patch("controllers.console.workspace.members.TenantService.get_user_role", return_value="owner"),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
            patch("controllers.console.workspace.members.AccountService.create_account") as create_mock,
        ):
            result, status = method(api)

        assert status == 400
        assert result["code"] == "invalid-role"
        create_mock.assert_not_called()


class TestMemberInviteEmailApi:
    def test_invite_success(self, app: Flask):
        api = MemberInviteEmailApi()
        method = unwrap(api.post)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        features = MagicMock()
        features.workspace_members.is_available.return_value = True

        payload = {
            "emails": ["a@test.com"],
            "role": "normal",
            "language": "en-US",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
            patch("controllers.console.workspace.members.RegisterService.invite_new_member", return_value="token"),
            patch("controllers.console.workspace.members.dify_config.CONSOLE_WEB_URL", "http://x"),
        ):
            result, status = method(api)

        assert status == 201
        assert result["result"] == "success"

    def test_invite_limit_exceeded(self, app: Flask):
        api = MemberInviteEmailApi()
        method = unwrap(api.post)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        features = MagicMock()
        features.workspace_members.is_available.return_value = False

        payload = {
            "emails": ["a@test.com"],
            "role": "normal",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
        ):
            with pytest.raises(WorkspaceMembersLimitExceeded):
                method(api)

    def test_invite_already_member(self, app: Flask):
        api = MemberInviteEmailApi()
        method = unwrap(api.post)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        features = MagicMock()
        features.workspace_members.is_available.return_value = True

        payload = {
            "emails": ["a@test.com"],
            "role": "normal",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
            patch(
                "controllers.console.workspace.members.RegisterService.invite_new_member",
                side_effect=AccountAlreadyInTenantError(),
            ),
            patch("controllers.console.workspace.members.dify_config.CONSOLE_WEB_URL", "http://x"),
        ):
            result, status = method(api)

        assert result["invitation_results"][0]["status"] == "success"

    def test_invite_invalid_role(self, app: Flask):
        api = MemberInviteEmailApi()
        method = unwrap(api.post)

        payload = {
            "emails": ["a@test.com"],
            "role": "owner",
        }

        with app.test_request_context("/", json=payload):
            result, status = method(api)

        assert status == 400
        assert result["code"] == "invalid-role"

    def test_invite_generic_exception(self, app: Flask):
        api = MemberInviteEmailApi()
        method = unwrap(api.post)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        features = MagicMock()
        features.workspace_members.is_available.return_value = True

        payload = {
            "emails": ["a@test.com"],
            "role": "normal",
        }

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.FeatureService.get_features", return_value=features),
            patch(
                "controllers.console.workspace.members.RegisterService.invite_new_member",
                side_effect=Exception("boom"),
            ),
            patch("controllers.console.workspace.members.dify_config.CONSOLE_WEB_URL", "http://x"),
        ):
            result, _ = method(api)

        assert result["invitation_results"][0]["status"] == "failed"


class TestMemberCancelInviteApi:
    def test_cancel_success(self, app: Flask):
        api = MemberCancelInviteApi()
        method = unwrap(api.delete)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        member = MagicMock()

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.db.session.get") as get_mock,
            patch("controllers.console.workspace.members.TenantService.remove_member_from_tenant"),
        ):
            get_mock.return_value = member
            result, status = method(api, member.id)

        assert status == 200
        assert result["result"] == "success"

    def test_cancel_not_found(self, app: Flask):
        api = MemberCancelInviteApi()
        method = unwrap(api.delete)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.db.session.get") as get_mock,
        ):
            get_mock.return_value = None

            with pytest.raises(HTTPException):
                method(api, "x")

    def test_cancel_cannot_operate_self(self, app: Flask):
        api = MemberCancelInviteApi()
        method = unwrap(api.delete)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        member = MagicMock()

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.db.session.get") as get_mock,
            patch(
                "controllers.console.workspace.members.TenantService.remove_member_from_tenant",
                side_effect=services.errors.account.CannotOperateSelfError("x"),
            ),
        ):
            get_mock.return_value = member
            result, status = method(api, member.id)

        assert status == 400

    def test_cancel_no_permission(self, app: Flask):
        api = MemberCancelInviteApi()
        method = unwrap(api.delete)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        member = MagicMock()

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.db.session.get") as get_mock,
            patch(
                "controllers.console.workspace.members.TenantService.remove_member_from_tenant",
                side_effect=services.errors.account.NoPermissionError("x"),
            ),
        ):
            get_mock.return_value = member
            result, status = method(api, member.id)

        assert status == 403

    def test_cancel_member_not_in_tenant(self, app: Flask):
        api = MemberCancelInviteApi()
        method = unwrap(api.delete)

        tenant = MagicMock(id="t1")
        user = MagicMock(current_tenant=tenant)
        member = MagicMock()

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.db.session.get") as get_mock,
            patch(
                "controllers.console.workspace.members.TenantService.remove_member_from_tenant",
                side_effect=services.errors.account.MemberNotInTenantError(),
            ),
        ):
            get_mock.return_value = member
            result, status = method(api, member.id)

        assert status == 404


class TestMemberPasswordResetApi:
    def test_reset_success_for_owner(self, app: Flask):
        api = MemberPasswordResetApi()
        method = unwrap(api.put)

        tenant = MagicMock()
        current_user = MagicMock(id="owner-id", current_tenant=tenant)
        member = MagicMock(id="member-id")
        payload = {"new_password": "newPassword123", "password_confirm": "newPassword123"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "t1")),
            patch("controllers.console.workspace.members.db.session.get", return_value=member),
            patch("controllers.console.workspace.members.TenantService.get_user_role", side_effect=["normal", "owner"]),
            patch("controllers.console.workspace.members.AccountService.set_account_password_without_current_password") as reset_mock,
            patch("controllers.console.workspace.members.db.session.add") as add_mock,
            patch("controllers.console.workspace.members.db.session.commit") as commit_mock,
        ):
            result = method(api, "member-id")

        assert result["result"] == "success"
        reset_mock.assert_called_once_with(member, "newPassword123")
        audit_log = add_mock.call_args.args[0]
        assert audit_log.action == "member.password.reset"
        assert audit_log.content["target_account_id"] == "member-id"
        assert "password" not in audit_log.content
        commit_mock.assert_called_once()

    def test_reset_rejects_admin_resetting_admin(self, app: Flask):
        api = MemberPasswordResetApi()
        method = unwrap(api.put)

        tenant = MagicMock()
        current_user = MagicMock(id="admin-id", current_tenant=tenant)
        member = MagicMock(id="member-id")
        payload = {"new_password": "newPassword123", "password_confirm": "newPassword123"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(current_user, "t1")),
            patch("controllers.console.workspace.members.db.session.get", return_value=member),
            patch("controllers.console.workspace.members.TenantService.get_user_role", side_effect=["admin", "admin"]),
            patch("controllers.console.workspace.members.AccountService.set_account_password_without_current_password") as reset_mock,
            patch("controllers.console.workspace.members.db.session.add") as add_mock,
        ):
            result, status = method(api, "member-id")

        assert status == 403
        assert result["code"] == "forbidden"
        reset_mock.assert_not_called()
        add_mock.assert_not_called()


class TestMemberUpdateRoleApi:
    def test_update_success(self, app: Flask):
        api = MemberUpdateRoleApi()
        method = unwrap(api.put)

        tenant = MagicMock()
        user = MagicMock(current_tenant=tenant)
        member = MagicMock()

        payload = {"role": "normal"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.db.session.get", return_value=member),
            patch("controllers.console.workspace.members.TenantService.update_member_role"),
        ):
            result = method(api, "id")

        if isinstance(result, tuple):
            result = result[0]

        assert result["result"] == "success"

    def test_update_invalid_role(self, app: Flask):
        api = MemberUpdateRoleApi()
        method = unwrap(api.put)

        payload = {"role": "invalid-role"}

        with app.test_request_context("/", json=payload):
            result, status = method(api, "id")

        assert status == 400

    def test_update_member_not_found(self, app: Flask):
        api = MemberUpdateRoleApi()
        method = unwrap(api.put)

        payload = {"role": "normal"}

        with (
            app.test_request_context("/", json=payload),
            patch(
                "controllers.console.workspace.members.current_account_with_tenant",
                return_value=(MagicMock(current_tenant=MagicMock()), "t1"),
            ),
            patch("controllers.console.workspace.members.db.session.get", return_value=None),
        ):
            with pytest.raises(HTTPException):
                method(api, "id")


class TestDatasetOperatorMemberListApi:
    def test_get_success(self, app: Flask):
        api = DatasetOperatorMemberListApi()
        method = unwrap(api.get)

        tenant = MagicMock()
        user = MagicMock(current_tenant=tenant)
        member = MagicMock()
        member.id = "op1"
        member.name = "Operator"
        member.email = "operator@test.com"
        member.avatar = "avatar.png"
        member.role = "operator"
        member.status = "active"
        members = [member]

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch(
                "controllers.console.workspace.members.TenantService.get_dataset_operator_members", return_value=members
            ),
        ):
            result, status = method(api)

        assert status == 200
        assert len(result["accounts"]) == 1

    def test_get_no_tenant(self, app: Flask):
        api = DatasetOperatorMemberListApi()
        method = unwrap(api.get)

        user = MagicMock(current_tenant=None)

        with (
            app.test_request_context("/"),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
        ):
            with pytest.raises(ValueError):
                method(api)


class TestSendOwnerTransferEmailApi:
    def test_send_success(self, app: Flask):
        api = SendOwnerTransferEmailApi()
        method = unwrap(api.post)

        tenant = MagicMock(name="ws")
        user = MagicMock(email="a@test.com", current_tenant=tenant)

        payload = {}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.extract_remote_ip", return_value="1.1.1.1"),
            patch("controllers.console.workspace.members.AccountService.is_email_send_ip_limit", return_value=False),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
            patch(
                "controllers.console.workspace.members.AccountService.send_owner_transfer_email", return_value="token"
            ),
        ):
            result = method(api)

        assert result["result"] == "success"

    def test_send_ip_limit(self, app: Flask):
        api = SendOwnerTransferEmailApi()
        method = unwrap(api.post)

        payload = {}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.extract_remote_ip", return_value="1.1.1.1"),
            patch("controllers.console.workspace.members.AccountService.is_email_send_ip_limit", return_value=True),
        ):
            with pytest.raises(EmailSendIpLimitError):
                method(api)

    def test_send_not_owner(self, app: Flask):
        api = SendOwnerTransferEmailApi()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(current_tenant=tenant)

        with (
            app.test_request_context("/", json={}),
            patch("controllers.console.workspace.members.extract_remote_ip", return_value="1.1.1.1"),
            patch("controllers.console.workspace.members.AccountService.is_email_send_ip_limit", return_value=False),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=False),
        ):
            with pytest.raises(NotOwnerError):
                method(api)


class TestOwnerTransferCheckApi:
    def test_check_invalid_code(self, app: Flask):
        api = OwnerTransferCheckApi()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(email="a@test.com", current_tenant=tenant)

        payload = {"code": "x", "token": "t"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
            patch(
                "controllers.console.workspace.members.AccountService.is_owner_transfer_error_rate_limit",
                return_value=False,
            ),
            patch(
                "controllers.console.workspace.members.AccountService.get_owner_transfer_data",
                return_value={"email": "a@test.com", "code": "y"},
            ),
        ):
            with pytest.raises(EmailCodeError):
                method(api)

    def test_rate_limited(self, app: Flask):
        api = OwnerTransferCheckApi()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(email="a@test.com", current_tenant=tenant)

        payload = {"code": "x", "token": "t"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
            patch(
                "controllers.console.workspace.members.AccountService.is_owner_transfer_error_rate_limit",
                return_value=True,
            ),
        ):
            with pytest.raises(OwnerTransferLimitError):
                method(api)

    def test_invalid_token(self, app: Flask):
        api = OwnerTransferCheckApi()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(email="a@test.com", current_tenant=tenant)

        payload = {"code": "x", "token": "t"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
            patch(
                "controllers.console.workspace.members.AccountService.is_owner_transfer_error_rate_limit",
                return_value=False,
            ),
            patch("controllers.console.workspace.members.AccountService.get_owner_transfer_data", return_value=None),
        ):
            with pytest.raises(InvalidTokenError):
                method(api)

    def test_invalid_email(self, app: Flask):
        api = OwnerTransferCheckApi()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(email="a@test.com", current_tenant=tenant)

        payload = {"code": "x", "token": "t"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
            patch(
                "controllers.console.workspace.members.AccountService.is_owner_transfer_error_rate_limit",
                return_value=False,
            ),
            patch(
                "controllers.console.workspace.members.AccountService.get_owner_transfer_data",
                return_value={"email": "b@test.com", "code": "x"},
            ),
        ):
            with pytest.raises(InvalidEmailError):
                method(api)


class TestOwnerTransferApi:
    def test_transfer_self(self, app: Flask):
        api = OwnerTransfer()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(id="1", email="a@test.com", current_tenant=tenant)

        payload = {"token": "t"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
        ):
            with pytest.raises(CannotTransferOwnerToSelfError):
                method(api, "1")

    def test_invalid_token(self, app: Flask):
        api = OwnerTransfer()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(id="1", email="a@test.com", current_tenant=tenant)

        payload = {"token": "t"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
            patch("controllers.console.workspace.members.AccountService.get_owner_transfer_data", return_value=None),
        ):
            with pytest.raises(InvalidTokenError):
                method(api, "2")

    def test_member_not_in_tenant(self, app: Flask):
        api = OwnerTransfer()
        method = unwrap(api.post)

        tenant = MagicMock()
        user = MagicMock(id="1", email="a@test.com", current_tenant=tenant)
        member = MagicMock()

        payload = {"token": "t"}

        with (
            app.test_request_context("/", json=payload),
            patch("controllers.console.workspace.members.current_account_with_tenant", return_value=(user, "t1")),
            patch("controllers.console.workspace.members.TenantService.is_owner", return_value=True),
            patch(
                "controllers.console.workspace.members.AccountService.get_owner_transfer_data",
                return_value={"email": "a@test.com"},
            ),
            patch("controllers.console.workspace.members.db.session.get", return_value=member),
            patch("controllers.console.workspace.members.TenantService.is_member", return_value=False),
        ):
            with pytest.raises(MemberNotInTenantError):
                method(api, "2")
