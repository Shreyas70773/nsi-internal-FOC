"""Router Agent — classifies incoming messages and dispatches to specialized agents."""

import json
import logging
from typing import Any

from app.agents.base import Agent
from app.models.schemas import ClassifiedIntent, IntentType, InternalMessage, TaskPriority

logger = logging.getLogger(__name__)

_KEYWORD_RULES: list[tuple[list[str], IntentType]] = [
    (["generate", "make", "create", "draft"], IntentType.GENERATE_DOCUMENT),
    (["assign", "task", "remind"], IntentType.ASSIGN_TASK),
    (["status", "check", "what's pending"], IntentType.CHECK_STATUS),
    (["cancel task"], IntentType.CANCEL_TASK),
    (["pause task"], IntentType.PAUSE_TASK),
    (["compare", "check prices"], IntentType.COMPARE_FILES),
    (["find", "search", "fetch", "get"], IntentType.QUERY_DATA),
    (["research", "look up", "what is the current"], IntentType.RESEARCH),
]

_ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for the NSI Bot (North Star Impex Group).

Given a user message, classify it into exactly ONE of these intents:
- generate_document: user wants to create/draft a document, email, report, invoice, PO, etc.
- assign_task: user wants to assign or delegate a task, set a reminder, or create an action item
- query_data: user wants to look up internal data, find records, check inventory, etc.
- compare_files: user wants to compare documents, prices, or data side-by-side
- check_status: user asks about task progress, pending items, or status updates
- cancel_task: user wants to cancel an existing task
- pause_task: user wants to pause/hold an existing task
- upload_file: user is sharing a file for processing
- research: user wants real-time web research on prices, regulations, suppliers, market data
- general_conversation: general chat, greetings, thank-yous, or questions about the bot itself
- noise: irrelevant message, spam, or something not directed at the bot

Respond with a JSON object:
{
  "intent": "<intent_type>",
  "confidence": <0.0-1.0>,
  "priority": "P0" | "P1" | "P2",
  "assignee": "<person name or null>",
  "deadline": "<deadline string or null>",
  "entities": ["<extracted entities>"]
}

Priority guide: P0 = urgent/time-sensitive, P1 = normal, P2 = low/nice-to-have.
Only output valid JSON, nothing else.
"""


class RouterAgent(Agent):
    def __init__(self):
        super().__init__(
            name="router",
            system_prompt=_ROUTER_SYSTEM_PROMPT,
            tool_categories=[],
            token_budget=1000,
        )

    def _match_rules(self, text: str) -> IntentType | None:
        """Stage 1: zero-cost keyword matching."""
        lower = text.lower().strip()
        for keywords, intent in _KEYWORD_RULES:
            for kw in keywords:
                if lower.startswith(kw):
                    return intent
        return None

    def _parse_llm_classification(self, raw: str, original_message: str) -> ClassifiedIntent:
        """Parse the LLM JSON response into a ClassifiedIntent."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Router LLM returned non-JSON, defaulting to GENERAL_CONVERSATION")
            return ClassifiedIntent(
                intent=IntentType.GENERAL_CONVERSATION,
                confidence=0.5,
                raw_command=original_message,
            )

        intent_str = data.get("intent", "general_conversation")
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.GENERAL_CONVERSATION

        priority_str = data.get("priority", "P1")
        try:
            priority = TaskPriority(priority_str)
        except ValueError:
            priority = TaskPriority.P1

        return ClassifiedIntent(
            intent=intent,
            confidence=data.get("confidence", 0.8),
            priority=priority,
            assignee=data.get("assignee"),
            deadline=data.get("deadline"),
            entities=data.get("entities", []),
            raw_command=original_message,
        )

    async def route(self, message: InternalMessage) -> ClassifiedIntent:
        """Classify the message intent: rule-based first, then LLM fallback."""
        text = (message.bot_command or message.content).strip()

        # Stage 1: keyword rules
        matched = self._match_rules(text)
        if matched:
            logger.info(f"Router: rule-matched intent={matched.value}")
            return ClassifiedIntent(
                intent=matched,
                confidence=1.0,
                raw_command=text,
            )

        # Stage 2: LLM classification
        logger.info("Router: no rule match, using LLM classification")
        response_text = await self.run(text)
        return self._parse_llm_classification(response_text, text)


router_agent = RouterAgent()
