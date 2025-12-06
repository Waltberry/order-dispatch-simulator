# app/simulation.py
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import List, Tuple

from .models import Assignment, Dasher, Metrics, Order
from .strategies import BatchingStrategy, LoadBalancedStrategy, NearestDasherStrategy


def get_strategy(name: str, batch_window_seconds: int = 60):
    if name == "nearest":
        return NearestDasherStrategy()
    if name == "load_balanced":
        return LoadBalancedStrategy()
    if name == "batched":
        return BatchingStrategy(batch_window_seconds=batch_window_seconds)
    raise ValueError(f"Unknown strategy: {name}")


def compute_metrics(assignments: List[Assignment], dashers: List[Dasher]) -> Metrics:
    if not assignments:
        return Metrics(
            avg_distance_km=0.0,
            avg_wait_seconds=0.0,
            avg_driver_utilization=0.0,
            assignments_per_dasher={},
        )

    avg_distance = mean(a.distance_km for a in assignments)
    avg_wait = mean(a.wait_seconds for a in assignments)

    counts = Counter(a.dasher_id for a in assignments)
    capacity_map = {d.id: d.capacity for d in dashers}

    utilizations = []
    for dasher_id, count in counts.items():
        cap = capacity_map.get(dasher_id, 1)
        u = min(count / cap, 1.0)
        utilizations.append(u)

    avg_util = mean(utilizations) if utilizations else 0.0

    return Metrics(
        avg_distance_km=avg_distance,
        avg_wait_seconds=avg_wait,
        avg_driver_utilization=avg_util,
        assignments_per_dasher=dict(counts),
    )


def run_simulation(
    strategy_name: str,
    dashers: List[Dasher],
    orders: List[Order],
    batch_window_seconds: int = 60,
) -> Tuple[List[Assignment], Metrics]:
    strategy = get_strategy(strategy_name, batch_window_seconds=batch_window_seconds)
    assignments = strategy.assign(dashers, orders)
    metrics = compute_metrics(assignments, dashers)
    return assignments, metrics
