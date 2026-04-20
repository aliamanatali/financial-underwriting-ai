"""
Dev-only re-analyze endpoint.

Gated by ENABLE_REANALYZE_ENDPOINTS=True in .env. The router is
conditionally registered in main.py — when the flag is False the
route literally does not exist (404), not just a 403.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query, Request
from typing import Any, Dict, List
from enum import IntEnum
import asyncio
import logging

from app.services.storage_service import storage_service
from app.services.normalization_service import NormalizationService
from app.models.schemas import DealPackage, NormalizedDataItem, DealParameters
from app.dependencies import (
    get_gemini_service,
    get_openai_service,
    get_progress_service,
    get_explainability_service,
    get_batch_logging_service,
)

router = APIRouter(prefix="/api/v1/dev", tags=["Dev Tools"])
logger = logging.getLogger(__name__)


class ReanalyzeLevel(IntEnum):
    """Escalating re-run levels. Each level is a superset of the one below.

    1 - Financial model only (fastest, no LLM calls)
    2 - Normalization + financial model (uses cached classifications)
    3 - Normalization + financial model, cache busted (fresh LLM classifications)
    4 - Full re-extraction from stored OCR text + everything downstream
    """
    FINANCIAL_MODEL = 1
    NORMALIZATION = 2
    NORMALIZATION_CACHE_BUST = 3
    FULL_RE_EXTRACTION = 4


@router.post("/reanalyze/{package_id}")
async def reanalyze_package(
    package_id: str,
    request: Request,
    level: int = Query(1, ge=1, le=4, description="Re-run level: 1=model, 2=normalize, 3=normalize+cache bust, 4=full re-extract"),
    gemini_service=Depends(get_gemini_service),
    openai_service=Depends(get_openai_service),
    progress_service=Depends(get_progress_service),
    explainability_service=Depends(get_explainability_service),
    batch_logging_service=Depends(get_batch_logging_service),
):
    """Re-run analysis on an already-uploaded deal package.

    Validates inputs and returns immediately. The actual work runs as a
    background asyncio task so it doesn't block the server from handling
    other requests (dashboard, SSE streams, etc.). Progress is reported
    via SSE — the frontend never needs the HTTP response body.
    """
    # Parse optional deal_parameters from request body (or use defaults)
    deal_parameters: Dict[str, Any] = {}
    try:
        body = await request.json()
        if isinstance(body, dict):
            deal_parameters = body
    except Exception:
        pass

    # Load the package
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)

    # ---------- Input validation per level ----------
    if level in (1, 2, 3):
        if not package.financials_data:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Level {level} requires stored financials_data (extracted expenses) "
                    f"but package {package_id} has none. Run a Level 4 re-extraction first, "
                    f"or upload and normalize the package via the normal flow."
                ),
            )

    if level == 4:
        has_documents = any(
            len(docs) > 0 for docs in package.documents.values()
        )
        if not has_documents:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Level 4 requires stored documents (OCR text / files) "
                    f"but package {package_id} has no document metadata. "
                    f"The package may need to be re-uploaded."
                ),
            )

    # Flip status + seed progress synchronously BEFORE returning, so the frontend
    # never races the background task. Without this, the analysis page can redirect
    # the user back to /analysis (status still shows "completed" from the prior run)
    # before _run_reanalyze gets a chance to flip it to "in_progress".
    await storage_service.update_deal_package_status(package_id, "in_progress")
    await progress_service.update_progress(package_id, 1, f"Dev re-analyze queued (level {level})")

    # Kick off the work in the background so the HTTP response returns immediately
    asyncio.create_task(
        _run_reanalyze(
            package=package,
            package_id=package_id,
            level=level,
            deal_parameters=deal_parameters,
            gemini_service=gemini_service,
            openai_service=openai_service,
            progress_service=progress_service,
            explainability_service=explainability_service,
            batch_logging_service=batch_logging_service,
        )
    )

    return {"package_id": package_id, "level": level, "status": "started"}


async def _run_reanalyze(
    package: DealPackage,
    package_id: str,
    level: int,
    deal_parameters: Dict[str, Any],
    gemini_service,
    openai_service,
    progress_service,
    explainability_service,
    batch_logging_service,
):
    """Background coroutine that performs the actual re-analysis work."""
    try:
        await progress_service.update_progress(
            package_id, 5, f"Dev re-analyze started (level {level})"
        )

        # ---------- Level 3: Package-scoped cache bust ----------
        if level == 3:
            await _bust_package_cache(package)

        # ---------- Level 4: Full re-extraction ----------
        if level == 4:
            package = await _re_extract_from_documents(
                package, package_id, gemini_service, progress_service, batch_logging_service
            )

        # ---------- Level 2/3: Re-normalize ----------
        if level >= 2:
            package = await _re_normalize(
                package, package_id, gemini_service, progress_service, batch_logging_service
            )

        # ---------- Level 1+: Re-run financial model ----------
        from app.api.routes.multi_document import _analyze_deal_package_logic

        logger.info(f"[Dev reanalyze] Running financial model for {package_id} (level={level})")
        await progress_service.update_progress(package_id, 60, "Running financial model...")

        await _analyze_deal_package_logic(
            package_id=package_id,
            deal_parameters=deal_parameters or DealParameters().model_dump(),
            gemini_service=gemini_service,
            openai_service=openai_service,
            progress_service=progress_service,
            explainability_service=explainability_service,
            progress_base=60,
        )

        await storage_service.update_deal_package_status(package_id, "completed")
        await progress_service.update_progress(package_id, 100, "Dev re-analyze complete")

    except Exception as e:
        logger.error(f"[Dev reanalyze] Failed for {package_id}: {e}", exc_info=True)
        await storage_service.update_deal_package_status(package_id, "failed")
        await progress_service.update_progress(package_id, -1, f"Re-analyze failed: {e}")


async def _bust_package_cache(package: DealPackage):
    """Invalidate normalization cache entries scoped to this package's expenses.

    Package-scoped, not global: iterates the package's financials_data,
    computes cache keys for each expense description, and deletes those
    specific keys from Redis and MongoDB. Other packages' cached
    classifications are unaffected.
    """
    descriptions = set()
    for item in package.financials_data:
        if item.raw_text:
            descriptions.add(item.raw_text)

    if not descriptions:
        logger.info("[Dev reanalyze] No expense descriptions to bust cache for")
        return

    logger.info(f"[Dev reanalyze] Busting cache for {len(descriptions)} expense descriptions")

    for desc in descriptions:
        try:
            await NormalizationService.invalidate_cache_entry(desc)
        except Exception as e:
            logger.warning(f"[Dev reanalyze] Cache bust failed for '{desc}': {e}")

    logger.info(f"[Dev reanalyze] Cache bust complete for {len(descriptions)} entries")


async def _re_normalize(
    package: DealPackage,
    package_id: str,
    gemini_service,
    progress_service,
    batch_logging_service,
):
    """Re-run normalization on the package's existing financials_data.

    Converts each NormalizedDataItem back to the raw dict format expected
    by normalize_expenses_async, re-classifies, and writes updated
    categories back onto the items.
    """
    logger.info(f"[Dev reanalyze] Re-normalizing {len(package.financials_data)} items for {package_id}")
    await progress_service.update_progress(package_id, 30, "Re-normalizing expenses...")

    norm_service = NormalizationService(
        llm_service=gemini_service, batch_logging_service=batch_logging_service
    )

    # Build raw expense dicts matching the format normalize_expenses_async expects
    raw_expenses = []
    for item in package.financials_data:
        if not item.raw_text:
            continue
        section_ctx = "unknown"
        if item.metadata and item.metadata.get("section_context"):
            section_ctx = item.metadata["section_context"]
        raw_expenses.append({
            "description": item.raw_text,
            "amount": (item.metadata.get("amount", 0) if item.metadata else 0) or 0,
            "section_context": section_ctx,
        })

    if raw_expenses:
        # Re-run full normalization (cache-aware for L2, cache-busted for L3)
        normalized_results = await norm_service.normalize_expenses_async(raw_expenses)

        # Build lookup from original_text -> new classification
        result_by_desc: Dict[str, Any] = {}
        for res in normalized_results:
            if hasattr(res, "original_text") and res.original_text:
                result_by_desc[res.original_text] = res

        # Apply updated classifications back to financials_data
        for item in package.financials_data:
            if item.raw_text and item.raw_text in result_by_desc:
                updated = result_by_desc[item.raw_text]
                if hasattr(updated, "mapped_category") and updated.mapped_category:
                    # ExpenseCategory inherits from (str, Enum), but str(member)
                    # returns "ExpenseCategory.CONTRACT_SERVICES" (the enum repr),
                    # not the value "Contract Services". Use .value.
                    mc = updated.mapped_category
                    item.normalized_value = mc.value if hasattr(mc, "value") else str(mc)
                if hasattr(updated, "confidence") and updated.confidence is not None:
                    item.confidence = updated.confidence
                if hasattr(updated, "category_group") and updated.category_group:
                    item.category_group = updated.category_group

    # Persist only the fields that changed (avoids rewriting the full 5MB+ document)
    package.normalized_data = package.financials_data
    financials_dump = [item.model_dump() if hasattr(item, "model_dump") else item for item in package.financials_data]
    await storage_service.partial_update_deal_package(package_id, {
        "financials_data": financials_dump,
        "normalized_data": financials_dump,
    })

    await progress_service.update_progress(package_id, 55, "Re-normalization complete")
    return package


async def _re_extract_from_documents(
    package: DealPackage,
    package_id: str,
    gemini_service,
    progress_service,
    batch_logging_service,
):
    """Re-extract financials and rent roll from stored document files.

    Uses the same extraction pipeline as normalize_package_documents
    but skips file upload — reads from GCP storage.
    """
    from app.services.multi_document_extraction_service import MultiDocumentExtractionService
    from app.services.synthesis_service import SynthesisService
    from app.models.schemas import DocumentType
    from pathlib import Path
    import asyncio
    import uuid

    logger.info(f"[Dev reanalyze] Full re-extraction for {package_id}")
    await progress_service.update_progress(package_id, 10, "Re-extracting from stored documents...")

    extraction_service = MultiDocumentExtractionService(
        gemini_service=gemini_service, batch_logging_service=batch_logging_service
    )

    # Load document files from storage
    om_docs = []
    financial_docs = []
    rent_roll_docs = []

    for doc_type, doc_list in package.documents.items():
        for doc_meta in doc_list:
            doc_id = doc_meta.document_id
            filename = doc_meta.filename
            extension = Path(filename).suffix
            storage_path = f"deal-packages/{package_id}/documents/{doc_id}{extension}"

            try:
                content = await storage_service.get_document_file(storage_path)
                if not content:
                    logger.warning(f"[Dev reanalyze] No content for {filename}")
                    continue
            except Exception as e:
                logger.warning(f"[Dev reanalyze] Failed to load {filename}: {e}")
                continue

            if filename.lower().endswith((".xlsx", ".xls")):
                file_type = "excel"
            elif filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
                file_type = "visual"
            elif filename.lower().endswith(".csv"):
                file_type = "csv"
            else:
                continue

            doc_info = {
                "content": content,
                "filename": filename,
                "type": file_type,
                "document_category": doc_meta.document_type,
                "document_id": doc_meta.document_id,
            }

            if doc_meta.document_type == DocumentType.RENT_ROLL:
                rent_roll_docs.append(doc_info)
            elif doc_meta.document_type == DocumentType.OFFERING_MEMORANDUM:
                om_docs.append(doc_info)
                financial_docs.append(doc_info)
            else:
                financial_docs.append(doc_info)

    await progress_service.update_progress(package_id, 15, f"Loaded {len(financial_docs) + len(rent_roll_docs)} documents")

    # Determine flow — exactly one OM triggers OM-Driven; zero or multiple OMs
    # fall back to MULTI_SOURCE (multiple OM classifications usually indicate a
    # false positive from a flyer/appraisal misclassified alongside the real OM).
    if len(om_docs) == 1:
        package.underwriting_flow = "OM_DRIVEN"
        rent_roll_docs = []
        financial_docs = [d for d in financial_docs if d.get("document_category") == DocumentType.OFFERING_MEMORANDUM]
    else:
        if len(om_docs) > 1:
            logger.info(f"[Dev reanalyze] {len(om_docs)} OMs detected — falling back to MULTI_SOURCE.")
            # Override document_category so the extractor routes these through
            # the generic financial pipeline instead of the OM-specific proforma
            # path (which hallucinates on misclassified flyers/appraisals).
            for d in financial_docs:
                if d.get("document_category") == DocumentType.OFFERING_MEMORANDUM:
                    d["document_category"] = DocumentType.FINANCIALS
        package.underwriting_flow = "MULTI_SOURCE"

    # Progress adapter that scales percentages into the 15-45% range
    # and forwards file-level details for the processing UI
    class DevProgressAdapter:
        async def update_progress(self, task_id, pct, msg, details=None):
            scaled = 15 + int(pct * 0.30)
            await progress_service.update_progress(package_id, scaled, msg, details=details)

    adapter = DevProgressAdapter()
    total_docs = len(financial_docs) + len(rent_roll_docs)

    # Extract financials
    all_financials = []
    financial_completed_files = []
    if financial_docs:
        result = await extraction_service.process_financial_documents(
            financial_docs,
            progress_service=adapter,
            task_id=package_id,
            progress_start=0, progress_end=100,
            initial_completed_files=[],
            total_files_override=total_docs,
        )
        extracted_expenses, extracted_proforma, financial_completed_files, verified_year, is_partial = result
        all_financials = extracted_expenses
        package.primary_fiscal_year = verified_year
        package.is_partial_year = is_partial
        if extracted_proforma:
            package.om_proforma_data = extracted_proforma

    # Extract rent roll (carry forward completed files so progress stays consistent)
    extracted_rent_roll = []
    if rent_roll_docs:
        extracted_rent_roll, _ = await extraction_service.process_rent_roll_documents(
            rent_roll_docs,
            progress_service=adapter,
            task_id=package_id,
            progress_start=0, progress_end=100,
            initial_completed_files=financial_completed_files,
            total_files_override=total_docs,
        )

    # Assign IDs and document_id metadata
    filename_to_id = {}
    for doc_list in package.documents.values():
        for doc_meta in doc_list:
            filename_to_id[doc_meta.filename] = doc_meta.document_id

    for item in all_financials:
        item.id = str(uuid.uuid4())
        if item.metadata is None:
            item.metadata = {}
        if "document_id" not in item.metadata or not item.metadata["document_id"]:
            if item.source_document in filename_to_id:
                item.metadata["document_id"] = filename_to_id[item.source_document]

    # Extract OM rent roll items
    synthesis_service = SynthesisService()
    om_expenses = [e for e in all_financials if any(
        doc_meta.document_type == DocumentType.OFFERING_MEMORANDUM
        for doc_list in package.documents.values()
        for doc_meta in doc_list
        if doc_meta.filename == e.source_document
    )]
    om_rr = synthesis_service.extract_rent_roll_from_normalized_items(om_expenses)
    if om_rr:
        for item in om_rr:
            if item.source_file and "OM" not in item.source_file.upper():
                item.source_file = f"OM - {item.source_file}"
        extracted_rent_roll.extend(om_rr)

    package.financials_data = all_financials
    package.rent_roll_data = extracted_rent_roll
    package.normalized_data = all_financials
    package.normalization_status = "in_progress"

    financials_dump = [item.model_dump() if hasattr(item, "model_dump") else item for item in all_financials]
    rent_roll_dump = [item.model_dump() if hasattr(item, "model_dump") else item for item in extracted_rent_roll]
    await storage_service.partial_update_deal_package(package_id, {
        "financials_data": financials_dump,
        "rent_roll_data": rent_roll_dump,
        "normalized_data": financials_dump,
        "normalization_status": "in_progress",
        "primary_fiscal_year": package.primary_fiscal_year,
        "is_partial_year": package.is_partial_year,
        "underwriting_flow": package.underwriting_flow,
    })
    await progress_service.update_progress(package_id, 50, "Re-extraction complete")

    return package
