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
    EnterprisePermissionTemplate,
    EnterprisePermissionTemplateApp,
    EnterprisePermissionTemplateDataset,
    EnterprisePermissionTemplateExploreApp,
    EnterprisePermissionTemplateMember,
    ExploreAppPermission,
    InstalledApp,
    OperationLog,
    TenantAccountJoin,
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
        app_ids: list[str],
        dataset_ids: list[str],
        explore_app_ids: list[str],
    ) -> None:
        if not name.strip():
            raise BadRequest("Template name is required")

        cls._assert_workspace_members(tenant_id, member_ids)
        cls._assert_workspace_apps(tenant_id, app_ids)
        cls._assert_workspace_datasets(tenant_id, dataset_ids)
        cls._assert_workspace_explore_apps(tenant_id, explore_app_ids)

    @staticmethod
    def _replace_bindings(
        tenant_id: str,
        template_id: str,
        member_ids: list[str],
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

    @classmethod
    def _serialize_template(cls, tenant_id: str, template: EnterprisePermissionTemplate) -> dict[str, Any]:
        member_ids, app_ids, dataset_ids, explore_app_ids = cls._binding_ids(tenant_id, template.id)
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "member_ids": member_ids,
            "app_ids": app_ids,
            "dataset_ids": dataset_ids,
            "explore_app_ids": explore_app_ids,
            "member_count": len(member_ids),
            "app_count": len(app_ids),
            "dataset_count": len(dataset_ids),
            "explore_app_count": len(explore_app_ids),
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }

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
        app_ids: Iterable[str] | None,
        dataset_ids: Iterable[str] | None,
        explore_app_ids: Iterable[str] | None,
    ) -> dict[str, Any]:
        normalized_member_ids = cls._normalize_ids(member_ids)
        normalized_app_ids = cls._normalize_ids(app_ids)
        normalized_dataset_ids = cls._normalize_ids(dataset_ids)
        normalized_explore_app_ids = cls._normalize_ids(explore_app_ids)
        cls._validate_payload(
            tenant_id,
            name,
            normalized_member_ids,
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
        app_ids: Iterable[str] | None,
        dataset_ids: Iterable[str] | None,
        explore_app_ids: Iterable[str] | None,
    ) -> dict[str, Any]:
        normalized_member_ids = cls._normalize_ids(member_ids)
        normalized_app_ids = cls._normalize_ids(app_ids)
        normalized_dataset_ids = cls._normalize_ids(dataset_ids)
        normalized_explore_app_ids = cls._normalize_ids(explore_app_ids)
        cls._validate_payload(
            tenant_id,
            name,
            normalized_member_ids,
            normalized_app_ids,
            normalized_dataset_ids,
            normalized_explore_app_ids,
        )
        template = cls._get_template(tenant_id, template_id)

        try:
            template.name = name.strip()
            template.description = description.strip() if description else None
            cls._replace_bindings(
                tenant_id,
                template.id,
                normalized_member_ids,
                normalized_app_ids,
                normalized_dataset_ids,
                normalized_explore_app_ids,
            )
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_template.updated",
                content={"template_id": template.id, "name": template.name},
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
        try:
            cls._replace_bindings(tenant_id, template.id, [], [], [], [])
            db.session.delete(template)
            db.session.add(OperationLog(
                tenant_id=tenant_id,
                account_id=operator.id,
                action="permission_template.deleted",
                content={"template_id": template_id, "name": template.name},
                created_ip=extract_remote_ip(request),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def apply_template(cls, tenant_id: str, template_id: str, operator: Account) -> dict[str, int]:
        template = cls._get_template(tenant_id, template_id)
        member_ids, app_ids, dataset_ids, explore_app_ids = cls._binding_ids(tenant_id, template.id)

        valid_member_ids = set(
            db.session.scalars(
                select(TenantAccountJoin.account_id).where(
                    TenantAccountJoin.tenant_id == tenant_id,
                    TenantAccountJoin.account_id.in_(member_ids),
                )
            ).all()
        ) if member_ids else set()
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
