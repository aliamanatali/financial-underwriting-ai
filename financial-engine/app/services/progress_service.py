import asyncio
from typing import Dict, Any, AsyncGenerator
import logging
import json

logger = logging.getLogger(__name__)

class ProgressService:
    def __init__(self):
        # In-memory storage for active progress: {id: {"percentage": 0, "message": "Starting..."}}
        self._active_progress: Dict[str, Dict[str, Any]] = {}
        # Event for notifying listeners of updates
        self._update_event = asyncio.Event()

    async def update_progress(self, task_id: str, percentage: int, message: str):
        """Updates the progress for a specific task ID."""
        self._active_progress[task_id] = {
            "percentage": percentage,
            "message": message
        }
        logger.info(f"Progress update for {task_id}: {percentage}% - {message}")
        # Notify all listeners that an update occurred
        self._update_event.set()
        # Clear the event immediately so we can wait for the next update
        # Note: In a high-concurrency scenario with many tasks, a more granular event system might be needed.
        # For this use case, a single global event triggering a check is sufficient or we can yield per task.
        # Actually, for SSE, it's better to use a dedicated queue per connection/task if possible, 
        # but simpler is to use a generator that polls or waits on a signal.
        
        # Improvement: We'll use a broadcast approach where the generator waits for changes.
        # But since _update_event is shared, it might get tricky. 
        # Let's keep it simple: The generator will check specifically for its task_id.

    async def stream_progress(self, task_id: str) -> AsyncGenerator[str, None]:
        """Streams progress updates for a specific task ID as SSE format."""
        
        last_percentage = -1
        last_message = ""
        
        # Initial yield to confirm connection
        yield f"data: {json.dumps({'percentage': 0, 'message': 'Connecting...'})}\n\n"
        
        try:
            while True:
                # Check if we have data for this task
                if task_id in self._active_progress:
                    data = self._active_progress[task_id]
                    current_percentage = data["percentage"]
                    current_message = data.get("message", "")
                    
                    # Only yield if there's a change in percentage OR message
                    if current_percentage != last_percentage or current_message != last_message:
                        yield f"data: {json.dumps(data)}\n\n"
                        last_percentage = current_percentage
                        last_message = current_message
                    
                    if current_percentage >= 100:
                        break
                        
                    # If failed/error state (could be handled via percentage -1 or specific message)
                    if "fail" in data.get("message", "").lower() and "check" not in data.get("message", "").lower():
                         # We might want to break here too, or let the client handle it
                         pass

                # Wait for the next update event
                # We use a small timeout to allow for periodic checks/keep-alive if needed
                try:
                    await asyncio.wait_for(self._update_event.wait(), timeout=1.0)
                    self._update_event.clear()
                except asyncio.TimeoutError:
                    # Timeout just means no updates happened globally, we loop again
                    pass
                
                # Small sleep to prevent busy loop if event is set frequently by other tasks
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for {task_id}")
        finally:
            # Cleanup if needed
            if task_id in self._active_progress and self._active_progress[task_id]["percentage"] >= 100:
                del self._active_progress[task_id]

    def get_current_progress(self, task_id: str) -> Dict[str, Any]:
        return self._active_progress.get(task_id, {"percentage": 0, "message": "Unknown task"})