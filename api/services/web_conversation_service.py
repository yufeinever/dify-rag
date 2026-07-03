from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.app.entities.app_invoke_entities import InvokeFrom
from extensions.ext_database import db
from libs.infinite_scroll_pagination import InfiniteScrollPagination
from models import Account
from models.enums import CreatorUserRole
from models.model import App, EndUser, Message
from models.web import PinnedConversation
from models.workflow import WorkflowRun
from services.conversation_service import ConversationService


class WebConversationService:
    @classmethod
    def pagination_by_last_id(
        cls,
        *,
        session: Session,
        app_model: App,
        user: Account | EndUser | None,
        last_id: str | None,
        limit: int,
        invoke_from: InvokeFrom,
        pinned: bool | None = None,
        sort_by="-updated_at",
    ) -> InfiniteScrollPagination:
        if not user:
            raise ValueError("User is required")
        include_ids = None
        exclude_ids = None
        if pinned is not None and user:
            stmt = (
                select(PinnedConversation.conversation_id)
                .where(
                    PinnedConversation.app_id == app_model.id,
                    PinnedConversation.created_by_role == ("account" if isinstance(user, Account) else "end_user"),
                    PinnedConversation.created_by == user.id,
                )
                .order_by(PinnedConversation.created_at.desc())
            )
            pinned_conversation_ids = session.scalars(stmt).all()

            if pinned:
                include_ids = pinned_conversation_ids
            else:
                exclude_ids = pinned_conversation_ids

        return ConversationService.pagination_by_last_id(
            session=session,
            app_model=app_model,
            user=user,
            last_id=last_id,
            limit=limit,
            invoke_from=invoke_from,
            include_ids=include_ids,
            exclude_ids=exclude_ids,
            sort_by=sort_by,
        )

    @classmethod
    def attach_latest_workflow_run_status(cls, *, session: Session, conversations: list, app_id: str) -> None:
        conversation_ids = [conversation.id for conversation in conversations]
        if not conversation_ids:
            return

        latest_message_query = (
            select(
                Message.conversation_id.label("conversation_id"),
                Message.id.label("message_id"),
                Message.workflow_run_id.label("workflow_run_id"),
                func.row_number()
                .over(
                    partition_by=Message.conversation_id,
                    order_by=(Message.created_at.desc(), Message.id.desc()),
                )
                .label("row_number"),
            )
            .where(
                Message.app_id == app_id,
                Message.conversation_id.in_(conversation_ids),
                Message.workflow_run_id.isnot(None),
            )
            .subquery()
        )

        rows = session.execute(
            select(
                latest_message_query.c.conversation_id,
                latest_message_query.c.message_id,
                latest_message_query.c.workflow_run_id,
                WorkflowRun.status,
            )
            .outerjoin(WorkflowRun, WorkflowRun.id == latest_message_query.c.workflow_run_id)
            .where(latest_message_query.c.row_number == 1)
        ).all()
        latest_by_conversation_id = {str(row.conversation_id): row for row in rows}

        for conversation in conversations:
            latest = latest_by_conversation_id.get(str(conversation.id))
            if not latest:
                continue
            setattr(conversation, "latest_message_id", str(latest.message_id) if latest.message_id else None)
            setattr(conversation, "latest_workflow_run_id", str(latest.workflow_run_id) if latest.workflow_run_id else None)
            setattr(conversation, "latest_workflow_run_status", latest.status)

    @classmethod
    def pin(cls, app_model: App, conversation_id: str, user: Account | EndUser | None):
        if not user:
            return
        pinned_conversation = db.session.scalar(
            select(PinnedConversation)
            .where(
                PinnedConversation.app_id == app_model.id,
                PinnedConversation.conversation_id == conversation_id,
                PinnedConversation.created_by_role == ("account" if isinstance(user, Account) else "end_user"),
                PinnedConversation.created_by == user.id,
            )
            .limit(1)
        )

        if pinned_conversation:
            return

        conversation = ConversationService.get_conversation(
            app_model=app_model, conversation_id=conversation_id, user=user
        )

        pinned_conversation = PinnedConversation(
            app_id=app_model.id,
            conversation_id=conversation.id,
            created_by_role=CreatorUserRole.ACCOUNT if isinstance(user, Account) else CreatorUserRole.END_USER,
            created_by=user.id,
        )

        db.session.add(pinned_conversation)
        db.session.commit()

    @classmethod
    def unpin(cls, app_model: App, conversation_id: str, user: Account | EndUser | None):
        if not user:
            return
        pinned_conversation = db.session.scalar(
            select(PinnedConversation)
            .where(
                PinnedConversation.app_id == app_model.id,
                PinnedConversation.conversation_id == conversation_id,
                PinnedConversation.created_by_role == ("account" if isinstance(user, Account) else "end_user"),
                PinnedConversation.created_by == user.id,
            )
            .limit(1)
        )

        if not pinned_conversation:
            return

        db.session.delete(pinned_conversation)
        db.session.commit()
