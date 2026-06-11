#!/usr/bin/env bash
# Assembles ready-to-push Hugging Face Space repos under hf-deploy/build/.
# Each Space = the service's app code + the HF Dockerfile/start.sh/README from this folder.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HF="$ROOT/hf-deploy"
OUT="$HF/build"

rm -rf "$OUT"
mkdir -p "$OUT/ocr-backend" "$OUT/financial-engine"

# --- OCR backend Space ---
cp -r "$ROOT/ocr-backend/app"              "$OUT/ocr-backend/app"
cp    "$ROOT/ocr-backend/requirements.txt" "$OUT/ocr-backend/"
cp    "$HF/ocr-backend/Dockerfile"         "$OUT/ocr-backend/"
cp    "$HF/ocr-backend/start.sh"           "$OUT/ocr-backend/"
cp    "$HF/ocr-backend/README.md"          "$OUT/ocr-backend/"
chmod +x "$OUT/ocr-backend/start.sh"

# --- Financial Engine Space ---
cp -r "$ROOT/financial-engine/app"              "$OUT/financial-engine/app"
cp    "$ROOT/financial-engine/requirements.txt" "$OUT/financial-engine/"
cp    "$HF/financial-engine/Dockerfile"         "$OUT/financial-engine/"
cp    "$HF/financial-engine/start.sh"           "$OUT/financial-engine/"
cp    "$HF/financial-engine/README.md"          "$OUT/financial-engine/"
chmod +x "$OUT/financial-engine/start.sh"

# Drop any local pyc/caches that might have been copied.
find "$OUT" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "Assembled Space repos:"
echo "  $OUT/ocr-backend"
echo "  $OUT/financial-engine"
