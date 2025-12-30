import requests
import time
import json

def test_ingestion():
    """
    Tests the ingestion pipeline by uploading a rent roll PDF to the ocr-backend
    and retrieving the extracted data.
    """
    # 1. Read the rent roll PDF
    with open("COX/ocr-backend/test_sample.pdf", "rb") as f:
        file_data = f.read()

    # 2. Upload the PDF to the ocr-backend
    response = requests.post(
        "http://localhost:8001/api/documents/upload",
        files={"file": ("test_sample.pdf", file_data, "application/pdf")},
    )
    response.raise_for_status()
    upload_data = response.json()
    document_id = upload_data["document_id"]

    # 3. Poll for the processing status
    while True:
        response = requests.get(f"http://localhost:8001/api/documents/{document_id}")
        response.raise_for_status()
        status_data = response.json()
        if status_data["status"] == "completed":
            break
        time.sleep(5)

    # 4. Retrieve the extracted text and save it to rent_roll.json
    response = requests.get(f"http://localhost:8001/api/documents/{document_id}/text")
    response.raise_for_status()
    text_data = response.json()
    with open("rent_roll.json", "w") as f:
        json.dump(text_data, f, indent=4)

if __name__ == "__main__":
    test_ingestion()