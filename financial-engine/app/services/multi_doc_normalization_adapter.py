"""
Extraction-to-normalization adapter for the multi-document flow.

Sits between MultiDocumentExtractionService's raw extraction output and
NormalizationService's normalize_expenses_async input. Handles:

1. Pre-classification cleanup (rules from multi-doc's _validate_and_fix_extraction)
2. Field mapping (raw_text → description, type → section_context)
3. Total line suppression
4. Post-normalization conversion (StandardizedExpense → NormalizedDataItem)
"""

import logging
from typing import List, Dict, Any, Optional

from app.models.schemas import (
    ExpenseCategory, CategoryGroup, DataClassification,
    NormalizedDataItem, StandardizedExpense,
)
from app.services.category_group_mapping import get_category_group

logger = logging.getLogger(__name__)


# ── Type → section_context mapping ──────────────────────────────────────────

_TYPE_TO_SECTION = {
    "revenue": "income",
    "expense": "expense",
    "capex": "capex",
}


# ── Pre-classification keywords ────────────────────────────────────────────

_PAST_DUE_KEYWORDS = ["past due", "delinquent", "arrears", "outstanding balance", "overdue"]

_CAPEX_KEYWORDS = [
    "electrical upgrade", "new service", "panel upgrade", "major renovation",
    "roof replacement", "hvac replacement", "elevator modernization",
    "cylinder replacement", "retaining wall", "seismic", "foundation work",
]

_HIGH_DOLLAR_CAPEX_KEYWORDS = [
    "proposal", "modernization", "installation", "replacement", "offer to purchase",
]

_PERMIT_CAPEX_QUALIFIERS = [
    "construction", "renovation", "upgrade", "installation",
    "replacement", "new", "capital", "electrical",
]

_DEPOSIT_KEYWORDS = [
    "deposit", "earnest money", "escrow",
]

_TOTAL_LINE_KEYWORDS = [
    "total charges", "total due", "amount due", "total amount", "current charges",
]

_STUDENT_BLACKLIST = [
    "tuition", "scholarship", "financial aid", "student services",
    "semester", "undergraduate resident",
]


# ═══════════════════════════════════════════════════════════════════════════
# A.  Extraction → NormalizationService input
# ═══════════════════════════════════════════════════════════════════════════

def adapt_extraction_to_normalization(
    raw_expenses: List[Dict[str, Any]],
    total_units: int = 0,
) -> List[Dict[str, Any]]:
    """Transform multi-doc extraction output into NormalizationService input.

    Applies pre-classification rules (type/subtype hints), maps fields,
    and suppresses total lines. Does NOT call NormalizationService itself.
    """
    adapted = []

    for exp in raw_expenses:
        raw_text = exp.get("raw_text", "")
        text_lower = raw_text.lower()
        item_type = exp.get("type", "expense")
        subtype = exp.get("subtype", "")
        amount = exp.get("amount", 0) or 0

        # ── Rule 11: Total line suppression (delete before anything else) ──
        if "total" in text_lower and item_type == "expense":
            if any(kw in text_lower for kw in _TOTAL_LINE_KEYWORDS):
                logger.info(f"Adapter: suppressing total line: '{raw_text}'")
                continue

        # ── Rule 0: Student blacklist ──
        if any(kw in text_lower for kw in _STUDENT_BLACKLIST):
            logger.warning(f"Adapter: student blacklist hit: '{raw_text}'")
            item_type = "other"
            subtype = "tuition_ignored"

        # ── Rule 1: Past due → receivable ──
        elif any(kw in text_lower for kw in _PAST_DUE_KEYWORDS):
            if item_type == "revenue":
                logger.info(f"Adapter: past-due revenue corrected: '{raw_text}'")
                item_type = "receivable"
                subtype = "past_due"

        # ── Rule 2: Late fees subtype ──
        elif any(kw in text_lower for kw in ["late fee", "late charge", "penalty", "nsf", "check return"]):
            if item_type == "revenue":
                subtype = "late_fee"

        # ── Rule 3: Parking/laundry/pet → other_income subtype ──
        elif any(kw in text_lower for kw in ["laundry", "parking", "garage", "pet fee", "pet rent", "storage"]):
            if item_type == "revenue":
                subtype = "other_income"

        # ── Rule 4: Reimbursements subtype ──
        elif any(kw in text_lower for kw in ["utility reimbursement", "cam reimbursement", "reimbursement"]):
            if item_type == "revenue":
                subtype = "reimbursement"

        # ── Rule 5: CapEx keywords ──
        elif any(kw in text_lower for kw in _CAPEX_KEYWORDS):
            if item_type == "expense":
                item_type = "capex"

        # ── Rule 7: High-dollar CapEx heuristic ──
        elif any(kw in text_lower for kw in _HIGH_DOLLAR_CAPEX_KEYWORDS):
            if amount and amount > 5000:
                item_type = "capex"

        # ── Rule 6: Qualified permit fees ──
        elif "permit" in text_lower:
            if item_type == "expense" and any(q in text_lower for q in _PERMIT_CAPEX_QUALIFIERS):
                item_type = "capex"

        # ── Rule 9: Deposits ──
        elif any(kw in text_lower for kw in _DEPOSIT_KEYWORDS):
            if item_type == "expense":
                item_type = "property_info"

        # ── Rule 10: Rent subtype fallback ──
        elif any(kw in text_lower for kw in ["monthly rent", "rent", "rental income"]) and "late" not in text_lower:
            if item_type == "revenue" and not subtype:
                subtype = "rent"

        # ── Map type → section_context ──
        section_context = _TYPE_TO_SECTION.get(item_type, "unknown")

        adapted.append({
            "description": raw_text,
            "amount": amount,
            "section_context": section_context,
            "source_snippet": exp.get("source_snippet"),
            "page_number": exp.get("page_number"),
            "bbox": exp.get("bbox"),
            "source_document": exp.get("source_document"),
            "document_id": exp.get("document_id"),
            "expense_year": exp.get("expense_year"),
            "amount_t3": exp.get("amount_t3"),
            "amount_t6": exp.get("amount_t6"),
            "amount_t9": exp.get("amount_t9"),
            "text_type": exp.get("text_type", "Computerized"),
            # Carry original type/subtype for audit trail
            "_original_type": item_type,
            "_original_subtype": subtype,
        })

    return adapted


# ═══════════════════════════════════════════════════════════════════════════
# B.  NormalizationService output → NormalizedDataItem
# ═══════════════════════════════════════════════════════════════════════════

def adapt_normalization_to_normalized_item(
    standardized: StandardizedExpense,
    original_raw: Dict[str, Any],
) -> NormalizedDataItem:
    """Convert a StandardizedExpense from NormalizationService into a
    NormalizedDataItem for the multi-doc verification UI.
    """
    # Derive category_group from the mapped_category enum
    if isinstance(standardized.mapped_category, ExpenseCategory):
        category_enum = standardized.mapped_category
    else:
        try:
            category_enum = ExpenseCategory(standardized.mapped_category)
        except ValueError:
            category_enum = ExpenseCategory.UNCATEGORIZED

    group = get_category_group(category_enum)

    # Derive field_type from category_group (matches multi_document_extraction_service.py:1976-1980)
    if group == CategoryGroup.PROPERTY_INFO:
        field_type = "property_meta"
    elif group == CategoryGroup.REVENUE:
        field_type = "revenue_item"
    else:
        field_type = "expense_category"

    raw_text = original_raw.get("raw_text", standardized.original_text)
    amount = original_raw.get("amount", standardized.amount)

    metadata = {
        "amount": amount,
        "amount_t3": original_raw.get("amount_t3"),
        "amount_t6": original_raw.get("amount_t6"),
        "amount_t9": original_raw.get("amount_t9"),
        "text_value": raw_text,
        "reasoning": standardized.audit_log.method if standardized.audit_log else "",
        "original_type": original_raw.get("type", "expense"),
        "expense_year": original_raw.get("expense_year"),
        "page_number": original_raw.get("page_number"),
        "bbox": original_raw.get("bbox"),
        "document_id": original_raw.get("document_id"),
    }

    return NormalizedDataItem(
        id="item_placeholder",
        raw_text=raw_text,
        normalized_value=category_enum.value,
        field_type=field_type,
        category_group=group,
        data_classification=DataClassification.SOURCED,
        confidence=standardized.confidence,
        user_verified=False,
        source_document=original_raw.get("source_document", "Unknown"),
        text_type=original_raw.get("text_type", "Computerized"),
        metadata=metadata,
    )
