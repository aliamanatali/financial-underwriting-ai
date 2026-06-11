# $0 Deployment — Free VPS + Vercel

The truly-free, always-on path. All three backends + Redis run on **one free VM** via
`docker-compose.yml`; the frontend goes on **Vercel** (free). MongoDB Atlas, GCP Storage,
and Gemini are already on free tiers.

> Why a VM and not Render/Koyeb/Fly? No managed free tier runs an **always-on Celery
> worker**: Render workers are paid, Koyeb free is one web service only, Railway pauses
> after credits, Fly has no free tier. A free VM is the only sustainable $0 option.

Verified: the full stack (`docker compose up`) boots locally — both APIs return `/health`,
the worker connects to Redis and registers tasks, OCR connects to live MongoDB Atlas.

---

## Prerequisites (one-time, requires YOU)

- **Oracle Cloud Always Free** account → provision a VM. Best pick: **Ampere A1 (ARM)**,
  ~2 OCPU / 12 GB RAM, Ubuntu 22.04. Always Free = perpetual; a card is required for ID
  verification but is never charged. (Any free/cheap VPS with ≥2 GB RAM works.)
- A **Cloudflare account** (free) — for HTTPS without a domain/cert hassle (Step 4).
- **Vercel** — already authenticated as your account.

---

## Step 1 — Prep the VM

SSH in, then install Docker:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

Open ports 8000 and 8001 in the Oracle **Security List** (ingress) AND the VM firewall:

```bash
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8001 -j ACCEPT
sudo netfilter-persistent save   # if available
```

## Step 2 — Get the code + env files onto the VM

```bash
git clone <your-repo-url> app && cd app
```

Create the two backend env files (do NOT commit these):

- `ocr-backend/.env` — copy from `ocr-backend/.env.example`, fill in:
  `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `MONGODB_URI`,
  `MONGODB_DATABASE`, and all `GCP_*` vars. **Leave Redis/Celery URLs out** — compose
  injects `redis://redis:6379/0` automatically.
- `financial-engine/.env` — `GEMINI_API_KEY`, `MONGODB_URI`, `MONGODB_DATABASE`,
  `GCP_*`, `OCR_BACKEND_URL=http://ocr-backend-api:8000`, and
  `CORS_ORIGINS=["https://<your-frontend>.vercel.app"]` (fill after Step 5).

> Tip: scp your existing local `.env` files up rather than retyping secrets.

## Step 3 — Launch the stack

```bash
docker compose up -d --build
docker compose ps                       # all should be Up / healthy
curl localhost:8000/health              # {"status":"healthy",...}
curl localhost:8001/health              # {"status":"ok"}
```

The Celery worker (`ocr-backend-worker`) starts automatically and stays always-on via
`restart: unless-stopped`.

## Step 4 — HTTPS via Cloudflare Tunnel (free, no domain needed)

A Vercel (HTTPS) frontend cannot call a plain `http://<vm-ip>` backend — browsers block
mixed content. Cloudflare Tunnel gives each backend a free `https://*.trycloudflare.com`
(or your own domain) URL with no open ports or certs:

```bash
# On the VM:
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o cloudflared
chmod +x cloudflared && sudo mv cloudflared /usr/local/bin/

# Named tunnels (persistent) — recommended; run `cloudflared tunnel login` first:
cloudflared tunnel create uw-backends
# Map hostnames -> localhost:8000 and localhost:8001 in ~/.cloudflared/config.yml, then:
cloudflared tunnel run uw-backends
```

(For a 5-minute throwaway test instead: `cloudflared tunnel --url http://localhost:8000`
prints an https URL.) Run cloudflared as a systemd service so it survives reboots:
`sudo cloudflared service install`.

You now have e.g. `https://ocr.example.com` and `https://fin.example.com`.

## Step 5 — Frontend on Vercel

```bash
cd ocr-frontend
vercel            # link/create the project
```

Set env vars (Vercel dashboard → Settings → Environment Variables, or `vercel env add`):

- `GEMINI_API_KEY` — for the server-side `/api/chat` route
- `NEXT_PUBLIC_OCR_API_URL` = `https://<ocr-tunnel-url>`
- `NEXT_PUBLIC_FINANCIAL_API_URL` = `https://<fin-tunnel-url>`

Then ship production:

```bash
vercel --prod
```

## Step 6 — Wire CORS

Put the deployed Vercel URL into `financial-engine/.env` →
`CORS_ORIGINS=["https://<your-frontend>.vercel.app"]`, then on the VM:

```bash
docker compose up -d financial-engine   # picks up the new env
```

The OCR backend already allows all origins, so no change needed there.

---

## Cost reality

| Piece | Cost | Notes |
|---|---|---|
| Oracle VM (Always Free) | **$0** | Perpetual; card for ID only |
| Vercel (Hobby) | **$0** | Frontend |
| Cloudflare Tunnel | **$0** | HTTPS |
| MongoDB Atlas M0 | **$0** | 512 MB |
| GCP Cloud Storage | **$0** | 5 GB free |
| Gemini API | **$0** | Free tier, rate-limited |

**Caveats:** Gemini free tier has request/minute limits; Atlas M0 is 512 MB; Oracle can
reclaim idle Always-Free ARM capacity, and ARM availability at signup can be flaky (retry
or pick a different region).
