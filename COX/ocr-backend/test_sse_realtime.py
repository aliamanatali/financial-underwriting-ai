#!/usr/bin/env python3
"""Test script to verify real-time SSE progress updates."""

import requests
import json
import time
import sys
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8000"
TEST_PDF = "test_document.pdf"  # You'll need a multi-page PDF for testing

def create_test_pdf():
    """Create a simple multi-page PDF for testing."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        c = canvas.Canvas(TEST_PDF, pagesize=letter)
        
        # Create 3 pages
        for page_num in range(1, 4):
            c.drawString(100, 750, f"Test Page {page_num}")
            c.drawString(100, 700, f"This is page {page_num} of the test document.")
            c.drawString(100, 650, "Testing real-time SSE progress updates.")
            c.showPage()
        
        c.save()
        print(f"✓ Created test PDF: {TEST_PDF}")
        return True
    except ImportError:
        print("⚠ reportlab not installed. Please provide a multi-page PDF manually.")
        return False

def upload_document(pdf_path):
    """Upload a document and return the document_id."""
    print(f"\n📤 Uploading document: {pdf_path}")
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path, f, 'application/pdf')}
        response = requests.post(f"{BACKEND_URL}/api/documents/upload", files=files)
    
    if response.status_code == 200:
        data = response.json()
        document_id = data['document_id']
        task_id = data['task_id']
        print(f"✓ Document uploaded successfully")
        print(f"  Document ID: {document_id}")
        print(f"  Task ID: {task_id}")
        return document_id
    else:
        print(f"✗ Upload failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def stream_progress(document_id):
    """Stream progress updates via SSE."""
    print(f"\n📡 Connecting to SSE stream for document {document_id}...")
    
    url = f"{BACKEND_URL}/api/documents/{document_id}/progress/stream"
    
    try:
        response = requests.get(url, stream=True, timeout=300)
        
        if response.status_code != 200:
            print(f"✗ SSE connection failed: {response.status_code}")
            return
        
        print("✓ SSE connection established")
        print("\n" + "="*60)
        print("REAL-TIME PROGRESS UPDATES:")
        print("="*60 + "\n")
        
        event_count = 0
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                
                if line.startswith('event:'):
                    event_type = line.split(':', 1)[1].strip()
                    print(f"\n🔔 Event: {event_type}")
                    
                elif line.startswith('data:'):
                    data_str = line.split(':', 1)[1].strip()
                    try:
                        data = json.loads(data_str)
                        event_count += 1
                        
                        # Pretty print the event data
                        print(f"   Time: {time.strftime('%H:%M:%S')}")
                        
                        if 'chunk_index' in data:
                            print(f"   Chunk: {data['chunk_index']}/{data.get('total_chunks', '?')}")
                        
                        if 'status' in data:
                            print(f"   Status: {data['status']}")
                        
                        if 'overall_progress' in data:
                            progress = data['overall_progress']
                            print(f"   Progress: {progress:.1f}%")
                            
                            # Progress bar
                            bar_length = 40
                            filled = int(bar_length * progress / 100)
                            bar = '█' * filled + '░' * (bar_length - filled)
                            print(f"   [{bar}] {progress:.1f}%")
                        
                        if 'completed_chunks' in data:
                            print(f"   Completed: {data['completed_chunks']}/{data.get('total_chunks', '?')}")
                        
                        if 'error' in data and data['error']:
                            print(f"   ⚠ Error: {data['error']}")
                        
                        # Check if this is a completion event
                        if data.get('event') in ['completed', 'error']:
                            print(f"\n{'='*60}")
                            print(f"Processing {data.get('event').upper()}")
                            print(f"{'='*60}")
                            break
                            
                    except json.JSONDecodeError as e:
                        print(f"   ⚠ Failed to parse data: {e}")
        
        print(f"\n✓ SSE stream closed")
        print(f"  Total events received: {event_count}")
        
        if event_count == 0:
            print("\n⚠ WARNING: No events received! This indicates the SSE issue is NOT fixed.")
        elif event_count == 1:
            print("\n⚠ WARNING: Only 1 event received! Real-time updates may not be working.")
        else:
            print(f"\n✓ SUCCESS: Received {event_count} events - real-time updates are working!")
        
    except requests.exceptions.Timeout:
        print("✗ SSE connection timeout")
    except Exception as e:
        print(f"✗ Error streaming progress: {e}")

def main():
    """Main test function."""
    print("="*60)
    print("SSE REAL-TIME PROGRESS UPDATE TEST")
    print("="*60)
    
    # Check if test PDF exists or create one
    if not Path(TEST_PDF).exists():
        print(f"\n⚠ Test PDF not found: {TEST_PDF}")
        if not create_test_pdf():
            print("\nPlease provide a multi-page PDF and update TEST_PDF variable.")
            sys.exit(1)
    
    # Upload document
    document_id = upload_document(TEST_PDF)
    if not document_id:
        sys.exit(1)
    
    # Small delay to ensure upload is complete
    time.sleep(0.5)
    
    # Stream progress
    stream_progress(document_id)
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
