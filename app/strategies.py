# app/strategies.py
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from .models import Assignment, Dasher, Order

AVG_SPEED_KMPH = 30.0  # assumed average speed for simulation


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points on Earth in kilometers.
    Good enough for city-level simulation.
    """
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        dlambda / 2
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@dataclass
class DasherState:
    id: str
    lat: float
    lng: float
    capacity: int
    next_available_time: datetime


@dataclass
class OrderState:
    id: str
    lat: float
    lng: float
    created_at: datetime


class DispatchStrategy(ABC):
    """
    Base class for all dispatch strategies.
    """

    name: str

    @abstractmethod
    def assign(self, dashers: List[Dasher], orders: List[Order]) -> List[Assignment]:
        ...


class NearestDasherStrategy(DispatchStrategy):
    """
    Greedy strategy: assign each order to the geographically nearest dasher,
    updating dasher location and availability over time.
    """

    def __init__(self) -> None:
        self.name = "nearest"

    def assign(self, dashers: List[Dasher], orders: List[Order]) -> List[Assignment]:
        if not dashers or not orders:
            return []

        start_time = min(o.created_at for o in orders)
        dasher_states = [
            DasherState(
                id=d.id,
                lat=d.location.lat,
                lng=d.location.lng,
                capacity=d.capacity,
                next_available_time=start_time,
            )
            for d in dashers
        ]
        orders_sorted = sorted(orders, key=lambda o: o.created_at)

        assignments: List[Assignment] = []

        for order in orders_sorted:
            if not dasher_states:
                break

            best_state = None
            best_distance = None

            for ds in dasher_states:
                dist = haversine_km(
                    ds.lat, ds.lng, order.location.lat, order.location.lng
                )
                if best_distance is None or dist < best_distance:
                    best_distance = dist
                    best_state = ds

            if best_state is None or best_distance is None:
                continue

            dispatch_time = max(order.created_at, best_state.next_available_time)
            travel_hours = best_distance / AVG_SPEED_KMPH
            travel_seconds = travel_hours * 3600.0
            finish_time = dispatch_time + timedelta(seconds=travel_seconds)
            wait_seconds = (dispatch_time - order.created_at).total_seconds()

            assignments.append(
                Assignment(
                    order_id=order.id,
                    dasher_id=best_state.id,
                    distance_km=best_distance,
                    wait_seconds=wait_seconds,
                    dispatch_time=dispatch_time,
                )
            )

            # Dasher moves to order location and becomes available after travel.
            best_state.lat = order.location.lat
            best_state.lng = order.location.lng
            best_state.next_available_time = finish_time

        return assignments


class LoadBalancedStrategy(DispatchStrategy):
    """
    Load-balanced strategy: choose dashers by (fewest assignments so far, then distance).
    """

    def __init__(self) -> None:
        self.name = "load_balanced"

    def assign(self, dashers: List[Dasher], orders: List[Order]) -> List[Assignment]:
        if not dashers or not orders:
            return []

        start_time = min(o.created_at for o in orders)
        dasher_states = [
            DasherState(
                id=d.id,
                lat=d.location.lat,
                lng=d.location.lng,
                capacity=d.capacity,
                next_available_time=start_time,
            )
            for d in dashers
        ]
        orders_sorted = sorted(orders, key=lambda o: o.created_at)

        assign_counts = {d.id: 0 for d in dashers}
        assignments: List[Assignment] = []

        for order in orders_sorted:
            best_state = None
            best_distance = None
            best_count = None

            for ds in dasher_states:
                dist = haversine_km(
                    ds.lat, ds.lng, order.location.lat, order.location.lng
                )
                count = assign_counts[ds.id]

                if (
                    best_state is None
                    or count < best_count  # prefer less-loaded
                    or (count == best_count and dist < best_distance)  # tie-breaker
                ):
                    best_state = ds
                    best_distance = dist
                    best_count = count

            if best_state is None or best_distance is None:
                continue

            dispatch_time = max(order.created_at, best_state.next_available_time)
            travel_hours = best_distance / AVG_SPEED_KMPH
            travel_seconds = travel_hours * 3600.0
            finish_time = dispatch_time + timedelta(seconds=travel_seconds)
            wait_seconds = (dispatch_time - order.created_at).total_seconds()

            assignments.append(
                Assignment(
                    order_id=order.id,
                    dasher_id=best_state.id,
                    distance_km=best_distance,
                    wait_seconds=wait_seconds,
                    dispatch_time=dispatch_time,
                )
            )

            best_state.lat = order.location.lat
            best_state.lng = order.location.lng
            best_state.next_available_time = finish_time
            assign_counts[best_state.id] += 1

        return assignments


class BatchingStrategy(DispatchStrategy):
    """
    Batched assignment: orders are accumulated in time windows, then assigned in a batch.
    This creates non-zero wait times because orders are held until the batch closes.
    """

    def __init__(self, batch_window_seconds: int = 60) -> None:
        self.name = "batched"
        self.batch_window_seconds = batch_window_seconds

    def assign(self, dashers: List[Dasher], orders: List[Order]) -> List[Assignment]:
        if not dashers or not orders:
            return []

        orders_sorted = sorted(orders, key=lambda o: o.created_at)

        start_time = orders_sorted[0].created_at
        dasher_states = [
            DasherState(
                id=d.id,
                lat=d.location.lat,
                lng=d.location.lng,
                capacity=d.capacity,
                next_available_time=start_time,
            )
            for d in dashers
        ]

        assignments: List[Assignment] = []
        batch: List[Order] = []
        batch_start: datetime | None = None

        def process_batch(batch_orders: List[Order], batch_start_time: datetime) -> None:
            if not batch_orders:
                return

            batch_end = batch_start_time + timedelta(seconds=self.batch_window_seconds)

            for order in batch_orders:
                best_state = None
                best_distance = None
                for ds in dasher_states:
                    dist = haversine_km(
                        ds.lat, ds.lng, order.location.lat, order.location.lng
                    )
                    if best_distance is None or dist < best_distance:
                        best_distance = dist
                        best_state = ds

                if best_state is None or best_distance is None:
                    continue

                dispatch_time = max(batch_end, best_state.next_available_time)
                travel_hours = best_distance / AVG_SPEED_KMPH
                travel_seconds = travel_hours * 3600.0
                finish_time = dispatch_time + timedelta(seconds=travel_seconds)
                wait_seconds = (dispatch_time - order.created_at).total_seconds()

                assignments.append(
                    Assignment(
                        order_id=order.id,
                        dasher_id=best_state.id,
                        distance_km=best_distance,
                        wait_seconds=wait_seconds,
                        dispatch_time=dispatch_time,
                    )
                )

                best_state.lat = order.location.lat
                best_state.lng = order.location.lng
                best_state.next_available_time = finish_time

        for order in orders_sorted:
            if batch_start is None:
                batch_start = order.created_at
                batch = [order]
                continue

            delta = (order.created_at - batch_start).total_seconds()
            if delta <= self.batch_window_seconds:
                batch.append(order)
            else:
                process_batch(batch, batch_start)
                batch_start = order.created_at
                batch = [order]

        if batch and batch_start is not None:
            process_batch(batch, batch_start)

        return assignments
