import asyncio
from typing import Dict, Any, AsyncGenerator, Set, Optional
import logging
import json

logger = logging.getLogger(__name__)

class ProgressService:
    def __init__(self):
        # In-memory storage for active progress: {id: {"percentage": 0, "message": "Starting...", "details": {}}}
        self._active_progress: Dict[str, Dict[str, Any]] = {}
        # Listeners: {task_id: Set[asyncio.Queue]}
        self._listeners: Dict[str, Set[asyncio.Queue]] = {}
        logger.info(f"ProgressService initialized at {id(self)}")

    async def update_progress(self, task_id: str, percentage: int, message: str, details: Optional[Dict[str, Any]] = None):
        """Updates the progress for a specific task ID."""
        progress_data = {
            "percentage": percentage,
            "message": message
        }
        if details:
            progress_data["details"] = details
            
        self._active_progress[task_id] = progress_data
        logger.info(f"Progress update for {task_id}: {percentage}% - {message} (Service ID: {id(self)})")
        
        # Notify listeners
        if task_id in self._listeners:
            listener_count = len(self._listeners[task_id])
            logger.info(f"Dispatching progress for {task_id} to {listener_count} listeners (Service ID: {id(self)})")
            # Create a snapshot of listeners to avoid modification during iteration if a listener disconnects
            for i, queue in enumerate(list(self._listeners[task_id])):
                try:
                    # Put data in queue (non-blocking)
                    queue.put_nowait(progress_data)
                except Exception as e:
                    logger.error(f"Error putting progress to queue {i}: {e}")
        else:
            logger.warning(f"No listeners found for task {task_id}")

    async def stream_progress(self, task_id: str) -> AsyncGenerator[str, None]:
        """Streams progress updates for a specific task ID as SSE format."""
        queue: asyncio.Queue = asyncio.Queue()
        
        if task_id not in self._listeners:
            self._listeners[task_id] = set()
        self._listeners[task_id].add(queue)
        
        logger.info(f"New listener connected for task {task_id} (Service ID: {id(self)})")
        
        # Send current state immediately if available
        if task_id in self._active_progress:
            yield f"data: {json.dumps(self._active_progress[task_id])}\n\n"
        else:
             yield f"data: {json.dumps({'percentage': 0, 'message': 'Connecting...'})}\n\n"
        
        try:
            while True:
                # Wait for new data
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                
                if data.get("percentage", 0) >= 100:
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for {task_id}")
        except Exception as e:
            logger.error(f"Stream error for {task_id}: {e}")
        finally:
            # Cleanup
            if task_id in self._listeners:
                self._listeners[task_id].discard(queue)
                if not self._listeners[task_id]:
                    del self._listeners[task_id]

    def get_current_progress(self, task_id: str) -> Dict[str, Any]:
        return self._active_progress.get(task_id, {"percentage": 0, "message": "Unknown task"})