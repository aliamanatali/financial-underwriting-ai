# $0 Deployment — Hugging Face Spaces + Vercel

Truly free, no credit card. Each backend runs as a **self-contained Docker Space**
(its own internal Redis + Celery worker + FastAPI in one container), reachable at an
HTTPS `*.hf.space` URL. Frontend goes on Vercel. MongoDB Atlas, GCP Storage, and Gemini
stay on their existing free tiers.

> **Verified locally:** the HF OCR image boots all three processes (uvicorn + celery
> worker + redis) in a single UID-1000 container, `/health` returns `healthy`, and it
> connects to live MongoDB Atlas + Gemini.

## What's in this folder

`hf-deploy/` holds the Space build files; `hf-deploy/build-spaces.sh` assembles two
ready-to-push Space repos into `hf-deploy/build/`:
- `hf-deploy/build/ocr-backend/`   → Space "uw-ocr-backend"   (port 8000)
- `hf-deploy/build/financial-engine/` → Space "uw-financial-engine" (port 8001)

Re-run `bash hf-deploy/build-spaces.sh` any time the app code changes to refresh them.

---

## Prerequisites (YOU — one-time, all free, no card)

1. Create a **Hugging Face account**: https://huggingface.co/join
2. Create a **write token**: https://huggingface.co/settings/tokens → "New token" → Write.
3. (For driving from CLI) `pip install -U huggingface_hub` then `hf auth login` (paste token).

---

## Step 1 — Assemble the Space repos

```bash
bash hf-deploy/build-spaces.sh
```

## Step 2 — Create the two Spaces

In the HF web UI: **New → Space**, SDK = **Docker**, hardware = **CPU basic (free)**.
Create two: `uw-ocr-backend` and `uw-financial-engine`. (Or via CLI:
`hf repo create uw-ocr-backend --repo-type space --space_sdk docker`.)

## Step 3 — Push the code to each Space

Each Space is a git repo at `https://huggingface.co/spaces/<user>/<space>`.

```bash
# OCR backend
cd hf-deploy/build/ocr-backend
git init && git add . && git commit -m "deploy"
git remote add hf https://huggingface.co/spaces/<your-user>/uw-ocr-backend
git push hf main           # auth: HF username + write token as password

# Financial engine
cd ../financial-engine
git init && git add . && git commit -m "deploy"
git remote add hf https://huggingface.co/spaces/<your-user>/uw-financial-engine
git push hf main
```

The Space builds the Dockerfile automatically and starts building on push.

## Step 4 — Set secrets in each Space

Space → **Settings → Variables and secrets → New secret**. HF preserves multi-line
values, so paste the full `GCP_PRIVATE_KEY` (with its `BEGIN/END` lines) as-is.

**uw-ocr-backend** secrets:
`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `MONGODB_URI`,
`MONGODB_DATABASE`, and all `GCP_*`
(`GCP_PROJECT_ID`, `GCP_STORAGE_BUCKET`, `GCP_TYPE`, `GCP_PRIVATE_KEY_ID`,
`GCP_PRIVATE_KEY`, `GCP_CLIENT_EMAIL`, `GCP_CLIENT_ID`, `GCP_AUTH_URI`, `GCP_TOKEN_URI`,
`GCP_AUTH_PROVIDER_X509_CERT_URL`, `GCP_CLIENT_X509_CERT_URL`, `GCP_UNIVERSE_DOMAIN`).
> Do NOT set REDIS/CELERY URLs — the Dockerfile points them at the in-container Redis.

**uw-financial-engine** secrets:
`GEMINI_API_KEY`, `MONGODB_URI`, `MONGODB_DATABASE`, all `GCP_*`,
`OCR_BACKEND_URL=https://<your-user>-uw-ocr-backend.hf.space`, and
`CORS_ORIGINS=["https://<your-frontend>.vercel.app"]` (fill the Vercel URL after Step 5).

After adding secrets, **Restart** each Space (Settings → Factory reboot) so they reload.
Confirm health: open `https://<your-user>-uw-ocr-backend.hf.space/health`.

## Step 5 — Frontend on Vercel

```bash
cd ocr-frontend
vercel            # link/create project (already authenticated)
```

Set env vars (`vercel env add` or dashboard):
- `GEMINI_API_KEY` — server-side `/api/chat`
- `NEXT_PUBLIC_OCR_API_URL` = `https://<your-user>-uw-ocr-backend.hf.space`
- `NEXT_PUBLIC_FINANCIAL_API_URL` = `https://<your-user>-uw-financial-engine.hf.space`

```bash
vercel --prod
```

## Step 6 — Wire CORS

Put the deployed Vercel URL into the `uw-financial-engine` Space's `CORS_ORIGINS` secret
and restart it. The OCR backend already allows all origins.

---

## Cost & caveats

| Piece | Cost |
|---|---|
| HF Spaces (CPU basic ×2) | **$0** — 2 vCPU / 16 GB RAM each, no card |
| Vercel Hobby | **$0** |
| MongoDB Atlas M0 / GCP 5 GB / Gemini free | **$0** |

- **Sleep:** free Spaces pause after ~48h of inactivity and cold-start on the next visit
  (~30–60s). Fine for demo/low traffic.
- **Ephemeral disk:** in-container Redis + any temp files reset on restart — intended;
  real state lives in Atlas/GCP.
- **Public by default:** Spaces are public. The app's data sits in Atlas/GCP (private),
  but set the Space to **Private** in Settings if you don't want the API openly reachable.
- **Gemini free tier** rate limits still apply.
