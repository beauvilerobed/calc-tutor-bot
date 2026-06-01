"""
LLM Step Helper - An AI assistant that helps students understand calculus steps.

Talks to any OpenAI-compatible chat-completions endpoint. Defaults to a local
Ollama server; in production we point this at the self-hosted Ollama on the
Hetzner box via env vars.

Routing (see get_response_stream):
  1. Parse the user's message for step references ("step 2", "step 3 and 4",
     "the second step").
  2. If step numbers are found AND we have the rendered steps HTML, pull
     each referenced step's block from the HTML and make a SEPARATE LLM
     call per step with [problem + that step + scoped question]. Each call
     yields a {"type": "step", ...} event as soon as it finishes, so the
     frontend can render progressively. Per-step calls drop conversation
     history and rewrite the question to scope it to that one step.
  3. If no step references, send the question to the LLM by itself — no
     steps context, no problem context. Honor conversation history.

API:
  llm_response(...)          -> str (collects the whole answer)
  llm_response_stream(...)   -> generator yielding event dicts

Env vars:
  LLM_BASE_URL  e.g. http://localhost:11434/v1
  LLM_API_KEY   bearer token (optional for local Ollama)
  LLM_MODEL     e.g. llama3.2:3b
"""

import os
import re
import requests


SYSTEM_PROMPT = """You are Calaun, a calculus tutor. Help the student understand calculus.

Rules:
- Answer ONLY the specific question asked. Do not re-derive the whole problem.
- Keep it brief: 1-3 sentences plus at most one formula.
- Wrap math in \\( ... \\) inline or \\[ ... \\] for display. Never bare \\frac.
- If asked for a numerical answer, say: "Check the steps above, or try a new expression in the search box."
- If off-topic, say: "I'm here to help with calculus! Ask me about derivatives, integrals, or limits.\""""


# Word-form ordinals for low numbers only. For anything higher, students will
# either say "step N" or "the Nth step" — both unlimited via regex below.
_ORDINAL_TO_NUM = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
    'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
}


def _referenced_step_numbers(message):
    """Find step numbers (1-indexed) explicitly named in the message.

    Supports any step number:
      - 'step 2', 'step2', 'STEP 56', 'step 100'
      - 'steps 2 and 3', 'steps 2, 3, and 4', 'step 2 and step 56'
      - 'the 11th step', 'the 56th step', 'the 100th step'
      - 'the first step', 'third step', ... 'tenth step' (word form, 1-10)

    Returns [] for ambiguous references like 'this step' or 'the next step'.
    """
    nums = set()

    # Each individual "step N" mention.
    for m in re.finditer(r'\bsteps?\s*(\d+)\b', message, re.IGNORECASE):
        nums.add(int(m.group(1)))

    # Number lists trailing a step word: "steps 2 and 3", "steps 2, 3, and 4".
    list_pattern = re.compile(
        r'\bsteps?\s+(\d+(?:\s*,\s*(?:and\s+)?\d+|\s+and\s+\d+)+)',
        re.IGNORECASE,
    )
    for m in list_pattern.finditer(message):
        for n in re.findall(r'\d+', m.group(1)):
            nums.add(int(n))

    # Numeric ordinals: "the 11th step", "56th step", "100th line".
    nth_pattern = re.compile(
        r'\b(?:the\s+)?(\d+)(?:st|nd|rd|th)\s+(?:step|line|part)\b',
        re.IGNORECASE,
    )
    for m in nth_pattern.finditer(message):
        nums.add(int(m.group(1)))

    # Word ordinals (low numbers only): "the first step", "third step".
    for word, n in _ORDINAL_TO_NUM.items():
        if re.search(rf'\b(the\s+)?{word}\s+(step|line|part)\b', message, re.IGNORECASE):
            nums.add(n)

    return sorted(nums)


def _extract_step_blocks(steps_html):
    """Parse rendered steps HTML and return {step_number: inner_html}.

    Steps are rendered as `<li class="step ..." data-step="N">...</li>` and
    nested substeps can appear inside (`<ol class="steps steps--nested">`).
    Track <li> nesting depth so each step's full block is captured.
    """
    if not steps_html:
        return {}

    open_pattern = re.compile(r'<li\b[^>]*>', re.IGNORECASE)
    close_pattern = re.compile(r'</li\s*>', re.IGNORECASE)
    step_attr_pattern = re.compile(r'\bdata-step="(\d+)"', re.IGNORECASE)

    tokens = []
    for m in open_pattern.finditer(steps_html):
        sn = step_attr_pattern.search(m.group(0))
        step_num = int(sn.group(1)) if sn else None
        tokens.append((m.start(), m.end(), 'open', step_num))
    for m in close_pattern.finditer(steps_html):
        tokens.append((m.start(), m.end(), 'close', None))
    tokens.sort(key=lambda t: t[0])

    blocks = {}
    stack = []
    for start, end, kind, step_num in tokens:
        if kind == 'open':
            stack.append((step_num, end))
        else:
            if not stack:
                continue
            opened_step_num, content_start = stack.pop()
            if opened_step_num is not None:
                blocks[opened_step_num] = steps_html[content_start:start]
    return blocks


def _html_to_text(html):
    """Strip HTML tags into readable text, preserving LaTeX delimiters."""
    if not html:
        return ""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    # Drop UI affordances that aren't part of the solution content.
    text = re.sub(
        r'<span[^>]*class="[^"]*step__hint[^"]*"[^>]*>.*?</span>',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r'<h\d[^>]*>', '\n## ', text)
    text = re.sub(r'</h\d>', '\n', text)
    text = re.sub(r'<li[^>]*>', '\n• ', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.2:3b"


class LLMStepHelper:
    """LLM-based assistant that helps students understand calculus solution steps."""

    def __init__(self, api_key=None, model=None, base_url=None):
        self.api_key = api_key or os.environ.get('LLM_API_KEY', '')
        self.model = model or os.environ.get('LLM_MODEL', DEFAULT_MODEL)
        base = (base_url or os.environ.get('LLM_BASE_URL', DEFAULT_BASE_URL)).rstrip('/')
        self.api_url = f"{base}/chat/completions"

        self.calculus_keywords = {
            'derivative', 'integral', 'limit', 'differentiate', 'integrate',
            'calculus', 'chain rule', 'power rule', 'product rule',
            'quotient rule', 'substitution', 'integration by parts',
            'antiderivative', 'slope', 'tangent',
            'rate of change', 'continuous', 'lhopital', "l'hopital",
            'indeterminate', 'infinity', 'converge', 'diverge',
            'theorem', 'proof', 'dx', 'dy', 'sin(', 'cos(', 'tan(',
            'log(', 'ln(', 'exp(',
        }

    def _is_calculus_related(self, message, has_steps=False):
        """Check if the message is related to calculus or the current problem."""
        message_lower = message.lower()

        if has_steps:
            step_references = ['step', 'this', 'that', 'here', 'above', 'why', 'how', 'what']
            if any(ref in message_lower for ref in step_references):
                return True

        for keyword in self.calculus_keywords:
            if keyword in message_lower:
                return True

        math_pattern = r'[xyz]\s*[\+\-\*\/\^]|d[xy]|∫|\d+\s*[\+\-\*\/\^]'
        if re.search(math_pattern, message_lower):
            return True

        return False

    def _format_steps_context(self, steps_html):
        """Public-facing wrapper kept for backwards compatibility with tests."""
        return _html_to_text(steps_html)

    def _build_context_block(self, problem, step_num, step_text):
        """Build the system context message for a step-specific LLM call.

        When the question is scoped to a step, hand the LLM ONLY that step's
        content — leaving the overall problem expression out keeps the model
        from re-deriving everything.
        """
        if step_num is not None and step_text:
            return f"The student is asking about this step:\n\n{step_text}"
        if problem:
            return f"The student is working on the problem: `{problem}`"
        return None

    def _call_llm(self, message, problem=None, step_num=None, step_text=None,
                  conversation_history=None):
        """Make a single chat-completions call."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        context = self._build_context_block(problem, step_num, step_text)
        if context:
            messages.append({"role": "system", "content": context})

        if conversation_history:
            for entry in conversation_history[-10:]:
                messages.append({
                    "role": entry.get("role", "user"),
                    "content": entry.get("content", ""),
                })

        messages.append({"role": "user", "content": message})

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
                timeout=90,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            return "The response is taking too long. Please try again."
        except requests.exceptions.RequestException as e:
            print(f"LLM API error: {e}")
            return (
                "I'm having trouble connecting right now. "
                "Please try again in a moment."
            )

    def get_response(self, message, steps_html=None, problem=None,
                     conversation_history=None):
        """Non-streaming wrapper: collect the stream into a single string.

        Kept so callers and tests that don't care about streaming still work.
        """
        parts = []
        for event in self.get_response_stream(
            message, steps_html=steps_html, problem=problem,
            conversation_history=conversation_history,
        ):
            kind = event.get('type')
            if kind == 'step':
                parts.append(f"**Step {event['step']}**\n\n{event['text']}")
            elif kind == 'answer':
                parts.append(event['text'])
        return '\n\n'.join(parts)

    def get_response_stream(self, message, steps_html=None, problem=None,
                            conversation_history=None):
        """Route the user's question and yield events as each chunk is ready.

        Yields:
          {"type": "step",   "step": N, "text": "..."} — one per referenced step
          {"type": "answer",            "text": "..."} — for non-step questions
          {"type": "done"}                              — terminator

        - Step references found and resolvable -> one LLM call per step,
          yielded as each call finishes so the frontend can render immediately.
        - Otherwise -> single LLM call answered plainly.
        """
        has_steps = bool(steps_html)

        if not self._is_calculus_related(message, has_steps):
            yield {
                'type': 'answer',
                'text': (
                    "I'm here to help with calculus! Feel free to ask me about "
                    "derivatives, integrals, limits, or any of the steps shown above."
                ),
            }
            yield {'type': 'done'}
            return

        referenced = _referenced_step_numbers(message)
        if referenced and steps_html:
            blocks = _extract_step_blocks(steps_html)
            found = [n for n in referenced if n in blocks]
            if found:
                for n in found:
                    step_text = _html_to_text(blocks[n])
                    ans = self._call_llm(
                        self._scoped_question(message, n, len(found)),
                        problem=problem,
                        step_num=n, step_text=step_text,
                        conversation_history=None,
                    )
                    yield {'type': 'step', 'step': n, 'text': ans}
                yield {'type': 'done'}
                return

        ans = self._call_llm(message, conversation_history=conversation_history)
        yield {'type': 'answer', 'text': ans}
        yield {'type': 'done'}

    @staticmethod
    def _scoped_question(original_message, step_num, total_found):
        """Rewrite a multi-step question into a single-step focused question.

        When the student references several steps in one message, each per-step
        LLM call should see a question scoped to just THAT step. This prevents
        the model from refusing on ambiguity when the other referenced steps
        aren't in its context.
        """
        if total_found <= 1:
            return original_message
        return (
            f"The student asked: \"{original_message.strip()}\"\n\n"
            f"Answer for Step {step_num} ONLY, using the step content provided "
            f"in the system context. Do not mention other steps."
        )


_llm_helper = None


def get_llm_helper():
    """Get or create the LLM helper instance."""
    global _llm_helper
    if _llm_helper is None:
        _llm_helper = LLMStepHelper()
    return _llm_helper


def llm_response(message, steps_html=None, problem=None, conversation_history=None):
    """Get an LLM response for the given message (non-streaming)."""
    helper = get_llm_helper()
    return helper.get_response(message, steps_html, problem, conversation_history)


def llm_response_stream(message, steps_html=None, problem=None, conversation_history=None):
    """Stream an LLM response as events. See LLMStepHelper.get_response_stream."""
    helper = get_llm_helper()
    yield from helper.get_response_stream(message, steps_html, problem, conversation_history)
