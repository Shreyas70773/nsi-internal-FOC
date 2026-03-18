"""Research Agent — real-time web search via the Perplexity API."""

import logging

logger = logging.getLogger(__name__)

_RESEARCH_SYSTEM_PROMPT = """\
You are a research assistant for a manufacturing and distribution company \
(North Star Impex Group). Provide factual, sourced answers about: current \
material prices, import/export regulations, supplier information, market data, \
and industry news. Always cite your sources.\
"""


class ResearchAgent:
    def __init__(self):
        self.name = "research"
        self._client = None

    def _get_client(self):
        """Lazy-init the async OpenAI client pointed at Perplexity."""
        if self._client is None:
            from app.config import settings

            if not settings.perplexity_api_key:
                return None

            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.perplexity_api_key,
                base_url=settings.perplexity_base_url,
            )
        return self._client

    async def research(self, query: str) -> str:
        """Run a research query through Perplexity and return the answer."""
        client = self._get_client()
        if client is None:
            logger.warning("Perplexity API key not configured, skipping research")
            return "Research is currently unavailable (API key not configured)."

        from app.config import settings

        try:
            response = await client.chat.completions.create(
                model=settings.perplexity_model,
                messages=[
                    {"role": "system", "content": _RESEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Perplexity API call failed: {e}", exc_info=True)
            return f"Research request failed: {e}"


research_agent = ResearchAgent()
