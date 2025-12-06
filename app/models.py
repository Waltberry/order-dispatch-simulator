# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field


class Location(BaseModel):
    lat: float
    lng: float


class Dasher(BaseModel):
    id: str
    location: Location
    capacity: int = Field(1, ge=1)


class Order(BaseModel):
    id: str
    location: Location
    created_at: datetime


class Assignment(BaseModel):
    order_id: str
    dasher_id: str
    distance_km: float
    wait_seconds: float
    dispatch_time: datetime


class Metrics(BaseModel):
    avg_distance_km: float
    avg_wait_seconds: float
    avg_driver_utilization: float
    assignments_per_dasher: Dict[str, int]
