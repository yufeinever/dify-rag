from typing import TypedDict

from extensions.ext_database import db
from models.account import Tenant


class MmbUiPolicy(TypedDict):
    show_unauthorized_resource_cards: bool


class UiPolicyService:
    MMB_UI_POLICY_KEY = "mmb_ui_policy"

    @classmethod
    def default_policy(cls) -> MmbUiPolicy:
        return {"show_unauthorized_resource_cards": False}

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
    def should_show_unauthorized_resource_cards(cls, tenant_id: str) -> bool:
        return cls.get_policy(tenant_id)["show_unauthorized_resource_cards"]
