"""Unit tests for the LLM summary module (no network: the client is mocked).

Run: docker compose run --rm qgis python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx2 as httpx  # noqa: E402  (HTTP library used by openai 3.x)
import openai  # noqa: E402

from report import llm  # noqa: E402

SUMMARY = {
    "name": "Kas Harbour Villa", "address": None, "lat": 36.2018, "lon": 29.6377,
    "utm_epsg": 32635, "buffers_m": [500, 1000], "poi_search_radius_m": 1500,
    "qgis_version": "3.44.15", "generated_at": "2026-11-11T08:00:00+00:00",
    "categories": {
        "beach": {"label": "Beach", "count_500": 0, "count_1000": 1,
                  "nearest_m": 746, "nearest_name": "Kucuk Cakil Plaji"},
        "cafe": {"label": "Cafe", "count_500": 0, "count_1000": 0,
                 "nearest_m": None, "nearest_name": None},
    },
}
CFG = llm.LlmConfig(provider="groq", model="test-model",
                    base_url="https://api.example/v1", api_key="secret-key")


def completion(text="A short summary.", finish="stop"):
    msg = SimpleNamespace(content=text)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)])


def api_error(cls, status, headers=None):
    req = httpx.Request("POST", "https://api.example/v1/chat/completions")
    resp = httpx.Response(status, request=req, headers=headers or {})
    return cls("error", response=resp, body=None)


def client_with(*outcomes):
    client = mock.Mock()
    client.chat.completions.create.side_effect = list(outcomes)
    return client


class ConfigTest(unittest.TestCase):
    def test_missing_key_gives_clear_error(self):
        with self.assertRaises(llm.LlmConfigError) as ctx:
            llm.load_config({"LLM_PROVIDER": "groq"})
        self.assertIn("LLM_API_KEY", str(ctx.exception))
        self.assertIn(".env", str(ctx.exception))

    def test_groq_defaults_and_env_override(self):
        cfg = llm.load_config({"LLM_API_KEY": "k"})
        self.assertEqual(cfg.base_url, "https://api.groq.com/openai/v1")
        cfg = llm.load_config({"LLM_API_KEY": "k", "LLM_PROVIDER": "openrouter",
                               "LLM_MODEL": "m", "LLM_BASE_URL": "https://openrouter.ai/api/v1"})
        self.assertEqual((cfg.provider, cfg.model), ("openrouter", "m"))

    def test_unknown_provider_needs_model_and_url(self):
        with self.assertRaises(llm.LlmConfigError):
            llm.load_config({"LLM_API_KEY": "k", "LLM_PROVIDER": "other"})

    def test_key_not_in_repr(self):
        self.assertNotIn("secret-key", repr(CFG))


class PromptTest(unittest.TestCase):
    def test_table_contains_only_report_facts(self):
        table = llm.prompt_table(SUMMARY)
        dumped = json.dumps(table)
        for leaked in ("36.2018", "32635", "3.44.15", "2026-11-11"):
            self.assertNotIn(leaked, dumped)
        self.assertIn("Kucuk Cakil Plaji", dumped)
        self.assertEqual(table["distance_type"], "straight-line")

    def test_unnamed_placeholder_becomes_null(self):
        summary = {"categories": {
            "bus_stop": {"label": "Bus stop", "count_500": 1, "count_1000": 1,
                         "nearest_m": 90, "nearest_name": "Unnamed bus stop"},
            "cafe": {"label": "Cafe", "count_500": 1, "count_1000": 1,
                     "nearest_m": 20, "nearest_name": "Kaptan Pide"}}}
        names = [c["nearest_name"] for c in llm.prompt_table(summary)["categories"]]
        self.assertEqual(names, [None, "Kaptan Pide"])

    def test_system_prompt_rules(self):
        msgs = llm.build_messages(llm.prompt_table(SUMMARY))
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("ONLY", msgs[0]["content"])
        self.assertIn("English", msgs[0]["content"])


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.sleep = mock.patch.object(llm.time, "sleep")
        self.sleep_mock = self.sleep.start()

    def tearDown(self):
        self.sleep.stop()

    def test_success_uses_low_temperature(self):
        client = client_with(completion("  Two cafes   nearby. "))
        text = llm.summarize(llm.prompt_table(SUMMARY), CFG, client=client)
        self.assertEqual(text, "Two cafes nearby.")
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "test-model")
        self.assertLessEqual(kwargs["temperature"], 0.3)

    def test_429_retries_with_backoff_then_succeeds(self):
        client = client_with(api_error(openai.RateLimitError, 429),
                             api_error(openai.RateLimitError, 429, {"retry-after": "3"}),
                             completion())
        self.assertEqual(llm.summarize({}, CFG, client=client), "A short summary.")
        self.assertEqual(client.chat.completions.create.call_count, 3)
        waits = [c.args[0] for c in self.sleep_mock.call_args_list]
        self.assertEqual(waits, [2.0, 3.0])  # exponential, then Retry-After header

    def test_429_gives_up_after_max_attempts(self):
        client = client_with(*[api_error(openai.RateLimitError, 429)] * llm.MAX_ATTEMPTS)
        with self.assertRaises(llm.LlmError):
            llm.summarize({}, CFG, client=client)
        self.assertEqual(client.chat.completions.create.call_count, llm.MAX_ATTEMPTS)

    def test_auth_error_is_not_retried(self):
        client = client_with(api_error(openai.AuthenticationError, 401))
        with self.assertRaises(llm.LlmError) as ctx:
            llm.summarize({}, CFG, client=client)
        self.assertIn("LLM_API_KEY", str(ctx.exception))
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_long_summary_is_kept_with_warning(self):
        long_text = "word " * (llm.MAX_WORDS + 5)
        with self.assertLogs(llm.log, "WARNING") as logs:
            text = llm.summarize({}, CFG, client=client_with(completion(long_text)))
        self.assertEqual(len(text.split()), llm.MAX_WORDS + 5)
        self.assertIn("limit", logs.output[0])

    def test_empty_or_truncated_output_is_an_error(self):
        for resp in (completion(""), completion(None), completion("Cut off mid", "length")):
            with self.subTest(resp=resp), self.assertRaises(llm.LlmError):
                llm.summarize({}, CFG, client=client_with(resp))


class TrySummarizeTest(unittest.TestCase):
    def test_missing_config_falls_back_to_unavailable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = llm.try_summarize(SUMMARY)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["text"], llm.UNAVAILABLE_TEXT)
        self.assertIn("LLM_API_KEY", result["error"])

    def test_api_failure_falls_back_to_unavailable(self):
        env = {"LLM_API_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(llm, "_client", return_value=client_with(
                    api_error(openai.APIStatusError, 500))):
            result = llm.try_summarize(SUMMARY)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("500", result["error"])

    def test_success(self):
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "k"}, clear=True), \
                mock.patch.object(llm, "_client", return_value=client_with(completion("Fine."))):
            result = llm.try_summarize(SUMMARY)
        self.assertEqual((result["status"], result["text"]), ("ok", "Fine."))
        self.assertEqual(result["model"], "openai/gpt-oss-120b")


if __name__ == "__main__":
    unittest.main()
