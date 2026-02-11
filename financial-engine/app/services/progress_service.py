import asyncio
from typing import Dict, Any, AsyncGenerator, Optional
import logging
import json
from app.db.redis import redis_client

logger = logging.getLogger(__name__)

class ProgressService:
    def __init__(self):
        logger.info(f"ProgressService initialized at {id(self)}")

    async def update_progress(self, task_id: str, percentage: int, message: str, details: Optional[Dict[str, Any]] = None):
        """Updates the progress for a specific task ID using Redis."""
        progress_data = {
            "percentage": percentage,
            "message": message
        }
        if details:
            progress_data["details"] = details
        
        try:
            client = redis_client.client
            if client:
                # Store current state with expiry (1 hour)
                await client.set(f"progress:{task_id}", json.dumps(progress_data), ex=3600)
                # Publish to channel
                await client.publish(f"progress:{task_id}", json.dumps(progress_data))
                logger.debug(f"Progress update published for {task_id}: {percentage}%")
            else:
                logger.warning(f"Redis client not available for progress update {task_id}")
        except Exception as e:
            logger.error(f"Failed to update progress for {task_id}: {e}")

    async def stream_progress(self, task_id: str) -> AsyncGenerator[str, None]:
        """Streams progress updates for a specific task ID as SSE format."""
        client = redis_client.client
        if not client:
             yield f"data: {json.dumps({'percentage': 0, 'message': 'Connecting (Redis unavailable)...'})}\n\n"
             return

        pubsub = client.pubsub()
        channel = f"progress:{task_id}"
        await pubsub.subscribe(channel)
        logger.info(f"Subscribed to Redis channel {channel}")
        
        try:
            # Send current state immediately if available
            current_data = await client.get(channel)
            if current_data:
                yield f"data: {current_data}\n\n"
            else:
                 yield f"data: {json.dumps({'percentage': 0, 'message': 'Connecting...'})}\n\n"
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    yield f"data: {data}\n\n"
                    
                    try:
                        parsed = json.loads(data)
                        if parsed.get("percentage", 0) >= 100:
                            break
                    except:
                        pass
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for {task_id}")
        except Exception as e:
            logger.error(f"Stream error for {task_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def get_current_progress(self, task_id: str) -> Dict[str, Any]:
        client = redis_client.client
        if not client:
            return {"percentage": 0, "message": "Redis unavailable"}
            
        data = await client.get(f"progress:{task_id}")
        if data:
            return json.loads(data)
        return {"percentage": 0, "message": "Unknown task"}