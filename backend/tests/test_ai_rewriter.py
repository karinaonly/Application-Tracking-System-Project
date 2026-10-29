import json
import unittest
from unittest.mock import MagicMock, patch

from app.analyzer.ai_rewriter import AIRewriter, MAX_BULLETS_PER_CALL


def make_rewriter_with_fake_client(responses=None, raise_exc=None, provider="openai"):
    """Build an AIRewriter with no real network: __init__ still runs (settings-based),
    but we swap in a MagicMock for .client so no HTTP call is ever made."""
    r = AIRewriter.__new__(AIRewriter)  # skip __init__ -> skip settings/env entirely
    r.provider = provider
    r.model = "test-model"
    fake_client = MagicMock()
    if raise_exc:
        fake_client.chat.completions.create.side_effect = raise_exc
    elif isinstance(responses, list):
        completions = []
        for response in responses:
            if isinstance(response, Exception):
                completions.append(response)
                continue
            msg = MagicMock()
            msg.content = response
            choice = MagicMock()
            choice.message = msg
            completion = MagicMock()
            completion.choices = [choice]
            completions.append(completion)
        fake_client.chat.completions.create.side_effect = completions
    else:
        msg = MagicMock()
        msg.content = responses
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        fake_client.chat.completions.create.return_value = completion
    r.client = fake_client
    return r, fake_client


class NoClientFallbackTests(unittest.TestCase):
    def test_no_client_returns_bullets_unchanged(self):
        r = AIRewriter.__new__(AIRewriter)
        r.provider = "groq"
        r.model = "x"
        r.client = None
        result = r.rewrite_bullets(["Helped with stuff", "Did things"])
        self.assertEqual(result["Helped with stuff"]["ai_output"], "Helped with stuff")
        self.assertEqual(result["Helped with stuff"]["source"], "fallback")
        self.assertEqual(result["Did things"]["source"], "fallback")

    def test_empty_input_returns_empty_dict(self):
        r = AIRewriter.__new__(AIRewriter)
        r.provider = "groq"
        r.client = None
        self.assertEqual(r.rewrite_bullets([]), {})
        self.assertEqual(r.rewrite_bullets(["", "   "]), {})


class SuccessfulRewriteTests(unittest.TestCase):
    def test_retry_count_is_zero(self):
        bad = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Built API pipelines"}])
        r, fake_client = make_rewriter_with_fake_client(responses=bad)
        with patch("app.analyzer.ai_rewriter.MAX_GUARD_RETRIES", 0):
            result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)
        self.assertEqual(result["ai_output"], "Built API")
        self.assertEqual(result["guard"], {"status": "rejected", "reasons": ["claim_word"], "retried": False, "rejected_variants": ["moderate", "aggressive"]})
        self.assertEqual(result["source"], "guard_rejected")

    def test_two_retries_can_reach_clean_result(self):
        bad = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Built API pipelines"}])
        good = json.dumps([{"moderate": "Developed API", "aggressive": "Developed API"}])
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, bad, good])
        with patch("app.analyzer.ai_rewriter.MAX_GUARD_RETRIES", 2):
            result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(fake_client.chat.completions.create.call_count, 3)
        self.assertEqual(result["guard"]["status"], "retried_passed")
        self.assertEqual(result["ai_output"], "Developed API")

    def test_retry_failure_keeps_variant_that_passed_first(self):
        first = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Developed API"}])
        r, fake_client = make_rewriter_with_fake_client(responses=[first, RuntimeError("timeout")])
        with patch("app.analyzer.ai_rewriter.MAX_GUARD_RETRIES", 2):
            result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["ai_output"], "Built API")
        self.assertEqual(result["aggressive"], "Developed API")
        self.assertEqual(result["guard"]["status"], "retry_failed")
        self.assertEqual(result["guard"]["rejected_variants"], ["moderate"])
        self.assertEqual(result["source"], "openai")
        self.assertIn("claim_word", result["guard"]["reasons"])
        self.assertIn("timeout", result["error"])

    def test_retry_failure_withholds_both_variants(self):
        bad = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Built API pipelines"}])
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, RuntimeError("timeout")])
        with patch("app.analyzer.ai_rewriter.MAX_GUARD_RETRIES", 2):
            result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["guard"]["status"], "retry_failed")
        self.assertEqual(result["guard"]["rejected_variants"], ["moderate", "aggressive"])
        self.assertEqual(result["source"], "guard_rejected")

    def test_identical_model_result_can_pass(self):
        response = json.dumps([{"moderate": "Built API", "aggressive": "Built API"}])
        r, fake_client = make_rewriter_with_fake_client(responses=response)
        result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)
        self.assertEqual(result["guard"]["status"], "passed")

    def test_every_clean_result_has_complete_guard_metadata(self):
        response = json.dumps([{"moderate": "Built API", "aggressive": "Built API"}])
        r, _ = make_rewriter_with_fake_client(responses=response)
        result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(set(result["guard"]), {"status", "reasons", "retried", "rejected_variants"})

    def test_two_bad_retries_remain_rejected(self):
        bad = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Built API pipelines"}])
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, bad, bad])
        with patch("app.analyzer.ai_rewriter.MAX_GUARD_RETRIES", 2):
            result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(fake_client.chat.completions.create.call_count, 3)
        self.assertEqual(result["guard"]["status"], "rejected")

    def test_first_call_exception_is_ai_error(self):
        r, fake_client = make_rewriter_with_fake_client(responses=[RuntimeError("service down")])
        result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)
        self.assertEqual(result["guard"]["status"], "ai_error")
        self.assertEqual(result["source"], "fallback")
        self.assertIn("service down", result["error"])

    def test_no_client_is_skipped(self):
        r = AIRewriter.__new__(AIRewriter)
        r.provider = "openai"
        r.client = None
        result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(result["guard"]["status"], "skipped")
        self.assertEqual(result["source"], "fallback")

    def test_partial_retry_keeps_first_passing_variant(self):
        first = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Developed API"}])
        retry = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Built API pipelines"}])
        r, _ = make_rewriter_with_fake_client(responses=[first, retry])
        with patch("app.analyzer.ai_rewriter.MAX_GUARD_RETRIES", 1):
            result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(result["ai_output"], "Built API")
        self.assertEqual(result["aggressive"], "Developed API")
        self.assertEqual(result["guard"]["status"], "partially_rejected")
        self.assertEqual(result["guard"]["rejected_variants"], ["moderate"])

    def test_retry_can_pass_moderate_while_withholding_aggressive(self):
        bad = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Built API pipelines"}])
        retry = json.dumps([{"moderate": "Developed API", "aggressive": "Built API pipelines"}])
        r, _ = make_rewriter_with_fake_client(responses=[bad, retry])
        with patch("app.analyzer.ai_rewriter.MAX_GUARD_RETRIES", 1):
            result = r.rewrite_bullets(["Built API"])["Built API"]
        self.assertEqual(result["moderate"], "Developed API")
        self.assertEqual(result["aggressive"], "Built API")
        self.assertEqual(result["guard"]["status"], "partially_rejected")
        self.assertEqual(result["guard"]["rejected_variants"], ["aggressive"])

    def test_original_bracketed_text_is_allowed(self):
        original = "Built the [Capstone] exam platform"
        response = json.dumps([{"moderate": "Developed the [Capstone] exam platform", "aggressive": "Developed the [Capstone] exam platform"}])
        r, fake_client = make_rewriter_with_fake_client(responses=response)
        result = r.rewrite_bullets([original])[original]
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)
        self.assertEqual(result["guard"]["status"], "passed")
        self.assertEqual(result["ai_output"], "Developed the [Capstone] exam platform")
    def test_invalid_bullet_is_retried_without_disturbing_clean_bullet(self):
        first = json.dumps([
            {"moderate": "Built API pipelines", "aggressive": "Built API pipelines"},
            {"moderate": "Improved billing workflows", "aggressive": "Improved billing workflows"},
        ])
        retry = json.dumps([
            {"moderate": "Developed API", "aggressive": "Developed API"},
        ])
        r, fake_client = make_rewriter_with_fake_client(responses=[first, retry])
        result = r.rewrite_bullets(["Built API", "Managed billing"])

        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["Built API"]["guard"]["status"], "retried_passed")
        self.assertEqual(result["Managed billing"]["guard"]["status"], "passed")
        retry_prompt = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"][1]["content"]
        self.assertIn("pipeline", retry_prompt)
        self.assertIn("Built API", retry_prompt)

    def test_still_invalid_retry_preserves_original_and_other_bullet(self):
        first = json.dumps([
            {"moderate": "Built API pipelines", "aggressive": "Built API pipelines"},
            {"moderate": "Improved billing", "aggressive": "Improved billing"},
        ])
        retry = json.dumps([
            {"moderate": "Built API pipelines", "aggressive": "Built API pipelines"},
        ])
        r, fake_client = make_rewriter_with_fake_client(responses=[first, retry])
        result = r.rewrite_bullets(["Built API", "Managed billing"])

        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["Built API"]["ai_output"], "Built API")
        self.assertIn(result["Built API"]["guard"]["status"], ("rejected", "partially_rejected"))
        self.assertEqual(result["Managed billing"]["moderate"], "Improved billing")

    def test_clean_response_uses_one_call_and_passed_guards(self):
        r, fake_client = make_rewriter_with_fake_client(responses=json.dumps([
            {"moderate": "Built API", "aggressive": "Developed API"},
            {"moderate": "Improved billing", "aggressive": "Improved billing"},
        ]))
        result = r.rewrite_bullets(["Built API", "Managed billing"])
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)
        self.assertTrue(all(item["guard"]["status"] == "passed" for item in result.values()))

    def test_moderate_rejected_does_not_promote_aggressive(self):
        first = json.dumps([
            {"moderate": "Built a REST API with Python and Docker", "aggressive": "Developed a REST API with Python"},
        ])
        retry = json.dumps([
            {"moderate": "Built a REST API with Python and Docker", "aggressive": "Developed a REST API with Python"},
        ])
        r, _ = make_rewriter_with_fake_client(responses=[first, retry])
        result = r.rewrite_bullets(["Built a REST API with Python"])["Built a REST API with Python"]
        self.assertEqual(result["ai_output"], "Built a REST API with Python")
        self.assertEqual(result["moderate"], "Built a REST API with Python")
        self.assertEqual(result["aggressive"], "Developed a REST API with Python")
        self.assertEqual(result["guard"]["status"], "partially_rejected")

    def test_batched_single_call_for_multiple_bullets(self):
        bullets = ["Helped the team migrate services", "Responsible for the billing module"]
        fake_json = json.dumps([
            {"moderate": "Supported migration of core services", "aggressive": "Assisted migration of core services",
             "keywords_used": ["migration"], "has_placeholder": False},
            {"moderate": "Managed the billing module", "aggressive": "Owned the billing module end-to-end",
             "keywords_used": [], "has_placeholder": False},
        ])
        r, fake_client = make_rewriter_with_fake_client(responses=fake_json)
        result = r.rewrite_bullets(bullets, target_role="Backend Dev")

        # Exactly ONE API call for both bullets (the whole point of batching)
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)

        self.assertEqual(result[bullets[0]]["ai_output"], "Supported migration of core services")
        self.assertEqual(result[bullets[0]]["moderate"], "Supported migration of core services")
        self.assertEqual(result[bullets[0]]["aggressive"], "Assisted migration of core services")
        self.assertEqual(result[bullets[0]]["source"], "openai")
        self.assertEqual(result[bullets[1]]["ai_output"], "Managed the billing module")

    def test_guard_never_makes_more_than_two_calls(self):
        invalid = json.dumps([{"moderate": "Built API pipelines", "aggressive": "Built API pipelines"}])
        r, fake_client = make_rewriter_with_fake_client(responses=[invalid, invalid])
        r.rewrite_bullets(["Built API"])
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)

    def test_ai_output_key_present_for_exporter_compatibility(self):
        # docx_exporter.py reads opt["ai_output"] directly -- this key must always exist on success.
        r, _ = make_rewriter_with_fake_client(responses=json.dumps(
            [{"moderate": "Built the thing", "aggressive": "Engineered the thing"}]
        ))
        result = r.rewrite_bullets(["original bullet"])
        self.assertIn("ai_output", result["original bullet"])
        self.assertEqual(result["original bullet"]["ai_output"], result["original bullet"]["moderate"])

    def test_unrenderable_hyphen_glyphs_are_normalized_to_ascii(self):
        # Real-resume bug: Groq emitted U+2011 non-breaking hyphens, which
        # render as tofu boxes (□) in the exported DOCX.
        r, _ = make_rewriter_with_fake_client(responses=json.dumps(
            [{
                "moderate": "Led end\u2011to\u2011end development of a web\u2011based platform",
                "aggressive": "Spearheaded full\u2010cycle delivery",
            }]
        ))
        result = r.rewrite_bullets(["Led end-to-end development"])
        out = result["Led end-to-end development"]
        self.assertEqual(out["ai_output"], "Led end-to-end development of a web-based platform")
        self.assertEqual(out["aggressive"], "Spearheaded full-cycle delivery")

    def test_aggressive_falls_back_to_moderate_if_missing(self):
        r, _ = make_rewriter_with_fake_client(responses=json.dumps(
            [{"moderate": "Built the thing"}]
        ))
        result = r.rewrite_bullets(["x"])
        self.assertEqual(result["x"]["aggressive"], "Built the thing")

    def test_markdown_fenced_json_is_parsed(self):
        fenced = "```json\n" + json.dumps([{"moderate": "Did a thing well"}]) + "\n```"
        r, _ = make_rewriter_with_fake_client(responses=fenced)
        result = r.rewrite_bullets(["x"])
        self.assertEqual(result["x"]["ai_output"], "Did a thing well")

    def test_object_wrapped_array_is_tolerated(self):
        wrapped = json.dumps({"results": [{"moderate": "Did a thing well"}]})
        r, _ = make_rewriter_with_fake_client(responses=wrapped)
        result = r.rewrite_bullets(["x"])
        self.assertEqual(result["x"]["ai_output"], "Did a thing well")

    def test_placeholder_rewrite_is_rejected_and_original_is_preserved(self):
        r, _ = make_rewriter_with_fake_client(responses=json.dumps(
            [{"moderate": "Reduced load time by [X%]"}]
        ))
        result = r.rewrite_bullets(["x"])
        self.assertEqual(result["x"]["ai_output"], "x")
        self.assertEqual(result["x"]["source"], "guard_rejected")
        self.assertFalse(result["x"]["has_placeholder"])
        self.assertEqual(result["x"]["guard"]["status"], "rejected")

    def test_openai_provider_requests_json_object_format(self):
        r, fake_client = make_rewriter_with_fake_client(
            responses=json.dumps([{"moderate": "ok"}]), provider="openai"
        )
        r.rewrite_bullets(["x"])
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs.get("response_format"), {"type": "json_object"})

    def test_groq_provider_does_not_request_json_object_format(self):
        r, fake_client = make_rewriter_with_fake_client(
            responses=json.dumps([{"moderate": "ok"}]), provider="groq"
        )
        r.rewrite_bullets(["x"])
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("response_format", kwargs)


class RobustnessTests(unittest.TestCase):
    def test_exception_from_api_falls_back_for_all_sent_bullets(self):
        r, _ = make_rewriter_with_fake_client(raise_exc=RuntimeError("network down"))
        result = r.rewrite_bullets(["a", "b"])
        self.assertEqual(result["a"]["ai_output"], "a")
        self.assertEqual(result["a"]["source"], "fallback")
        self.assertIn("network down", result["a"]["error"])
        self.assertEqual(result["b"]["source"], "fallback")

    def test_invalid_json_falls_back_for_all_sent_bullets(self):
        r, _ = make_rewriter_with_fake_client(responses="not json at all, sorry")
        result = r.rewrite_bullets(["a"])
        self.assertEqual(result["a"]["source"], "fallback")
        self.assertIn("error", result["a"])

    def test_short_response_array_falls_back_only_for_missing_entries(self):
        # Model returns rewrites for only 1 of 2 bullets requested
        r, _ = make_rewriter_with_fake_client(responses=json.dumps(
            [{"moderate": "Rewrote first one"}]
        ))
        result = r.rewrite_bullets(["first", "second"])
        self.assertEqual(result["first"]["ai_output"], "Rewrote first one")
        self.assertEqual(result["second"]["source"], "fallback")
        self.assertEqual(result["second"]["ai_output"], "second")

    def test_empty_moderate_string_falls_back_for_that_bullet(self):
        r, _ = make_rewriter_with_fake_client(responses=json.dumps(
            [{"moderate": ""}, {"moderate": "Rewrote second one"}]
        ))
        result = r.rewrite_bullets(["first", "second"])
        self.assertEqual(result["first"]["source"], "fallback")
        self.assertEqual(result["second"]["ai_output"], "Rewrote second one")

    def test_duplicate_bullets_collapse_to_one_entry(self):
        r, fake_client = make_rewriter_with_fake_client(responses=json.dumps(
            [{"moderate": "Rewrote it"}]
        ))
        result = r.rewrite_bullets(["same text", "same text"])
        self.assertEqual(len(result), 1)
        # only ONE copy was actually sent to the model
        sent_prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertEqual(sent_prompt.count("same text"), 1)

    def test_model_not_found_is_logged_with_actionable_cause_and_key_redacted(self):
        secret = "gsk_unit_test_secret_key_1234567890"
        exc = Exception(
            "Error code: 404 - {'error': {'code': 'model_not_found', "
            f"'message': 'The model `gone` does not exist. key={secret}'}}"
        )
        r, _ = make_rewriter_with_fake_client(raise_exc=exc)
        r._api_key = secret

        with self.assertLogs("app.analyzer.ai_rewriter", level="WARNING") as captured:
            result = r.rewrite_bullets(["a"])["a"]

        self.assertEqual(result["source"], "fallback")
        self.assertIn("model not found", result["error"])
        self.assertIn("check AI_MODEL", result["error"])
        joined = "\n".join(captured.output)
        self.assertIn("model not found", joined)
        self.assertNotIn(secret, joined)


class BatchLimitTests(unittest.TestCase):
    def test_bullets_beyond_cap_are_skipped_not_sent(self):
        bullets = [f"bullet {i}" for i in range(MAX_BULLETS_PER_CALL + 3)]
        fake_json = json.dumps([{"moderate": f"rewritten {i}"} for i in range(MAX_BULLETS_PER_CALL)])
        r, fake_client = make_rewriter_with_fake_client(responses=fake_json)
        result = r.rewrite_bullets(bullets)

        sent_prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        for b in bullets[:MAX_BULLETS_PER_CALL]:
            self.assertIn(b, sent_prompt)
        for b in bullets[MAX_BULLETS_PER_CALL:]:
            self.assertNotIn(b, sent_prompt)
            self.assertEqual(result[b]["source"], "skipped_batch_limit")
            self.assertEqual(result[b]["ai_output"], b)  # untouched, not invented


class PromptContentTests(unittest.TestCase):
    def test_system_prompt_forbids_fabricating_metrics_and_tools(self):
        r = AIRewriter.__new__(AIRewriter)
        prompt = r._system_prompt()
        self.assertIn("NEVER invent a number", prompt)
        self.assertIn("NEVER add a tool", prompt)
        self.assertIn("NEVER add a placeholder", prompt)

    def test_system_prompt_instructs_natural_capitalization(self):
        r = AIRewriter.__new__(AIRewriter)
        prompt = r._system_prompt()
        self.assertIn("lowercase", prompt.lower())
        # must call out that technology proper nouns stay capitalized
        self.assertIn("React", prompt)

    def test_missing_keywords_included_in_user_prompt(self):
        r, fake_client = make_rewriter_with_fake_client(responses=json.dumps([{"moderate": "ok"}]))
        r.rewrite_bullets(["x"], target_role="Backend Dev", missing_keywords=["Docker", "CI/CD"])
        sent_prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("Docker", sent_prompt)
        self.assertIn("CI/CD", sent_prompt)
        self.assertIn("Backend Dev", sent_prompt)


class GenerateTextTests(unittest.TestCase):
    """C7: empty content from a reasoning model is retried, real errors are not."""

    def test_empty_content_is_retried_with_a_larger_budget(self):
        r, fake_client = make_rewriter_with_fake_client(responses=["", "hello"])
        text, error = r.generate_text("sys", "user", max_tokens=400)

        self.assertEqual(text, "hello")
        self.assertIsNone(error)
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        caps = [
            call.kwargs["max_tokens"]
            for call in fake_client.chat.completions.create.call_args_list
        ]
        self.assertEqual(caps, [400, 800])

    def test_two_empty_responses_return_an_error(self):
        r, fake_client = make_rewriter_with_fake_client(responses=["", ""])
        text, error = r.generate_text("sys", "user", max_tokens=400)

        self.assertIsNone(text)
        self.assertEqual(error, "empty response from model")
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)

    def test_real_error_is_not_retried(self):
        r, fake_client = make_rewriter_with_fake_client(
            raise_exc=RuntimeError("429 rate limit")
        )
        text, error = r.generate_text("sys", "user", max_tokens=400)

        self.assertIsNone(text)
        self.assertIn("429", error)
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)

    def test_retry_budget_is_capped(self):
        r, fake_client = make_rewriter_with_fake_client(responses=["", "hello"])
        r.generate_text("sys", "user", max_tokens=3000)
        caps = [
            call.kwargs["max_tokens"]
            for call in fake_client.chat.completions.create.call_args_list
        ]
        self.assertEqual(caps, [3000, 4000])


class SummaryRewriteTests(unittest.TestCase):
    """C7: the professional summary is rewritten under the same claim guard."""

    ORIGINAL = "Backend developer who builds APIs with Python."

    def test_clean_summary_passes_in_one_call(self):
        r, fake_client = make_rewriter_with_fake_client(
            responses="Backend developer who builds reliable APIs with Python."
        )
        result = r.rewrite_summary(self.ORIGINAL)

        self.assertEqual(fake_client.chat.completions.create.call_count, 1)
        self.assertEqual(
            result["ai_output"],
            "Backend developer who builds reliable APIs with Python.",
        )
        self.assertEqual(result["source"], "openai")
        self.assertEqual(result["guard"]["status"], "passed")
        self.assertEqual(result["original"], self.ORIGINAL)

    def test_new_number_is_rejected_then_retried(self):
        bad = "Backend developer who builds 12 APIs with Python."
        good = "Backend developer who builds APIs with Python."
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, good])
        result = r.rewrite_summary(self.ORIGINAL)

        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["guard"]["status"], "retried_passed")
        self.assertTrue(result["guard"]["retried"])
        self.assertEqual(result["ai_output"], good)
        retry_prompt = (
            fake_client.chat.completions.create.call_args_list[1]
            .kwargs["messages"][1]["content"]
        )
        self.assertIn("12", retry_prompt)

    def test_two_rejections_withhold_the_suggestion(self):
        bad = "Backend developer who builds APIs with Python and Kubernetes."
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, bad])
        result = r.rewrite_summary(self.ORIGINAL)

        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["ai_output"], self.ORIGINAL)
        self.assertEqual(result["source"], "guard_rejected")
        self.assertEqual(result["guard"]["status"], "rejected")
        self.assertTrue(result["guard"]["reasons"])

    def test_provider_error_returns_original_without_a_suggestion(self):
        r, _ = make_rewriter_with_fake_client(raise_exc=RuntimeError("network down"))
        result = r.rewrite_summary(self.ORIGINAL)

        self.assertEqual(result["ai_output"], self.ORIGINAL)
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["guard"]["status"], "ai_error")
        self.assertIn("network down", result["error"])

    def test_no_client_skips_the_section(self):
        r = AIRewriter.__new__(AIRewriter)
        r.provider = "groq"
        r.model = "x"
        r.client = None

        result = r.rewrite_summary(self.ORIGINAL)
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["guard"]["status"], "skipped")

    def test_empty_summary_is_not_rewritten(self):
        r, fake_client = make_rewriter_with_fake_client(responses="anything")
        self.assertEqual(r.rewrite_summary("   "), {})
        fake_client.chat.completions.create.assert_not_called()


class SkillsRewriteTests(unittest.TestCase):
    """C7: skills may only be regrouped/reordered, never changed."""

    INVENTORY = ["Python", "Docker", "SQL"]

    def test_valid_regrouping_passes(self):
        response = json.dumps({
            "lines": ["Languages: Python, SQL", "Tools: Docker"],
        })
        r, fake_client = make_rewriter_with_fake_client(responses=response)
        result = r.rewrite_skills("Python\nDocker\nSQL", self.INVENTORY)

        self.assertEqual(fake_client.chat.completions.create.call_count, 1)
        self.assertEqual(result["guard"]["status"], "passed")
        self.assertEqual(
            result["lines"], ["Languages: Python, SQL", "Tools: Docker"]
        )
        self.assertEqual(result["ai_output"], "Languages: Python, SQL\nTools: Docker")

    def test_added_skill_is_rejected(self):
        bad = json.dumps({"lines": ["Languages: Python, SQL", "Tools: Docker, Kubernetes"]})
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, bad])
        result = r.rewrite_skills("Python\nDocker\nSQL", self.INVENTORY)

        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["source"], "guard_rejected")
        self.assertEqual(result["guard"]["status"], "rejected")
        self.assertEqual(result["ai_output"], "Python\nDocker\nSQL")
        self.assertTrue(any("Kubernetes" in reason for reason in result["guard"]["reasons"]))

    def test_dropped_skill_is_rejected(self):
        bad = json.dumps({"lines": ["Languages: Python, SQL"]})
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, bad])
        result = r.rewrite_skills("Python\nDocker\nSQL", self.INVENTORY)

        self.assertEqual(result["guard"]["status"], "rejected")
        self.assertTrue(any("Docker" in reason for reason in result["guard"]["reasons"]))

    def test_numbers_and_placeholders_are_rejected(self):
        numbered = json.dumps({"lines": ["Languages: Python, SQL, 3 more"]})
        r, _ = make_rewriter_with_fake_client(responses=[numbered, numbered])
        self.assertEqual(
            r.rewrite_skills("Python\nDocker\nSQL", self.INVENTORY)["guard"]["status"],
            "rejected",
        )

        placeholder = json.dumps({"lines": ["Languages: Python, [Skill]"]})
        r, _ = make_rewriter_with_fake_client(responses=[placeholder, placeholder])
        self.assertEqual(
            r.rewrite_skills("Python\nDocker\nSQL", self.INVENTORY)["guard"]["status"],
            "rejected",
        )

    def test_retry_can_recover(self):
        bad = json.dumps({"lines": ["Languages: Python, SQL", "Tools: Docker, Kubernetes"]})
        good = json.dumps({"lines": ["Tools: Docker", "Languages: Python, SQL"]})
        r, fake_client = make_rewriter_with_fake_client(responses=[bad, good])
        result = r.rewrite_skills("Python\nDocker\nSQL", self.INVENTORY)

        self.assertEqual(fake_client.chat.completions.create.call_count, 2)
        self.assertEqual(result["guard"]["status"], "retried_passed")
        self.assertEqual(result["lines"], ["Tools: Docker", "Languages: Python, SQL"])

    def test_plain_text_lines_are_accepted_as_a_fallback_shape(self):
        r, _ = make_rewriter_with_fake_client(
            responses="Languages: Python, SQL\nTools: Docker"
        )
        result = r.rewrite_skills("Python\nDocker\nSQL", self.INVENTORY)
        self.assertEqual(result["lines"], ["Languages: Python, SQL", "Tools: Docker"])

    def test_skill_names_with_versions_are_allowed(self):
        inventory = ["Python 3", "S3", "Docker"]
        response = json.dumps({
            "lines": ["Languages: Python 3, S3", "Tools: Docker"],
        })
        r, _ = make_rewriter_with_fake_client(responses=response)
        result = r.rewrite_skills("Python 3\nS3\nDocker", inventory)
        self.assertEqual(result["guard"]["status"], "passed")

    def test_no_parsed_skills_means_nothing_to_rewrite(self):
        r, fake_client = make_rewriter_with_fake_client(responses="anything")
        self.assertEqual(r.rewrite_skills("", []), {})
        fake_client.chat.completions.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
