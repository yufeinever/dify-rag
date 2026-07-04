from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChatType(StrEnum):
    P2P = "p2p"
    GROUP = "group"


class ResourceScope(StrEnum):
    ENTERPRISE = "enterprise"
    DEPARTMENT = "department"
    PROJECT = "project"
    TEAM = "team"
    PERSONAL = "personal"


class ToolContext(BaseModel):
    tenant_id: str = Field(min_length=1)
    bot_id: str = Field(min_length=1)
    channel: str = Field(default="feishu")
    chat_type: ChatType = ChatType.P2P
    open_id: str | None = None
    sender_open_id: str | None = None
    chat_id: str | None = None
    department_id: str | None = None
    project_id: str | None = None
    role: str = "member"
    scopes: list[ResourceScope] = Field(default_factory=lambda: [ResourceScope.ENTERPRISE])
    use_personal_context: bool = False

    @model_validator(mode="after")
    def validate_identity(self) -> "ToolContext":
        if self.chat_type == ChatType.P2P and not (self.open_id or self.sender_open_id):
            raise ValueError("open_id or sender_open_id is required for p2p context")
        if self.chat_type == ChatType.GROUP and not self.chat_id:
            raise ValueError("chat_id is required for group context")
        if self.use_personal_context and not (self.sender_open_id or self.open_id):
            raise ValueError("sender_open_id or open_id is required for personal context")
        return self

    @property
    def actor_id(self) -> str:
        return self.sender_open_id or self.open_id or "unknown"

    @property
    def session_key(self) -> str:
        parts = [self.tenant_id, self.bot_id, self.channel]
        if self.chat_type == ChatType.P2P:
            parts.extend(["p2p", self.open_id or self.sender_open_id or "unknown"])
        elif self.use_personal_context:
            parts.extend(["group-user", self.chat_id or "unknown", self.actor_id])
        else:
            parts.extend(["group", self.chat_id or "unknown"])
        return ":".join(parts)

    @property
    def user_key(self) -> str:
        raw = f"{self.tenant_id}:{self.channel}:{self.actor_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class ContextResponse(BaseModel):
    session_key: str
    user_key: str
    chat_type: ChatType
    shared_context: bool


class SearchEnterpriseKnowledgeRequest(BaseModel):
    context: ToolContext
    query: str = Field(min_length=1)
    dataset_id: str | None = None
    document_id: str | None = None
    limit: int = Field(default=8, ge=1, le=30)


class ReadKnowledgeRequest(BaseModel):
    context: ToolContext
    document_id: str = Field(min_length=1)
    center_position: int | None = None
    before: int = Field(default=2, ge=0, le=10)
    after: int = Field(default=2, ge=0, le=10)
    limit: int = Field(default=20, ge=1, le=100)


class SearchMaterialsRequest(BaseModel):
    context: ToolContext
    query: str | None = None
    extension: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ReadMaterialRequest(BaseModel):
    context: ToolContext
    relative_path: str = Field(min_length=1)
    max_chars: int = Field(default=12000, ge=1, le=50000)


class GenerateCopywritingRequest(BaseModel):
    context: ToolContext
    user_query: str = Field(min_length=1)
    platform: str | None = None
    audience: str | None = None
    style: str | None = None
    extra_context: str | None = None


class PosterBrief(BaseModel):
    theme: str
    background: str | None = None
    special_elements: list[str] = Field(default_factory=list)
    audience: str | None = None
    main_title: str | None = None
    subtitle: str | None = None
    selling_points: list[str] = Field(default_factory=list)
    brand_constraints: str | None = None


class PosterAsset(BaseModel):
    url: str | None = None
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreatePosterJobRequest(BaseModel):
    context: ToolContext
    user_query: str = Field(min_length=1)
    brief: PosterBrief | None = None
    assets: list[PosterAsset] = Field(default_factory=list)
    size: str = "1080x1440"
    request_id: str | None = None


class CreateBusinessArtifactRequest(BaseModel):
    context: ToolContext
    artifact_type: Literal["word", "excel", "ppt", "document", "spreadsheet", "presentation", "team_note", "other"] = "other"
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    instructions: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class CreateTeamArtifactRequest(BaseModel):
    context: ToolContext
    artifact_type: Literal["copywriting", "poster", "summary", "research", "other"] = "other"
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    visibility: Literal["team", "project", "personal"] = "team"
    source_request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolDescriptor(BaseModel):
    name: str
    description: str
    resource_scopes: list[ResourceScope]
    endpoint: str
    side_effect: bool = False


class ToolResponse(BaseModel):
    request_id: str
    session_key: str
    tool: str
    data: dict[str, Any]
    sources: list[dict[str, Any]] = Field(default_factory=list)
