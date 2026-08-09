from fastapi import APIRouter
from schemas import BatchReviewRequest, TaskStatusResponse
from celery_app import celery_app
from schemas import BatchReviewRequest, TaskStatusResponse
from celery_app import celery_app
from tasks import process_batch_reviews


router = APIRouter()

@router.post("/api/v1/batch-analyze", response_model=TaskStatusResponse)
def analyze_batch_reviews(request: BatchReviewRequest):
  reviews_data = [r.model_dump() for r in request.reviews]
  task = process_batch_reviews.delay(reviews_data)
  return TaskStatusResponse(task_id=task.id, status="PENDING")


@router.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
  task_result = celery_app.AsyncResult(task_id)

  if task_result.state == "PENDING":
    return TaskStatusResponse(task_id=task_id, status="PENDING")
  elif task_result.state == "PROGRESS":
    return TaskStatusResponse(
        task_id=task_id, status=f"PROGRESS ({task_result.info})"
    )
  elif task_result.state == "SUCCESS":
    return TaskStatusResponse(
        task_id=task_id, status="SUCCESS", result=task_result.result
    )
  else:
    return TaskStatusResponse(task_id=task_id, status=task_result.state)