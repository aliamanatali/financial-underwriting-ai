"""
Synthesis Service - Priority-Based Data Synthesis
Implements the "Omniscient" pattern for extracting truth from multiple document sources.

This service replaces the fragile "OM-centric" approach with a priority-based synthesis
that finds data regardless of which document contains it.
"""

import logging
from typing import List, Dict, Any, Optional
from app.models.schemas import NormalizedDataItem, RentRollItem, StandardizedExpense

logger = logging.getLogger(__name__)


class SynthesisService:
    """
    Service for synthesizing property metadata and rent roll data from multiple document sources.
    Uses priority-based selection to find the "best" value when data appears in multiple documents.
    """
    
    # Document Priority Weights (Higher = More Reliable)
    DOCUMENT_WEIGHTS = {
        "PSA": 120, # PSA beats OM for Purchase Price & Terms
        "PURCHASE AND SALE": 120,
        "SALE PURCHASE AGREEMENT": 120,
        "OFFERING MEMORANDUM": 110, # User requested First Priority
        "OM": 110,
        "PURCHASE": 100,
        "AGREEMENT": 100,
        "MGMT AGMT": 95,
        "MANAGEMENT AGREEMENT": 95,
        "GRANT OF EASEMENT": 90,
        "PRELIM": 90,
        "RENT ROLL": 80, # Priority 2
        "RENTROLL": 80,  # Handle missing space
        "T12": 75,      # Priority 3 (Financials)
        "P&L": 75,
        "PROFIT & LOSS": 75,
        "INCOME STATEMENT": 75,
        "OPERATING STATEMENT": 75,
        "FINANCIALS": 75,
        "TAX BILL": 70,
        "TAX": 70,
        "FIRE INSPECTION": 60,
        "FIRE": 60,
        "INSPECTION": 60,
        "DISCLOSURE": 30,
        "UNKNOWN": 10
    }
    
    def __init__(self):
        """Initialize the synthesis service."""
        pass

    async def verify_purchase_price(
        self,
        candidates: List[Dict[str, Any]],
        gemini_service: Any
    ) -> Dict[str, Any]:
        """
        Verify Purchase Price using an LLM agent that analyzes context from all sources.
        
        Args:
            candidates: List of dicts containing:
                - value: float
                - source: str (filename)
                - text_context: str (surrounding text or full page text)
                - document_id: str
            gemini_service: Service to interact with LLM
            
        Returns:
            Dict with "value" (float), "source" (str), "confidence" (float), "reasoning" (str)
        """
        if not candidates:
            return {"value": 0.0, "source": None, "confidence": 0.0, "reasoning": "No candidates found"}
            
        # Deduplicate candidates based on value and source
        unique_candidates = {}
        for c in candidates:
            key = f"{c['value']}_{c['source']}"
            if key not in unique_candidates:
                unique_candidates[key] = c
        
        candidates_list = list(unique_candidates.values())
        
        # If only one candidate, just return it (unless we want to verify it specifically?)
        # But the prompt says "looks through... context... come up with final value"
        # Even with 1 candidate, context verification helps ensure it's not a deposit.
        
        prompt = """
        You are a real estate underwriting verification agent. Your goal is to determine the definitive Purchase Price of the property from the provided data excerpts.
        
        Candidates found:
        """
        
        for idx, c in enumerate(candidates_list):
            prompt += f"""
            --- Candidate {idx + 1} ---
            Extracted Value: ${c['value']:,.2f}
            Source Document: {c['source']}
            Context/Page Content:
            {c['text_context'][:2000]}  # Truncated to avoid token limits
            -----------------------
            """
            
        prompt += """
        
        INSTRUCTIONS:
        1. Analyze the context for each candidate.
        2. Identify the TRUE Purchase Price.
        3. CRITICAL - DISTINGUISH FROM DEPOSIT:
           - You MUST distinguish between "Purchase Price" and "Deposit" / "Earnest Money".
           - Deposits are often smaller amounts (e.g. $50k, $100k, or 3-5% of price) mentioned in "Deposit" sections.
           - Do NOT confuse the Deposit amount with the Purchase Price.
        4. SOURCE PRIORITY - MAIN AGREEMENT:
           - The "Main" Purchase and Sale Agreement (PSA) is the PRIMARY authority.
           - Be cautious with "Amendments" or "Addenda" - they often discuss deposits or extensions, not necessarily the total price.
           - Always prefer the value defined in the "Purchase Price" section (often Section 2) of the Main PSA.
        5. IGNORE extracted values that are actually:
           - "Earnest Money Deposit" or "Deposit"
           - "Loan Amount" or "Debt"
           - "Price per Unit"
           - "Broker Opinion of Value" (unless it's the only price available in an OM)
           - "Strike Price" or "Guidance" (if a firm contract price exists)
        
        Return a JSON object:
        {
            "selected_value": float,
            "selected_source": "Source filename",
            "confidence": float (0.0 to 1.0),
            "reasoning": "Explanation of why this value was chosen and others rejected."
        }
        """
        
        try:
            # Use generate_structured_data if available on the service, or just content
            # Assuming gemini_service has generate_content or generate_structured_data
            # We'll use a simple wrapper or if it's the GeminiService class we saw earlier
            
            if hasattr(gemini_service, "generate_content_async"):
                response = await gemini_service.generate_content_async(prompt)
            else:
                # Fallback synchronous or different method signature
                response = gemini_service.generate_content(prompt)
            
            # Clean and parse JSON
            import json
            import re
            
            cleaned_text = response.strip()
            # Extract JSON block
            match = re.search(r"```json\s*([\s\S]*?)\s*```", cleaned_text, re.DOTALL)
            if match:
                cleaned_text = match.group(1)
            else:
                # Try generic block
                match = re.search(r"```\s*(.*?)```", cleaned_text, re.DOTALL)
                if match:
                    cleaned_text = match.group(1)
            
            # Cleanup potential trailing chars
            cleaned_text = cleaned_text.strip()
            if cleaned_text.startswith("json"):
                cleaned_text = cleaned_text[4:]
            
            result = json.loads(cleaned_text)
            
            return {
                "value": result.get("selected_value", 0.0),
                "source": result.get("selected_source", "Verification Agent"),
                "confidence": result.get("confidence", 0.0),
                "reasoning": result.get("reasoning", "")
            }
            
        except Exception as e:
            logger.error(f"Error in Purchase Price Verification Agent: {e}")
            # Fallback to the highest priority logic already in place (caller handles this)
            return None

    def _normalize_unit_id(self, unit_id: str) -> str:
        """
        Normalize unit ID for deduplication.
        - Removes leading zeros (01 -> 1)
        - Lowercase
        - Removes 'unit', '#', 'apt' prefixes
        - Handles 'vacant' or 'n/a'
        """
        if not unit_id:
            return ""
        
        s = str(unit_id).lower().strip()
        
        # Handle garbage values
        if s in ["unknown", "n/a", "vacant", "-", ".", "none", "null"]:
            return ""
        
        # Remove common prefixes
        for prefix in ["unit", "apt", "#", "suite", "no."]:
            if s.startswith(prefix):
                s = s[len(prefix):].strip()
        
        # Remove leading zeros if it looks like a number
        if s.isdigit():
            s = str(int(s))
            
        return s

    def _get_document_score(self, source_document: str) -> int:
        """
        Calculate priority score for a source document.
        
        Args:
            source_document: Name of the source document
            
        Returns:
            Priority score (higher = more reliable)
        """
        if not source_document:
            return self.DOCUMENT_WEIGHTS["UNKNOWN"]
        
        source_upper = source_document.upper()
        
        # Check for exact matches first
        for key, score in self.DOCUMENT_WEIGHTS.items():
            if key in source_upper:
                return score
        
        # Default to unknown
        return self.DOCUMENT_WEIGHTS["UNKNOWN"]

    def _is_garbage_property_string(self, text: str) -> bool:
        """
        Check if a string is likely garbage/generic property name.
        """
        if not text:
            return True
        
        s = str(text).strip().lower()
        if len(s) < 3:
            return True
        
        # Common generic headers/labels that get extracted as values
        garbage = [
            "property name", "property address", "name", "address",
            "subject property", "current", "year 1", "pro forma",
            "t12", "rent roll", "profit & loss", "income statement",
            "operating statement", "date", "total", "page", "1 of 1",
            "unknown", "statement", "period", "ending", "month",
            "field", "document", "method", "value", "confidence",
            "analysis", "summary", "report"
        ]
        
        if s in garbage:
            return True
            
        # Check if it looks like a date or filename
        if any(x in s for x in ["/20", "/19", "202", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
             # Simple heuristic to avoid "January 2023" being a property name
             if len(s) < 20:
                 return True
        
        if s.endswith(".pdf") or s.endswith(".xlsx") or s.endswith(".docx"):
            return True
                 
        return False
    
    def synthesize_property_metadata(
        self,
        normalized_items: List[NormalizedDataItem]
    ) -> Dict[str, Any]:
        """
        Synthesize property metadata from normalized items using priority-based selection.
        
        This function implements the "Metadata Synthesizer" pattern:
        - Looks at ALL normalized items across ALL documents
        - Picks the "winner" for each field based on document priority
        - PSA beats Rent Roll beats Tax Bill beats Fire Inspection beats OM
        
        Args:
            normalized_items: List of all normalized data items from all documents
            
        Returns:
            Dictionary with synthesized property metadata:
            {
                "purchase_price": {"value": float, "source": str, "score": int},
                "total_units": {"value": int, "source": str, "score": int},
                "year_built": {"value": int, "source": str, "score": int},
                "rentable_area": {"value": float, "source": str, "score": int},
                "real_estate_tax": {"value": float, "source": str, "score": int},
                "management_fee": {"value": float, "source": str, "score": int}
            }
        """
        logger.info(f"Synthesizing property metadata from {len(normalized_items)} items")
        
        # Initialize best values with score -1 (will be beaten by any real data)
        best_values = {
            "property_name": {"value": None, "source": None, "score": -1},
            "address": {"value": None, "source": None, "score": -1},
            "purchase_price": {"value": 0.0, "source": None, "score": -1},
            "total_units": {"value": 0, "source": None, "score": -1},
            "year_built": {"value": 0, "source": None, "score": -1},
            "rentable_area": {"value": 0.0, "source": None, "score": -1},
            "real_estate_tax": {"value": 0.0, "source": None, "score": -1},
            "management_fee": {"value": 0.0, "source": None, "score": -1},
            "current_loan_balance": {"value": 0.0, "source": None, "score": -1}
        }
        
        # Voting Collections
        name_candidates = []
        address_candidates = []
        
        # Scan all items and pick winners based on priority
        for item in normalized_items:
            source_doc = item.source_document
            doc_score = self._get_document_score(source_doc)
            
            # Get normalized value and raw text for matching
            normalized_val = item.normalized_value.lower() if item.normalized_value else ""
            raw_text = item.raw_text.lower() if item.raw_text else ""
            
            # Extract amount from metadata if available
            amount = 0.0
            if item.metadata:
                metadata_amount = item.metadata.get("amount", 0.0)
                if metadata_amount:
                    try:
                        amount = float(metadata_amount)
                    except (ValueError, TypeError):
                        amount = 0.0
            
            # PROPERTY NAME (Collect for voting)
            if "property name" in normalized_val:
                text_val = item.metadata.get("text_value") or item.raw_text
                # Remove prefixes if present in raw text
                if text_val:
                    text_val = str(text_val).replace("Property Name:", "").strip()
                    if not self._is_garbage_property_string(text_val):
                        name_candidates.append({
                            "value": text_val,
                            "source": source_doc,
                            "score": doc_score
                        })

            # PROPERTY ADDRESS (Collect for voting)
            elif "property address" in normalized_val or ("address" in normalized_val and item.category_group == "Property Info"):
                text_val = item.metadata.get("text_value") or item.raw_text
                # Ensure we don't match accidental substrings, check if it is truly an address field
                if text_val:
                     text_val = str(text_val).replace("Property Address:", "").replace("Address:", "").strip()
                     if not self._is_garbage_property_string(text_val):
                        address_candidates.append({
                            "value": text_val,
                            "source": source_doc,
                            "score": doc_score
                        })

            # PURCHASE PRICE
            elif ("purchase price" in normalized_val or
                "purchase price" in raw_text or
                "sales price" in raw_text or
                "contract price" in raw_text or
                "price" in normalized_val):
                
                # Exclude small amounts that might be deposits or fees
                # Increased threshold to $100k to avoid "Earnest Money Deposit" ($50k) errors
                if amount > 100000 and doc_score > best_values["purchase_price"]["score"]:
                    best_values["purchase_price"] = {
                        "value": amount,
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Purchase Price: ${amount:,.2f} from {source_doc} (score: {doc_score})")
            
            # TOTAL UNITS
            elif ("total units" in normalized_val or
                  "total units" in raw_text or
                  "number of units" in raw_text or
                  "unit count" in raw_text):
                # Valid unit count range 1-1000
                if amount > 0 and amount < 1000 and doc_score > best_values["total_units"]["score"]:
                    best_values["total_units"] = {
                        "value": int(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Total Units: {int(amount)} from {source_doc} (score: {doc_score})")
            
            # YEAR BUILT
            elif ("year built" in normalized_val or "year built" in raw_text or "year constructed" in raw_text or "build year" in raw_text):
                # Ensure year is valid
                if amount > 1800 and amount < 2030 and doc_score > best_values["year_built"]["score"]:
                    best_values["year_built"] = {
                        "value": int(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Year Built: {int(amount)} from {source_doc} (score: {doc_score})")
                    
            # RENTABLE AREA (SQ FT)
            elif ("rentable area" in normalized_val or
                  "rentable area" in raw_text or
                  "sq ft" in raw_text or
                  "sq. ft" in raw_text or
                  "square feet" in raw_text or
                  "gross area" in raw_text or
                  "building size" in raw_text):
                if amount > 500 and doc_score > best_values["rentable_area"]["score"]:
                    best_values["rentable_area"] = {
                        "value": float(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Rentable Area: {amount:,.2f} from {source_doc} (score: {doc_score})")

            # REAL ESTATE TAXES
            elif ("real estate tax" in normalized_val or
                  "property tax" in normalized_val or
                  "tax amount" in raw_text):
                 if amount > 0 and doc_score > best_values["real_estate_tax"]["score"]:
                    best_values["real_estate_tax"] = {
                        "value": float(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Real Estate Tax: ${amount:,.2f} from {source_doc} (score: {doc_score})")

            # MANAGEMENT FEE
            elif ("management fee" in normalized_val or
                  "mgmt fee" in raw_text):
                 # Allow 0 for management fee (self-managed)
                 if doc_score > best_values["management_fee"]["score"]:
                    best_values["management_fee"] = {
                        "value": float(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Management Fee: ${amount:,.2f} from {source_doc} (score: {doc_score})")

            # CURRENT LOAN BALANCE
            elif ("loan balance" in normalized_val or
                  "current loan" in normalized_val or
                  "mortgage balance" in normalized_val or
                  "existing debt" in raw_text or
                  "principal balance" in raw_text or
                  "loan amount" in raw_text):
                
                # Exclude monthly payments or small amounts
                if amount > 100000 and doc_score > best_values["current_loan_balance"]["score"]:
                    best_values["current_loan_balance"] = {
                        "value": float(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Current Loan Balance: ${amount:,.2f} from {source_doc} (score: {doc_score})")
            
            # SPECIAL CASE: Rent Roll row count for Total Units
            if item.metadata and item.metadata.get("row_count") and "rent roll" in raw_text:
                row_count = item.metadata.get("row_count")
                if row_count and row_count > 0:
                    # Rent Roll row count gets a bonus score (very reliable)
                    rent_roll_score = self.DOCUMENT_WEIGHTS["RENT ROLL"] + 10
                    if rent_roll_score > best_values["total_units"]["score"]:
                        best_values["total_units"] = {
                            "value": int(row_count),
                            "source": source_doc,
                            "score": rent_roll_score
                        }
                        logger.info(f"Updated Total Units from Rent Roll row count: {row_count} from {source_doc} (score: {rent_roll_score})")

        # --- Resolve Voting for Property Name and Address ---
        
        def resolve_voting(candidates: List[Dict], field_name: str):
            if not candidates:
                return None
            
            # Group by value
            grouped = {}
            for c in candidates:
                val = c["value"]
                # Use simple normalization for grouping (case insensitive)
                norm_val = val.lower().strip()
                
                if norm_val not in grouped:
                    grouped[norm_val] = {
                        "display_value": val,
                        "score": 0,
                        "count": 0,
                        "sources": set(),
                        "best_source_doc": c["source"]
                    }
                
                # Update max score seen for this value
                if c["score"] > grouped[norm_val]["score"]:
                    grouped[norm_val]["score"] = c["score"]
                    grouped[norm_val]["best_source_doc"] = c["source"]
                    grouped[norm_val]["display_value"] = val # Keep the casing from high score doc
                
                grouped[norm_val]["count"] += 1
                grouped[norm_val]["sources"].add(c["source"])
            
            # Apply Frequency Boost
            # If a name appears in multiple distinct documents, it gets a significant boost
            for norm_val, data in grouped.items():
                unique_docs = len(data["sources"])
                if unique_docs > 1:
                    # Boost: +15 points for each additional document
                    # This allows a consensus (e.g. 3 docs) to beat a single higher-priority doc if appropriate
                    boost = (unique_docs - 1) * 15
                    data["score"] += boost
                    logger.info(f"Boosting '{data['display_value']}' by {boost} points (Found in {unique_docs} docs)")

            # Pick winner
            best_group = max(grouped.values(), key=lambda x: x["score"])
            return {
                "value": best_group["display_value"],
                "source": best_group["best_source_doc"],
                "score": best_group["score"]
            }

        # Apply results
        best_name = resolve_voting(name_candidates, "Property Name")
        if best_name:
             best_values["property_name"] = best_name
             logger.info(f"Voting Winner - Property Name: '{best_name['value']}' (Score: {best_name['score']}, Source: {best_name['source']})")

        best_addr = resolve_voting(address_candidates, "Property Address")
        if best_addr:
             best_values["address"] = best_addr
             logger.info(f"Voting Winner - Property Address: '{best_addr['value']}' (Score: {best_addr['score']}, Source: {best_addr['source']})")
        
        # Log final synthesis results
        logger.info("=== METADATA SYNTHESIS RESULTS ===")
        for field, data in best_values.items():
            if data["source"]:
                logger.info(f"{field}: {data['value']} (from {data['source']}, score: {data['score']})")
            else:
                logger.info(f"{field}: NOT FOUND")
        
        return best_values
    
    def build_master_rent_roll(
        self,
        all_rent_roll_items: List[RentRollItem]
    ) -> List[RentRollItem]:
        """
        Build a master rent roll by prioritizing the document with the MOST data,
        but also including UNIQUE items from other documents.
        
        This function implements the "Best Source + Unique Add-ons" pattern:
        1. Identify the "Best Source" (document with the most rent roll items).
        2. Initialize master list with ALL items from Best Source.
        3. Scan other documents for items with UNIQUE unit numbers not in Best Source.
        4. Add those unique items to the master list.
        
        Args:
            all_rent_roll_items: List of all rent roll items from all documents
            
        Returns:
            List of rent roll items from the best source + unique items from others
        """
        if not all_rent_roll_items:
            logger.warning("No rent roll items provided for synthesis")
            return []
        
        logger.info(f"Synthesizing master rent roll from {len(all_rent_roll_items)} total items")
        
        # Group items by source file
        items_by_source: Dict[str, List[RentRollItem]] = {}
        
        for item in all_rent_roll_items:
            # Handle cases where source_file might be None
            source = item.source_file or "Unknown Source"
            if source not in items_by_source:
                items_by_source[source] = []
            items_by_source[source].append(item)
            
        # Find the source with the most items
        if not items_by_source:
             return []

        # --- OM PRIMACY LOGIC ---
        # If OM has rent roll items, use ONLY OM items (unless very sparse/error).
        om_source = None
        for source in items_by_source.keys():
            if "OM" in source.upper() or "OFFERING" in source.upper() or "MEMORANDUM" in source.upper():
                # Check if it has decent data
                if len(items_by_source[source]) > 0:
                    om_source = source
                    break
        
        if om_source:
            logger.info(f"OM Primacy: Found Rent Roll in OM ('{om_source}'). Using this source exclusively per priority rules.")
            final_items = items_by_source[om_source]
            
            # Log summary
            total_rent = sum(item.current_rent or 0.0 for item in final_items)
            logger.info(f"OM Rent Roll Summary: {len(final_items)} units, ${total_rent:,.2f} monthly rent")
            return final_items

        # --- Fallback to Best Source Selection (if no OM) ---
        # FIX: Use document priority to select best source (OM > Rent Roll)
        def get_source_priority(source_name: str, items: List[RentRollItem]) -> int:
            base_score = self._get_document_score(source_name)
            
            # Bonus for structured data formats (Excel/CSV) as they are more reliable than PDF OCR
            format_bonus = 0
            src_lower = source_name.lower()
            # Check for extension anywhere (handles "filename.xlsx | Sheet1" format)
            if ".xlsx" in src_lower or ".xls" in src_lower or ".csv" in src_lower:
                format_bonus = 5000 # Significant bonus to beat PDF of same type/score
            
            # Weight priority heavily, use count as tie-breaker
            return (base_score * 10000) + format_bonus + len(items)

        best_source = max(items_by_source, key=lambda s: get_source_priority(s, items_by_source[s]))
        primary_items = items_by_source[best_source]
        
        logger.info(f"Selected Primary Rent Roll Source: '{best_source}' with {len(primary_items)} items (Score: {self._get_document_score(best_source)})")
        
        # Initialize master dictionary with items from the best source
        # We use a dictionary keyed by NORMALIZED unit_number for fast lookup
        master_roll: Dict[str, RentRollItem] = {}
        
        # Add primary items first (they have authority)
        for item in primary_items:
            unit_id = self._normalize_unit_id(item.unit_number)
            if not unit_id: continue
            
            # Deduplication within primary source
            if unit_id not in master_roll:
                master_roll[unit_id] = item
        
        # Scan other sources for UNIQUE items
        added_unique_count = 0
        for source, items in items_by_source.items():
            if source == best_source:
                continue
                
            for item in items:
                unit_id = self._normalize_unit_id(item.unit_number)
                if not unit_id: continue

                # If unit number is NOT in master roll, it's unique to this secondary source
                if unit_id not in master_roll:
                    master_roll[unit_id] = item
                    added_unique_count += 1
                    logger.debug(f"Added unique unit {item.unit_number} (norm: {unit_id}) from secondary source {source}")
                else:
                    # Data Enrichment: Fill in missing gaps in the Master item from this Secondary item
                    master_item = master_roll[unit_id]
                    
                    # Fill Unit Size (Critical for this task)
                    if (master_item.unit_size == 0 or master_item.unit_size is None) and (item.unit_size and item.unit_size > 0):
                        master_item.unit_size = item.unit_size
                        logger.info(f"Enriched Unit {unit_id} Size ({item.unit_size}) from secondary source {source}")
                    
                    # Fill Market Rent
                    if (master_item.market_rent == 0 or master_item.market_rent is None) and (item.market_rent and item.market_rent > 0):
                        master_item.market_rent = item.market_rent
                    
                    # Fill Stabilized Rent
                    if (master_item.stabilized_rent == 0 or master_item.stabilized_rent is None) and (item.stabilized_rent and item.stabilized_rent > 0):
                        master_item.stabilized_rent = item.stabilized_rent
                        
                    # Fill Move-in / Lease Dates if missing
                    if not master_item.lease_start and item.lease_start:
                        master_item.lease_start = item.lease_start
                    if not master_item.lease_end and item.lease_end:
                        master_item.lease_end = item.lease_end
        
        if added_unique_count > 0:
            logger.info(f"Added {added_unique_count} unique items from secondary sources")
        else:
            logger.info("No unique items found in secondary sources")
            
        final_items = list(master_roll.values())
        
        # Calculate summary stats
        total_rent = sum(item.current_rent or 0.0 for item in final_items)
        occupied_units = sum(1 for item in final_items if (item.current_rent or 0.0) > 0)
        
        logger.info(f"Master Rent Roll Summary:")
        logger.info(f"  - Total Units: {len(final_items)}")
        logger.info(f"  - Occupied Units: {occupied_units}")
        logger.info(f"  - Total Monthly Rent: ${total_rent:,.2f}")
        logger.info(f"  - Annual GPR: ${total_rent * 12:,.2f}")
        
        return final_items
    
    def extract_rent_roll_from_normalized_items(
        self,
        normalized_items: List[NormalizedDataItem]
    ) -> List[RentRollItem]:
        """
        Extract rent roll items from normalized data items.
        
        This is a helper function to convert NormalizedDataItem objects
        that represent rent roll data into RentRollItem objects.
        
        Args:
            normalized_items: List of normalized data items
            
        Returns:
            List of RentRollItem objects
        """
        rent_roll_items = []
        
        for item in normalized_items:
            # Check if this is a rent roll item
            if item.field_type == "rent_roll_item" or (
                item.metadata and
                item.metadata.get("is_rent_roll_item", False)
            ):
                try:
                    # Extract rent roll data from metadata
                    if item.metadata:
                        unit_number = item.metadata.get("unit_number", "Unknown")
                        
                        # Skip if unit number is garbage
                        clean_unit_number = str(unit_number).strip()
                        if clean_unit_number in ["-", "Unknown", "", "null", "None"]:
                            continue
                        
                        # Skip if it looks like a year (19xx or 20xx)
                        if clean_unit_number.isdigit() and len(clean_unit_number) == 4 and (clean_unit_number.startswith("19") or clean_unit_number.startswith("20")):
                             # Unless it has a clear unit type
                             if item.metadata.get("unit_type") in ["Unknown", None]:
                                 continue

                        unit_type = item.metadata.get("unit_type", "")
                        # Handle literal "Unknown" strings
                        if unit_type and str(unit_type).lower() == "unknown":
                            unit_type = ""

                        unit_size = item.metadata.get("unit_size", 0)

                        # Filter out rows with Unknown/Empty type and 0 size (likely noise)
                        if (not unit_type) and (unit_size == 0 or unit_size is None):
                             # Exception: If it has a tenant name and rent, it might be valid
                             current_rent = item.metadata.get("current_rent", 0.0)
                             tenant_name = item.metadata.get("tenant_name", "Unknown")
                             
                             if (current_rent is None or current_rent == 0) and (not tenant_name or tenant_name == "Unknown"):
                                 continue
                             
                             # If it has rent but no size/type, it's still suspicious if unit number is just 4 digits (could be sqft or year)
                             if str(clean_unit_number).isdigit() and len(str(clean_unit_number)) >= 4:
                                  continue

                        rent_roll_item = RentRollItem(
                            unit_number=unit_number,
                            unit_type=unit_type,
                            unit_size=unit_size,
                            tenant_name=item.metadata.get("tenant_name", "Unknown"),
                            current_rent=item.metadata.get("current_rent", 0.0),
                            stabilized_rent=item.metadata.get("stabilized_rent", 0.0),
                            market_rent=item.metadata.get("market_rent", 0.0),
                            move_in_date=item.metadata.get("move_in_date", ""),
                            lease_start=item.metadata.get("lease_start", ""),
                            lease_end=item.metadata.get("lease_end", ""),
                            source_file=item.source_document
                        )
                        rent_roll_items.append(rent_roll_item)
                except Exception as e:
                    logger.warning(f"Failed to parse rent roll item from normalized data: {e}")
        
        logger.info(f"Extracted {len(rent_roll_items)} rent roll items from normalized data")
        return rent_roll_items

    def deduplicate_expenses(
        self,
        expenses: List[StandardizedExpense]
    ) -> List[StandardizedExpense]:
        """
        Deduplicate expenses that appear to be identical across multiple documents
        (e.g. duplicate file uploads or same invoice in multiple files).
        """
        if not expenses:
            return []
            
        logger.info(f"Deduplicating {len(expenses)} expenses...")
        
        unique_expenses = []
        seen_hashes = set()
        duplicates_removed = 0
        
        for exp in expenses:
            # Create a hash based on key attributes to identify duplicates
            # 1. Amount (rounded to 2 decimals)
            # 2. Category
            # 3. Year (if available)
            # 4. Normalized Text (alphanumeric only, first 30 chars)
            
            amount_key = round(exp.amount, 2)
            cat_key = exp.mapped_category
            year_key = exp.expense_year or 0
            
            # Simple text normalization for fuzzy matching
            # "PG&E Gas Charges" -> "pgegascharges"
            text_key = "".join(e for e in exp.original_text.lower() if e.isalnum())[:30]
            
            dedup_key = (amount_key, cat_key, year_key, text_key)
            
            if dedup_key in seen_hashes:
                # This is a duplicate
                duplicates_removed += 1
                continue
                
            seen_hashes.add(dedup_key)
            unique_expenses.append(exp)
            
        logger.info(f"Deduplication complete. Removed {duplicates_removed} duplicates. Final count: {len(unique_expenses)}")
        return unique_expenses
