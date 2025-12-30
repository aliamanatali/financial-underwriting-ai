import os
import json
from app.services.ingestion_service import IngestionService
from app.models.schemas import PropertyMeta

def test_ingest_rent_roll_from_pdf():
    """
    Tests the ingestion of a rent roll from a PDF file.
    """
    # Create a dummy PDF file for testing
    pdf_path = "test_rent_roll.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 52 >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Unit #,Unit Type,Tenant Name,Current Rent,Market Rent,Lease Start,Lease End) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000059 00000 n \n0000000112 00000 n \n0000000199 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n292\n%%EOF")

    # Initialize the ingestion service
    ingestion_service = IngestionService()

    # Define dummy property metadata
    property_meta = PropertyMeta(
        address="123 Main St",
        year_built=2020,
        purchase_price=10000000,
        total_units=1
    )

    # Ingest the rent roll from the PDF
    rent_roll = ingestion_service.ingest_rent_roll_from_pdf(pdf_path, property_meta)

    # Save the output to rent_roll.json
    with open("rent_roll.json", "w") as f:
        json.dump([item.model_dump() for item in rent_roll], f, indent=4)

    # Clean up the dummy PDF file
    os.remove(pdf_path)

if __name__ == "__main__":
    test_ingest_rent_roll_from_pdf()