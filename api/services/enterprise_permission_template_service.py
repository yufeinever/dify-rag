from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from flask import request
from sqlalchemy import delete, select, update
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from extensions.ext_database import db
from libs.helper import extract_remote_ip
from models import (
    Account,
    App,
    AppPermission,
    Dataset,
    DatasetPermission,
    DatasetPermissionEnum,
    EnterprisePermissionGroup,
    EnterprisePermissionGroupMember,
    EnterprisePermissionTemplate,
    EnterprisePermissionTemplateApp,
    EnterprisePermissionTemplateDataset,
    EnterprisePermissionTemplateExploreApp,
    EnterprisePermissionTemplateGroup,
    EnterprisePermissionTemplateMember,
    ExploreAppPermission,
    InstalledApp,
    OperationLog,
    TenantAccountJoin,
    TenantAccountRole,
)


class EnterprisePermissionTemplateService:
    """Manage reusable workspace permission templates.

    Templates are a management layer only. Applying a template merges its members
    into the existing explore app, studio app, and dataset grant tables so runtime
    permission checks can keep using the current Dify authorization path.
    """

    @staticmethod
    def _normalize_ids(values: Iterable[str] | None) -> list[str]:
        if not values:
            return []

        return list(dict.fromkeys(str(value) for value in values if value))

    @staticmethod
    def _get_template(tenant_id: str, template_id: str) -> EnterprisePermissionTemplate:
        template = db.session.scalar(
            select(EnterprisePermissionTemplate).where(
                EnterprisePermissionTemplate.tenant_id == tenant_id,
                EnterprisePermissionTemplate.id == template_id,
            )
        )
        if not template:
            raise NotFound("Permission template not found")
        return template

    @staticmethod
    def _assert_workspace_members(tenant_id: str, member_ids: list[str]) -> None:
        if not member_ids:
            return

        existing = set(
            db.session.scalars(
                select(TenantAccountJoin.account_id).where(
                    TenantAccountJoin.tenant_id == tenant_id,
                    TenantAccountJoin.account_id.in_(member_ids),
                )
            ).all()
        )
        if existing != set(member_ids):
            raise Forbidden("Selected template members must belong to the current workspace")

    @staticmethod
    def _assert_workspace_groups(tenant_id: str, group_ids: list[str]) -> None:
        if not group_ids:
            return

        existing = set(
            db.session.scalars(
                select(EnterprisePermissionGroup.id).where(
                    EnterprisePermissionGroup.tenant_id == tenant_id,
                    EnterprisePermissionGroup.id.in_(group_ids),
                )
            ).all()
        )
        if existing != set(group_ids):
            raise Forbidden("Selected permission groups must belong to the current workspace")

    @staticmethod
    def _get_group_member_ids(tenant_id: str, group_ids: Iterable[str]) -> set[str]:
        normalized_group_ids = list(dict.fromkeys(str(group_id) for group_id in group_ids if group_id))
        if not normalized_group_ids:
            return set()

        return set(
            db.session.scalars(
                select(EnterprisePermissionGroupMember.account_id).where(
                    EnterprisePermissionGroupMember.tenant_id == tenant_id,
                    EnterprisePermissionGroupMember.group_id.in_(normalized_group_ids),
                )
            ).all()
        )

    @classmethod
    def _effective_member_ids_from_bindings(
        cls, tenant_id: str, member_ids: Iterable[str], group_ids: Iterable[str]
    ) -> set[str]:
        effective_member_ids = set(member_ids)
        effective_member_ids.update(cls._get_group_member_ids(tenant_id, group_ids))
        return effective_member_ids

    @staticmethod
    def _assert_workspace_apps(tenant_id: str, app_ids: list[str]) -> None:
        if not app_ids:
            return

        existing = set(
            db.session.scalars(
                select(App.id).where(
                    App.tenant_id == tenant_id,
                    App.id.in_(app_ids),
                )
            ).all()
        )
        if existing != set(app_ids):
            raise Forbidden("Selected template apps must belong to the current workspace")

    @staticmethod
    def _assert_workspace_explore_apps(tenant_id: str, app_ids: list[str]) -> None:
        if not app_ids:
            return

        existing = set(
            db.session.scalars(
                select(InstalledApp.app_id).where(
                    InstalledApp.tenant_id == tenant_id,
                    InstalledApp.app_id.in_(app_ids),
                )
            ).all()
        )
        if existing != set(app_ids):
            raise Forbidden("Selected template explore apps must be installed in the current workspace")

    @staticmethod
    def _assert_workspace_datasets(tenant_id: str, dataset_ids: list[str]) -> None:
        if not dataset_ids:
            return

        existing = set(
            db.session.scalars(
                select(Dataset.id).where(
                    Dataset.tenant_id == tenant_id,
                    Dataset.id.in_(dataset_ids),
                )
            ).all()
        )
        if existing != set(dataset_ids):
            raise Forbidden("Selected template datasets must belong to the current workspace")

    @classmethod
    def _validate_payload(
        cls,
        tenant_id: str,
        name: str,
        member_ids: list[str],
        group_ids: list[str],
        app_ids: list[str],
        dataset_ids: list[str],
        explore_app_ids: list[str],
    ) -> None:
        if not name.strip():
            raise BadRequest("Template name is required")

        cls._assert_workspace_members(tenant_id, member_ids)
        cls._assert_workspace_groups(tenant_id, group_ids)
        cls._assert_workspace_apps(tenant_id, app_ids)
        cls._assert_workspace_datasets(tenant_id, dataset_ids)
        cls._assert_workspace_explore_apps(tenant_id, explore_app_ids)

    @staticmethod
    def _replace_bindings(
        tenant_id: str,
        template_id: str,
        member_ids: list[str],
        group_ids: list[str],
        app_ids: list[str],
        dataset_ids: list[str],
        explore_app_ids: list[str],
    ) -> None:
        db.session.execute(
            delete(EnterprisePermissionTemplateMember).where(
                EnterprisePermissionTemplateMember.tenant_id == tenant_id,
                EnterprisePermissionTemplateMember.template_id == template_id,
            )
        )
        db.session.execute(
            delete(EnterprisePermissionTemplateGroup).where(
                EnterprisePermissionTemplateGroup.tenant_id == tenant_id,
                EnterprisePermissionTemplateGroup.template_id == template_id,
            )
        )
        db.session.execute(
            delete(EnterprisePermissionTemplateApp).where(
                EnterprisePermissionTemplateApp.tenant_id == tenant_id,
                EnterprisePermissionTemplateApp.template_id == template_id,
            )
        )
        db.session.execute(
            delete(EnterprisePermissionTemplateDataset).where(
                EnterprisePermissionTemplateDataset.tenant_id == tenant_id,
                EnterprisePermissionTemplateDataset.template_id == template_id,
            )
        )
        db.session.execute(
            delete(EnterprisePermissionTemplateExploreApp).where(
                EnterprisePermissionTemplateExploreApp.tenant_id == tenant_id,
                EnterprisePermissionTemplateExploreApp.template_id == template_id,
            )
        )
        db.session.add_all([
            EnterprisePermissionTemplateMember(tenant_id=tenant_id, template_id=template_id, account_id=account_id)
            for account_id in member_ids
        ])
        db.session.add_all([
            EnterprisePermissionTemplateGroup(tenant_id=tenant_id, template_id=template_id, group_id=group_id)
            for group_id in group_ids
        ])
        db.session.add_all([
            EnterprisePermissionTemplateApp(tenant_id=tenant_id, template_id=template_id, app_id=app_id)
            for app_id in app_ids
        ])
        db.session.add_all([
            EnterprisePermissionTemplateDataset(tenant_id=tenant_id, template_id=template_id, dataset_id=dataset_id)
            for dataset_id in dataset_ids
        ])
        db.session.add_all([
            EnterprisePermissionTemplateExploreApp(tenant_id=tenant_id, template_id=template_id, app_id=app_id)
            for app_id in explore_app_ids
        ])

    @staticmethod
    def _binding_ids(tenant_id: str, template_id: str) -> tuple[list[str], list[str], list[str], list[str]]:
        member_ids = db.session.scalars(
            select(EnterprisePermissionTemplateMember.account_id).where(
                EnterprisePermissionTemplateMember.tenant_id == tenant_id,
                EnterprisePermissionTemplateMember.template_id == template_id,
            )
        ).all()
        app_ids = db.session.scalars(
            select(EnterprisePermissionTemplateApp.app_id).where(
                EnterprisePermissionTemplateApp.tenant_id == tenant_id,
                EnterprisePermissionTemplateApp.template_id == template_id,
            )
        ).all()
        dataset_ids = db.session.scalars(
            select(EnterprisePermissionTemplateDataset.dataset_id).where(
                EnterprisePermissionTemplateDataset.tenant_id == tenant_id,
                EnterprisePermissionTemplateDataset.template_id == template_id,
            )
        ).all()
        explore_app_ids = db.session.scalars(
            select(EnterprisePermissionTemplateExploreApp.app_id).where(
                EnterprisePermissionTemplateExploreApp.tenant_id == tenant_id,
                EnterprisePermissionTemplateExploreApp.template_id == template_id,
            )
        ).all()
        return list(member_ids), list(app_ids), list(dataset_ids), list(explore_app_ids)

    @staticmethod
    def _binding_group_ids(tenant_id: str, template_id: str) -> list[str]:
        return list(
            db.session.scalars(
                select(EnterprisePermissionTemplateGroup.group_id).where(
                    EnterprisePermissionTemplateGroup.tenant_id == tenant_id,
                    EnterprisePermissionTemplateGroup.template_id == template_id,
                )
            ).all()
        )

    @classmethod
    def _effective_member_ids(cls, tenant_id: str, template_id: str) -> set[str]:
        member_ids, _, _, _ = cls._binding_ids(tenant_id, template_id)
        group_ids = cls._binding_group_ids(tenant_id, template_id)
        return cls._effective_member_ids_from_bindings(tenant_id, member_ids, group_ids)

    @staticmethod
    def _permission_pairs(member_ids: Iterable[str], resource_ids: Iterable[str]) -> set[tuple[str, str]]:
        return {(member_id, resource_id) for member_id in member_ids for resource_id in resource_ids}

    @staticmethod
    def _group_pairs_by_resource(pairs: set[tuple[str, str]]) -> dict[str, set[str]]:
        grouped: dict[str, set[str]] = {}
        for member_id, resource_id in pairs:
            grouped.setdefault(resource_id, set()).add(member_id)
        return grouped

    @staticmethod
    def _pairs_covered_by_other_templates(
        tenant_id: str,
        template_id: str,
        pairs: set[tuple[str, str]],
        resource_model: Any,
        resource_attr_name: str,
    ) -> set[tuple[str, str]]:
        if not pairs:
            return set()

        member_ids = {member_id for member_id, _ in pairs}
        resource_ids = {resource_id for _, resource_id in pairs}
        resource_column = getattr(resource_model, resource_attr_name)
        direct_rows = db.session.execute(
            select(EnterprisePermissionTemplateMember.account_id, resource_column)
            .join(
                resource_model,
                sa.and_(
                    EnterprisePermissionTemplateMember.tenant_id == resource_model.tenant_id,
                    EnterprisePermissionTemplateMember.template_id == resource_model.template_id,
                ),
            )
            .where(
                EnterprisePermissionTemplateMember.tenant_id == tenant_id,
                EnterprisePermissionTemplateMember.template_id != template_id,
                EnterprisePermissionTemplateMember.account_id.in_(member_ids),
                resource_column.in_(resource_ids),
            )
        ).all()
        group_rows = db.session.execute(
            select(EnterprisePermissionGroupMember.account_id, resource_column)
            .join(
                EnterprisePermissionTemplateGroup,
                sa.and_(
                    EnterprisePermissionTemplateGroup.tenant_id == EnterprisePermissionGroupMember.tenant_id,
                    EnterprisePermissionTemplateGroup.group_id == EnterprisePermissionGroupMember.group_id,
                ),
            )
            .join(
                resource_model,
                sa.and_(
                    EnterprisePermissionTemplateGroup.tenant_id == resource_model.tenant_id,
                    EnterprisePermissionTemplateGroup.template_id == resource_model.template_id,
                ),
            )
            .where(
                EnterprisePermissionTemplateGroup.tenant_id == tenant_id,
                EnterprisePermissionTemplateGroup.template_id != template_id,
                EnterprisePermissionGroupMember.account_id.in_(member_ids),
                resource_column.in_(resource_ids),
            )
        ).all()
        return {(account_id, resource_id) for account_id, resource_id in [*direct_rows, *group_rows]}

    @staticmethod
    def _revoke_direct_permission_pairs(
        tenant_id: str,
        pairs: set[tuple[str, str]],
        permission_model: Any,
        resource_attr_name: str,
    ) -> int:
        if not pairs:
            return 0

        revoked_count = 0
        resource_column = getattr(permission_model, resource_attr_name)
        for resource_id, member_ids in EnterprisePermissionTemplateService._group_pairs_by_resource(pairs).items():
            result = db.session.execute(
                update(permission_model)
                .where(
                    permission_model.tenant_id == tenant_id,
                    resource_column == resource_id,
                    permission_model.account_id.in_(member_ids),
                )
                .values(has_permission=sa.false())
            )
            revoked_count += result.rowcount or 0
        return revoked_count

    @classmethod
    def _revoke_removed_template_permissions(
        cls,
        tenant_id: str,
        template_id: str,
        old_member_ids: Iterable[str],
        old_app_ids: Iterable[str],
        old_dataset_ids: Iterable[str],
        old_explore_app_ids: Iterable[str],
        new_member_ids: Iterable[str],
        new_app_ids: Iterable[str],
        new_dataset_ids: Iterable[str],
        new_explore_app_ids: Iterable[str],
    ) -> dict[str, int]:
        old_members = set(old_member_ids)
        new_members = set(new_member_ids)

        def revoked_pairs(
            old_resource_ids: Iterable[str],
            new_resource_ids: Iterable[str],
            resource_model: Any,
            resource_attr_name: str,
        ) -> set[tuple[str, str]]:
            removed = cls._permission_pairs(old_members, old_resource_ids) - cls._permission_pairs(
                new_members, new_resource_ids
            )
            return removed - cls._pairs_covered_by_other_templates(
                tenant_id, template_id, removed, resource_model, resource_attr_name
            )

        explore_pairs = revoked_pairs(
            old_explore_app_ids,
            new_explore_app_ids,
            EnterprisePermissionTemplateExploreApp,
            "app_id",
        )
        app_pairs = revoked_pairs(old_app_ids, new_app_ids, EnterprisePermissionTemplateApp, "app_id")
        dataset_pairs = revoked_pairs(
            old_dataset_ids,
            new_dataset_ids,
            EnterprisePermissionTemplateDataset,
            "dataset_id",
        )

        return {
            "explore_app_permission_revoked_count": cls._revoke_direct_permission_pairs(
                tenant_id, explore_pairs, ExploreAppPermission, "app_id"
            ),
            "app_permission_revoked_count": cls._revoke_direct_permission_pairs(
                tenant_id, app_pairs, AppPermission, "app_id"
            ),
            "dataset_permission_revoked_count": cls._revoke_direct_permission_pairs(
                tenant_id, dataset_pairs, DatasetPermission, "dataset_id"
            ),
        }

    @classmethod
    def _serialize_template(cls, tenant_id: str, template: EnterprisePermissionTemplate) -> dict[str, Any]:
        member_ids, app_ids, dataset_ids, explore_app_ids = cls._binding_ids(tenant_id, template.id)
        group_ids = cls._binding_group_ids(tenant_id, template.id)
        effective_member_ids = cls._effective_member_ids_from_bindings(tenant_id, member_ids, group_ids)
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "member_ids": member_ids,
            "group_ids": group_ids,
            "app_ids": app_ids,
            "dataset_ids": dataset_ids,
            "explore_app_ids": explore_app_ids,
            "member_count": len(effective_member_ids),
            "direct_member_count": len(member_ids),
            "group_count": len(group_ids),
            "app_count": len(app_ids),
            "dataset_count": len(dataset_ids),
            "explore_app_count": len(explore_app_ids),
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }

    @staticmethod
    def _get_group(tenant_id: str, group_id: str) -> EnterprisePermissionGroup:
        group = db.session.scalar(
            select(EnterprisePermissionGroup).where(
                EnterprisePermissionGroup.tenant_id == tenant_id,
                EnterprisePermissionGroup.id == group_id,
            )
        )
        if not group:
            raise NotFound("Permission group not found")
        return group

    @staticmethod
    def _direct_group_member_ids(tenant_id: str, group_id: str) -> list[str]:
        return list(
            db.session.scalars(
                select(EnterprisePermissionGroupMember.account_id).where(
                    EnterprisePermissionGroupMember.tenant_id == tenant_id,
                    EnterprisePermissionGroupMember.group_id == group_id,
                )
            ).all()
        )

    @classmethod
    def _serialize_group(cls, tenant_id: str, group: EnterprisePermissionGroup) -> dict[str, Any]:
        member_ids = cls._direct_group_member_ids(tenant_id, group.id)
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "member_ids": member_ids,
            "member_count": len(member_ids),
            "created_at": group.created_at,
            "updated_at": group.updated_at,
        }

    @staticmethod
    def _replace_group_members(tenant_id: str, group_id: str, member_ids: list[str]) -> None:
        db.session.execute(
            delete(EnterprisePermissionGroupMember).where(
                EnterprisePermissionGroupMember.tenant_id == tenant_id,
                EnterprisePermissionGroupMember.group_id == group_id,
            )
        )
        db.session.add_all([
            EnterprisePermissionGroupMember(tenant_id=tenant_id, group_id=group_id, account_id=account_id)
            for account_id in member_ids
        ])

    @classmethod
    def list_groups(cls, tenant_id: str) -> list[dict[str, Any]]:
        groups = db.session.scalars(
            select(EnterprisePermissionGroup)
            .where(EnterprisePermissionGroup.tenant_id == tenant_id)
            .order_by(EnterprisePermissionGroup.updated_at.desc(), EnterprisePermissionGroup.created_at.desc())
        ).all()
        return [cls._serialize_group(tenant_id, group) for group in groups]

    @classmethod
    def create_group(
        cls,
        tenant_id: str,
        operator: Account,
        name: str,
        description: str | None,
        member_ids: Iterable[str] | None,
    ) -> dict[str, Any]:
        normalized_member_ids = cls._normalize_ids(member_ids)
        if not name.strip():
            raise BadRequest("Permission group name is required")
        cls._assert_workspace_members(tenant_id, normalized_member_ids)

        try:
            group = EnterprisePermissionGroup(
                tenant_id=tenant_id,
                name=name.strip(),
                description=description.strip() if description else None,
                created_by=operator.id,
            )
            db.session.add(group)
            db.session.flush()
            cls._replace_group_members(tenant_id, group.id, normalized_member_ids)
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_group.created",
                content={"group_id": group.id, "name": group.name, "member_count": len(normalized_member_ids)},
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return cls._serialize_group(tenant_id, group)

    @classmethod
    def _templates_bound_to_group(cls, tenant_id: str, group_id: str) -> list[EnterprisePermissionTemplate]:
        return list(
            db.session.scalars(
                select(EnterprisePermissionTemplate)
                .join(
                    EnterprisePermissionTemplateGroup,
                    sa.and_(
                        EnterprisePermissionTemplateGroup.tenant_id == EnterprisePermissionTemplate.tenant_id,
                        EnterprisePermissionTemplateGroup.template_id == EnterprisePermissionTemplate.id,
                    ),
                )
                .where(
                    EnterprisePermissionTemplateGroup.tenant_id == tenant_id,
                    EnterprisePermissionTemplateGroup.group_id == group_id,
                )
            ).all()
        )

    @classmethod
    def _template_permission_snapshot(cls, tenant_id: str, template: EnterprisePermissionTemplate) -> dict[str, Any]:
        member_ids, app_ids, dataset_ids, explore_app_ids = cls._binding_ids(tenant_id, template.id)
        group_ids = cls._binding_group_ids(tenant_id, template.id)
        return {
            "template_id": template.id,
            "member_ids": cls._effective_member_ids_from_bindings(tenant_id, member_ids, group_ids),
            "app_ids": app_ids,
            "dataset_ids": dataset_ids,
            "explore_app_ids": explore_app_ids,
        }

    @classmethod
    def update_group(
        cls,
        tenant_id: str,
        group_id: str,
        operator: Account,
        name: str,
        description: str | None,
        member_ids: Iterable[str] | None,
    ) -> dict[str, Any]:
        normalized_member_ids = cls._normalize_ids(member_ids)
        if not name.strip():
            raise BadRequest("Permission group name is required")
        cls._assert_workspace_members(tenant_id, normalized_member_ids)
        group = cls._get_group(tenant_id, group_id)
        snapshots = [
            cls._template_permission_snapshot(tenant_id, template)
            for template in cls._templates_bound_to_group(tenant_id, group.id)
        ]

        try:
            group.name = name.strip()
            group.description = description.strip() if description else None
            cls._replace_group_members(tenant_id, group.id, normalized_member_ids)
            revoked_totals = {
                "explore_app_permission_revoked_count": 0,
                "app_permission_revoked_count": 0,
                "dataset_permission_revoked_count": 0,
            }
            for snapshot in snapshots:
                revoked_counts = cls._revoke_removed_template_permissions(
                    tenant_id,
                    snapshot["template_id"],
                    snapshot["member_ids"],
                    snapshot["app_ids"],
                    snapshot["dataset_ids"],
                    snapshot["explore_app_ids"],
                    cls._effective_member_ids(tenant_id, snapshot["template_id"]),
                    snapshot["app_ids"],
                    snapshot["dataset_ids"],
                    snapshot["explore_app_ids"],
                )
                for key, value in revoked_counts.items():
                    revoked_totals[key] += value
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_group.updated",
                content={
                    "group_id": group.id,
                    "name": group.name,
                    "member_count": len(normalized_member_ids),
                    **revoked_totals,
                },
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return cls._serialize_group(tenant_id, group)

    @classmethod
    def delete_group(cls, tenant_id: str, group_id: str, operator: Account) -> None:
        group = cls._get_group(tenant_id, group_id)
        snapshots = [
            cls._template_permission_snapshot(tenant_id, template)
            for template in cls._templates_bound_to_group(tenant_id, group.id)
        ]
        try:
            db.session.execute(
                delete(EnterprisePermissionTemplateGroup).where(
                    EnterprisePermissionTemplateGroup.tenant_id == tenant_id,
                    EnterprisePermissionTemplateGroup.group_id == group.id,
                )
            )
            cls._replace_group_members(tenant_id, group.id, [])
            revoked_totals = {
                "explore_app_permission_revoked_count": 0,
                "app_permission_revoked_count": 0,
                "dataset_permission_revoked_count": 0,
            }
            for snapshot in snapshots:
                revoked_counts = cls._revoke_removed_template_permissions(
                    tenant_id,
                    snapshot["template_id"],
                    snapshot["member_ids"],
                    snapshot["app_ids"],
                    snapshot["dataset_ids"],
                    snapshot["explore_app_ids"],
                    cls._effective_member_ids(tenant_id, snapshot["template_id"]),
                    snapshot["app_ids"],
                    snapshot["dataset_ids"],
                    snapshot["explore_app_ids"],
                )
                for key, value in revoked_counts.items():
                    revoked_totals[key] += value
            db.session.delete(group)
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_group.deleted",
                content={"group_id": group_id, "name": group.name, **revoked_totals},
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def list_templates(cls, tenant_id: str) -> list[dict[str, Any]]:
        templates = db.session.scalars(
            select(EnterprisePermissionTemplate)
            .where(EnterprisePermissionTemplate.tenant_id == tenant_id)
            .order_by(EnterprisePermissionTemplate.updated_at.desc(), EnterprisePermissionTemplate.created_at.desc())
        ).all()
        return [cls._serialize_template(tenant_id, template) for template in templates]

    @classmethod
    def create_template(
        cls,
        tenant_id: str,
        operator: Account,
        name: str,
        description: str | None,
        member_ids: Iterable[str] | None,
        group_ids: Iterable[str] | None,
        app_ids: Iterable[str] | None,
        dataset_ids: Iterable[str] | None,
        explore_app_ids: Iterable[str] | None,
    ) -> dict[str, Any]:
        normalized_member_ids = cls._normalize_ids(member_ids)
        normalized_group_ids = cls._normalize_ids(group_ids)
        normalized_app_ids = cls._normalize_ids(app_ids)
        normalized_dataset_ids = cls._normalize_ids(dataset_ids)
        normalized_explore_app_ids = cls._normalize_ids(explore_app_ids)
        cls._validate_payload(
            tenant_id,
            name,
            normalized_member_ids,
            normalized_group_ids,
            normalized_app_ids,
            normalized_dataset_ids,
            normalized_explore_app_ids,
        )

        try:
            template = EnterprisePermissionTemplate(
                tenant_id=tenant_id,
                name=name.strip(),
                description=description.strip() if description else None,
                created_by=operator.id,
            )
            db.session.add(template)
            db.session.flush()
            cls._replace_bindings(
                tenant_id,
                template.id,
                normalized_member_ids,
                normalized_group_ids,
                normalized_app_ids,
                normalized_dataset_ids,
                normalized_explore_app_ids,
            )
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_template.created",
                content={"template_id": template.id, "name": template.name},
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return cls.get_template(tenant_id, template.id)

    @classmethod
    def get_template(cls, tenant_id: str, template_id: str) -> dict[str, Any]:
        template = cls._get_template(tenant_id, template_id)
        return cls._serialize_template(tenant_id, template)

    @classmethod
    def update_template(
        cls,
        tenant_id: str,
        template_id: str,
        operator: Account,
        name: str,
        description: str | None,
        member_ids: Iterable[str] | None,
        group_ids: Iterable[str] | None,
        app_ids: Iterable[str] | None,
        dataset_ids: Iterable[str] | None,
        explore_app_ids: Iterable[str] | None,
    ) -> dict[str, Any]:
        normalized_member_ids = cls._normalize_ids(member_ids)
        normalized_group_ids = cls._normalize_ids(group_ids)
        normalized_app_ids = cls._normalize_ids(app_ids)
        normalized_dataset_ids = cls._normalize_ids(dataset_ids)
        normalized_explore_app_ids = cls._normalize_ids(explore_app_ids)
        cls._validate_payload(
            tenant_id,
            name,
            normalized_member_ids,
            normalized_group_ids,
            normalized_app_ids,
            normalized_dataset_ids,
            normalized_explore_app_ids,
        )
        template = cls._get_template(tenant_id, template_id)
        old_member_ids, old_app_ids, old_dataset_ids, old_explore_app_ids = cls._binding_ids(tenant_id, template.id)
        old_group_ids = cls._binding_group_ids(tenant_id, template.id)
        old_effective_member_ids = cls._effective_member_ids_from_bindings(tenant_id, old_member_ids, old_group_ids)
        new_effective_member_ids = cls._effective_member_ids_from_bindings(
            tenant_id, normalized_member_ids, normalized_group_ids
        )

        try:
            template.name = name.strip()
            template.description = description.strip() if description else None
            cls._replace_bindings(
                tenant_id,
                template.id,
                normalized_member_ids,
                normalized_group_ids,
                normalized_app_ids,
                normalized_dataset_ids,
                normalized_explore_app_ids,
            )
            revoked_counts = cls._revoke_removed_template_permissions(
                tenant_id,
                template.id,
                old_effective_member_ids,
                old_app_ids,
                old_dataset_ids,
                old_explore_app_ids,
                new_effective_member_ids,
                normalized_app_ids,
                normalized_dataset_ids,
                normalized_explore_app_ids,
            )
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_template.updated",
                content={"template_id": template.id, "name": template.name, **revoked_counts},
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return cls.get_template(tenant_id, template.id)

    @classmethod
    def delete_template(cls, tenant_id: str, template_id: str, operator: Account) -> None:
        template = cls._get_template(tenant_id, template_id)
        old_member_ids, old_app_ids, old_dataset_ids, old_explore_app_ids = cls._binding_ids(tenant_id, template.id)
        old_group_ids = cls._binding_group_ids(tenant_id, template.id)
        old_effective_member_ids = cls._effective_member_ids_from_bindings(tenant_id, old_member_ids, old_group_ids)
        try:
            cls._replace_bindings(tenant_id, template.id, [], [], [], [], [])
            revoked_counts = cls._revoke_removed_template_permissions(
                tenant_id,
                template.id,
                old_effective_member_ids,
                old_app_ids,
                old_dataset_ids,
                old_explore_app_ids,
                [],
                [],
                [],
                [],
            )
            db.session.delete(template)
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_template.deleted",
                content={"template_id": template_id, "name": template.name, **revoked_counts},
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def _source_item(source: str, source_id: str | None = None, source_name: str | None = None) -> dict[str, Any]:
        return {"source": source, "source_id": source_id, "source_name": source_name}

    @staticmethod
    def _append_permission_source(
        resources: dict[str, dict[str, Any]],
        resource_id: str,
        source: dict[str, Any],
    ) -> None:
        resource = resources.setdefault(resource_id, {"sources": []})
        existing = {
            (item.get("source"), item.get("source_id"), item.get("source_name")) for item in resource["sources"]
        }
        key = (source.get("source"), source.get("source_id"), source.get("source_name"))
        if key not in existing:
            resource["sources"].append(source)

    @staticmethod
    def _resource_rows(model: Any, ids: Iterable[str]) -> dict[str, Any]:
        resource_ids = list(dict.fromkeys(str(resource_id) for resource_id in ids if resource_id))
        if not resource_ids:
            return {}

        return {
            str(resource.id): resource
            for resource in db.session.scalars(select(model).where(model.id.in_(resource_ids))).all()
        }

    @classmethod
    def _direct_template_resource_sources(
        cls,
        tenant_id: str,
        account_id: str,
        resource_model: Any,
        resource_attr_name: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        resource_column = getattr(resource_model, resource_attr_name)
        rows = db.session.execute(
            select(resource_column, EnterprisePermissionTemplate.id, EnterprisePermissionTemplate.name)
            .join(
                EnterprisePermissionTemplateMember,
                sa.and_(
                    EnterprisePermissionTemplateMember.tenant_id == resource_model.tenant_id,
                    EnterprisePermissionTemplateMember.template_id == resource_model.template_id,
                ),
            )
            .join(
                EnterprisePermissionTemplate,
                sa.and_(
                    EnterprisePermissionTemplate.tenant_id == resource_model.tenant_id,
                    EnterprisePermissionTemplate.id == resource_model.template_id,
                ),
            )
            .where(
                resource_model.tenant_id == tenant_id,
                EnterprisePermissionTemplateMember.account_id == account_id,
            )
        ).all()
        return [
            (str(resource_id), cls._source_item("direct_template", str(template_id), template_name))
            for resource_id, template_id, template_name in rows
        ]

    @classmethod
    def _group_template_resource_sources(
        cls,
        tenant_id: str,
        account_id: str,
        resource_model: Any,
        resource_attr_name: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        resource_column = getattr(resource_model, resource_attr_name)
        rows = db.session.execute(
            select(
                resource_column,
                EnterprisePermissionTemplate.id,
                EnterprisePermissionTemplate.name,
                EnterprisePermissionGroup.id,
                EnterprisePermissionGroup.name,
            )
            .join(
                EnterprisePermissionTemplateGroup,
                sa.and_(
                    EnterprisePermissionTemplateGroup.tenant_id == resource_model.tenant_id,
                    EnterprisePermissionTemplateGroup.template_id == resource_model.template_id,
                ),
            )
            .join(
                EnterprisePermissionGroupMember,
                sa.and_(
                    EnterprisePermissionGroupMember.tenant_id == EnterprisePermissionTemplateGroup.tenant_id,
                    EnterprisePermissionGroupMember.group_id == EnterprisePermissionTemplateGroup.group_id,
                ),
            )
            .join(
                EnterprisePermissionTemplate,
                sa.and_(
                    EnterprisePermissionTemplate.tenant_id == resource_model.tenant_id,
                    EnterprisePermissionTemplate.id == resource_model.template_id,
                ),
            )
            .join(
                EnterprisePermissionGroup,
                sa.and_(
                    EnterprisePermissionGroup.tenant_id == EnterprisePermissionTemplateGroup.tenant_id,
                    EnterprisePermissionGroup.id == EnterprisePermissionTemplateGroup.group_id,
                ),
            )
            .where(
                resource_model.tenant_id == tenant_id,
                EnterprisePermissionGroupMember.account_id == account_id,
            )
        ).all()
        return [
            (
                str(resource_id),
                cls._source_item(
                    "group_template",
                    str(template_id),
                    f"{template_name} / {group_name}",
                ),
            )
            for resource_id, template_id, template_name, _group_id, group_name in rows
        ]

    @staticmethod
    def _serialize_effective_resource(
        resource: Any,
        resource_type: str,
        sources: list[dict[str, Any]],
        permission: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": str(resource.id),
            "name": getattr(resource, "name", "Untitled"),
            "resource_type": resource_type,
            "mode": getattr(resource, "mode", None),
            "permission": permission,
            "sources": sources,
        }

    @classmethod
    def get_effective_permissions(cls, tenant_id: str, account_id: str) -> dict[str, Any]:
        join = db.session.scalar(
            select(TenantAccountJoin).where(
                TenantAccountJoin.tenant_id == tenant_id,
                TenantAccountJoin.account_id == account_id,
            )
        )
        if not join:
            raise Forbidden("Selected member must belong to the current workspace")

        account = db.session.get(Account, account_id)
        if not account:
            raise NotFound("Account not found")

        role = join.role
        is_workspace_admin = role in {TenantAccountRole.OWNER, TenantAccountRole.ADMIN}
        workspace_source = cls._source_item("workspace_role", account_id, role)

        app_sources: dict[str, dict[str, Any]] = {}
        explore_sources: dict[str, dict[str, Any]] = {}
        dataset_sources: dict[str, dict[str, Any]] = {}

        if is_workspace_admin:
            for app_id in db.session.scalars(select(App.id).where(App.tenant_id == tenant_id)).all():
                cls._append_permission_source(app_sources, str(app_id), workspace_source)
            installed_app_ids = db.session.scalars(
                select(InstalledApp.app_id).where(InstalledApp.tenant_id == tenant_id)
            ).all()
            for app_id in installed_app_ids:
                cls._append_permission_source(explore_sources, str(app_id), workspace_source)
            for dataset_id in db.session.scalars(select(Dataset.id).where(Dataset.tenant_id == tenant_id)).all():
                cls._append_permission_source(dataset_sources, str(dataset_id), workspace_source)
        else:
            for app_id in db.session.scalars(
                select(AppPermission.app_id).where(
                    AppPermission.tenant_id == tenant_id,
                    AppPermission.account_id == account_id,
                    AppPermission.has_permission == sa.true(),
                )
            ).all():
                cls._append_permission_source(
                    app_sources,
                    str(app_id),
                    cls._source_item("direct", account_id, "工作室直授权"),
                )
            for app_id, source in cls._direct_template_resource_sources(
                tenant_id, account_id, EnterprisePermissionTemplateApp, "app_id"
            ):
                cls._append_permission_source(app_sources, app_id, source)
            for app_id, source in cls._group_template_resource_sources(
                tenant_id, account_id, EnterprisePermissionTemplateApp, "app_id"
            ):
                cls._append_permission_source(app_sources, app_id, source)

            for app_id in db.session.scalars(
                select(ExploreAppPermission.app_id).where(
                    ExploreAppPermission.tenant_id == tenant_id,
                    ExploreAppPermission.account_id == account_id,
                    ExploreAppPermission.has_permission == sa.true(),
                )
            ).all():
                cls._append_permission_source(
                    explore_sources, str(app_id), cls._source_item("direct", account_id, "探索直授权")
                )
            for app_id, source in cls._direct_template_resource_sources(
                tenant_id, account_id, EnterprisePermissionTemplateExploreApp, "app_id"
            ):
                cls._append_permission_source(explore_sources, app_id, source)
            for app_id, source in cls._group_template_resource_sources(
                tenant_id, account_id, EnterprisePermissionTemplateExploreApp, "app_id"
            ):
                cls._append_permission_source(explore_sources, app_id, source)

            for dataset_id in db.session.scalars(
                select(DatasetPermission.dataset_id).where(
                    DatasetPermission.tenant_id == tenant_id,
                    DatasetPermission.account_id == account_id,
                    DatasetPermission.has_permission == sa.true(),
                )
            ).all():
                cls._append_permission_source(
                    dataset_sources, str(dataset_id), cls._source_item("direct", account_id, "知识库直授权")
                )
            for dataset_id in db.session.scalars(
                select(Dataset.id).where(
                    Dataset.tenant_id == tenant_id,
                    Dataset.permission == DatasetPermissionEnum.ALL_TEAM,
                )
            ).all():
                cls._append_permission_source(
                    dataset_sources, str(dataset_id), cls._source_item("workspace_role", account_id, "全员知识库")
                )
            for dataset_id, source in cls._direct_template_resource_sources(
                tenant_id, account_id, EnterprisePermissionTemplateDataset, "dataset_id"
            ):
                cls._append_permission_source(dataset_sources, dataset_id, source)
            for dataset_id, source in cls._group_template_resource_sources(
                tenant_id, account_id, EnterprisePermissionTemplateDataset, "dataset_id"
            ):
                cls._append_permission_source(dataset_sources, dataset_id, source)

        app_rows = cls._resource_rows(App, app_sources.keys())
        explore_app_rows = cls._resource_rows(App, explore_sources.keys())
        dataset_rows = cls._resource_rows(Dataset, dataset_sources.keys())

        apps = [
            cls._serialize_effective_resource(app_rows[app_id], "app", data["sources"])
            for app_id, data in app_sources.items()
            if app_id in app_rows
        ]
        explore_apps = [
            cls._serialize_effective_resource(explore_app_rows[app_id], "explore_app", data["sources"])
            for app_id, data in explore_sources.items()
            if app_id in explore_app_rows
        ]
        datasets = [
            cls._serialize_effective_resource(
                dataset_rows[dataset_id],
                "dataset",
                data["sources"],
                getattr(dataset_rows[dataset_id], "permission", None),
            )
            for dataset_id, data in dataset_sources.items()
            if dataset_id in dataset_rows
        ]

        source_counts: dict[str, int] = {}
        for resource in [*apps, *explore_apps, *datasets]:
            for source in resource["sources"]:
                source_counts[source["source"]] = source_counts.get(source["source"], 0) + 1

        return {
            "account": {
                "id": account.id,
                "name": account.name,
                "email": account.email,
                "role": role,
            },
            "is_workspace_admin": is_workspace_admin,
            "apps": sorted(apps, key=lambda item: item["name"].lower()),
            "explore_apps": sorted(explore_apps, key=lambda item: item["name"].lower()),
            "datasets": sorted(datasets, key=lambda item: item["name"].lower()),
            "source_counts": source_counts,
        }

    @classmethod
    def apply_template(cls, tenant_id: str, template_id: str, operator: Account) -> dict[str, int]:
        template = cls._get_template(tenant_id, template_id)
        member_ids, app_ids, dataset_ids, explore_app_ids = cls._binding_ids(tenant_id, template.id)
        group_ids = cls._binding_group_ids(tenant_id, template.id)
        effective_member_ids = cls._effective_member_ids_from_bindings(tenant_id, member_ids, group_ids)

        valid_member_ids = set(
            db.session.scalars(
                select(TenantAccountJoin.account_id).where(
                    TenantAccountJoin.tenant_id == tenant_id,
                    TenantAccountJoin.account_id.in_(effective_member_ids),
                )
            ).all()
        ) if effective_member_ids else set()
        if not valid_member_ids:
            raise BadRequest("Permission template has no valid workspace members")

        valid_app_ids = set(
            db.session.scalars(select(App.id).where(App.tenant_id == tenant_id, App.id.in_(app_ids))).all()
        ) if app_ids else set()
        valid_dataset_ids = set(
            db.session.scalars(
                select(Dataset.id).where(Dataset.tenant_id == tenant_id, Dataset.id.in_(dataset_ids))
            ).all()
        ) if dataset_ids else set()
        valid_explore_app_ids = set(
            db.session.scalars(
                select(InstalledApp.app_id).where(
                    InstalledApp.tenant_id == tenant_id, InstalledApp.app_id.in_(explore_app_ids)
                )
            ).all()
        ) if explore_app_ids else set()

        try:
            explore_app_permission_count = cls._merge_explore_app_permissions(
                tenant_id, valid_explore_app_ids, valid_member_ids
            )
            app_permission_count = cls._merge_app_permissions(tenant_id, valid_app_ids, valid_member_ids)
            dataset_permission_count = cls._merge_dataset_permissions(
                tenant_id,
                valid_dataset_ids,
                valid_member_ids,
                operator.id,
            )
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_template.applied",
                content={
                    "template_id": template.id,
                    "name": template.name,
                    "member_count": len(valid_member_ids),
                    "app_count": len(valid_app_ids),
                    "dataset_count": len(valid_dataset_ids),
                    "explore_app_count": len(valid_explore_app_ids),
                },
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return {
            "member_count": len(valid_member_ids),
            "app_count": len(valid_app_ids),
            "dataset_count": len(valid_dataset_ids),
            "explore_app_count": len(valid_explore_app_ids),
            "app_permission_count": app_permission_count,
            "explore_app_permission_count": explore_app_permission_count,
            "dataset_permission_count": dataset_permission_count,
        }

    @staticmethod
    def _merge_explore_app_permissions(tenant_id: str, app_ids: set[str], member_ids: set[str]) -> int:
        permission_count = 0
        for app_id in app_ids:
            existing_member_ids = set(
                db.session.scalars(
                    select(ExploreAppPermission.account_id).where(
                        ExploreAppPermission.tenant_id == tenant_id,
                        ExploreAppPermission.app_id == app_id,
                        ExploreAppPermission.account_id.in_(member_ids),
                    )
                ).all()
            )
            db.session.execute(
                update(ExploreAppPermission)
                .where(
                    ExploreAppPermission.tenant_id == tenant_id,
                    ExploreAppPermission.app_id == app_id,
                    ExploreAppPermission.account_id.in_(member_ids),
                )
                .values(has_permission=sa.true())
            )
            missing_member_ids = member_ids - existing_member_ids
            db.session.add_all([
                ExploreAppPermission(tenant_id=tenant_id, app_id=app_id, account_id=account_id)
                for account_id in missing_member_ids
            ])
            permission_count += len(member_ids)
        return permission_count

    @staticmethod
    def _merge_app_permissions(tenant_id: str, app_ids: set[str], member_ids: set[str]) -> int:
        permission_count = 0
        for app_id in app_ids:
            existing_member_ids = set(
                db.session.scalars(
                    select(AppPermission.account_id).where(
                        AppPermission.tenant_id == tenant_id,
                        AppPermission.app_id == app_id,
                        AppPermission.account_id.in_(member_ids),
                    )
                ).all()
            )
            db.session.execute(
                update(AppPermission)
                .where(
                    AppPermission.tenant_id == tenant_id,
                    AppPermission.app_id == app_id,
                    AppPermission.account_id.in_(member_ids),
                )
                .values(has_permission=sa.true())
            )
            missing_member_ids = member_ids - existing_member_ids
            db.session.add_all([
                AppPermission(tenant_id=tenant_id, app_id=app_id, account_id=account_id)
                for account_id in missing_member_ids
            ])
            permission_count += len(member_ids)
        return permission_count

    @staticmethod
    def _merge_dataset_permissions(
        tenant_id: str, dataset_ids: set[str], member_ids: set[str], operator_id: str
    ) -> int:
        permission_count = 0
        for dataset_id in dataset_ids:
            db.session.execute(
                update(Dataset)
                .where(Dataset.tenant_id == tenant_id, Dataset.id == dataset_id)
                .values(permission=DatasetPermissionEnum.PARTIAL_TEAM, updated_by=operator_id)
            )
            existing_member_ids = set(
                db.session.scalars(
                    select(DatasetPermission.account_id).where(
                        DatasetPermission.tenant_id == tenant_id,
                        DatasetPermission.dataset_id == dataset_id,
                        DatasetPermission.account_id.in_(member_ids),
                    )
                ).all()
            )
            db.session.execute(
                update(DatasetPermission)
                .where(
                    DatasetPermission.tenant_id == tenant_id,
                    DatasetPermission.dataset_id == dataset_id,
                    DatasetPermission.account_id.in_(member_ids),
                )
                .values(has_permission=sa.true())
            )
            missing_member_ids = member_ids - existing_member_ids
            db.session.add_all([
                DatasetPermission(tenant_id=tenant_id, dataset_id=dataset_id, account_id=account_id)
                for account_id in missing_member_ids
            ])
            permission_count += len(member_ids)
        return permission_count
