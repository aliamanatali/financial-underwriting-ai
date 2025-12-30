"""Redis-based progress tracking for document processing."""

import json
from typing import Dict, Any, Optional
import redis

from app.config import settings
from app.utils.logger import logger


class RedisProgressTracker:
    """Track document processing progress in Redis for real-time updates."""
    
    def __init__(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis progress tracker initialized")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis_client = None
    
    def _get_channel(self, document_id: str) -> str:
        """Get Redis pub/sub channel for document progress."""
        return f"document:{document_id}:progress"
    
    def _get_key(self, document_id: str) -> str:
        """Get Redis key for document progress."""
        return f"document:progress:{document_id}"
    
    def _get_start_time_key(self, document_id: str) -> str:
        """Get Redis key for document start time."""
        return f"document:start_time:{document_id}"
    
    def set_start_time(self, document_id: str, start_time: float):
        """
        Store the start time for a document.
        
        Args:
            document_id: Document identifier
            start_time: Unix timestamp when processing started
        """
        if not self.redis_client:
            return
        
        try:
            key = self._get_start_time_key(document_id)
            self.redis_client.setex(
                key,
                3600,  # Expire after 1 hour
                str(start_time)
            )
            logger.info(f"Stored start time for {document_id}: {start_time}")
        except Exception as e:
            logger.error(f"Failed to store start time for {document_id}: {str(e)}")
    
    def get_start_time(self, document_id: str) -> Optional[float]:
        """
        Retrieve the start time for a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Unix timestamp or None if not found
        """
        if not self.redis_client:
            return None
        
        try:
            key = self._get_start_time_key(document_id)
            start_time_str = self.redis_client.get(key)
            
            if start_time_str:
                return float(start_time_str)
            return None
        except Exception as e:
            logger.error(f"Failed to get start time for {document_id}: {str(e)}")
            return None
    
    def publish_progress_update(self, document_id: str, progress_data: Dict[str, Any]):
        """
        Publish progress update to Redis pub/sub channel.
        
        Args:
            document_id: Document identifier
            progress_data: Progress data to publish
        """
        if not self.redis_client:
            logger.warning(f"[REDIS-PUB] Redis client not available, cannot publish progress for {document_id}")
            return
        
        try:
            channel = self._get_channel(document_id)
            message = json.dumps(progress_data)
            logger.info(
                f"[REDIS-PUB] Publishing to channel '{channel}' - "
                f"Event: {progress_data.get('event', 'unknown')}, "
                f"Chunk: {progress_data.get('chunk_index', 'N/A')}, "
                f"Data: {message[:100]}..."
            )
            subscribers = self.redis_client.publish(channel, message)
            logger.info(
                f"[REDIS-PUB] ✓ Published {progress_data.get('event', 'unknown')} event to {channel} "
                f"(subscribers: {subscribers}, chunk: {progress_data.get('chunk_index', 'N/A')})"
            )
            if subscribers == 0:
                logger.warning(f"[REDIS-PUB] ⚠ No subscribers listening on channel {channel}")
        except Exception as e:
            logger.error(f"[REDIS-PUB] ✗ Failed to publish progress update for {document_id}: {str(e)}")
    
    def initialize_document(self, document_id: str, total_chunks: int):
        """
        Initialize progress tracking for a document.
        
        Args:
            document_id: Document identifier
            total_chunks: Total number of chunks to process
        """
        if not self.redis_client:
            return
        
        try:
            progress_data = {
                'total_chunks': total_chunks,
                'completed_chunks': 0,
                'failed_chunks': 0,
                'processing_chunks': 0,
                'chunks': {},
                'overall_progress': 0.0
            }
            
            key = self._get_key(document_id)
            self.redis_client.setex(
                key,
                3600,  # Expire after 1 hour
                json.dumps(progress_data)
            )
            
            logger.info(f"Initialized progress tracking for {document_id} with {total_chunks} chunks")
            
            # Publish initialization event
            self.publish_progress_update(document_id, {
                'event': 'initialized',
                'document_id': document_id,
                'total_chunks': total_chunks,
                'completed_chunks': 0,
                'failed_chunks': 0,
                'overall_progress': 0.0
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize progress for {document_id}: {str(e)}")
    
    def update_chunk_progress(
        self,
        document_id: str,
        chunk_index: int,
        status: str,
        error: Optional[str] = None
    ):
        """
        Update progress for a specific chunk.
        
        Args:
            document_id: Document identifier
            chunk_index: Chunk index (1-based)
            status: Chunk status (processing, completed, failed)
            error: Error message if failed
        """
        logger.info(
            f"[PROGRESS-UPDATE] Called for document {document_id}, "
            f"chunk {chunk_index}, status: {status}"
        )
        
        if not self.redis_client:
            logger.warning(f"[PROGRESS-UPDATE] Redis client not available for {document_id}")
            return
        
        try:
            key = self._get_key(document_id)
            progress_json = self.redis_client.get(key)
            
            if not progress_json:
                logger.warning(f"[PROGRESS-UPDATE] No progress data found for {document_id}")
                return
            
            progress_data = json.loads(progress_json)
            
            # Update chunk status
            chunk_key = str(chunk_index)
            old_status = progress_data['chunks'].get(chunk_key, {}).get('status')
            
            progress_data['chunks'][chunk_key] = {
                'status': status,
                'error': error
            }
            
            # Update counters
            if old_status == 'processing':
                progress_data['processing_chunks'] -= 1
            
            if status == 'processing':
                progress_data['processing_chunks'] += 1
            elif status == 'completed':
                progress_data['completed_chunks'] += 1
            elif status == 'failed':
                progress_data['failed_chunks'] += 1
            
            # Calculate overall progress
            total = progress_data['total_chunks']
            completed = progress_data['completed_chunks']
            failed = progress_data['failed_chunks']
            progress_data['overall_progress'] = ((completed + failed) / total) * 100 if total > 0 else 0
            
            # Save updated progress
            self.redis_client.setex(
                key,
                3600,
                json.dumps(progress_data)
            )
            
            logger.info(
                f"[PROGRESS-UPDATE] Updated chunk {chunk_index} for {document_id}: {status} "
                f"(Progress: {progress_data['overall_progress']:.1f}%, "
                f"Completed: {completed}/{total}, Failed: {failed})"
            )
            
            # Publish progress update
            event_type = 'chunk_completed' if status == 'completed' else 'progress'
            logger.info(
                f"[PROGRESS-UPDATE] About to publish event '{event_type}' for "
                f"document {document_id}, chunk {chunk_index}"
            )
            self.publish_progress_update(document_id, {
                'event': event_type,
                'document_id': document_id,
                'chunk_index': chunk_index,
                'status': status,
                'total_chunks': progress_data['total_chunks'],
                'completed_chunks': progress_data['completed_chunks'],
                'failed_chunks': progress_data['failed_chunks'],
                'processing_chunks': progress_data['processing_chunks'],
                'overall_progress': progress_data['overall_progress'],
                'error': error
            })
            logger.info(f"[PROGRESS-UPDATE] Publish call completed for chunk {chunk_index}")
            
        except Exception as e:
            logger.error(f"Failed to update chunk progress for {document_id}: {str(e)}")
    
    def get_progress(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current progress for a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Progress data dictionary or None
        """
        if not self.redis_client:
            return None
        
        try:
            key = self._get_key(document_id)
            progress_json = self.redis_client.get(key)
            
            if not progress_json:
                return None
            
            return json.loads(progress_json)
            
        except Exception as e:
            logger.error(f"Failed to get progress for {document_id}: {str(e)}")
            return None
    
    def clear_progress(self, document_id: str):
        """
        Clear progress data for a document.
        
        Args:
            document_id: Document identifier
        """
        if not self.redis_client:
            return
        
        try:
            key = self._get_key(document_id)
            self.redis_client.delete(key)
            logger.info(f"Cleared progress data for {document_id}")
        except Exception as e:
            logger.error(f"Failed to clear progress for {document_id}: {str(e)}")
    
    def mark_completed(self, document_id: str):
        """
        Mark document processing as completed and publish event.
        
        Args:
            document_id: Document identifier
        """
        if not self.redis_client:
            return
        
        try:
            progress = self.get_progress(document_id)
            if progress:
                self.publish_progress_update(document_id, {
                    'event': 'completed',
                    'document_id': document_id,
                    'status': 'completed',
                    'total_chunks': progress.get('total_chunks', 0),
                    'completed_chunks': progress.get('completed_chunks', 0),
                    'overall_progress': 100.0
                })
            logger.info(f"Marked document {document_id} as completed")
        except Exception as e:
            logger.error(f"Failed to mark document {document_id} as completed: {str(e)}")
    
    def mark_failed(self, document_id: str, error_message: str):
        """
        Mark document processing as failed and publish event.
        
        Args:
            document_id: Document identifier
            error_message: Error message
        """
        if not self.redis_client:
            return
        
        try:
            progress = self.get_progress(document_id)
            self.publish_progress_update(document_id, {
                'event': 'error',
                'document_id': document_id,
                'status': 'failed',
                'error_message': error_message,
                'total_chunks': progress.get('total_chunks', 0) if progress else 0,
                'completed_chunks': progress.get('completed_chunks', 0) if progress else 0,
                'overall_progress': progress.get('overall_progress', 0.0) if progress else 0.0
            })
            logger.info(f"Marked document {document_id} as failed: {error_message}")
        except Exception as e:
            logger.error(f"Failed to mark document {document_id} as failed: {str(e)}")
    
    def get_chunk_details(self, document_id: str) -> Dict[int, Dict[str, Any]]:
        """
        Get detailed status for all chunks.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Dictionary mapping chunk index to chunk details
        """
        progress = self.get_progress(document_id)
        
        if not progress:
            return {}
        
        return {
            int(k): v for k, v in progress.get('chunks', {}).items()
        }
