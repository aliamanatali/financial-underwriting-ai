from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.dependencies import get_progress_service
from app.services.progress_service import ProgressService

router = APIRouter()


@router.get("/progress/current/{task_id}")
async def get_current_progress(task_id: str, progress_service: ProgressService = Depends(get_progress_service)):
    """
    Get current progress snapshot for a task (non-streaming).
    Used by frontend on page load to get initial state before SSE connects.
    """
    return await progress_service.get_current_progress(task_id)


@router.get("/progress/{task_id}")
async def progress_stream(task_id: str, progress_service: ProgressService = Depends(get_progress_service)):
    """
    Stream progress updates for a specific task using Server-Sent Events (SSE).
    """
    return StreamingResponse(
        progress_service.stream_progress(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )