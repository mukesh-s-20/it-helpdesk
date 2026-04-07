"""
IT Helpdesk / DevOps Incident Triage — OpenEnv Backend
FastAPI application exposing the environment API.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from env.incident_env import IncidentEnv
from env.tasks import load_task, list_tasks
from graders import run_grader
from models import (
    GraderResult,
    HealthResponse,
    ResetRequest,
    ResetResponse,
    StateResponse,
    StepRequest,
    StepResponse,
    TasksResponse,
)
# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="IT Helpdesk Incident Triage — OpenEnv",
    description=(
        "An OpenEnv-style environment where an AI agent acts as an IT Helpdesk / DevOps "
        "Incident Triage assistant. The agent diagnoses and resolves employee or system "
        "incidents using logs, tickets, system facts, and policy constraints."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Static files and templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Single shared environment instance (stateful, single-session)
env = IncidentEnv()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse, tags=["Meta"])
def health():
    """Health check and environment info."""
    tasks = list_tasks()
    return HealthResponse(
        status="ok",
        environment="IT Helpdesk Incident Triage OpenEnv",
        version="1.0.0",
        tasks_available=len(tasks),
        endpoints=[
            "GET  /          — health & info",
            "GET  /tasks     — list available tasks",
            "POST /reset     — start a new task",
            "POST /step      — execute an action",
            "GET  /state     — current environment state",
            "GET  /grade     — score the current episode",
            "GET  /ui        — interactive demo UI",
            "GET  /docs      — OpenAPI docs",
        ],
    )


@app.get("/tasks", response_model=TasksResponse, tags=["Environment"])
def get_tasks():
    """List all available tasks with metadata."""
    return TasksResponse(tasks=list_tasks())


@app.post("/reset", response_model=ResetResponse, tags=["Environment"])
def reset(request: ResetRequest):
    """
    Reset the environment and start a new task.

    - **task_id**: one of `easy_vpn_lock`, `medium_disk_full`, `hard_ssl_expiry`
    """
    valid_ids = {"easy_vpn_lock", "medium_disk_full", "hard_ssl_expiry"}
    if request.task_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_id '{request.task_id}'. Valid options: {sorted(valid_ids)}",
        )
    obs = env.reset(request.task_id)
    return ResetResponse(**obs)


@app.post("/step", response_model=StepResponse, tags=["Environment"])
def step(request: StepRequest):
    """
    Execute one action in the current environment.

    Returns the observation, reward, and updated environment status.
    """
    if env._task is None:
        raise HTTPException(status_code=400, detail="Environment not initialized. Call /reset first.")
    result = env.step(request.action)
    return StepResponse(**result)


@app.get("/state", response_model=StateResponse, tags=["Environment"])
def state():
    """Return the full current environment state."""
    s = env.state()
    return StateResponse(**s)


@app.get("/grade", response_model=GraderResult, tags=["Evaluation"])
def grade():
    """
    Run the grader for the current episode and return a score in [0.0, 1.0].

    Can be called at any point during or after an episode.
    """
    if env._task is None:
        raise HTTPException(status_code=400, detail="No active episode. Call /reset first.")
    current_state = env.state()
    task_def = env._task
    result = run_grader(task_def["task_id"], current_state, task_def)
    return result


@app.get("/ui", response_class=HTMLResponse, tags=["UI"])
def ui(request: Request):
    """Serve the interactive demo UI."""
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("main:app", host=host, port=port, reload=False)
