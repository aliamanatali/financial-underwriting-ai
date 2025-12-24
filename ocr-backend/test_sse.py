#!/usr/bin/env python3
"""
Test script to verify SSE endpoint functionality.
This script simulates a document upload and monitors SSE progress updates.
"""

import requests
import json
import time
from pathlib import Path

API_URL = "http://localhost:8000"

def test_sse_endpoint():
    """Test the SSE endpoint with a real document upload."""
    
    print("=" * 60)
    print("SSE Endpoint Test")
    print("=" * 60)
    
    # Check if we have a test PDF
    test_pdf_path = Path("test_document.pdf")
    if not test_pdf_path.exists():
        print("\n❌ No test_document.pdf found in current directory")
        print("Please create a multi-page PDF for testing")
        return
    
    # Upload document
    print("\n1. Uploading document...")
    with open(test_pdf_path, 'rb') as f:
        files = {'file': ('test_document.pdf', f, 'application/pdf')}
        response = requests.post(f"{API_URL}/api/documents/upload", files=files)
    
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        return
    
    upload_data = response.json()
    document_id = upload_data['document_id']
    print(f"✅ Document uploaded: {document_id}")
    print(f"   Task ID: {upload_data['task_id']}")
    
    # Test SSE endpoint
    print(f"\n2. Connecting to SSE endpoint...")
    sse_url = f"{API_URL}/api/documents/{document_id}/progress/stream"
    print(f"   URL: {sse_url}")
    
    try:
        # Connect to SSE stream
        response = requests.get(sse_url, stream=True, timeout=120)
        
        if response.status_code != 200:
            print(f"❌ SSE connection failed: {response.status_code}")
            return
        
        print("✅ SSE connection established")
        print("\n3. Monitoring progress updates:")
        print("-" * 60)
        
        event_count = 0
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                
                # Parse SSE format
                if decoded_line.startswith('event:'):
                    event_type = decoded_line.split(':', 1)[1].strip()
                    print(f"\n📡 Event: {event_type}")
                    event_count += 1
                    
                elif decoded_line.startswith('data:'):
                    data_str = decoded_line.split(':', 1)[1].strip()
                    try:
                        data = json.loads(data_str)
                        
                        # Display relevant progress info
                        if 'overall_progress' in data:
                            print(f"   Progress: {data['overall_progress']:.1f}%")
                        if 'completed_chunks' in data and 'total_chunks' in data:
                            print(f"   Chunks: {data['completed_chunks']}/{data['total_chunks']}")
                        if 'chunk_index' in data:
                            print(f"   Current chunk: {data['chunk_index']}")
                        if 'status' in data:
                            print(f"   Status: {data['status']}")
                        if 'error_message' in data:
                            print(f"   ❌ Error: {data['error_message']}")
                            
                    except json.JSONDecodeError:
                        print(f"   Raw data: {data_str}")
                
                # Check for completion
                if 'event: completed' in decoded_line or 'event: error' in decoded_line:
                    print("\n" + "-" * 60)
                    print(f"✅ Stream completed after {event_count} events")
                    break
        
        print("\n4. Verifying final document state...")
        doc_response = requests.get(f"{API_URL}/api/documents/{document_id}")
        if doc_response.status_code == 200:
            doc_data = doc_response.json()
            print(f"   Final status: {doc_data['status']}")
            if doc_data.get('metadata'):
                print(f"   Pages: {doc_data['metadata'].get('page_count', 'N/A')}")
            print("✅ Document processing verified")
        
    except requests.exceptions.Timeout:
        print("❌ SSE connection timeout")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)


if __name__ == "__main__":
    test_sse_endpoint()
