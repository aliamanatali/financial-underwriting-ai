#!/usr/bin/env python3
"""Test script to verify SSE completion events are received."""

import requests
import json
import time
import sys
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Configuration
API_BASE_URL = "http://localhost:8000"
UPLOAD_URL = f"{API_BASE_URL}/api/documents/upload"

def create_test_pdf(num_pages=2):
    """Create a simple test PDF with specified number of pages."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    for page_num in range(1, num_pages + 1):
        c.drawString(100, 750, f"Test Document - Page {page_num}")
        c.drawString(100, 700, "This is a test document for SSE completion verification.")
        c.drawString(100, 650, f"Page {page_num} of {num_pages}")
        c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def upload_document():
    """Upload a test document and return document_id."""
    print("Creating test PDF...")
    pdf_data = create_test_pdf(num_pages=2)
    
    print("Uploading document...")
    files = {'file': ('test_document.pdf', pdf_data, 'application/pdf')}
    response = requests.post(UPLOAD_URL, files=files)
    
    if response.status_code != 200:
        print(f"Upload failed: {response.status_code} - {response.text}")
        sys.exit(1)
    
    result = response.json()
    document_id = result['document_id']
    print(f"Document uploaded: {document_id}")
    print(f"Task ID: {result['task_id']}")
    return document_id

def monitor_sse_stream(document_id):
    """Monitor SSE stream and verify completion event is received."""
    stream_url = f"{API_BASE_URL}/api/documents/{document_id}/progress/stream"
    
    print(f"\nConnecting to SSE stream: {stream_url}")
    print("Waiting for events...\n")
    
    events_received = []
    completion_received = False
    
    try:
        response = requests.get(stream_url, stream=True, timeout=60)
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                
                # Parse SSE format
                if line.startswith('event:'):
                    event_type = line.split(':', 1)[1].strip()
                elif line.startswith('data:'):
                    data = line.split(':', 1)[1].strip()
                    try:
                        event_data = json.loads(data)
                        events_received.append({
                            'type': event_type if 'event_type' in locals() else 'unknown',
                            'data': event_data
                        })
                        
                        print(f"Event: {event_type}")
                        print(f"Data: {json.dumps(event_data, indent=2)}\n")
                        
                        # Check for completion
                        if event_type in ['completed', 'error']:
                            completion_received = True
                            print(f"✓ Completion event received: {event_type}")
                            break
                    except json.JSONDecodeError:
                        print(f"Failed to parse data: {data}")
    
    except requests.exceptions.Timeout:
        print("✗ SSE stream timeout - no completion event received")
    except Exception as e:
        print(f"✗ Error monitoring SSE stream: {str(e)}")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total events received: {len(events_received)}")
    print(f"Completion event received: {'✓ YES' if completion_received else '✗ NO'}")
    
    if events_received:
        print("\nEvents timeline:")
        for i, event in enumerate(events_received, 1):
            print(f"  {i}. {event['type']}: {event['data'].get('event', 'N/A')}")
    
    return completion_received

def main():
    """Main test function."""
    print("="*60)
    print("SSE COMPLETION EVENT TEST")
    print("="*60)
    
    # Upload document
    document_id = upload_document()
    
    # Wait a moment for processing to start
    time.sleep(1)
    
    # Monitor SSE stream
    success = monitor_sse_stream(document_id)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
