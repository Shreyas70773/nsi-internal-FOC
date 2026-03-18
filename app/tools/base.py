"""MCP-compatible tool registry. Tools are defined once and consumed by any agent."""

import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class Tool:
    """A single tool that an agent can invoke via LLM function calling."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Awaitable[Any]],
        category: str = "general",
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.category = category

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs) -> Any:
        return await self.handler(**kwargs)


class ToolRegistry:
    """Central registry. Agents pull tools by category."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} [{tool.category}]")

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_by_category(self, *categories: str) -> list[Tool]:
        return [t for t in self._tools.values() if t.category in categories]

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_tools(self, *categories: str) -> list[dict]:
        """Get tool schemas for a set of categories, ready to pass to LLM."""
        tools = self.get_by_category(*categories) if categories else self.get_all()
        return [t.to_openai_schema() for t in tools]


# Module-level singleton
tool_registry = ToolRegistry()


def register_tool(
    name: str, description: str, parameters: dict, category: str = "general"
):
    """Decorator to register an async function as a tool."""

    def decorator(func):
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
            category=category,
        )
        tool_registry.register(tool)
        return func

    return decorator
