"""
Synthesis Service - Priority-Based Data Synthesis
Implements the "Omniscient" pattern for extracting truth from multiple document sources.

This service replaces the fragile "OM-centric" approach with a priority-based synthesis
that finds data regardless of which document contains it.
"""

import logging
from typing import List, Dict, Any, Optional
from app.models.schemas import NormalizedDataItem, RentRollItem

logger = logging.getLogger(__name__)


class SynthesisService:
    """
    Service for synthesizing property metadata and rent roll data from multiple document sources.
    Uses priority-based selection to find the "best" value when data appears in multiple documents.
    """
    
    # Document Priority Weights (Higher = More Reliable)
    DOCUMENT_WEIGHTS = {
        "PSA": 100,
        "PURCHASE": 100,
        "AGREEMENT": 100,
        "RENT ROLL": 80,
        "TAX BILL": 70,
        "TAX": 70,
        "FIRE INSPECTION": 60,
        "FIRE": 60,
        "INSPECTION": 60,
        "OFFERING MEMORANDUM": 50,
        "OM": 50,
        "DISCLOSURE": 30,
        "UNKNOWN": 10
    }
    
    def __init__(self):
        """Initialize the synthesis service."""
        pass
    
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
                "year_built": {"value": int, "source": str, "score": int}
            }
        """
        logger.info(f"Synthesizing property metadata from {len(normalized_items)} items")
        
        # Initialize best values with score -1 (will be beaten by any real data)
        best_values = {
            "purchase_price": {"value": 0.0, "source": None, "score": -1},
            "total_units": {"value": 0, "source": None, "score": -1},
            "year_built": {"value": 0, "source": None, "score": -1}
        }
        
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
            
            # PURCHASE PRICE
            if ("purchase price" in normalized_val or 
                "purchase price" in raw_text or 
                "asking price" in raw_text):
                if amount > 0 and doc_score > best_values["purchase_price"]["score"]:
                    best_values["purchase_price"] = {
                        "value": amount,
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Purchase Price: ${amount:,.2f} from {source_doc} (score: {doc_score})")
            
            # TOTAL UNITS
            elif ("total units" in normalized_val or 
                  "total units" in raw_text or 
                  "number of units" in raw_text):
                if amount > 0 and doc_score > best_values["total_units"]["score"]:
                    best_values["total_units"] = {
                        "value": int(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Total Units: {int(amount)} from {source_doc} (score: {doc_score})")
            
            # YEAR BUILT
            elif ("year built" in normalized_val or "year built" in raw_text):
                if amount > 1800 and amount < 2030 and doc_score > best_values["year_built"]["score"]:
                    best_values["year_built"] = {
                        "value": int(amount),
                        "source": source_doc,
                        "score": doc_score
                    }
                    logger.info(f"Updated Year Built: {int(amount)} from {source_doc} (score: {doc_score})")
            
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
        Build a master rent roll by deduplicating units across multiple rent roll documents.
        
        This function implements the "Rent Roll Accumulator" pattern:
        - Groups units by unit_number across ALL rent roll documents
        - When duplicates exist, takes the one with the HIGHEST rent (most recent/accurate)
        - Returns a deduplicated master rent roll
        
        Args:
            all_rent_roll_items: List of all rent roll items from all documents
            
        Returns:
            Deduplicated list of rent roll items (one per unique unit)
        """
        if not all_rent_roll_items:
            logger.warning("No rent roll items provided for deduplication")
            return []
        
        logger.info(f"Building master rent roll from {len(all_rent_roll_items)} total items")
        
        # Dictionary to track best item for each unit
        master_roll: Dict[str, RentRollItem] = {}
        
        for item in all_rent_roll_items:
            unit_id = item.unit_number
            
            # If this is the first time we see this unit, add it
            if unit_id not in master_roll:
                master_roll[unit_id] = item
            else:
                # Unit already exists - take the one with higher rent
                existing_rent = master_roll[unit_id].current_rent or 0.0
                new_rent = item.current_rent or 0.0
                
                if new_rent > existing_rent:
                    logger.debug(f"Unit {unit_id}: Updating rent from ${existing_rent:,.2f} to ${new_rent:,.2f}")
                    master_roll[unit_id] = item
        
        deduplicated_items = list(master_roll.values())
        
        logger.info(f"Master rent roll built: {len(deduplicated_items)} unique units (deduplicated from {len(all_rent_roll_items)} items)")
        
        # Calculate summary stats
        total_rent = sum(item.current_rent or 0.0 for item in deduplicated_items)
        occupied_units = sum(1 for item in deduplicated_items if (item.current_rent or 0.0) > 0)
        
        logger.info(f"Master Rent Roll Summary:")
        logger.info(f"  - Total Units: {len(deduplicated_items)}")
        logger.info(f"  - Occupied Units: {occupied_units}")
        logger.info(f"  - Total Monthly Rent: ${total_rent:,.2f}")
        logger.info(f"  - Annual GPR: ${total_rent * 12:,.2f}")
        
        return deduplicated_items
    
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
                        rent_roll_item = RentRollItem(
                            unit_number=item.metadata.get("unit_number", "Unknown"),
                            unit_type=item.metadata.get("unit_type", "Unknown"),
                            unit_size=item.metadata.get("unit_size", 0),
                            tenant_name=item.metadata.get("tenant_name", "Unknown"),
                            current_rent=item.metadata.get("current_rent", 0.0),
                            stabilized_rent=item.metadata.get("stabilized_rent", 0.0),
                            market_rent=item.metadata.get("market_rent", 0.0),
                            move_in_date=item.metadata.get("move_in_date", ""),
                            lease_start=item.metadata.get("lease_start", ""),
                            lease_end=item.metadata.get("lease_end", "")
                        )
                        rent_roll_items.append(rent_roll_item)
                except Exception as e:
                    logger.warning(f"Failed to parse rent roll item from normalized data: {e}")
        
        logger.info(f"Extracted {len(rent_roll_items)} rent roll items from normalized data")
        return rent_roll_items
