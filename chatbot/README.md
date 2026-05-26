# Math Step Helper Chatbot

An AI-powered chatbot that helps students understand calculus solution steps. Talks to any OpenAI-compatible chat-completions endpoint; production runs a self-hosted Ollama.

## Features

- **Self-hosted**: no third-party LLM vendor dependency
- **Streaming answers**: when the student asks about several steps in one message, each step's answer is streamed to the browser as soon as it's ready — the user starts reading Step 1 while Step 2 is still being generated
- **Focused per-step routing**: parses the user's message for step references ("step 2", "the 56th step", "steps 1 and 3") and sends only those step blocks plus the original problem to the model — not the full solution
- **Per-step scoping**: each per-step LLM call sees a question rewritten to focus on just that step, plus that step's content and the original problem — no conversation history, no other steps. Keeps small models from refusing on ambiguity.
- **Calculus-focused**: politely deflects clearly off-topic questions
- **Teaching-focused**: explains concepts without giving direct numerical answers
- **Conversation memory**: keeps the last 10 messages in context (for non-step questions only)
- **LaTeX support**: responds with `\(...\)` / `\[...\]` for MathJax

## Setup

1. **Install Ollama** from https://ollama.com (one-line installer for macOS / Linux).

2. **Pull a model**:
   ```bash
   ollama pull llama3.2:3b
   ```

3. **Start the server** — the defaults already point at local Ollama (`http://localhost:11434/v1`), so no env vars are needed for local dev.

Environment variables (override defaults as needed):
- `LLM_BASE_URL` - OpenAI-compatible base URL (default: `http://localhost:11434/v1`)
- `LLM_API_KEY` - Bearer token (optional for local Ollama; required if exposing publicly)
- `LLM_MODEL` - Model name (default: `llama3.2:3b`)
- `CHATBOT_ENABLED` - Set to `False` to short-circuit the LLM and return a graceful disclaimer (emergency kill switch)

## Supported models

Anything Ollama can run. Picks that fit a CCX13-class box (8 GB RAM, CPU-only) shared with Django + Postgres:

| Model | Pull | RAM | Notes |
|---|---|---|---|
| **llama3.2:3b** (recommended) | `ollama pull llama3.2:3b` | ~2.5 GB | Plain conversational English, good context awareness, rarely refuses |
| qwen2.5-math:1.5b | `ollama pull qwen2.5-math:1.5b` | ~1.5 GB | Math-tuned but more terse |
| phi3:mini | `ollama pull phi3:mini` | ~2.5 GB | Good step-by-step explanations |
| qwen2.5:3b | `ollama pull qwen2.5:3b` | ~2.5 GB | Solid general model |

Larger 7B+ models work too, but inference on a 2-vCPU CPU box gets slow (~5-10 tok/s).

Production currently runs `llama3.2:3b` on a single Hetzner Cloud CCX13 VPS (~8 GB RAM, ~$20/month).

## Production architecture

| Component | Where it runs |
| --- | --- |
| Django (gunicorn) | Hetzner CCX13, behind nginx with TLS |
| PostgreSQL | Same Hetzner CCX13 (loopback) |
| Ollama | Same Hetzner CCX13, listening on `localhost:11434` |

No third-party LLM API in the critical path. No per-token billing meter. If the box dies, everything dies together — restore is restoring one VPS.

**Important nginx note for streaming:** the chatbot endpoint streams responses, so nginx must not buffer the body. The Django view sets `X-Accel-Buffering: no` on every chatbot response, which tells nginx to pass chunks through immediately. No nginx config change is required.

## HTTP API

### `POST /api/chatbot/`

Request body:
```json
{
  "text": "how did you get step 2 and step 3?",
  "steps": "<ol class=\"steps\">...</ol>",
  "problem": "diff(x^2 * ln(x), x)",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

Response: `Content-Type: application/x-ndjson` — one JSON object per line:

```json
{"type": "step", "step": 2, "text": "Apply the product rule because ..."}
{"type": "step", "step": 3, "text": "Differentiate each factor ..."}
{"type": "done"}
```

For questions with no step reference, a single `{"type": "answer", "text": "..."}` event is emitted instead, followed by `{"type": "done"}`.

Rate-limited responses (HTTP 429) return a regular JSON body:
```json
{"text": "You've sent too many messages. ...", "rate_limited": true, "retry_after": 30}
```

## Python usage

```python
from chatbot.llm_chat import llm_response, llm_response_stream

# Non-streaming: collect everything into one string.
answer = llm_response(
    "Walk me through step 1 and step 3",
    steps_html=rendered_steps_html,
    problem="diff(x^5, x)",
)
# -> "**Step 1**\n\n...\n\n**Step 3**\n\n..."

# Streaming: yield events as each step's call finishes.
for event in llm_response_stream(
    "Walk me through step 1 and step 3",
    steps_html=rendered_steps_html,
    problem="diff(x^5, x)",
):
    if event["type"] == "step":
        print(f"Step {event['step']} ready: {event['text']}")
    elif event["type"] == "answer":
        print(f"Answer: {event['text']}")
    elif event["type"] == "done":
        break

# With conversation history (only honored for non-step questions).
history = [
    {"role": "user", "content": "What is a derivative?"},
    {"role": "assistant", "content": "A derivative measures..."},
]
answer = llm_response("Can you give an example?", conversation_history=history)
```

## How it works

Routing happens in `LLMStepHelper.get_response_stream()`:

1. **Off-topic filter**: messages that don't reference calculus keywords or the on-screen steps get a polite redirect — no LLM call.
2. **Parse step numbers** from the user's message (`step 2`, `step2`, `steps 2 and 3`, `steps 2, 3, and 4`, `step 2 and step 56`, `the 11th step`, `the third step`, etc.).
3. **If step numbers are found** AND the rendered steps HTML was provided, extract just those step blocks via `<li data-step="N">` markers. Then for each referenced step:
   - Rewrite the user's question to scope it to that single step (so the model isn't confused by references to other steps it doesn't have in context).
   - Make an LLM call with `[system prompt + problem + that step's content + scoped question]`. **No conversation history is passed on per-step calls** — each call is independent.
   - Yield a `{"type": "step", "step": N, "text": ...}` event immediately so the frontend can render it.
4. **If no step numbers are found**, make a single LLM call with the user's message + conversation history, and yield one `{"type": "answer", ...}` event.

Why this shape: small self-hosted models struggle with long prompts and ambiguous multi-step questions. Cutting context to one specific step + scoping the question to that step keeps each call short, focused, and resistant to refusal.

The model is instructed (via `SYSTEM_PROMPT`) to answer only what was asked, keep replies to 1-3 sentences plus at most one formula, and never compute a final numerical answer.

## Topics it can help with

**Derivative Rules**
- Power, chain, product, quotient rules
- Trig derivatives (sin, cos, tan, sec, csc, cot)
- Inverse trig and hyperbolic derivatives
- Exponential and logarithmic differentiation

**Integration Techniques**
- U-substitution, integration by parts
- Trig substitution, partial fractions
- Inverse hyperbolic integrals

**Limits**
- Direct substitution, factoring
- L'Hôpital's rule, rationalization
- Special limits (sin(x)/x, etc.)

**General Calculus Concepts**
- Continuity, differentiability
- Fundamental Theorem of Calculus
- Applications and word problems

## Files

- `llm_chat.py` - LLM chatbot client (OpenAI-compatible; defaults to local Ollama). Exposes `llm_response()` and `llm_response_stream()`.
- `test_llm_chat.py` - Unit tests for routing, step extraction, streaming, and per-step scoping.
