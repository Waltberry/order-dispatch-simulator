# tests/test_simulation.py
import datetime as dt

from app.models import Dasher, Location, Order
from app.simulation import run_simulation


def make_sample_data():
    dashers = [
        Dasher(
            id="d1",
            location=Location(lat=51.05011, lng=-114.08529),
            capacity=2,
        ),
        Dasher(
            id="d2",
            location=Location(lat=51.04427, lng=-114.06302),
            capacity=2,
        ),
    ]

    base = dt.datetime(2025, 1, 1, 12, 0, 0)
    orders = [
        Order(
            id="o1",
            location=Location(lat=51.0505, lng=-114.0850),
            created_at=base,
        ),
        Order(
            id="o2",
            location=Location(lat=51.0440, lng=-114.0635),
            created_at=base + dt.timedelta(minutes=1),
        ),
        Order(
            id="o3",
            location=Location(lat=51.0480, lng=-114.0800),
            created_at=base + dt.timedelta(minutes=2),
        ),
    ]

    return dashers, orders


def test_nearest_assigns_all_orders():
    dashers, orders = make_sample_data()
    assignments, metrics = run_simulation("nearest", dashers, orders)

    assert len(assignments) == len(orders)
    assert {a.order_id for a in assignments} == {o.id for o in orders}
    assert metrics.avg_distance_km > 0
    assert metrics.avg_wait_seconds >= 0


def test_load_balanced_assigns_all_orders():
    dashers, orders = make_sample_data()
    assignments, metrics = run_simulation("load_balanced", dashers, orders)

    assert len(assignments) == len(orders)
    # both dashers should get at least 1 order in this tiny example
    assert len(metrics.assignments_per_dasher) == 2


def test_batched_creates_wait_time():
    dashers, orders = make_sample_data()
    assignments, metrics = run_simulation(
        "batched", dashers, orders, batch_window_seconds=300
    )

    assert len(assignments) == len(orders)
    assert any(a.wait_seconds > 0 for a in assignments)
