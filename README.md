# CaLaun

A free, open-source Django calculus tutor that shows step-by-step solutions for derivatives, integrals, and limits. Includes an AI chatbot powered by a self-hosted open-weight LLM (Llama 3.2 3B via Ollama).

**Live:** [https://calaun.org](https://calaun.org) · **License:** MIT · **Status:** personal open-source project (not a non-profit;)

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Features

- **Step-by-step solutions** for derivatives, integrals, and limits
- **AI chatbot sidebar** that explains calculus concepts (powered by self-hosted Ollama; streams per-step answers progressively)
- **Reference page** with common formulas and "try it" links

## Screenshots

The results page shows step-by-step solutions with an AI chatbot sidebar:
- Click any step to expand/collapse details
- Ask the chatbot to explain concepts or clarify steps
- Chatbot is context-aware and sees the current solution

## Requirements

- Python 3.9+ (tested with Python 3.12)
- pip
- (Optional) [Ollama](https://ollama.com) running locally for the AI chatbot

## Setup

1. **Create a virtual environment:**
   ```bash
   python3 -m venv env
   source env/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Set up the AI chatbot (optional but recommended):**
   ```bash
   # Install Ollama from https://ollama.com, then:
   ollama pull llama3.2:3b
   # Set LLM_MODEL=llama3.2:3b in your .env (or whichever model you pulled).
   # LLM_BASE_URL defaults to http://localhost:11434/v1, so no other env vars
   # are needed for local dev.
   ```

4. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

5. **Visit** http://127.0.0.1:8000

## Usage

Enter calculus expressions like:

**Derivatives:**
- `diff(x^5, x)` - Power rule
- `diff(sin(x^2), x)` - Chain rule
- `diff(x^2 * ln(x), x)` - Product rule

**Integrals:**
- `integrate(x^3, x)` - Power rule
- `integrate(x*exp(x), x)` - Integration by parts
- `integrate(1/(x^2 - 1), x)` - Partial fractions

**Limits:**
- `limit(sin(x)/x, x, 0)` - Fundamental trig limit
- `limit((1 + 1/x)^x, x, oo)` - Definition of e
- `limit((x^2 - 4)/(x - 2), x, 2)` - Indeterminate form

## AI Chatbot

The chatbot talks to any OpenAI-compatible chat-completions endpoint via env vars (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`). Production runs an open-weight model on self-hosted Ollama (currently Llama 3.2 3B). It:
- Explains calculus concepts and rules
- Understands the current solution steps as context
- **Streams per-step answers**: when the student asks about multiple steps in one message, each step's answer reaches the browser as soon as it's generated, instead of waiting for all of them
- Uses proper LaTeX formatting in responses

See [chatbot/README.md](chatbot/README.md) for routing details and HTTP API shape.

## Testing

```bash
python manage.py test        # Run all tests
python -m pytest logic/      # Run logic tests only
python -m pytest chatbot/    # Run chatbot tests only
```

## Tech Stack

- **Backend:** Django 4.2
- **Math Engine:** SymPy
- **AI Chatbot:** Ollama + Llama 3.2 3B (self-hosted, OpenAI-compatible API; NDJSON streaming response)
- **Frontend:** Vanilla ES6 JavaScript, MathJax 3, CSS custom properties
- **Database:** SQLite (dev) / PostgreSQL (prod via DATABASE_URL)

## Production deployment

The live site at [calaun.org](https://calaun.org) runs on a single Hetzner Cloud CCX13 VPS (~$20/month) hosting Django, PostgreSQL, and Ollama all on the same box. Django talks to Ollama over `localhost:11434`. See [DEPLOY.md](DEPLOY.md) for the deployment guide.

The chatbot endpoint streams NDJSON, so nginx must pass response chunks through immediately. The Django view sets `X-Accel-Buffering: no` on every chatbot response — no nginx config change required.

Required env vars in production: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `LLM_BASE_URL` (typically `http://localhost:11434/v1`), `LLM_MODEL` (e.g. `llama3.2:3b`).

## Project Structure

```
├── app/                 # Django app (views, URLs, template tags)
├── chatbot/             # AI chatbot module
│   ├── llm_chat.py      # Chatbot client (OpenAI-compatible, defaults to local Ollama)
│   └── README.md        # Chatbot documentation
├── logic/               # Math solving logic
│   ├── diffsteps.py     # Derivative steps
│   ├── intsteps.py      # Integral steps  
│   ├── limitsteps.py    # Limit steps (including exponential forms)
│   └── resultsets.py    # Result card definitions
├── static/
│   ├── css/modern.css   # Modern CSS with custom properties
│   └── js/app.js        # ES6 JavaScript (ChatSidebar, Collapsible)
├── templates/           # HTML5 templates
└── mathtutor/           # Django settings
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you find this project helpful and want to chip in, you can:

- Use [GitHub Sponsors](https://github.com/sponsors/beauvilerobed) (one-time or recurring)
- Email [rbeauvile@calaun.org](mailto:rbeauvile@calaun.org?subject=Supporting%20CaLaun) with any other ideas

CaLaun is a open-source project, not a 501(c)(3), so contributions are **not** tax-deductible.
