import asyncio
import os
from dataclasses import dataclass, replace
from typing import Callable, Optional
from urllib.parse import urlparse

from openai import AsyncOpenAI


@dataclass(frozen=True)
class AIProviderConfig:
    provider: str = "openai"
    fallback_provider: str = "none"
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-5-nano"
    local_api_key: Optional[str] = None
    local_base_url: Optional[str] = None
    local_model: Optional[str] = None
    timeout_seconds: float = 45.0
    retry_attempts: int = 1
    retry_backoff_seconds: float = 1.5
    openai_max_output_tokens: Optional[int] = None
    local_max_output_tokens: Optional[int] = None
    local_context_tokens: Optional[int] = None
    local_temperature: Optional[float] = None


class AIProviderError(RuntimeError):
    pass


class _ResponsesProxy:
    def __init__(self, gateway):
        self._gateway = gateway

    async def create(self, **kwargs):
        return await self._gateway.create_response(**kwargs)


def _clean_provider(value):
    provider = str(value or "").strip().lower()
    return provider or "openai"


def _normalize_provider_mode(provider, fallback_provider):
    provider = _clean_provider(provider)
    fallback_provider = _clean_provider(fallback_provider)

    if provider in {"openai-only", "local-only"}:
        fallback_provider = "none"
        provider = provider.replace("-only", "")

    if provider == "openai-first":
        provider = "openai"
        if fallback_provider == "none":
            fallback_provider = "local"

    elif provider == "local-first":
        provider = "local"
        if fallback_provider == "none":
            fallback_provider = "openai"

    elif provider == "local":
        pass

    elif provider == "openai":
        pass

    elif provider not in {"openai", "local"}:
        provider = "openai"
        if fallback_provider == "none":
            fallback_provider = "local"

    if fallback_provider not in {"openai", "local", "none"}:
        fallback_provider = "none"

    return provider, fallback_provider


def _redact_base_url(url):
    if not url:
        return "none"

    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"

    return str(url)


class AIGateway:
    def __init__(
        self,
        config: AIProviderConfig,
        *,
        client_factory: Callable[..., AsyncOpenAI] = AsyncOpenAI,
    ):
        provider, fallback_provider = _normalize_provider_mode(
            config.provider,
            config.fallback_provider,
        )

        self.config = replace(
            config,
            provider=provider,
            fallback_provider=fallback_provider,
        )
        self._client_factory = client_factory
        self._clients = {}
        self._last_success_provider = None
        self._last_success_at = None
        self._last_error = None
        self._last_failure_provider = None
        self._last_failure_at = None
        self.responses = _ResponsesProxy(self)

    def _provider_chain(self):
        chain = [self.config.provider]
        if self.config.fallback_provider != "none":
            if self.config.fallback_provider not in chain:
                chain.append(self.config.fallback_provider)
        return chain

    def _provider_model(self, provider, requested_model):
        if provider == "local" and self.config.local_model:
            return self.config.local_model

        if provider == "openai" and self.config.openai_model:
            return self.config.openai_model

        return requested_model

    def _provider_max_output_tokens(self, provider, requested_tokens):
        if provider == "local" and self.config.local_max_output_tokens is not None:
            if requested_tokens is None:
                return self.config.local_max_output_tokens
            return min(int(requested_tokens), int(self.config.local_max_output_tokens))

        if provider == "openai" and self.config.openai_max_output_tokens is not None:
            if requested_tokens is None:
                return self.config.openai_max_output_tokens
            return min(int(requested_tokens), int(self.config.openai_max_output_tokens))

        return requested_tokens

    def _provider_temperature(self, provider, requested_temperature):
        if requested_temperature is not None:
            return requested_temperature

        if provider == "local" and self.config.local_temperature is not None:
            return self.config.local_temperature

        return requested_temperature

    def _provider_client(self, provider):
        provider = _clean_provider(provider)

        cached = self._clients.get(provider)
        if cached is not None:
            return cached

        if provider == "openai":
            kwargs = {
                "api_key": self.config.openai_api_key or os.getenv("OPENAI_API_KEY"),
            }
            if self.config.openai_base_url:
                kwargs["base_url"] = self.config.openai_base_url
        elif provider == "local":
            if not self.config.local_base_url:
                raise AIProviderError(
                    "LOCAL_AI_BASE_URL is required when the local provider is selected."
                )
            kwargs = {
                "api_key": self.config.local_api_key or "local",
                "base_url": self.config.local_base_url,
            }
        else:
            raise AIProviderError(f"Unsupported AI provider: {provider}")

        client = self._client_factory(**kwargs)
        self._clients[provider] = client
        return client

    async def _create_with_provider(self, provider, kwargs):
        client = self._provider_client(provider)
        timeout_seconds = max(1.0, float(self.config.timeout_seconds))
        attempts = max(1, int(self.config.retry_attempts))
        backoff = max(0.0, float(self.config.retry_backoff_seconds))
        last_error = None

        for attempt in range(attempts):
            try:
                return await asyncio.wait_for(
                    client.responses.create(**kwargs),
                    timeout=timeout_seconds,
                )
            except Exception as error:
                last_error = error
                if attempt + 1 < attempts:
                    await asyncio.sleep(backoff * (attempt + 1))

        raise last_error

    async def create_response(self, **kwargs):
        requested_model = kwargs.get("model")
        requested_tokens = kwargs.get("max_output_tokens")
        requested_temperature = kwargs.get("temperature")
        errors = []

        for provider in self._provider_chain():
            provider_kwargs = dict(kwargs)
            provider_kwargs["model"] = self._provider_model(provider, requested_model)
            provider_kwargs["max_output_tokens"] = self._provider_max_output_tokens(
                provider,
                requested_tokens,
            )
            provider_kwargs["temperature"] = self._provider_temperature(
                provider,
                requested_temperature,
            )

            try:
                response = await self._create_with_provider(
                    provider,
                    provider_kwargs,
                )
            except Exception as error:
                errors.append((provider, error))
                self._last_error = error
                self._last_failure_provider = provider
                self._last_failure_at = asyncio.get_running_loop().time()
                continue

            self._last_success_provider = provider
            self._last_success_at = asyncio.get_running_loop().time()
            self._last_error = None
            self._last_failure_provider = None
            self._last_failure_at = None
            return response

        if errors:
            provider_list = ", ".join(provider for provider, _ in errors)
            error_text = "; ".join(f"{provider}: {error!r}" for provider, error in errors)
            raise AIProviderError(
                f"All configured AI providers failed ({provider_list}). {error_text}"
            )

        raise AIProviderError("No AI providers are configured.")

    async def health_check(self, prompt="ping"):
        response = await self.create_response(
            model=self.config.openai_model,
            input=prompt,
            max_output_tokens=1,
            store=False,
        )
        return response

    def describe(self):
        return {
            "provider": self.config.provider,
            "fallback_provider": self.config.fallback_provider,
            "openai_model": self.config.openai_model,
            "local_model": self.config.local_model or "unset",
            "openai_base_url": _redact_base_url(self.config.openai_base_url),
            "local_base_url": _redact_base_url(self.config.local_base_url),
            "timeout_seconds": self.config.timeout_seconds,
            "retry_attempts": self.config.retry_attempts,
            "openai_max_output_tokens": self.config.openai_max_output_tokens,
            "local_max_output_tokens": self.config.local_max_output_tokens,
            "local_context_tokens": self.config.local_context_tokens,
            "local_temperature": self.config.local_temperature,
            "last_success_provider": self._last_success_provider or "none",
            "last_failure_provider": self._last_failure_provider or "none",
            "last_error": repr(self._last_error) if self._last_error else "none",
        }


def _env_int(name, default=None):
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return int(value)


def _env_float(name, default=None):
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return float(value)


def build_ai_gateway():
    provider, fallback_provider = _normalize_provider_mode(
        os.getenv("AI_PROVIDER", "openai"),
        os.getenv("AI_FALLBACK_PROVIDER", "none"),
    )

    config = AIProviderConfig(
        provider=provider,
        fallback_provider=fallback_provider,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        openai_model=os.getenv(
            "OPENAI_MODEL",
            "gpt-5-nano",
        ),
        local_api_key=os.getenv("LOCAL_AI_API_KEY"),
        local_base_url=os.getenv("LOCAL_AI_BASE_URL"),
        local_model=os.getenv("LOCAL_AI_MODEL"),
        timeout_seconds=_env_float("AI_TIMEOUT_SECONDS", 45.0),
        retry_attempts=_env_int("AI_RETRY_ATTEMPTS", 1),
        retry_backoff_seconds=_env_float("AI_RETRY_BACKOFF_SECONDS", 1.5),
        openai_max_output_tokens=_env_int("OPENAI_MAX_OUTPUT_TOKENS"),
        local_max_output_tokens=_env_int("LOCAL_AI_MAX_OUTPUT_TOKENS"),
        local_context_tokens=_env_int("LOCAL_AI_CONTEXT_TOKENS"),
        local_temperature=_env_float("LOCAL_AI_TEMPERATURE"),
    )

    return AIGateway(config)


def format_ai_status(ai_gateway):
    status = ai_gateway.describe()
    lines = [
        "AI provider: "
        + status["provider"],
        "AI fallback: "
        + status["fallback_provider"],
        "OpenAI model: "
        + status["openai_model"],
        "Local model: "
        + status["local_model"],
        "OpenAI endpoint: "
        + status["openai_base_url"],
        "Local endpoint: "
        + status["local_base_url"],
        "Timeout: "
        + str(status["timeout_seconds"])
        + "s",
        "Retries: "
        + str(status["retry_attempts"]),
    ]

    if status["local_context_tokens"] is not None:
        lines.append(
            "Local context limit: "
            + str(status["local_context_tokens"])
        )

    if status["local_temperature"] is not None:
        lines.append(
            "Local temperature: "
            + str(status["local_temperature"])
        )

    lines.append(
        "Last success: "
        + status["last_success_provider"]
    )
    lines.append(
        "Last failure: "
        + status["last_failure_provider"]
    )

    return "\n".join(lines)
