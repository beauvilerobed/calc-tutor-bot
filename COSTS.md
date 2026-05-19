# CaLaun Costs

Last updated: 2026-05-18. Production reality, not theoretical pricing.

## What it currently costs to run

**Operational: ~$20/month** once the Hetzner migration is complete. Everything else is free-tier.

| Service | What it does | Tier | Cost |
|---------|--------------|------|------|
| **Render** Web Service | Django app hosting (until Hetzner cutover) | Free (sleeps 15min idle) | $0 |
| **Neon** Postgres | Database (DATABASE_URL) | Free (0.5 GB, 100 CU-hr/mo) | $0 |
| **Hetzner Cloud CCX13** | Self-hosted Ollama running Qwen2.5-Math-7B | Paid VPS (~8 GB RAM) | ~$20/mo |
| **Render TLS / Let's Encrypt** | HTTPS | Free | $0 |
| **Cloudflare** CDN | Edge caching (via Render) | Free (passthrough) | $0 |

> **Why we left Groq:** the Groq API key was burned and the linked organization was restricted (`organization_restricted`, HTTP 400 on every request). See [CHATBOT_HOSTING.html](CHATBOT_HOSTING.html) for the self-hosting plan we picked. Once the Hetzner box is the source of truth for everything (Django + Postgres + Ollama on one VPS), Render and Neon can both be decommissioned and the total becomes a flat ~$20/mo.

**Cold-start trade-off:** the free Render instance sleeps after 15 min of no traffic. First request after sleep takes ~30 s. Self-hosting on the Hetzner VPS removes this entirely.

---

## Annual fixed costs (already paid or recurring)

| Item | Provider | Cost | Notes |
|------|----------|------|-------|
| `calaun.org` domain | Namecheap | ~$12/yr | Year-1 paid |
| `rbeauvile@calaun.org` private email | Namecheap Private Email | ~$15/yr ($1.24/mo) | Real send + receive inbox |
| **Annual recurring total** | | **~$27/yr** | |

---

## Scaling estimates

| Daily users | Stack | Monthly cost |
|-------------|-------|--------------|
| 100 | Single Hetzner CCX13 (Django + Postgres + Ollama) | **~$20** |
| 1,000 | Same single-box setup; CCX13 still fits | **~$20** |
| 5,000 | Hetzner CCX23 (16 GB) for headroom on Ollama | **~$35–45** |
| 10,000+ | Hetzner CCX33 (32 GB) or split web/LLM onto two boxes | **~$60–90** |

Scaling triggers:
- **CCX23 (16 GB / ~$35–45/mo)** when Ollama starts swapping or response latency creeps past ~6 s.
- **Postgres off-box** (Neon Launch $19/mo, or a managed Hetzner Postgres) when DB I/O starts contending with LLM CPU.
- **Split web + LLM** onto two boxes when you need to scale either independently — adds ~$15–20/mo for a small web box.

---

## Recommended path

1. **Now**: finish the Hetzner CCX13 migration (~$20/mo) and decommission Render + Neon. Single-box hosting, no third-party LLM vendor.
2. **As traffic grows**: bump to CCX23 (16 GB) only when Ollama latency or memory pressure warrants. Don't pre-pay.
3. **If traffic justifies it**: split web and LLM onto separate boxes for independent scaling (+~$15–20/mo).

Total realistic year-1 budget: **~$267** (Hetzner CCX13 ~$240/yr + domain & email ~$27/yr).
