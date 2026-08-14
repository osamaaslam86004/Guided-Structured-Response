from celery.result import AsyncResult
from fastapi import APIRouter
from schemas import TaskStatusResponse
from celery_app import celery_app

task_status_router = APIRouter()

@task_status_router.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
  task_result = AsyncResult(task_id, app=celery_app)

  if task_result.state == "PENDING":
    return TaskStatusResponse(task_id=task_id, status="PENDING")
  elif task_result.state == "SUCCESS":
    return TaskStatusResponse(
        task_id=task_id, status="SUCCESS", result=task_result.result
    )
  else:
    return TaskStatusResponse(task_id=task_id, status=task_result.state)