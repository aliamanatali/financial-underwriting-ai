#!/usr/bin/env python3
"""
Test script to verify real-time progress events are being published.
This script uploads a document and monitors Redis pub/sub for events.
"""

import asyncio
import aiohttp
import redis.asyncio as aioredis
import json
import sys
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
REDIS_URL = "redis://localhost:6379/0"

async def monitor_redis_pubsub(document_id: str, timeout: int = 60):
    """Monitor Redis pub/sub channel for progress events."""
    print(f"\n{'='*80}")
    print(f"MONITORING REDIS PUB/SUB FOR DOCUMENT: {document_id}")
    print(f"{'='*80}\n")
    
    redis_client = None
    pubsub = None
    events_received = []
    
    try:
        # Connect to Redis
        redis_client = await aioredis.from_url(REDIS_URL, decode_responses=True)
        channel = f"document:{document_id}:progress"
        
        print(f"✓ Connected to Redis")
        print(f"✓ Subscribing to channel: {channel}\n")
        
        # Subscribe to channel
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        
        print(f"{'─'*80}")
        print(f"LISTENING FOR EVENTS (timeout: {timeout}s)...")
        print(f"{'─'*80}\n")
        
        # Listen for messages with timeout
        start_time = asyncio.get_event_loop().time()
        
        async def listen_with_timeout():
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        event_type = data.get('event', 'unknown')
                        chunk_index = data.get('chunk_index', 'N/A')
                        status = data.get('status', 'N/A')
                        progress = data.get('overall_progress', 0)
                        
                        events_received.append(data)
                        
                        # Print event details
                        print(f"[EVENT #{len(events_received)}] Type: {event_type}")
                        print(f"  ├─ Chunk: {chunk_index}")
                        print(f"  ├─ Status: {status}")
                        print(f"  ├─ Progress: {progress:.1f}%")
                        print(f"  └─ Data: {json.dumps(data, indent=4)}")
                        print()
                        
                        # Stop if completed or error
                        if event_type in ['completed', 'error']:
                            print(f"{'─'*80}")
                            print(f"STREAM ENDED: {event_type}")
                            print(f"{'─'*80}\n")
                            return
                            
                    except json.JSONDecodeError as e:
                        print(f"✗ Failed to decode message: {e}")
                
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    print(f"\n{'─'*80}")
                    print(f"TIMEOUT REACHED ({timeout}s)")
                    print(f"{'─'*80}\n")
                    return
        
        await listen_with_timeout()
        
    except Exception as e:
        print(f"\n✗ Error monitoring Redis: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        if pubsub:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        if redis_client:
            await redis_client.close()
    
    return events_received


async def upload_test_document():
    """Upload a test PDF document."""
    print(f"\n{'='*80}")
    print(f"UPLOADING TEST DOCUMENT")
    print(f"{'='*80}\n")
    
    # Create a simple test PDF (or use existing one)
    test_pdf_path = Path("test_sample.pdf")
    
    if not test_pdf_path.exists():
        print(f"✗ Test PDF not found: {test_pdf_path}")
        print(f"  Please create a test PDF file or specify an existing one.")
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            # Upload document
            with open(test_pdf_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename='test.pdf', content_type='application/pdf')
                
                print(f"✓ Uploading: {test_pdf_path}")
                
                async with session.post(f"{API_BASE_URL}/api/documents/upload", data=data) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        print(f"✗ Upload failed: {resp.status}")
                        print(f"  Response: {text}")
                        return None
                    
                    result = await resp.json()
                    document_id = result['document_id']
                    task_id = result['task_id']
                    
                    print(f"✓ Upload successful!")
                    print(f"  ├─ Document ID: {document_id}")
                    print(f"  ├─ Task ID: {task_id}")
                    print(f"  └─ Status: {result['status']}")
                    
                    return document_id
                    
    except Exception as e:
        print(f"\n✗ Error uploading document: {e}")
        import traceback
        traceback.print_exc()
        return None


async def check_celery_worker():
    """Check if Celery worker is running by inspecting active workers."""
    print(f"\n{'='*80}")
    print(f"CHECKING CELERY WORKER STATUS")
    print(f"{'='*80}\n")
    
    try:
        from app.celery_app import celery_app
        
        # Inspect active workers
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            print(f"✓ Celery workers are running:")
            for worker_name, tasks in active_workers.items():
                print(f"  ├─ Worker: {worker_name}")
                print(f"  └─ Active tasks: {len(tasks)}")
        else:
            print(f"✗ No active Celery workers found!")
            print(f"  Please start a Celery worker with:")
            print(f"  celery -A app.celery_app worker --loglevel=info")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Error checking Celery worker: {e}")
        return False


async def main():
    """Main test function."""
    print(f"\n{'#'*80}")
    print(f"# REAL-TIME PROGRESS EVENTS DEBUG TEST")
    print(f"{'#'*80}")
    
    # Check Celery worker
    worker_running = await check_celery_worker()
    if not worker_running:
        print(f"\n⚠ WARNING: Celery worker may not be running!")
        print(f"  Events will only be published if a worker is processing tasks.\n")
    
    # Upload document
    document_id = await upload_test_document()
    if not document_id:
        print(f"\n✗ Test failed: Could not upload document")
        return
    
    # Small delay to allow task to be queued
    await asyncio.sleep(1)
    
    # Monitor Redis pub/sub
    events = await monitor_redis_pubsub(document_id, timeout=120)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}\n")
    print(f"Document ID: {document_id}")
    print(f"Total events received: {len(events)}")
    
    if events:
        print(f"\n✓ SUCCESS: Real-time events are being published!")
        print(f"\nEvent types received:")
        event_types = {}
        for event in events:
            event_type = event.get('event', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        for event_type, count in event_types.items():
            print(f"  ├─ {event_type}: {count}")
    else:
        print(f"\n✗ FAILURE: No events received!")
        print(f"\nPossible issues:")
        print(f"  1. Celery worker not running or not processing tasks")
        print(f"  2. Redis pub/sub not publishing events")
        print(f"  3. Document processing failed before publishing")
        print(f"  4. Network/connection issues")
        print(f"\nCheck Celery worker logs for details.")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n✗ Test interrupted by user")
        sys.exit(1)
