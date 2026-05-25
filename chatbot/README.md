# Math Step Helper Chatbot

An AI-powered chatbot that helps students understand calculus solution steps. Talks to any OpenAI-compatible chat-completions endpoint; production runs a self-hosted Ollama with Qwen2.5-Math-1.5B.

## Features

- **Self-hosted**: no third-party LLM vendor dependency
- **Focused per-step routing**: parses the user's message for step references ("step 2", "the 56th step", "steps 1 and 3") and sends only those step blocks plus the original problem to the model — not the full solution
- **Multi-step splitting**: if the user asks about multiple steps in one message, the chatbot makes a separate LLM call per step and concatenates the answers under `**Step N**` headers
- **Calculus-focused**: politely deflects off-topic questions
- **Teaching-focused**: explains concepts without giving direct numerical answers
- **Conversation memory**: keeps the last 10 messages in context
- **LaTeX support**: responds with `\(...\)` / `\[...\]` for MathJax

## Setup

1. **Install Ollama** from https://ollama.com (one-line installer for macOS / Linux).

2. **Pull a model**:
   ```bash
   ollama pull qwen2.5:7b
   ```

3. **Start the server** — the defaults already point at local Ollama (`http://localhost:11434/v1`), so no env vars are needed for local dev.

Environment variables (override defaults as needed):
- `LLM_BASE_URL` - OpenAI-compatible base URL (default: `http://localhost:11434/v1`)
- `LLM_API_KEY` - Bearer token (optional for local Ollama; required if exposing publicly)
- `LLM_MODEL` - Model name (default: `qwen2.5:7b`)

## Supported models

Anything Ollama can run. For a calculus tutor:
- `qwen2.5:7b` - Good general default (~10–12 GB RAM)
- `qwen2.5-math:7b` - Math-specialized, best for this use case
- `qwen2.5-math:1.5b` - Tiny math-specialized model (~3 GB RAM)
- `phi3:mini` - Microsoft Phi-3-mini, good general reasoning
- `llama3.1:8b` - Meta Llama 3.1 8B

Production runs `qwen2.5:7b` on a single Hetzner Cloud CCX13 VPS (~8 GB RAM, ~$20/month). The chatbot and Django share the same box and talk over `localhost:11434`.

## Production architecture

| Component | Where it runs |
| --- | --- |
| Django (gunicorn) | Hetzner CCX13, behind reverse proxy w/ TLS |
| PostgreSQL | Same Hetzner CCX13 (loopback) |
| Ollama + Qwen2.5-Math-1.5B | Same Hetzner CCX13, listening on `localhost:11434` |

No third-party LLM API in the critical path. No per-token billing meter. If the box dies, everything dies together — restore is restoring one VPS.

## Usage

```python
from chatbot.llm_chat import llm_response

# Plain question, no step reference: single LLM call, no extra context.
answer = llm_response("What is the chain rule?")

# Step-specific question with the rendered steps and the original problem.
# Parses "step 2" from the message, sends only step 2's HTML block + the
# problem to the model. Returns one focused answer.
answer = llm_response(
    "Why do we multiply by 2 in step 2?",
    steps_html=rendered_steps_html,
    problem="diff(x^2, x)",
)

# Multi-step question: makes one LLM call per referenced step and joins
# the answers under "**Step N**" headers.
answer = llm_response(
    "Walk me through step 1 and step 3",
    steps_html=rendered_steps_html,
    problem="diff(x^5, x)",
)

# With conversation history
history = [
    {"role": "user", "content": "What is a derivative?"},
    {"role": "assistant", "content": "A derivative measures..."}
]
answer = llm_response("Can you give an example?", conversation_history=history)
```

## How It Works

Routing happens in `LLMStepHelper.get_response()`:

1. **Off-topic filter**: messages that don't reference calculus keywords or the on-screen steps get a polite redirect — no LLM call.
2. **Parse step numbers** from the user's message (`step 2`, `step2`, `steps 2 and 3`, `steps 2, 3, and 4`, `step 2 and step 56`, `the 11th step`, `the third step`, etc.).
3. **If step numbers are found** AND the rendered steps HTML was provided, extract just those step blocks via `<li data-step="N">` markers. Then make a **separate LLM call per step** with a minimal prompt: `[system prompt + problem + that step's content + user question]`. Multiple referenced steps → multiple sequential calls; answers are joined under `**Step N**` headers.
4. **If no step numbers are found**, make a single LLM call with just the user's message — no problem context, no steps context. The model answers the question plainly.

Why this shape: the production model (Qwen2.5-Math-1.5B) is small and struggles with long prompts. Cutting context to one specific step keeps each call short, focused, and fast.

The model is instructed (via `SYSTEM_PROMPT`) to answer only what was asked, keep replies to 1-3 sentences plus at most one formula, and never compute a final numerical answer.

## Topics It Can Help With

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

- `llm_chat.py` - LLM chatbot client (OpenAI-compatible; defaults to local Ollama)
