---
title: UW OCR Backend
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---

OCR backend (FastAPI + Celery + in-container Redis) for the financial underwriting app.
Document text extraction via Google Gemini. Set secrets in the Space Settings tab:
`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `MONGODB_URI`,
`MONGODB_DATABASE`, and the `GCP_*` storage credentials.
