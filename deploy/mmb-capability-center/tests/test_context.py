from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.models import ChatType, ToolContext


class ToolContextTest(unittest.TestCase):
    def test_p2p_session_is_per_user(self) -> None:
        context = ToolContext(tenant_id="t1", bot_id="b1", chat_type=ChatType.P2P, open_id="ou_a")

        self.assertEqual(context.session_key, "t1:b1:feishu:p2p:ou_a")
        self.assertEqual(len(context.user_key), 24)

    def test_group_session_is_shared_by_default(self) -> None:
        context = ToolContext(tenant_id="t1", bot_id="b1", chat_type=ChatType.GROUP, chat_id="oc_1", sender_open_id="ou_a")

        self.assertEqual(context.session_key, "t1:b1:feishu:group:oc_1")

    def test_group_personal_context_adds_sender(self) -> None:
        context = ToolContext(
            tenant_id="t1",
            bot_id="b1",
            chat_type=ChatType.GROUP,
            chat_id="oc_1",
            sender_open_id="ou_a",
            use_personal_context=True,
        )

        self.assertEqual(context.session_key, "t1:b1:feishu:group-user:oc_1:ou_a")

    def test_p2p_requires_actor(self) -> None:
        with self.assertRaises(ValidationError):
            ToolContext(tenant_id="t1", bot_id="b1", chat_type=ChatType.P2P)

    def test_group_requires_chat_id(self) -> None:
        with self.assertRaises(ValidationError):
            ToolContext(tenant_id="t1", bot_id="b1", chat_type=ChatType.GROUP, sender_open_id="ou_a")


if __name__ == "__main__":
    unittest.main()
