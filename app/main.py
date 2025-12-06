# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .schemas import SimulationRequest, SimulationResponse
from .simulation import run_simulation

app = FastAPI(
    title="Order Dispatch Simulator",
    description="Simulate different dispatch strategies for dashers and orders.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "message": "Order Dispatch Simulator API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/simulate", response_model=SimulationResponse)
def simulate(request: SimulationRequest) -> SimulationResponse:
    assignments, metrics = run_simulation(
        strategy_name=request.strategy,
        dashers=request.dashers,
        orders=request.orders,
        batch_window_seconds=request.batch_window_seconds or 60,
    )
    return SimulationResponse(
        strategy=request.strategy,
        assignments=assignments,
        metrics=metrics,
    )
