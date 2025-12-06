# app/schemas.py
from typing import List, Literal, Optional

from pydantic import BaseModel

from .models import Assignment, Dasher, Metrics, Order


class SimulationRequest(BaseModel):
    strategy: Literal["nearest", "load_balanced", "batched"]
    dashers: List[Dasher]
    orders: List[Order]
    batch_window_seconds: Optional[int] = 60


class SimulationResponse(BaseModel):
    strategy: str
    assignments: List[Assignment]
    metrics: Metrics
