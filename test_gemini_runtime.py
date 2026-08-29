"""Focused regression tests for Gemini model selection and Copywriter failure handling."""

import unittest
from unittest.mock import patch

import generator
from agents.base import PRIMARY_GEMINI_MODEL, get_gemini_model_chain
from agents.copywriter_agent import CopywriterAgent, CopywriterGenerationError
from agents.editorial_agent import EditorialAgent


class ProviderError(RuntimeError):
    pass


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append(model)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return type("Response", (), {"text": outcome})()


class FakeClient:
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)


class TestGeminiRuntime(unittest.TestCase):
    def test_36_flash_is_primary_and_retired_models_are_not_in_chain(self):
        self.assertEqual(PRIMARY_GEMINI_MODEL, "gemini-3.6-flash")
        self.assertEqual(get_gemini_model_chain(), ["gemini-3.6-flash", "gemini-3.5-flash"])
        self.assertEqual(EditorialAgent(client=object()).model_name, "gemini-3.6-flash")
        chain = get_gemini_model_chain()
        self.assertFalse(any(model.startswith("gemini-2.") for model in chain))

    def test_transient_503_retries_then_falls_back_to_35(self):
        client = FakeClient([
            ProviderError("503 high demand"),
            ProviderError("503 high demand"),
            "generated draft",
        ])
        agent = CopywriterAgent(client=client)
        with patch("agents.base.time.sleep") as sleep:
            result = agent.run_llm("draft")

        self.assertEqual(result, "generated draft")
        self.assertEqual(client.models.calls, ["gemini-3.6-flash", "gemini-3.6-flash", "gemini-3.5-flash"])
        self.assertEqual(sleep.call_count, 1)

    def test_copywriter_provider_failure_stops_before_qa(self):
        client = FakeClient([
            ProviderError("404 model unavailable"),
            ProviderError("404 model unavailable"),
        ])
        evaluation = {
            "client": client,
            "model_name": "gemini-3.6-flash",
            "best_candidate": {
                "title": "Dental maintenance",
                "source": "Journal",
                "date": "2026-08-29",
                "summary": "Summary",
                "full_text": "Source text",
            },
        }
        with patch("generator.QAAgent") as qa_agent:
            with self.assertRaises(CopywriterGenerationError):
                generator.generate_blog_post_from_evaluation(evaluation)

        self.assertEqual(client.models.calls, ["gemini-3.6-flash", "gemini-3.5-flash"])
        qa_agent.return_value.validate_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
