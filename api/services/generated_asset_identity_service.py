"""Manage console identity grouping for generated assets without changing asset ownership."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.account import Account, TenantAccountJoin
from models.model import App, EndUser, OperationLog
from models.tools import GeneratedAssetIdentityBinding, GeneratedFile


def channel_type_for_end_user(end_user: EndUser) -> str:
    session_id = end_user.session_id or ""
    if end_user.type == "web-app":
        return "webapp"
    if ":" in session_id:
        namespace = session_id.split(":", 1)[0].strip().lower()
        if namespace in {"feishu", "openclaw", "workbuddy", "mmb-enterprise-mcp"}:
            return namespace
    if end_user.type == "service-api":
        return "service-api"
    return end_user.type or "unknown"


def identity_display_name(end_user: EndUser, binding: GeneratedAssetIdentityBinding | None = None) -> str:
    if binding and binding.display_name:
        return binding.display_name
    session_id = end_user.session_id or str(end_user.id)
    namespace, separator, external_id = session_id.partition(":")
    value = external_id if separator else session_id
    short = f"{value[:4]}...{value[-4:]}" if len(value) > 12 else value
    channel = channel_type_for_end_user(end_user)
    labels = {
        "service-api": "Service API",
        "webapp": "WebApp",
        "feishu": "飞书",
        "openclaw": "OpenClaw",
        "workbuddy": "WorkBuddy",
        "mmb-enterprise-mcp": "企业 MCP",
    }
    return f"{labels.get(channel, namespace if separator else '外部用户')} · {short}"


def generated_asset_identity_context(session: Session, *, tenant_id: str, owner_user_id: str) -> dict[str, Any]:
    account = session.get(Account, owner_user_id)
    if account:
        return {
            "owner_name": account.name,
            "person_name": account.name,
            "identity_name": None,
            "channel_type": "console",
            "identity_bound": False,
        }
    row = session.execute(
        select(EndUser, GeneratedAssetIdentityBinding, Account.name)
        .outerjoin(
            GeneratedAssetIdentityBinding,
            (GeneratedAssetIdentityBinding.tenant_id == tenant_id)
            & (GeneratedAssetIdentityBinding.end_user_id == EndUser.id),
        )
        .outerjoin(Account, Account.id == GeneratedAssetIdentityBinding.account_id)
        .where(EndUser.tenant_id == tenant_id, EndUser.id == owner_user_id)
    ).first()
    if not row:
        return {
            "owner_name": None,
            "person_name": None,
            "identity_name": None,
            "channel_type": None,
            "identity_bound": False,
        }
    end_user, binding, person_name = row
    identity_name = identity_display_name(end_user, binding)
    return {
        "owner_name": identity_name,
        "person_name": person_name,
        "identity_name": identity_name,
        "channel_type": binding.channel_type if binding else channel_type_for_end_user(end_user),
        "identity_bound": bool(binding and binding.account_id),
    }


def bound_identity_ids(session: Session, *, tenant_id: str, account_id: str) -> list[str]:
    return list(
        session.scalars(
            select(GeneratedAssetIdentityBinding.end_user_id).where(
                GeneratedAssetIdentityBinding.tenant_id == tenant_id,
                GeneratedAssetIdentityBinding.account_id == account_id,
            )
        )
    )


def list_asset_identities(session: Session, *, tenant_id: str, include_test: bool = False) -> dict[str, Any]:
    rows = session.execute(
        select(
            EndUser,
            GeneratedAssetIdentityBinding,
            Account.name,
            func.count(GeneratedFile.id),
            func.max(GeneratedFile.created_at),
            func.string_agg(func.distinct(App.name), ", "),
        )
        .join(GeneratedFile, GeneratedFile.owner_user_id == EndUser.id)
        .outerjoin(
            GeneratedAssetIdentityBinding,
            (GeneratedAssetIdentityBinding.tenant_id == tenant_id)
            & (GeneratedAssetIdentityBinding.end_user_id == EndUser.id),
        )
        .outerjoin(Account, Account.id == GeneratedAssetIdentityBinding.account_id)
        .outerjoin(App, App.id == GeneratedFile.source_app_id)
        .where(
            EndUser.tenant_id == tenant_id,
            GeneratedFile.tenant_id == tenant_id,
            GeneratedFile.deleted_at.is_(None),
        )
        .group_by(EndUser.id, GeneratedAssetIdentityBinding.id, Account.name)
        .order_by(func.count(GeneratedFile.id).desc(), func.max(GeneratedFile.created_at).desc())
    ).all()
    identities = []
    for end_user, binding, account_name, asset_count, last_used_at, app_names in rows:
        if binding and binding.is_test and not include_test:
            continue
        identities.append(
            {
                "id": str(end_user.id),
                "name": identity_display_name(end_user, binding),
                "channel_type": binding.channel_type if binding else channel_type_for_end_user(end_user),
                "session_hint": identity_display_name(end_user),
                "account_id": str(binding.account_id) if binding and binding.account_id else None,
                "account_name": account_name,
                "is_bound": bool(binding and binding.account_id),
                "is_test": bool(binding and binding.is_test),
                "asset_count": int(asset_count),
                "last_used_at": int(last_used_at.timestamp()) if last_used_at else None,
                "app_names": [name for name in (app_names or "").split(", ") if name],
            }
        )
    members = session.execute(
        select(Account.id, Account.name, Account.email)
        .join(TenantAccountJoin, TenantAccountJoin.account_id == Account.id)
        .where(TenantAccountJoin.tenant_id == tenant_id)
        .order_by(Account.name.asc(), Account.email.asc())
    ).all()
    return {
        "identities": identities,
        "accounts": [
            {"id": str(account_id), "name": name or email, "email": email} for account_id, name, email in members
        ],
    }


def update_asset_identities(
    session: Session,
    *,
    tenant_id: str,
    actor_id: str,
    actor_ip: str,
    end_user_ids: list[str],
    account_id: str | None,
    is_test: bool | None,
) -> None:
    if account_id:
        is_member = session.scalar(
            select(func.count())
            .select_from(TenantAccountJoin)
            .where(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == account_id)
        )
        if not is_member:
            raise ValueError("Target account is not a workspace member.")
    end_users = list(
        session.scalars(select(EndUser).where(EndUser.tenant_id == tenant_id, EndUser.id.in_(end_user_ids)))
    )
    if len(end_users) != len(set(end_user_ids)):
        raise ValueError("One or more identities do not belong to this workspace.")
    changed = []
    for end_user in end_users:
        binding = session.scalar(
            select(GeneratedAssetIdentityBinding).where(
                GeneratedAssetIdentityBinding.tenant_id == tenant_id,
                GeneratedAssetIdentityBinding.end_user_id == end_user.id,
            )
        )
        if not binding:
            binding = GeneratedAssetIdentityBinding(
                tenant_id=tenant_id,
                end_user_id=str(end_user.id),
                account_id=account_id,
                channel_type=channel_type_for_end_user(end_user),
                display_name=None,
                is_test=bool(is_test),
                created_by=actor_id,
                updated_by=actor_id,
            )
        else:
            binding.account_id = account_id
            if is_test is not None:
                binding.is_test = is_test
            binding.channel_type = channel_type_for_end_user(end_user)
            binding.updated_by = actor_id
            binding.updated_at = datetime.utcnow()
        session.add(binding)
        changed.append(str(end_user.id))
    session.add(
        OperationLog(
            tenant_id=tenant_id,
            account_id=actor_id,
            action="generated_asset.identity.update",
            content={"end_user_ids": changed, "account_id": account_id, "is_test": is_test},
            created_ip=actor_ip or "unknown",
        )
    )
    session.commit()
