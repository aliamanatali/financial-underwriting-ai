#!/usr/bin/env python3
"""
Push secrets from the local .env files into the two Hugging Face Spaces, then restart them.

YOU run this on your own machine (it reads your credentials and sends them only to your
own HF Spaces). It is intentionally not run by the assistant.

Usage:
    pip install -U huggingface_hub python-dotenv
    HF_TOKEN=hf_xxx python3 hf-deploy/set-secrets.py

Re-run any time you rotate a credential.
"""
import os
import sys
from dotenv import dotenv_values
from huggingface_hub import HfApi

TOKEN = os.environ.get("HF_TOKEN")
if not TOKEN:
    sys.exit("Set HF_TOKEN env var first:  HF_TOKEN=hf_xxx python3 hf-deploy/set-secrets.py")

api = HfApi(token=TOKEN)
user = api.whoami()["name"]

# Redis/Celery must point at each container's internal redis (set via Dockerfile ENV).
# Never override them with values from .env.
EXCLUDE = {"REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND",
           "CELERY_WORKER_CONCURRENCY", "PORT"}

OCR_URL = f"https://{user}-uw-ocr-backend.hf.space"
FIN_URL = f"https://{user}-uw-financial-engine.hf.space"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def push(space, env_rel, extra=None):
    repo_id = f"{user}/{space}"
    vals = dotenv_values(os.path.join(ROOT, env_rel))
    merged = {**vals, **(extra or {})}
    n = 0
    for k, v in merged.items():
        if not k or v is None or v == "" or k in EXCLUDE:
            continue
        api.add_space_secret(repo_id=repo_id, key=k, value=v)
        n += 1
    print(f"  {repo_id}: set {n} secrets")
    api.restart_space(repo_id=repo_id)
    print(f"  {repo_id}: restart triggered")


print(f"HF user: {user}")
print("OCR backend Space:")
push("uw-ocr-backend", "ocr-backend/.env")
print("Financial engine Space:")
# OCR_BACKEND_URL points the financial engine at the OCR Space.
# CORS_ORIGINS: add your Vercel URL once the frontend is deployed (re-run with it set in .env).
push("uw-financial-engine", "financial-engine/.env", extra={"OCR_BACKEND_URL": OCR_URL})

print()
print("Done. Health-check in ~1-2 min (after the Spaces rebuild):")
print(f"  {OCR_URL}/health")
print(f"  {FIN_URL}/health")
