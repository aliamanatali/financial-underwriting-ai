# Deployment Runbook

Deploy the 3-service financial-underwriting app on a low-cost stack:

| Service | Platform | App / Project |
|---|---|---|
| `ocr-backend` (FastAPI API + Celery worker, 2 process groups) | Fly.io | `fin-uw-ocr-backend` |
| `financial-engine` (FastAPI) | Fly.io | `fin-uw-financial-engine` |
| `ocr-frontend` (Next.js) | Vercel | (your choice) |

Managed dependencies: Redis = **Upstash**, MongoDB = **Atlas M0** (already configured), object storage = **GCP Cloud Storage**, LLM = **Gemini**.

The `fly.toml` and `Dockerfile` for both backends already exist. `ocr-backend/fly.toml` defines two process groups (`app` + `worker`) on one app; `financial-engine/fly.toml` is a single web service. Both listen on port `8080` and expose `/health`.

> Secrets below use placeholders like `<YOUR_GEMINI_API_KEY>`. Substitute your real values; never commit them.

---

## Prerequisites

Accounts:

- **Fly.io** — note: Fly **no longer has a truly-free tier** and **requires a credit card** on file. Expect ~2 small `shared-cpu-1x` machines running (~$7–10/mo total).
- **Vercel** — Hobby plan is free, sufficient for the frontend.
- **Upstash** — free Redis tier (used as Celery broker + cache).
- **MongoDB Atlas** — free M0 cluster, **already set up**. You only need the connection string.

CLIs:

```bash
# Install (macOS)
brew install flyctl
npm i -g vercel
```

One-time logins **you (the user)** must run interactively:

```bash
flyctl auth login
vercel login
```

---

## Step 1 — Provision Upstash Redis

1. Create a database at https://console.upstash.com/ (Redis, region close to Fly `iad` / US-East).
2. Copy the connection URL. Either form works:
   - `redis://default:<PASSWORD>@<HOST>:<PORT>`
   - `rediss://default:<PASSWORD>@<HOST>:<PORT>` (TLS — preferred on Upstash)
3. Save it; you'll reuse the **same URL** for `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` in ocr-backend, and `REDIS_URL` in financial-engine.

> If you use the `rediss://` (TLS) URL with Celery, no extra config is needed here — Celery accepts the `rediss://` scheme directly.

---

## Step 2 — Deploy `ocr-backend` to Fly

```bash
cd ocr-backend

# Create the app without deploying yet, reusing the existing fly.toml.
flyctl launch --no-deploy --copy-config --name fin-uw-ocr-backend
# (equivalent alternative: flyctl apps create fin-uw-ocr-backend)
```

Set all required secrets. These names are the exact env vars read by `ocr-backend/app/config.py`:

```bash
flyctl secrets set \
  GEMINI_API_KEY='<YOUR_GEMINI_API_KEY>' \
  GEMINI_MODEL='gemini-2.5-pro' \
  GEMINI_EMBEDDING_MODEL='text-embedding-004' \
  REDIS_URL='<YOUR_UPSTASH_REDIS_URL>' \
  CELERY_BROKER_URL='<YOUR_UPSTASH_REDIS_URL>' \
  CELERY_RESULT_BACKEND='<YOUR_UPSTASH_REDIS_URL>' \
  MONGODB_URI='<YOUR_MONGODB_ATLAS_URI>' \
  MONGODB_DATABASE='<YOUR_MONGODB_DATABASE>' \
  GCP_PROJECT_ID='<YOUR_GCP_PROJECT_ID>' \
  GCP_STORAGE_BUCKET='<YOUR_GCP_BUCKET>' \
  GCP_TYPE='service_account' \
  GCP_PRIVATE_KEY_ID='<YOUR_GCP_PRIVATE_KEY_ID>' \
  GCP_CLIENT_EMAIL='<YOUR_GCP_CLIENT_EMAIL>' \
  GCP_CLIENT_ID='<YOUR_GCP_CLIENT_ID>' \
  GCP_AUTH_URI='https://accounts.google.com/o/oauth2/auth' \
  GCP_TOKEN_URI='https://oauth2.googleapis.com/token' \
  GCP_AUTH_PROVIDER_X509_CERT_URL='https://www.googleapis.com/oauth2/v1/certs' \
  GCP_CLIENT_X509_CERT_URL='<YOUR_GCP_CLIENT_X509_CERT_URL>' \
  GCP_UNIVERSE_DOMAIN='googleapis.com' \
  --app fin-uw-ocr-backend
```

The `GCP_PRIVATE_KEY` contains literal `\n` escapes and newlines, so set it on its own to avoid quoting issues:

```bash
flyctl secrets set --app fin-uw-ocr-backend \
  GCP_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----
<YOUR_KEY_BODY>
-----END PRIVATE KEY-----
'
```

> `GEMINI_MODEL` and `GEMINI_EMBEDDING_MODEL` are **required** (no default in `config.py`). The other Gemini/Celery/PDF tuning vars (`GEMINI_TEMPERATURE`, `GEMINI_MAX_OUTPUT_TOKENS`, `CHUNK_SIZE_PAGES`, etc.) have safe defaults and can be omitted. `LOG_LEVEL` and `CELERY_WORKER_CONCURRENCY` are already pinned in `fly.toml`. `CORS_ORIGINS` defaults to `*`, so the OCR backend already allows all origins.

Deploy:

```bash
flyctl deploy --app fin-uw-ocr-backend
```

This launches **both** process groups from one image: the `app` machine (HTTP API, auto-sleeps when idle) and the `worker` machine (always-on Celery worker, `min_machines_running` keeps it alive so queued OCR jobs are always picked up). No separate command is needed to start the worker.

Verify:

```bash
curl https://fin-uw-ocr-backend.fly.dev/health
flyctl status --app fin-uw-ocr-backend   # confirm both 'app' and 'worker' machines are present
```

---

## Step 3 — Deploy `financial-engine` to Fly

```bash
cd ../financial-engine

flyctl launch --no-deploy --copy-config --name fin-uw-financial-engine
# (or: flyctl apps create fin-uw-financial-engine)
```

Set secrets (names match `financial-engine/app/config.py`). Point `OCR_BACKEND_URL` at the deployed OCR backend, and set `CORS_ORIGINS` as a **JSON array string** (you can use a placeholder now and tighten it in Step 5 once the Vercel URL exists):

```bash
flyctl secrets set \
  GEMINI_API_KEY='<YOUR_GEMINI_API_KEY>' \
  MONGODB_URI='<YOUR_MONGODB_ATLAS_URI>' \
  MONGODB_DATABASE='<YOUR_MONGODB_DATABASE>' \
  REDIS_URL='<YOUR_UPSTASH_REDIS_URL>' \
  OCR_BACKEND_URL='https://fin-uw-ocr-backend.fly.dev' \
  GCP_PROJECT_ID='<YOUR_GCP_PROJECT_ID>' \
  GCP_STORAGE_BUCKET='<YOUR_GCP_BUCKET>' \
  GCP_TYPE='service_account' \
  GCP_PRIVATE_KEY_ID='<YOUR_GCP_PRIVATE_KEY_ID>' \
  GCP_CLIENT_EMAIL='<YOUR_GCP_CLIENT_EMAIL>' \
  GCP_CLIENT_ID='<YOUR_GCP_CLIENT_ID>' \
  GCP_AUTH_URI='https://accounts.google.com/o/oauth2/auth' \
  GCP_TOKEN_URI='https://oauth2.googleapis.com/token' \
  GCP_AUTH_PROVIDER_X509_CERT_URL='https://www.googleapis.com/oauth2/v1/certs' \
  GCP_CLIENT_X509_CERT_URL='<YOUR_GCP_CLIENT_X509_CERT_URL>' \
  GCP_UNIVERSE_DOMAIN='googleapis.com' \
  CORS_ORIGINS='["https://your-frontend.vercel.app"]' \
  --app fin-uw-financial-engine

# Set the GCP private key separately (multi-line):
flyctl secrets set --app fin-uw-financial-engine \
  GCP_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----
<YOUR_KEY_BODY>
-----END PRIVATE KEY-----
'
```

> `GEMINI_MODEL` defaults to `gemini-2.5-pro` in `config.py`, so it's optional here. Leave `ENABLE_REANALYZE_ENDPOINTS` unset (defaults to `False`) unless you need the dev `/api/v1/dev/*` endpoints in production.

Deploy:

```bash
flyctl deploy --app fin-uw-financial-engine
curl https://fin-uw-financial-engine.fly.dev/health
```

---

## Step 4 — Deploy `ocr-frontend` to Vercel

```bash
cd ../ocr-frontend

vercel          # first run: link/create the project, deploy a preview
```

Set the environment variables (these are the names the Next.js code reads). Use `vercel env add <NAME> production` (it prompts for the value), or set them in the Vercel dashboard under Project → Settings → Environment Variables:

```bash
vercel env add GEMINI_API_KEY production
# value: <YOUR_GEMINI_API_KEY>

vercel env add NEXT_PUBLIC_OCR_API_URL production
# value: https://fin-uw-ocr-backend.fly.dev

vercel env add NEXT_PUBLIC_FINANCIAL_API_URL production
# value: https://fin-uw-financial-engine.fly.dev

vercel env add NEXT_PUBLIC_API_URL production
# value: https://fin-uw-financial-engine.fly.dev   (optional / legacy alias)

vercel env add NEXT_PUBLIC_ENABLE_REANALYZE production
# value: false   (optional)
```

> `NEXT_PUBLIC_*` vars are **build-time** inlined — after changing any of them you must redeploy for the change to take effect.

Promote to production:

```bash
vercel --prod
```

Note the resulting production URL (e.g. `https://ocr-frontend-xxxx.vercel.app`) for the next step.

---

## Step 5 — Wire up CORS

The frontend's real Vercel URL is only known after Step 4. Update the financial-engine to allow it:

```bash
flyctl secrets set --app fin-uw-financial-engine \
  CORS_ORIGINS='["https://<your-actual-frontend>.vercel.app"]'

flyctl deploy --app fin-uw-financial-engine
```

(Setting a secret already triggers a rolling restart; the explicit `deploy` guarantees the new value is live.)

- **ocr-backend** already allows all origins (`CORS_ORIGINS` defaults to `*`), so no change is needed there.
- If you use a custom domain on Vercel, add it to the `CORS_ORIGINS` array too: `'["https://app.example.com","https://<...>.vercel.app"]'`.

Final smoke test: open the Vercel URL, upload a PDF, and confirm OCR progress advances (worker is processing) and the financial analysis renders (financial-engine reachable + CORS OK).

---

## Gotchas / Not-Truly-Free

- **Fly.io is not free.** A credit card is required and there is no free allowance; two `shared-cpu-1x` / 512 MB machines (one API, one worker) run roughly **$7–10/mo**. The API machine auto-sleeps when idle (`auto_stop_machines`), but the worker has `min_machines_running` keeping it **always-on** by design — it must stay up to pick up queued OCR jobs, so you cannot scale it to zero without breaking processing.
- **Gemini free tier has rate limits.** The free API key is rate-limited (requests/min and tokens/day) and can return 429s under load; large or concurrent PDFs may need a paid Gemini tier.
- **GCP Cloud Storage** free tier is ~5 GB; uploaded PDFs accumulate there, so prune old objects or expect to pay past the quota.
- **Upstash free Redis** has a daily command cap; heavy Celery polling can hit it.
- **MongoDB Atlas M0** is free but capped at 512 MB storage and shared throughput.
- **Cold starts:** the auto-sleeping API machine adds a few seconds of latency on the first request after idle.

---

## Quick Redeploy Reference

```bash
# Backends
cd ocr-backend       && flyctl deploy --app fin-uw-ocr-backend
cd financial-engine  && flyctl deploy --app fin-uw-financial-engine

# Frontend
cd ocr-frontend      && vercel --prod

# Inspect / debug
flyctl logs   --app fin-uw-ocr-backend
flyctl status --app fin-uw-ocr-backend
flyctl secrets list --app fin-uw-ocr-backend   # names only, values hidden
```
