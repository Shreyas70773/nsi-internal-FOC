"""Base Agent class implementing the tool-calling execution loop."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10


class Agent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tool_categories: list[str] | None = None,
        token_budget: int = 8000,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.tool_categories = tool_categories or []
        self.token_budget = token_budget

    def _get_tools(self) -> list[dict]:
        from app.tools.base import tool_registry

        if not self.tool_categories:
            return []
        return tool_registry.to_openai_tools(*self.tool_categories)

    async def _call_llm(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> dict:
        """Call the LLM gateway. Returns the raw response message dict."""
        from app.services.llm_gateway import llm_gateway

        return await llm_gateway.chat(
            messages=messages,
            tools=tools if tools else None,
            max_tokens=self.token_budget,
            request_type=f"agent:{self.name}",
        )

    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a registered tool and return the result as a string."""
        from app.tools.base import tool_registry

        tool = tool_registry.get(tool_name)
        if not tool:
            return json.dumps({"error": f"Tool '{tool_name}' not found"})
        try:
            result = await tool.execute(**arguments)
            return json.dumps(result) if not isinstance(result, str) else result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    async def run(self, user_message: str, context: list[dict] | None = None) -> str:
        """Execute the agent's task with a multi-turn tool-calling loop."""
        tools = self._get_tools()
        messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": user_message})

        for iteration in range(MAX_ITERATIONS):
            response = await self._call_llm(messages, tools=tools or None)

            if not response.get("tool_calls"):
                return response.get("content", "")

            messages.append({
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": tc["function"]}
                    for tc in response["tool_calls"]
                ],
            })

            for tool_call in response["tool_calls"]:
                fn = tool_call["function"]
                tool_name = fn["name"]
                try:
                    arguments = (
                        json.loads(fn["arguments"])
                        if isinstance(fn["arguments"], str)
                        else fn["arguments"]
                    )
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(f"[{self.name}] Calling tool: {tool_name}")
                result = await self._execute_tool(tool_name, arguments)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result,
                    }
                )

        logger.warning(f"[{self.name}] Hit max iterations ({MAX_ITERATIONS})")
        return "I wasn't able to complete this task within the allowed steps. Please try simplifying your request."
