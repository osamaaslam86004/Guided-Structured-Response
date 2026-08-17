# Keep the endpoint for compatibility
# But the primary integration should now use WebSocket events,

from celery.result import AsyncResult
from fastapi import APIRouter
from schemas import TaskStatusResponse
from celery_app import celery_app

router = APIRouter()


@router.get(
    "/api/v1/tasks/{task_id}",
    response_model=TaskStatusResponse,
)
def get_task_status(task_id: str):

    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":

        return TaskStatusResponse(
            task_id=task_id,
            status="PENDING",
        )

    if result.state == "STARTED":

        return TaskStatusResponse(
            task_id=task_id,
            status="STARTED",
        )

    if result.state == "SUCCESS":

        return TaskStatusResponse(
            task_id=task_id,
            status="SUCCESS",
            result=result.result,
        )

    if result.failed():

        return TaskStatusResponse(
            task_id=task_id,
            status="FAILURE",
            error=str(result.result),
        )

    return TaskStatusResponse(
        task_id=task_id,
        status=result.state,
    )
