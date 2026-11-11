"""Multi-Provider LLM Router with automatic Groq-to-Gemini circuit breaker failover."""

import re
import time
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMResult(BaseModel):
    """Structured response container from LLM generation."""
    content: str
    cleaned_sql: str
    provider: str  # 'GROQ' or 'GEMINI'
    model: str
    latency_ms: float
    fallback_triggered: bool = False
    tokens_used: Optional[int] = None
    error_reason: Optional[str] = None


def extract_sql_from_markdown(raw_text: str) -> str:
    """Extract raw SQL statement from LLM output, stripping markdown code fences."""
    text = raw_text.strip()
    # Match ```sql ... ``` or ``` ... ```
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


class LLMRouter:
    """Orchestrates query synthesis across Groq and Gemini with automated failover."""

    def __init__(
        self,
        http_client: Optional[httpx.AsyncClient] = None,
        settings: Optional[Any] = None,
    ):
        self._settings = settings or get_settings()
        self._http_client = http_client

    async def generate_sql(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        preferred_provider: Optional[str] = None,
    ) -> LLMResult:
        """Generate SQL query targeting Groq with automatic sub-2.5s Gemini fallback.

        Args:
            prompt: User question along with retrieved schema cards and few-shot examples.
            system_prompt: Base instruction set for Text-to-SQL synthesis.
            preferred_provider: Optional override ('GROQ' or 'GEMINI').

        Returns:
            LLMResult containing raw output, cleaned SQL, telemetry, and provider metadata.
        """
        sys_prompt = system_prompt or (
            "You are an expert Text-to-SQL engineer. Output ONLY a valid, single SELECT query. "
            "Do not include commentary or explanatory markdown outside the SQL code fence."
        )

        # Force Gemini if explicitly requested
        if preferred_provider == "GEMINI":
            return await self._call_gemini(prompt, sys_prompt, fallback=False)

        # 1. Primary Attempt: Groq (sub-300ms ultra-low latency)
        if self._settings.groq_api_key and preferred_provider != "GEMINI":
            try:
                start_time = time.perf_counter()
                result = await self._call_groq(prompt, sys_prompt)
                return result
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                reason = f"Groq failure (status={status_code}, error={str(exc)}). Failing over to Gemini."
                logger.warning(reason)

                # Fallback to Gemini
                fallback_result = await self._call_gemini(prompt, sys_prompt, fallback=True, failure_reason=reason)
                return fallback_result
            except Exception as exc:
                reason = f"Unexpected Groq error: {str(exc)}. Failing over to Gemini."
                logger.warning(reason)
                return await self._call_gemini(prompt, sys_prompt, fallback=True, failure_reason=reason)

        # If Groq is not configured, directly route to Gemini
        return await self._call_gemini(
            prompt,
            sys_prompt,
            fallback=False,
            failure_reason="Groq API key not configured; routed to Gemini directly.",
        )

    async def _call_groq(self, prompt: str, system_prompt: str) -> LLMResult:
        """Call Groq API (LLaMA-3.3-70B-versatile)."""
        start_time = time.perf_counter()
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        client = self._http_client or httpx.AsyncClient(timeout=self._settings.groq_timeout_seconds)
        should_close = self._http_client is None
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            raw_text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens")
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            return LLMResult(
                content=raw_text,
                cleaned_sql=extract_sql_from_markdown(raw_text),
                provider="GROQ",
                model=self._settings.groq_model,
                latency_ms=round(latency_ms, 2),
                tokens_used=tokens,
                fallback_triggered=False,
            )
        finally:
            if should_close:
                await client.aclose()

    async def _call_gemini(
        self,
        prompt: str,
        system_prompt: str,
        fallback: bool = False,
        failure_reason: Optional[str] = None,
    ) -> LLMResult:
        """Call Google Gemini 1.5/2.0 Flash API."""
        start_time = time.perf_counter()

        if not self._settings.gemini_api_key:
            # When running in mock or unit testing environment without external keys
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            mock_sql = "SELECT 1;"
            return LLMResult(
                content=mock_sql,
                cleaned_sql=mock_sql,
                provider="MOCK_FALLBACK",
                model="local-test-fallback",
                latency_ms=round(latency_ms, 2),
                fallback_triggered=fallback,
                error_reason=failure_reason or "No active LLM API keys provided",
            )

        model = self._settings.gemini_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self._settings.gemini_api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"System Instructions:\n{system_prompt}\n\nUser Question:\n{prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
            },
        }

        client = self._http_client or httpx.AsyncClient(timeout=self._settings.gemini_timeout_seconds)
        should_close = self._http_client is None
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates", [])
            raw_text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    raw_text = parts[0].get("text", "")

            tokens = data.get("usageMetadata", {}).get("totalTokenCount")
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            return LLMResult(
                content=raw_text,
                cleaned_sql=extract_sql_from_markdown(raw_text),
                provider="GEMINI",
                model=model,
                latency_ms=round(latency_ms, 2),
                tokens_used=tokens,
                fallback_triggered=fallback,
                error_reason=failure_reason,
            )
        finally:
            if should_close:
                await client.aclose()
