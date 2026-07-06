from typing import TypedDict

from extensions.ext_database import db
from models.account import Tenant


class MmbUiPolicy(TypedDict):
    show_unauthorized_resource_cards: bool
    default_access_enabled: bool
    default_permission_group_id: str | None
    default_permission_template_id: str | None


class UiPolicyService:
    MMB_UI_POLICY_KEY = "mmb_ui_policy"

    @classmethod
    def default_policy(cls) -> MmbUiPolicy:
        return {
            "show_unauthorized_resource_cards": False,
            "default_access_enabled": False,
            "default_permission_group_id": None,
            "default_permission_template_id": None,
        }

    @classmethod
    def get_policy_from_tenant(cls, tenant: Tenant) -> MmbUiPolicy:
        custom_config = tenant.custom_config_dict
        raw_policy = custom_config.get(cls.MMB_UI_POLICY_KEY) or {}
        if not isinstance(raw_policy, dict):
            raw_policy = {}

        policy = cls.default_policy()
        policy["show_unauthorized_resource_cards"] = bool(
            raw_policy.get("show_unauthorized_resource_cards", policy["show_unauthorized_resource_cards"])
        )
        policy["default_access_enabled"] = bool(
            raw_policy.get("default_access_enabled", policy["default_access_enabled"])
        )
        default_group_id = raw_policy.get("default_permission_group_id")
        default_template_id = raw_policy.get("default_permission_template_id")
        policy["default_permission_group_id"] = str(default_group_id) if default_group_id else None
        policy["default_permission_template_id"] = str(default_template_id) if default_template_id else None
        return policy

    @classmethod
    def get_policy(cls, tenant_id: str) -> MmbUiPolicy:
        tenant = db.get_or_404(Tenant, tenant_id)
        return cls.get_policy_from_tenant(tenant)

    @classmethod
    def update_policy(cls, tenant_id: str, show_unauthorized_resource_cards: bool) -> MmbUiPolicy:
        tenant = db.get_or_404(Tenant, tenant_id)
        custom_config = dict(tenant.custom_config_dict)
        raw_policy = custom_config.get(cls.MMB_UI_POLICY_KEY) or {}
        if not isinstance(raw_policy, dict):
            raw_policy = {}

        raw_policy["show_unauthorized_resource_cards"] = bool(show_unauthorized_resource_cards)
        custom_config[cls.MMB_UI_POLICY_KEY] = raw_policy
        tenant.custom_config_dict = custom_config
        db.session.commit()
        return cls.get_policy_from_tenant(tenant)

    @classmethod
    def set_default_access_policy(cls, tenant_id: str, group_id: str, template_id: str) -> MmbUiPolicy:
        tenant = db.get_or_404(Tenant, tenant_id)
        custom_config = dict(tenant.custom_config_dict)
        raw_policy = custom_config.get(cls.MMB_UI_POLICY_KEY) or {}
        if not isinstance(raw_policy, dict):
            raw_policy = {}

        raw_policy["default_access_enabled"] = True
        raw_policy["default_permission_group_id"] = str(group_id)
        raw_policy["default_permission_template_id"] = str(template_id)
        custom_config[cls.MMB_UI_POLICY_KEY] = raw_policy
        tenant.custom_config_dict = custom_config
        db.session.commit()
        return cls.get_policy_from_tenant(tenant)

    @classmethod
    def should_show_unauthorized_resource_cards(cls, tenant_id: str) -> bool:
        return cls.get_policy(tenant_id)["show_unauthorized_resource_cards"]

    @classmethod
    def is_default_access_enabled(cls, tenant_id: str) -> bool:
        policy = cls.get_policy(tenant_id)
        return bool(
            policy["default_access_enabled"]
            and policy["default_permission_group_id"]
            and policy["default_permission_template_id"]
        )
