# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

Three independently-deployed services that must all run together:

| Service | Directory | Port | Stack |
|---|---|---|---|
| OCR Backend | `ocr-backend/` | 8000 | Python FastAPI + Celery |
| Financial Engine | `financial-engine/` | 8001 | Python FastAPI |
| Frontend | `ocr-frontend/` | 3000 | Next.js 16 / React 19 / TypeScript |

**Data flow:** User uploads PDF via Frontend → OCR Backend stores to GCP Cloud Storage and queues a Celery task → Celery worker sends PDF to Gemini Vision API in chunks → extracted text saved to MongoDB → Frontend triggers Financial Engine analysis → Financial Engine fetches text, normalizes expenses (Gemini + Redis cache), runs deterministic 5-step financial model, generates Excel/PDF output.

**Infrastructure dependencies:** Redis (Celery broker + progress cache), MongoDB (document/analysis metadata), GCP Cloud Storage (files).

## Running the Services

All three services must run simultaneously in separate terminals.

```bash
# Terminal 1 – OCR Backend API
cd ocr-backend && source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 – Celery worker (required for OCR processing)
cd ocr-backend && source venv/bin/activate
celery -A app.celery_app worker --loglevel=info

# Terminal 3 – Financial Engine API
cd financial-engine && source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Terminal 4 – Frontend dev server
cd ocr-frontend && npm run dev
```

Redis must be running before the backends start:
```bash
brew services start redis   # macOS
```

## Setup

```bash
# OCR Backend
cd ocr-backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set GEMINI_API_KEY, GCP credentials, REDIS_URL, MONGODB_URI

# Financial Engine
cd financial-engine && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# configure .env: GEMINI_API_KEY, OCR_BACKEND_URL, MONGODB_URI, REDIS_URL

# Frontend
cd ocr-frontend && npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_OCR_API_URL, NEXT_PUBLIC_FINANCIAL_API_URL
```

## Common Commands

```bash
# OCR Backend
pytest                        # run tests
curl http://localhost:8000/health

# Financial Engine
pytest
pytest -p pytest_asyncio      # async tests

# Frontend
npm run lint
npm run build
npm start                     # production server

# Root-level integration tests
python test_all_systems.py
python test_normalization.py
```

## Key Code Locations

**OCR Backend** (`ocr-backend/app/`):
- `main.py` – FastAPI app entry, CORS, routers
- `services/gemini_service.py` – Gemini Vision OCR; DocuMind prompt, chunking (15 pages default, 5 for dense), semaphore(4) concurrency
- `services/pdf_chunking_service.py` – PDF splitting logic
- `tasks/document_tasks.py` – Celery task: retrieves file, chunks, calls Gemini, merges, stores
- `services/redis_progress.py` – SSE-based real-time progress (0–100%) via Redis

**Financial Engine** (`financial-engine/app/services/`):
- `financial_service.py` – Core 5-step calculation: GPR → EGI → NOI → Debt Service → IRR/MOIC/CoC (deterministic, no AI)
- `normalization_service.py` – Maps raw expense text → `StandardExpenseCategory` enum via Gemini; two-tier cache (Redis 30-day TTL + MongoDB)
- `ingestion_service.py` – Parses OCR text into `PropertyMeta`, `RentRollItem`, `StandardizedExpense` Pydantic models
- `synthesis_service.py` – Merges multi-document data; enforces priority: OM > T12/P&L > raw bills
- `gemini_client.py` – LLM calls: gemini-2.5-pro (accuracy), gemini-3-flash-preview (chat/speed); retry + circuit breaker

**Frontend** (`ocr-frontend/`):
- `app/page.tsx` – Upload page and main dashboard
- `app/documents/` – Document detail and analysis view
- `lib/` – API client and TypeScript types for both backends

## Financial Model (5 Steps)

1. **Revenue:** Gross Potential Rent → Loss to Lease → Vacancy Loss → EGI
2. **Expenses:** Normalize + deduplicate; recalculate taxes (price × 1.2%) and mgmt fees (EGI × 4%)
3. **NOI:** EGI − Total Expenses; Entry Cap Rate = NOI / Purchase Price
4. **Debt Service:** Loan × interest rate / 12; Pre-tax Cash Flow = NOI − DS
5. **Returns:** IRR (5-year hold), MOIC, Cash-on-Cash — solver uses user-supplied deal parameters

## Business Rules

**38% Expense Ratio Floor** (`financial_service.py:1231-1240`): If pro forma operating expenses sum to less than 38% of EGI, Capital Reserves are added to make up the shortfall. The target ratio is `DealParameters.expense_ratio_target` (default 0.38 in `schemas.py:206`). This is a CRE underwriting convention that prevents unrealistically optimistic expense projections. The shortfall is logged to the audit trail as "38% Rule — Added Reserves to hit 38% Expense Ratio." The Capital Reserves line in the pro forma breakdown is synthetic when this rule fires — it represents the gap between actual extracted expenses and the 38% floor, not an actual reserve amount from the documents.

## Environment Variables

**Required in both backends:**
- `GEMINI_API_KEY`
- `REDIS_URL` (default: `redis://localhost:6379/0`)
- `MONGODB_URI`
- GCP credentials: `GCP_PROJECT_ID`, `GCP_STORAGE_BUCKET`, `GCP_CLIENT_EMAIL`, `GCP_PRIVATE_KEY`

**Financial Engine only:**
- `OCR_BACKEND_URL` (default: `http://localhost:8000`)

**Frontend:**
- `NEXT_PUBLIC_OCR_API_URL`
- `NEXT_PUBLIC_FINANCIAL_API_URL`
