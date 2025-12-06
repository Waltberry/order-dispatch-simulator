# dashboard/dashboard_app.py
from __future__ import annotations

import sys
from pathlib import Path

# --- make project root importable when running via `streamlit run dashboard/...` ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from typing import List

import pandas as pd
import streamlit as st
from pydantic import ValidationError


from app.models import Dasher, Order
from app.simulation import run_simulation

st.set_page_config(page_title="Order Dispatch Simulator", layout="wide")

st.title("Order Dispatch Simulator")
st.write(
    "Compare different dispatch strategies (nearest, load-balanced, batched) on a toy dataset of dashers and orders."
)

st.sidebar.header("Configuration")

strategy = st.sidebar.selectbox(
    "Dispatch strategy",
    options=["nearest", "load_balanced", "batched"],
    format_func=lambda s: {
        "nearest": "Nearest dasher",
        "load_balanced": "Load-balanced",
        "batched": "Batched (time-window)",
    }[s],
)

batch_window = 60
if strategy == "batched":
    batch_window = st.sidebar.slider(
        "Batch window (seconds)", min_value=30, max_value=600, value=60, step=30
    )

use_sample = st.sidebar.checkbox("Use sample data from /data", value=True)

if use_sample:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    dashers_path = data_dir / "dashers_sample.json"
    orders_path = data_dir / "orders_sample.json"

    st.sidebar.write(f"Dashers: `{dashers_path.name}`")
    st.sidebar.write(f"Orders: `{orders_path.name}`")

    dashers_data = json.loads(dashers_path.read_text())
    orders_data = json.loads(orders_path.read_text())
else:
    st.sidebar.write("Paste JSON for dashers and orders below.")

    dashers_json = st.text_area("Dashers JSON", height=150)
    orders_json = st.text_area("Orders JSON", height=200)

    if not dashers_json or not orders_json:
        st.stop()

    try:
        dashers_data = json.loads(dashers_json)
        orders_data = json.loads(orders_json)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

try:
    dashers: List[Dasher] = [Dasher(**d) for d in dashers_data]
    orders: List[Order] = [Order(**o) for o in orders_data]
except ValidationError as e:
    st.error(f"Validation error: {e}")
    st.stop()

if st.button("Run simulation"):
    assignments, metrics = run_simulation(
        strategy_name=strategy,
        dashers=dashers,
        orders=orders,
        batch_window_seconds=batch_window,
    )

    st.subheader("Summary metrics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg distance (km)", f"{metrics.avg_distance_km:.2f}")
    c2.metric("Avg wait (s)", f"{metrics.avg_wait_seconds:.1f}")
    c3.metric("Avg driver utilization", f"{metrics.avg_driver_utilization:.2f}")

    st.subheader("Assignments table")
    st.dataframe([a.model_dump() for a in assignments])

    st.subheader("Assignments per dasher")
    df_dashers = pd.DataFrame(
        [
            {
                "dasher_id": d.id,
                "lat": d.location.lat,
                "lng": d.location.lng,
                "assigned_orders": metrics.assignments_per_dasher.get(d.id, 0),
            }
            for d in dashers
        ]
    )
    st.bar_chart(df_dashers.set_index("dasher_id")["assigned_orders"])

    st.subheader("Map view (dashers + orders)")
    df_dashers_map = df_dashers[["lat", "lng"]].copy()
    # df_dashers_map.rename(columns={"lng": "lon"}, inplace=True)
    df_dashers_map["type"] = "dasher"

    df_orders_map = pd.DataFrame(
        [
            {"lat": o.location.lat, "lng": o.location.lng, "type": "order"}
            for o in orders
        ]
    )

    df_all = pd.concat([df_dashers_map, df_orders_map], ignore_index=True)
    # st.map(df_all[["lat", "lng"]])
    st.map(df_all, latitude="lat", longitude="lng")
else:
    st.info("Configure parameters and click **Run simulation**.")
