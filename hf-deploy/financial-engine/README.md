---
title: UW Financial Engine
emoji: 📊
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8001
pinned: false
---

Financial Engine (FastAPI + in-container Redis cache) for the underwriting app.
Runs the deterministic 5-step CRE financial model. Set secrets in the Space Settings tab:
`GEMINI_API_KEY`, `MONGODB_URI`, `MONGODB_DATABASE`, the `GCP_*` credentials,
`OCR_BACKEND_URL` (the OCR Space URL), and `CORS_ORIGINS` (JSON array incl. the Vercel URL).
