import asyncio
import time
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    async def acquire(self):
        while True:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            wait = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait)


class LLMProvider:
    def __init__(self, name: str, client: AsyncOpenAI, model: str,
                 rate_limiter: TokenBucket | None = None,
                 extra_body: dict | None = None):
        self.name = name
        self.client = client
        self.model = model
        self.rate_limiter = rate_limiter
        self.extra_body = extra_body or {}

    async def chat(self, messages: list[dict], tools: list[dict] | None, max_tokens: int):
        if self.rate_limiter:
            await self.rate_limiter.acquire()

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": 60,
        }
        if tools:
            kwargs["tools"] = tools
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return choice, usage


class LLMGateway:
    def __init__(self):
        self._providers: list[LLMProvider] = []
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        self._initialized = True

        if settings.nvidia_api_key:
            self._providers.append(LLMProvider(
                name="nvidia",
                client=AsyncOpenAI(api_key=settings.nvidia_api_key, base_url=settings.nvidia_base_url),
                model=settings.nvidia_model,
                rate_limiter=TokenBucket(rate=40 / 60, capacity=40),
                extra_body={"chat_template_kwargs": {"thinking": True}},
            ))

        if settings.openai_api_key:
            self._providers.append(LLMProvider(
                name="openai",
                client=AsyncOpenAI(api_key=settings.openai_api_key),
                model=settings.openai_model,
            ))

        if settings.anthropic_api_key:
            self._providers.append(LLMProvider(
                name="anthropic",
                client=AsyncOpenAI(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url),
                model=settings.anthropic_model,
            ))

        if not self._providers:
            logger.warning("No LLM providers configured — all API keys are empty")

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 8000, request_type: str = "general") -> dict:
        self._ensure_init()

        if not self._providers:
            raise RuntimeError("No LLM providers are configured")

        last_exc: Exception | None = None

        for provider in self._providers:
            start = time.monotonic()
            try:
                choice, usage = await provider.chat(messages, tools, max_tokens)
                latency_ms = int((time.monotonic() - start) * 1000)

                await self._log_usage(provider.name, provider.model, request_type, usage, latency_ms)

                content = choice.message.content
                tool_calls = None
                if choice.message.tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in choice.message.tool_calls
                    ]

                return {"content": content, "tool_calls": tool_calls}

            except Exception as exc:
                latency_ms = int((time.monotonic() - start) * 1000)
                last_exc = exc

                status = getattr(exc, "status_code", None)
                is_retriable = (
                    status in (429, 500, 502, 503, 504)
                    or "timeout" in str(exc).lower()
                    or "timed out" in str(exc).lower()
                )

                if is_retriable:
                    logger.warning(
                        "Provider %s failed (status=%s, %dms), falling back: %s",
                        provider.name, status, latency_ms, exc,
                    )
                    continue

                logger.error("Provider %s non-retriable error: %s", provider.name, exc)
                raise

        raise RuntimeError(f"All LLM providers failed. Last error: {last_exc}")

    async def _log_usage(self, provider_name: str, model: str, request_type: str,
                         usage: dict, latency_ms: int):
        try:
            from app.core.database import db
            await db.execute(
                "INSERT INTO token_usage (provider, model, request_type, "
                "prompt_tokens, completion_tokens, total_tokens, latency_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (
                    provider_name,
                    model,
                    request_type,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    usage.get("total_tokens", 0),
                    latency_ms,
                ),
            )
        except Exception as exc:
            logger.error("Failed to log token usage: %s", exc)


llm_gateway = LLMGateway()
