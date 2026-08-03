from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
  LOW = "low"
  MEDIUM = "medium"
  HIGH = "high"
  CRITICAL = "critical"


# Enforced team categories
class Team(str, Enum):
  BILLING = "Billing"
  SUPPORT = "Support"
  ENGINEERING = "Engineering"
  DEVOPS = "DevOps"
  PRODUCT = "Product"


class ActionableItem(BaseModel):
  task: str = Field(
      ...,
      min_length=5,
      max_length=60,
      description="Specific action step to take",
  )
  assigned_team: Team  # Model forced to pick from Team enum


class SupportTicketAnalysis(BaseModel):
  summary: str = Field(
      ..., min_length=10, max_length=120, description="Brief issue summary"
  )
  severity: Severity
  action_items: List[ActionableItem] = Field(
      ..., max_items=2, description="1 or 2 distinct action items"
  )


# API Request / Response schemas
class TicketRequest(BaseModel):
  ticket_text: str
  prompt: Optional[str] = None


class TicketResponse(BaseModel):
  id: int
  ticket_text: str
  cached: bool
  analysis: SupportTicketAnalysis