"""
Typed Pydantic request/response models for the IT Helpdesk OpenEnv API.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class ResetRequest(BaseModel):
    task_id: str = Field(
        default="easy_vpn_lock",
        description="Task ID to initialize. One of: easy_vpn_lock, medium_disk_full, hard_ssl_expiry",
        examples=["easy_vpn_lock", "medium_disk_full", "hard_ssl_expiry"],
    )


class StepRequest(BaseModel):
    action: str = Field(
        description="Action string to execute in the environment.",
        examples=["check_logs", "inspect_account", "unlock_account", "resolve_ticket"],
    )


# ---------------------------------------------------------------------------
# Shared Sub-Models
# ---------------------------------------------------------------------------

class TicketInfo(BaseModel):
    id: str
    priority: str
    user: str
    subject: str
    body: str
    created_at: str


class ActionHistoryEntry(BaseModel):
    step: int
    action: str
    reward: float
    observation_preview: str


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class ResetResponse(BaseModel):
    task_id: str
    difficulty: str
    title: str
    ticket: TicketInfo
    logs: list[str]
    system_facts: dict[str, Any]
    available_actions: list[str]
    observation: str
    reward: float
    cumulative_reward: float
    steps: int
    max_steps: int
    done: bool
    success: bool
    action_history: list[ActionHistoryEntry]


class StepResponse(BaseModel):
    action: str
    observation: str
    reward: float
    cumulative_reward: float
    steps: int
    max_steps: int
    done: bool
    success: bool
    action_history: list[ActionHistoryEntry]
    info: str


class StateResponse(BaseModel):
    task_id: Optional[str] = None
    difficulty: Optional[str] = None
    title: Optional[str] = None
    ticket: Optional[TicketInfo] = None
    system_facts: Optional[dict[str, Any]] = None
    logs: Optional[list[str]] = None
    available_actions: Optional[list[str]] = None
    action_history: Optional[list[ActionHistoryEntry]] = None
    actions_taken: Optional[list[str]] = None
    cumulative_reward: Optional[float] = None
    steps: Optional[int] = None
    max_steps: Optional[int] = None
    done: Optional[bool] = None
    success: Optional[bool] = None
    required_actions_total: Optional[int] = None
    required_actions_completed: Optional[int] = None
    progress_pct: Optional[float] = None
    status: Optional[str] = None
    message: Optional[str] = None


class TaskMeta(BaseModel):
    task_id: str
    difficulty: str
    title: str
    description: str
    max_steps: int
    passing_score: float


class TasksResponse(BaseModel):
    tasks: list[TaskMeta]


class GraderResult(BaseModel):
    task_id: str
    difficulty: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    passing_score: float
    cumulative_reward: float
    steps_taken: int
    max_steps: int
    required_actions_completed: int
    required_actions_total: int
    actions_taken: list[str]
    feedback: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    tasks_available: int
    endpoints: list[str]
