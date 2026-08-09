from celery_app import celery_app
from engine import get_sentiment_engine


@celery_app.task(bind=True)
def process_batch_reviews(self, reviews_list: list):
  engine = get_sentiment_engine()
  results = []

  total = len(reviews_list)
  for idx, item in enumerate(reviews_list):
    analysis = engine.analyze_review(
        text=item["text"],
        product_category=item.get("product_category", "Product"),
        content_type=item.get("content_type", "review"),
        review_title=item.get("review_title", ""),
    )
    results.append(analysis.model_dump())

    # Update Celery task state
    self.update_state(
        state="PROGRESS", meta={"current": idx + 1, "total": total}
    )

  return results