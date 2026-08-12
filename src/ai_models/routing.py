"""Input routing for Rule, Moderation, FAQ and LLM/RAG flows."""

from __future__ import annotations

import re

from .contracts import FlowName, RoutingPlan

RULE_COMMANDS = frozenset(
    {
        "/start",
        "/help",
        "/rule",
        "/rules",
        "/event",
        "/daily",
        "/weekly",
        "/faq",
        "/report",
        "/admin",
        "/resources",
        "/settings",
    }
)


class InputRouter:
    """Plan processing without coupling to Discord, Telegram or HTTP models."""

    def plan(
        self,
        text: str,
        *,
        bot_mentioned: bool,
        private_chat: bool = False,
        bot_username: str | None = None,
    ) -> RoutingPlan:
        cleaned = text.strip()
        command = self._command(cleaned)
        if command in RULE_COMMANDS or command is not None:
            return RoutingPlan(
                stages=(FlowName.RULE,),
                question=cleaned,
                is_qa_request=False,
                reason="command-is-handled-by-deterministic-rule-flow",
            )

        is_qa_request = private_chat or bot_mentioned
        if not is_qa_request:
            return RoutingPlan(
                stages=(FlowName.MODERATION,),
                question="",
                is_qa_request=False,
                reason="ordinary-group-message-only-needs-realtime-moderation",
            )

        question = self._strip_mention(cleaned, bot_username)
        return RoutingPlan(
            stages=(FlowName.MODERATION, FlowName.FAQ, FlowName.LLM_RAG),
            question=question,
            is_qa_request=True,
            reason="bot-was-mentioned-or-message-is-private",
        )

    @staticmethod
    def _command(text: str) -> str | None:
        match = re.match(r"^(/[^\s@]+)(?:@[^\s]+)?(?:\s|$)", text.casefold())
        return match.group(1) if match else None

    @staticmethod
    def _strip_mention(text: str, bot_username: str | None) -> str:
        if not bot_username:
            return text
        username = bot_username.removeprefix("@")
        question = re.sub(rf"@{re.escape(username)}\b", "", text, flags=re.IGNORECASE).strip()
        return question or "hello"
