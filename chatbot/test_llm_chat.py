"""Tests for the LLM Step Helper chatbot."""

import unittest
from unittest.mock import patch, MagicMock
from chatbot.llm_chat import (
    LLMStepHelper, llm_response, llm_response_stream,
    _referenced_step_numbers, _extract_step_blocks,
)


SAMPLE_STEPS_HTML = """
<ol class="steps">
    <li class="step collapsible" data-step="1">
        <h3>Apply the power rule</h3>
        <p>\\(\\frac{d}{dx} x^5 = 5 x^4\\)</p>
    </li>
    <li class="step collapsible" data-step="2">
        <h3>Multiply by the coefficient</h3>
        <p>The 5 stays in front.</p>
        <ol class="steps steps--nested">
            <li class="step" data-step="2.1">
                <p>Substep content</p>
            </li>
        </ol>
    </li>
    <li class="step collapsible" data-step="3">
        <h3>Simplify</h3>
        <p>Final answer: \\(5 x^4\\).</p>
    </li>
</ol>
"""


class TestStepReferenceParsing(unittest.TestCase):
    """Tests for parsing step numbers out of user messages."""

    def test_explicit_step_number(self):
        self.assertEqual(_referenced_step_numbers("explain step 2"), [2])
        self.assertEqual(_referenced_step_numbers("STEP 3 please"), [3])
        self.assertEqual(_referenced_step_numbers("how did you get step2?"), [2])

    def test_multiple_step_numbers(self):
        self.assertEqual(
            _referenced_step_numbers("walk me through step 1 and step 3"),
            [1, 3],
        )
        self.assertEqual(
            _referenced_step_numbers("steps 2, 3, and 4 please"),
            [2, 3, 4],
        )

    def test_ordinals(self):
        self.assertEqual(_referenced_step_numbers("the first step"), [1])
        self.assertEqual(_referenced_step_numbers("explain the third step"), [3])

    def test_numeric_ordinals_unlimited(self):
        """Numeric ordinals work for any step number, not just 1-10."""
        self.assertEqual(_referenced_step_numbers("the 11th step"), [11])
        self.assertEqual(_referenced_step_numbers("explain the 56th step"), [56])
        self.assertEqual(_referenced_step_numbers("the 100th step"), [100])

    def test_large_step_numbers(self):
        """Plain 'step N' works for arbitrarily large N."""
        self.assertEqual(_referenced_step_numbers("step 56"), [56])
        self.assertEqual(_referenced_step_numbers("step 123"), [123])

    def test_ambiguous_returns_empty(self):
        self.assertEqual(_referenced_step_numbers("this step"), [])
        self.assertEqual(_referenced_step_numbers("the next step"), [])
        self.assertEqual(_referenced_step_numbers("what is the power rule?"), [])


class TestExtractStepBlocks(unittest.TestCase):
    """Tests for extracting per-step HTML chunks from the rendered steps."""

    def test_extracts_top_level_steps(self):
        blocks = _extract_step_blocks(SAMPLE_STEPS_HTML)
        self.assertIn(1, blocks)
        self.assertIn(2, blocks)
        self.assertIn(3, blocks)
        self.assertIn("Apply the power rule", blocks[1])
        self.assertIn("Multiply by the coefficient", blocks[2])
        self.assertIn("Simplify", blocks[3])

    def test_step_2_includes_its_nested_substep(self):
        """A step's block should contain its nested substeps, not be truncated."""
        blocks = _extract_step_blocks(SAMPLE_STEPS_HTML)
        self.assertIn("Substep content", blocks[2])

    def test_step_3_not_polluted_by_step_2_nesting(self):
        """Step 3's block should NOT contain step 2's content despite nesting."""
        blocks = _extract_step_blocks(SAMPLE_STEPS_HTML)
        self.assertNotIn("Multiply by the coefficient", blocks[3])
        self.assertNotIn("Substep content", blocks[3])

    def test_empty_html(self):
        self.assertEqual(_extract_step_blocks(""), {})
        self.assertEqual(_extract_step_blocks(None), {})


class TestLLMStepHelper(unittest.TestCase):
    """Tests for the LLMStepHelper class."""

    def setUp(self):
        self.helper = LLMStepHelper(api_key='test-key')

    def test_is_calculus_related_with_keywords(self):
        helper = self.helper

        self.assertTrue(helper._is_calculus_related("What is a derivative?"))
        self.assertTrue(helper._is_calculus_related("How do I integrate this?"))
        self.assertTrue(helper._is_calculus_related("Explain the power rule"))
        self.assertTrue(helper._is_calculus_related("What is limit of sin(x)/x?"))

        self.assertFalse(helper._is_calculus_related("What's the weather today?"))
        self.assertFalse(helper._is_calculus_related("Tell me a joke"))
        self.assertFalse(helper._is_calculus_related("Hello"))

    def test_is_calculus_related_with_steps_context(self):
        helper = self.helper

        self.assertFalse(helper._is_calculus_related("What does this mean?", has_steps=False))

        self.assertTrue(helper._is_calculus_related("What does this mean?", has_steps=True))
        self.assertTrue(helper._is_calculus_related("Why did we do that step?", has_steps=True))
        self.assertTrue(helper._is_calculus_related("I don't understand step 2", has_steps=True))

    def test_get_response_non_calculus(self):
        response = self.helper.get_response("What's your favorite color?")
        self.assertIn("calculus", response.lower())
        self.assertIn("derivatives", response.lower())

    @patch('chatbot.llm_chat.requests.post')
    def test_get_response_no_step_reference_skips_steps_context(self, mock_post):
        """When no step is referenced, the prompt must NOT include steps or problem."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Brief answer."}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = self.helper.get_response(
            "What is the chain rule?",
            steps_html=SAMPLE_STEPS_HTML,
            problem="diff(sin(x^2), x)",
        )

        self.assertEqual(response, "Brief answer.")
        mock_post.assert_called_once()

        sent = mock_post.call_args.kwargs['json']['messages']
        # First system msg is the prompt itself. There should be NO additional
        # system messages containing steps or problem context.
        for m in sent:
            if m['role'] == 'system':
                self.assertNotIn('Apply the power rule', m['content'])
                self.assertNotIn('diff(sin', m['content'])

    @patch('chatbot.llm_chat.requests.post')
    def test_get_response_single_step_reference(self, mock_post):
        """One step referenced -> one LLM call with that step + problem."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Step 2 explanation."}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = self.helper.get_response(
            "Explain step 2",
            steps_html=SAMPLE_STEPS_HTML,
            problem="diff(x^5, x)",
        )

        self.assertIn("Step 2 explanation.", response)
        self.assertIn("**Step 2**", response)
        self.assertEqual(mock_post.call_count, 1)

        sent = mock_post.call_args.kwargs['json']['messages']
        system_content = '\n'.join(m['content'] for m in sent if m['role'] == 'system')
        self.assertIn("diff(x^5, x)", system_content)
        self.assertIn("Step 2", system_content)
        self.assertIn("Multiply by the coefficient", system_content)
        # Should NOT include step 1 or step 3 content.
        self.assertNotIn("Apply the power rule", system_content)
        self.assertNotIn("Final answer", system_content)

    @patch('chatbot.llm_chat.requests.post')
    def test_get_response_multiple_step_references_makes_multiple_calls(self, mock_post):
        """N steps referenced -> N separate LLM calls, answers concatenated."""
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {"choices": [{"message": {"content": "Step 1 answer."}}]},
            {"choices": [{"message": {"content": "Step 3 answer."}}]},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = self.helper.get_response(
            "Walk me through step 1 and step 3",
            steps_html=SAMPLE_STEPS_HTML,
            problem="diff(x^5, x)",
        )

        self.assertEqual(mock_post.call_count, 2)
        self.assertIn("**Step 1**", response)
        self.assertIn("Step 1 answer.", response)
        self.assertIn("**Step 3**", response)
        self.assertIn("Step 3 answer.", response)

    @patch('chatbot.llm_chat.requests.post')
    def test_step_reference_with_no_matching_block_falls_back(self, mock_post):
        """Referencing a step that doesn't exist -> single simple call, no context."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Plain answer."}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = self.helper.get_response(
            "Explain step 99",
            steps_html=SAMPLE_STEPS_HTML,
            problem="diff(x^5, x)",
        )

        self.assertEqual(response, "Plain answer.")
        self.assertEqual(mock_post.call_count, 1)

        sent = mock_post.call_args.kwargs['json']['messages']
        system_content = '\n'.join(m['content'] for m in sent if m['role'] == 'system')
        self.assertNotIn("diff(x^5, x)", system_content)
        self.assertNotIn("Apply the power rule", system_content)

    def test_format_steps_context(self):
        helper = self.helper

        html = """
        <div class="step">
            <h3>Apply power rule</h3>
            <ul>
                <li>First item</li>
                <li>Second item</li>
            </ul>
        </div>
        """

        text = helper._format_steps_context(html)

        self.assertIn("Apply power rule", text)
        self.assertIn("First item", text)
        self.assertIn("Second item", text)
        self.assertNotIn("<div>", text)
        self.assertNotIn("<h3>", text)

    @patch('chatbot.llm_chat.requests.post')
    def test_conversation_history(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        history = [
            {"role": "user", "content": "What is a derivative?"},
            {"role": "assistant", "content": "A derivative measures rate of change."},
        ]

        self.helper.get_response(
            "Can you explain the power rule?",
            conversation_history=history,
        )

        sent = mock_post.call_args.kwargs['json']['messages']
        user_messages = [m for m in sent if m['role'] == 'user']
        self.assertGreaterEqual(len(user_messages), 2)


class TestLLMResponseFunction(unittest.TestCase):
    """Tests for the llm_response convenience function."""

    @patch('chatbot.llm_chat.get_llm_helper')
    def test_llm_response_with_helper(self, mock_get_helper):
        mock_helper = MagicMock()
        mock_helper.get_response.return_value = "Test response"
        mock_get_helper.return_value = mock_helper

        response = llm_response(
            "What is a derivative?",
            steps_html="<div>steps</div>",
            problem="diff(x, x)",
        )

        mock_helper.get_response.assert_called_once_with(
            "What is a derivative?",
            "<div>steps</div>",
            "diff(x, x)",
            None,
        )
        self.assertEqual(response, "Test response")


class TestStreamingResponse(unittest.TestCase):
    """Tests for the streaming response API.

    The streaming API yields one event per step (or a single answer event for
    non-step questions), then a terminating 'done' event. Each step event is
    emitted as its own LLM call finishes, so the frontend can render
    progressively instead of waiting for all steps.
    """

    def setUp(self):
        self.helper = LLMStepHelper(api_key='test-key')

    def test_stream_non_calculus_yields_redirect(self):
        events = list(self.helper.get_response_stream("What's the weather?"))
        self.assertEqual(events[-1], {'type': 'done'})
        self.assertEqual(events[0]['type'], 'answer')
        self.assertIn('calculus', events[0]['text'].lower())

    @patch('chatbot.llm_chat.requests.post')
    def test_stream_no_step_reference_yields_single_answer(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Chain rule answer."}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        events = list(self.helper.get_response_stream("What is the chain rule?"))

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], {'type': 'answer', 'text': 'Chain rule answer.'})
        self.assertEqual(events[1], {'type': 'done'})

    @patch('chatbot.llm_chat.requests.post')
    def test_stream_multiple_steps_yields_one_event_per_step(self, mock_post):
        """Each step's answer is yielded as that step's LLM call finishes."""
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {"choices": [{"message": {"content": "Step 1 answer."}}]},
            {"choices": [{"message": {"content": "Step 3 answer."}}]},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        events = list(self.helper.get_response_stream(
            "Walk me through step 1 and step 3",
            steps_html=SAMPLE_STEPS_HTML,
            problem="diff(x^5, x)",
        ))

        step_events = [e for e in events if e['type'] == 'step']
        self.assertEqual(len(step_events), 2)
        self.assertEqual(step_events[0], {'type': 'step', 'step': 1, 'text': 'Step 1 answer.'})
        self.assertEqual(step_events[1], {'type': 'step', 'step': 3, 'text': 'Step 3 answer.'})
        self.assertEqual(events[-1], {'type': 'done'})

    @patch('chatbot.llm_chat.requests.post')
    def test_multi_step_scoping_drops_history_and_rewrites_message(self, mock_post):
        """Per-step calls must NOT include conversation history and must use a
        question scoped to that single step."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        history = [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
        ]

        list(self.helper.get_response_stream(
            "how did you get step 1 and step 3?",
            steps_html=SAMPLE_STEPS_HTML,
            problem="diff(x^5, x)",
            conversation_history=history,
        ))

        for call in mock_post.call_args_list:
            messages = call.kwargs['json']['messages']
            # History assistant messages must not leak into per-step calls.
            roles_contents = [(m['role'], m['content']) for m in messages]
            self.assertNotIn(('assistant', 'earlier answer'), roles_contents)
            self.assertNotIn(('user', 'earlier question'), roles_contents)
            # The user-facing message should be the scoped rewrite, not the
            # original "step 1 and step 3" wording verbatim as the question.
            user_msgs = [m['content'] for m in messages if m['role'] == 'user']
            self.assertEqual(len(user_msgs), 1)
            self.assertIn('Step', user_msgs[0])  # scoped to a specific step
            self.assertIn('ONLY', user_msgs[0])

    @patch('chatbot.llm_chat.requests.post')
    def test_html_to_text_strips_step_hint(self, mock_post):
        """The 'Click to show step' UI hint must not be sent to the LLM."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        steps_with_hint = (
            '<ol class="steps">'
            '<li class="step collapsible" data-step="1">'
            '<span class="step__hint" aria-hidden="true">Click to show step</span>'
            '<p>Apply the rule</p>'
            '</li>'
            '</ol>'
        )

        list(self.helper.get_response_stream(
            "explain step 1",
            steps_html=steps_with_hint,
        ))

        all_content = '\n'.join(
            m['content']
            for call in mock_post.call_args_list
            for m in call.kwargs['json']['messages']
        )
        self.assertNotIn('Click to show step', all_content)
        self.assertIn('Apply the rule', all_content)

    @patch('chatbot.llm_chat.get_llm_helper')
    def test_llm_response_stream_module_function(self, mock_get_helper):
        mock_helper = MagicMock()
        mock_helper.get_response_stream.return_value = iter([
            {'type': 'answer', 'text': 'hi'},
            {'type': 'done'},
        ])
        mock_get_helper.return_value = mock_helper

        events = list(llm_response_stream("test"))

        self.assertEqual(events, [
            {'type': 'answer', 'text': 'hi'},
            {'type': 'done'},
        ])


if __name__ == '__main__':
    unittest.main()
