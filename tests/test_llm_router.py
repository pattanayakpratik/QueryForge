"""Tests for Multi-Provider LLM Router with circuit-breaker fallback."""

import unittest
import httpx
from unittest.mock import AsyncMock, patch
from app.core.llm_router import LLMRouter, extract_sql_from_markdown, LLMResult
from app.config import Settings


class TestLLMRouter(unittest.IsolatedAsyncioTestCase):
    """Unit tests verifying Groq execution and automated Gemini failover."""

    def test_extract_sql_from_markdown_fences(self):
        """Markdown code blocks should be stripped cleanly."""
        markdown_text = "```sql\nSELECT id, name FROM customers;\n```"
        extracted = extract_sql_from_markdown(markdown_text)
        self.assertEqual(extracted, "SELECT id, name FROM customers;")

        plain_text = "SELECT 1;"
        self.assertEqual(extract_sql_from_markdown(plain_text), "SELECT 1;")

    @patch("app.core.llm_router.get_settings")
    async def test_groq_primary_success(self, mock_get_settings):
        """When Groq succeeds, it returns the result without triggering fallback."""
        mock_settings = Settings(
            groq_api_key="mock_groq_key",
            gemini_api_key="mock_gemini_key",
        )
        mock_get_settings.return_value = mock_settings

        # Mock HTTP client
        mock_response = httpx.Response(
            status_code=200,
            json={
                "choices": [{"message": {"content": "SELECT id, name FROM customers;"}}],
                "usage": {"total_tokens": 42},
            },
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        router = LLMRouter(http_client=mock_client, settings=mock_settings)
        result = await router.generate_sql("List all customers")

        self.assertEqual(result.provider, "GROQ")
        self.assertEqual(result.cleaned_sql, "SELECT id, name FROM customers;")
        self.assertFalse(result.fallback_triggered)
        self.assertEqual(result.tokens_used, 42)

    @patch("app.core.llm_router.get_settings")
    async def test_groq_rate_limit_429_triggers_gemini_fallback(self, mock_get_settings):
        """When Groq returns HTTP 429, router automatically falls back to Gemini."""
        mock_settings = Settings(
            groq_api_key="mock_groq_key",
            gemini_api_key="mock_gemini_key",
        )
        mock_get_settings.return_value = mock_settings

        # First request to Groq fails with 429, second request to Gemini succeeds
        groq_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        gemini_req = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent")

        groq_resp = httpx.Response(status_code=429, text="Too Many Requests", request=groq_req)
        gemini_resp = httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "SELECT id, total_amount_cents FROM orders;"}]}}
                ],
                "usageMetadata": {"totalTokenCount": 65},
            },
            request=gemini_req,
        )

        async def mock_post(url, *args, **kwargs):
            if "groq.com" in str(url):
                raise httpx.HTTPStatusError("429 Too Many Requests", request=groq_req, response=groq_resp)
            return gemini_resp

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = mock_post

        router = LLMRouter(http_client=mock_client, settings=mock_settings)
        result = await router.generate_sql("List all orders")

        self.assertEqual(result.provider, "GEMINI")
        self.assertEqual(result.cleaned_sql, "SELECT id, total_amount_cents FROM orders;")
        self.assertTrue(result.fallback_triggered)
        self.assertIn("429", str(result.error_reason))

    @patch("app.core.llm_router.get_settings")
    async def test_groq_timeout_triggers_gemini_fallback(self, mock_get_settings):
        """When Groq times out (>2.5s), router automatically falls back to Gemini."""
        mock_settings = Settings(
            groq_api_key="mock_groq_key",
            gemini_api_key="mock_gemini_key",
        )
        mock_get_settings.return_value = mock_settings

        gemini_req = httpx.Request("POST", "https://generativelanguage.googleapis.com")
        gemini_resp = httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "SELECT * FROM products;"}]}}
                ],
                "usageMetadata": {"totalTokenCount": 50},
            },
            request=gemini_req,
        )

        async def mock_post(url, *args, **kwargs):
            if "groq.com" in str(url):
                raise httpx.TimeoutException("Connection timed out after 2.5s")
            return gemini_resp

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = mock_post

        router = LLMRouter(http_client=mock_client, settings=mock_settings)
        result = await router.generate_sql("List products")

        self.assertEqual(result.provider, "GEMINI")
        self.assertEqual(result.cleaned_sql, "SELECT * FROM products;")
        self.assertTrue(result.fallback_triggered)

    @patch("app.core.llm_router.get_settings")
    async def test_missing_keys_safe_mock_fallback(self, mock_get_settings):
        """When no API keys are provided, router safely falls back without crashing."""
        mock_settings = Settings(
            groq_api_key=None,
            gemini_api_key=None,
        )
        mock_get_settings.return_value = mock_settings

        router = LLMRouter(settings=mock_settings)
        result = await router.generate_sql("SELECT test")

        self.assertEqual(result.provider, "MOCK_FALLBACK")
        self.assertEqual(result.cleaned_sql, "SELECT 1;")


if __name__ == "__main__":
    unittest.main()
