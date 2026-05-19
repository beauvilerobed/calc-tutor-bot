# CaLaun Deployment Guide

## Recommended free stack (May 2026)

| Layer | Provider | Free tier |
|-------|----------|-----------|
| Web app | **Render** (Web Service) | 750 instance hrs/mo, sleeps after 15 min idle, auto-wakes |
| Database | **Neon** (Postgres) | 0.5 GB storage, 100 CU-hrs/mo, no expiry |
| Domain | `*.onrender.com` (free, included) — or attach a custom domain on the Hobby workspace (2 free) |
| TLS | Free, auto-managed by Render |

Render's own free Postgres expires after 30 days — that's why we use **Neon** instead, which is genuinely free with no time limit.

---

## Step 1 — Create a free Neon Postgres database

1. Sign up at https://neon.com (GitHub login works, no card required).
2. Create a new project — pick the region closest to where Render runs (`us-east` is a safe default).
3. Open the project's **Connection details** and copy the **pooled** connection string. It looks like:
   ```
   postgres://USER:PASSWORD@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Save this — you'll paste it into Render as `DATABASE_URL`.

## Step 2 — Generate a SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the output for the next step.

## Step 3 — Deploy on Render

1. Push your branch to GitHub (or fork the repo).
2. Go to https://dashboard.render.com → **New** → **Web Service** → connect your repo.
3. Choose:
   - **Environment**: Python
   - **Build command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - **Start command**: `gunicorn mathtutor.wsgi --bind 0.0.0.0:$PORT`
   - **Instance type**: Free
4. Add **Environment Variables**:

   | Key | Value |
   |-----|-------|
   | `SECRET_KEY` | (paste from Step 2) |
   | `DEBUG` | `False` |
   | `ALLOWED_HOSTS` | `your-app-name.onrender.com` |
   | `CSRF_TRUSTED_ORIGINS` | `https://your-app-name.onrender.com` |
   | `DATABASE_URL` | (paste from Step 1) |
   | `LLM_BASE_URL` | URL of your self-hosted LLM (e.g. `https://llm.calaun.org/v1`) — see [CHATBOT_HOSTING.html](CHATBOT_HOSTING.html) |
   | `LLM_API_KEY` | Bearer token for the LLM (required when exposing Ollama publicly) |
   | `LLM_MODEL` | Model name (e.g. `qwen2.5:7b`) |
   | `LOG_LEVEL` | `INFO` |

5. Click **Create Web Service**. First deploy takes ~3–5 min.
6. Visit `https://your-app-name.onrender.com` — you're live.

> **Cold start note:** the free instance sleeps after 15 minutes of inactivity and takes ~30 s to wake up on the next request. For a free teaching tool that's typically fine; if you want it always-on, Render's Starter ($7/mo) or self-hosting on a small VPS removes the sleep.

## Step 4 — (Optional) Add a custom domain

If you have a domain, add it under **Settings → Custom Domains** in Render — TLS is auto-issued. The full step-by-step is in [Wiring a custom domain](#wiring-a-custom-domain-what-we-did-with-calaunorg) below.

If you don't have a domain, the free `*.onrender.com` subdomain is a perfectly valid public URL.

---

## Wiring a custom domain (what we did with calaun.org)

Production reference. This is the actual flow used to put `calaun.org` in front of `calaun.onrender.com`. Domain bought at Namecheap; same flow with any registrar.

### Step 1 — Add custom domains in Render

Either via the dashboard (**Service → Settings → Custom Domains → Add**) or via API:

```bash
SERVICE_ID=srv-...        # your Render service id
RENDER_TOKEN=rnd_...

# Adds both apex + www in one call (Render auto-creates the www-redirect)
curl -X POST https://api.render.com/v1/services/$SERVICE_ID/custom-domains \
  -H "Authorization: Bearer $RENDER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "calaun.org"}'
```

Render returns a domain id and `verificationStatus: unverified`.

### Step 2 — Add DNS records at the registrar

Point your domain at Render's edge IPs. As of May 2026 these are `216.24.57.7` and `216.24.57.251` — confirm with `dig +short A calaun.onrender.com`.

| Type | Host / Name | Value | TTL |
|------|-------------|-------|-----|
| `A` | `@` (apex) | `216.24.57.7` | Automatic |
| `A` | `@` (apex) | `216.24.57.251` | Automatic |
| `CNAME` | `www` | `calaun.onrender.com.` | Automatic |

**Namecheap quirk:** delete the default parking records first (URL Redirect on `@`, CNAME `www → parkingpage.namecheap.com`) — they conflict.

If your registrar supports `ALIAS` / `ANAME` at the apex (Cloudflare, DNSimple, Namecheap PremiumDNS), use that instead of two A records — survives Render rotating IPs.

### Step 3 — Wait for DNS propagation

Usually 2–60 min. Check from a public resolver:

```bash
dig +short A calaun.org @1.1.1.1
# expected: 216.24.57.7  216.24.57.251
```

### Step 4 — Verify with Render

```bash
curl -H "Authorization: Bearer $RENDER_TOKEN" \
  "https://api.render.com/v1/services/$SERVICE_ID/custom-domains/$DOMAIN_ID" \
  | jq .verificationStatus
# expected: "verified"
```

Render auto-issues a TLS cert (Google Trust Services) within ~30 s of verification.

### Step 5 — Update Render env vars for the new host

**Critical** — without this you get `400 DisallowedHost` because Django won't accept the new Host header.

```bash
# ALLOWED_HOSTS — comma-separated hosts (no scheme)
curl -X PUT \
  "https://api.render.com/v1/services/$SERVICE_ID/env-vars/ALLOWED_HOSTS" \
  -H "Authorization: Bearer $RENDER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": "calaun.org,www.calaun.org,calaun.onrender.com"}'

# CSRF_TRUSTED_ORIGINS — comma-separated, WITH https:// prefix
curl -X PUT \
  "https://api.render.com/v1/services/$SERVICE_ID/env-vars/CSRF_TRUSTED_ORIGINS" \
  -H "Authorization: Bearer $RENDER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": "https://calaun.org,https://www.calaun.org,https://calaun.onrender.com"}'
```

### Step 6 — Trigger a redeploy

Env-var changes don't take effect until gunicorn restarts.

```bash
curl -X POST \
  "https://api.render.com/v1/services/$SERVICE_ID/deploys" \
  -H "Authorization: Bearer $RENDER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": "do_not_clear"}'
```

### Step 7 — Smoke-test

```bash
# If local DNS cache is stale, force the resolution:
curl -I --resolve calaun.org:443:216.24.57.7 https://calaun.org/
# expected: HTTP/2 200, server: cloudflare, x-render-origin-server: gunicorn

# www should 301 to apex
curl -I --resolve www.calaun.org:443:216.24.57.7 https://www.calaun.org/
# expected: HTTP/2 301, location: https://calaun.org/

# TLS cert
echo | openssl s_client -servername calaun.org -connect 216.24.57.7:443 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
```

### Step 8 — (Optional) Add a canonical link tag

In `templates/base.html`, inside `<head>`:

```html
<link rel="canonical" href="https://calaun.org{{ request.path }}">
```

Tells search engines the .org apex is the source of truth even if pages are indexed under `www.calaun.org` or `calaun.onrender.com`.

### Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `400 Bad Request — DisallowedHost` | New host not in `ALLOWED_HOSTS`, or env updated but no redeploy | Redeploy after env-var update |
| `CSRF verification failed` on POSTs | New host not in `CSRF_TRUSTED_ORIGINS` | Add `https://...` + host, redeploy |
| Render says `unverified` for hours | DNS records wrong or not propagated | `dig +short A calaun.org @1.1.1.1` to confirm |
| TLS cert error | Render hasn't issued cert yet | Wait 60 s after verification flips |
| Local `curl` fails but browser works | macOS DNS cache | `sudo killall -HUP mDNSResponder` or use `--resolve` |

---

## Local development

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then edit .env
python manage.py migrate
python manage.py runserver
```

Local dev defaults to SQLite (no `DATABASE_URL` set), so you don't need Postgres locally unless you want to mirror production.

To run against a local Postgres:

```bash
# Install postgres (macOS)
brew install postgresql@16 && brew services start postgresql@16
createdb calaun
# Then in .env:
# DATABASE_URL=postgres://$USER@localhost:5432/calaun
```

---

## Environment variables reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | prod | dev key | Django secret. 50+ random chars. |
| `DEBUG` | yes | `True` | `False` in production. |
| `ALLOWED_HOSTS` | prod | `127.0.0.1,localhost` | Comma-separated hosts. |
| `CSRF_TRUSTED_ORIGINS` | prod | empty | Comma-separated, **with scheme**: `https://example.com`. Required for HTTPS POSTs. |
| `DATABASE_URL` | prod | unset (SQLite) | Full Postgres URL. |
| `LLM_BASE_URL` | optional | `http://localhost:11434/v1` | OpenAI-compatible chat-completions base URL. Defaults to local Ollama. |
| `LLM_API_KEY` | optional | unset | Bearer token for the LLM endpoint. Optional for local Ollama; required when exposing publicly. |
| `LLM_MODEL` | optional | `qwen2.5:7b` | Model name to send to the endpoint. |
| `SECURE_SSL_REDIRECT` | optional | `True` | Honored only when `DEBUG=False`. |
| `SECURE_HSTS_SECONDS` | optional | `31536000` | HSTS duration. |
| `LOG_LEVEL` | optional | `INFO` | Standard logging levels. |

---

## Other deployment targets

### Docker

```bash
docker build -t calaun .
docker run -p 8000:8000 \
  -e SECRET_KEY=... \
  -e DEBUG=False \
  -e ALLOWED_HOSTS=localhost \
  -e DATABASE_URL=postgres://... \
  -e LLM_BASE_URL=https://llm.example.com/v1 \
  -e LLM_API_KEY=... \
  -e LLM_MODEL=qwen2.5:7b \
  calaun
```

### Railway

The repo includes `railway.toml`. Connect the repo in Railway, add the same env vars as above, and provision a Postgres add-on (Railway's free credit covers low traffic for a while, but it's not a permanent free tier).

### VPS (Ubuntu/Debian)

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv nginx postgresql
git clone https://github.com/calaun-learning/calaun.git
cd calaun
python3.12 -m venv env && source env/bin/activate
pip install -r requirements.txt

cat > .env <<EOF
SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(64))')
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
DATABASE_URL=postgres://user:pass@localhost:5432/calaun
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:7b
EOF

python manage.py collectstatic --noinput
python manage.py migrate
gunicorn mathtutor.wsgi --bind 127.0.0.1:8000 --daemon
# then put nginx in front for TLS / reverse proxy
```

---

## Security checklist

- [ ] `SECRET_KEY` is 50+ random chars, set via env (never committed)
- [ ] `DEBUG=False` in production
- [ ] `ALLOWED_HOSTS` contains only your real hosts
- [ ] `CSRF_TRUSTED_ORIGINS` includes your `https://...` host(s)
- [ ] `.env` is in `.gitignore` (it is — verified)
- [ ] HTTPS enforced (Render does this automatically; on a VPS use nginx + certbot)
- [ ] `python manage.py check --deploy` reports no issues with prod env vars set

## Troubleshooting

- **Static files 404 in prod** → re-run `python manage.py collectstatic --noinput` (already in build command).
- **CSRF "Origin checking failed"** → add the full `https://...` URL to `CSRF_TRUSTED_ORIGINS`.
- **Postgres SSL error on Neon** → settings already set `sslmode=require` automatically when `DEBUG=False`.
- **App is slow on first request** → cold start from sleep. Upgrade Render plan or ping it via uptime monitor.
