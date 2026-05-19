# Math Step Helper Chatbot

An AI-powered chatbot that helps students understand calculus solution steps. Talks to any OpenAI-compatible chat-completions endpoint; production runs a self-hosted Ollama with Qwen2.5-Math-7B.

## Features

- **Self-hosted**: no third-party LLM vendor dependency
- **Step-aware**: Receives the current solution steps as context
- **Calculus-focused**: Only answers calculus-related questions
- **Teaching-focused**: Explains concepts without giving direct answers
- **Conversation memory**: Remembers previous messages in the chat
- **LaTeX support**: Responds with mathematical notation
- **Dynamic reply length**: Caps response tokens based on question intent — quick lookups ("what's the power rule") get short answers; "explain why / how does" questions get longer ones

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

See [CHATBOT_HOSTING.html](../CHATBOT_HOSTING.html) for the full self-hosting plan and tradeoffs.

## Usage

```python
from chatbot.llm_chat import llm_response

# With solution steps context
steps_html = "<div>Step 1: Apply power rule...</div>"
answer = llm_response("Why do we multiply by 2 here?", steps_html=steps_html)

# With conversation history
history = [
    {"role": "user", "content": "What is a derivative?"},
    {"role": "assistant", "content": "A derivative measures..."}
]
answer = llm_response("Can you give an example?", conversation_history=history)
```

## How It Works

The chatbot is designed to be a helpful tutor, not a calculator:

1. **Receives context**: Gets the current solution steps being displayed
2. **Understands the question**: Uses the configured LLM to understand what the student is asking
3. **Explains concepts**: Provides explanations of rules and techniques
4. **Never calculates**: Won't solve problems directly - encourages learning

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
