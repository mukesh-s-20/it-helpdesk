"""
IT Helpdesk / DevOps Incident Triage — OpenEnv Backend
FastAPI application exposing the environment API.
"""

from agent import choose_action
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
from fastapi.responses import RedirectResponse

from sim_env.incident_env import IncidentEnv
from sim_env.tasks import load_task, list_tasks
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

@app.get("/", tags=["Meta"])
def health():
    return RedirectResponse(url="/ui")


@app.get("/tasks", response_model=TasksResponse, tags=["Environment"])
def get_tasks():
    """List all available tasks with metadata."""
    return TasksResponse(tasks=list_tasks())


@app.post("/reset", response_model=ResetResponse, tags=["Environment"])
def reset(request: ResetRequest | None = None):
    """
    Reset the environment and start a new task.
    """
    task_aliases = {
        "task_1": "easy_vpn_lock",
        "task_2": "medium_disk_full",
        "task_3": "hard_ssl_expiry",
    }

    if request is None:
        task_id = "easy_vpn_lock"
    else:
        task_id = task_aliases.get(request.task_id, request.task_id)

    valid_ids = {"easy_vpn_lock", "medium_disk_full", "hard_ssl_expiry"}

    if task_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_id '{task_id}'. Valid options: {sorted(valid_ids)}",
        )

    obs = env.reset(task_id)
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

@app.post("/solve", tags=["Agent"])
def solve(request: ResetRequest | None = None):
    """
    Use the LLM agent to solve a task automatically.
    This endpoint is required so the evaluator can verify LLM proxy usage.
    """
    task_aliases = {
        "task_1": "easy_vpn_lock",
        "task_2": "medium_disk_full",
        "task_3": "hard_ssl_expiry",
    }

    if request is None:
        task_id = "easy_vpn_lock"
    else:
        task_id = task_aliases.get(request.task_id, request.task_id)

    valid_ids = {"easy_vpn_lock", "medium_disk_full", "hard_ssl_expiry"}

    if task_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_id '{task_id}'. Valid options: {sorted(valid_ids)}",
        )

    obs = env.reset(task_id)

    trajectory = []

    while not env._done and env._steps < env._task["max_steps"]:
        try:
            action = choose_action(obs)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM agent failed: {str(e)}")

        step_result = env.step(action)
        trajectory.append({
            "step": env._steps,
            "action": action,
            "reward": step_result["reward"],
            "done": step_result["done"],
            "success": step_result["success"],
        })

        obs = {
            **env.state(),
            "observation": step_result["observation"]
        }

    grade_result = run_grader(env._task["task_id"], env.state(), env._task)

    return {
        "task_id": env._task["task_id"],
        "success": env._success,
        "done": env._done,
        "steps": env._steps,
        "cumulative_reward": env._cumulative_reward,
        "trajectory": trajectory,
        "final_state": env.state(),
        "grade": grade_result,
    }


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
