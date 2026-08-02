from pydantic import BaseModel, Field
from enum import Enum
from typing import List

from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class Severity(str, Enum):
  LOW = "low"
  MEDIUM = "medium"
  HIGH = "high"
  CRITICAL = "critical"


class ActionableItem(BaseModel):
  task: str = Field(
      ...,
      min_length=5,
      max_length=60,
      description="Specific, non-generic step to resolve the issue",
  )
  assigned_team: str = Field(
      ...,
      min_length=2,
      max_length=30,
      description="Responsible department (e.g. Engineering, Billing, DevOps)",
  )


class SupportTicketAnalysis(BaseModel):
  summary: str = Field(
      ...,
      min_length=10,
      max_length=120,
      description="Brief breakdown of the customer's issue",
  )
  severity: Severity
  # HARD CAP: Prevents repetitive loops by capping the list size to 2
  action_items: List[ActionableItem] = Field(
      ..., max_items=2, description="1 or 2 distinct action items"
  )