"""
IncidentEnv: OpenEnv-style environment for IT Helpdesk / DevOps Incident Triage.

Implements:
- reset(task_id) -> Observation
- step(action) -> StepResult
- state() -> EnvironmentState
"""

from __future__ import annotations

import time
from typing import Optional

from app_env.tasks import load_task


class IncidentEnv:
    """Deterministic IT Incident Triage environment."""

    def __init__(self):
        self._task: Optional[dict] = None
        self._action_history: list[dict] = []
        self._cumulative_reward: float = 0.0
        self._steps: int = 0
        self._done: bool = False
        self._success: bool = False
        self._actions_taken: set[str] = set()
        self._started_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def reset(self, task_id: str) -> dict:
        """Reset environment to a new task. Returns initial observation."""
        self._task = load_task(task_id)
        self._action_history = []
        self._cumulative_reward = 0.0
        self._steps = 0
        self._done = False
        self._success = False
        self._actions_taken = set()
        self._started_at = time.time()

        return {
            "task_id": self._task["task_id"],
            "difficulty": self._task["difficulty"],
            "title": self._task["title"],
            "ticket": self._task["ticket"],
            "logs": self._task["logs"],
            "system_facts": self._redact_system_facts(self._task["system_facts"]),
            "available_actions": self._task["valid_actions"] + self._task["invalid_actions"],
            "observation": (
                f"NEW INCIDENT RECEIVED\n"
                f"Ticket: {self._task['ticket']['id']}\n"
                f"Priority: {self._task['ticket']['priority'].upper()}\n"
                f"Subject: {self._task['ticket']['subject']}\n\n"
                f"{self._task['ticket']['body']}\n\n"
                f"Initial system logs are available. Begin diagnosis."
            ),
            "reward": 0.0,
            "cumulative_reward": 0.0,
            "steps": 0,
            "max_steps": self._task["max_steps"],
            "done": False,
            "success": False,
            "action_history": [],
        }

    def step(self, action: str) -> dict:
        """Execute one action and return the result."""
        if self._task is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        if self._done:
            return self._build_step_result(
                action=action,
                observation="Episode is already complete. Call reset() to start a new task.",
                reward=0.0,
                info="done",
            )

        self._steps += 1
        action = action.strip().lower().replace(" ", "_")

        # Determine reward
        reward = self._compute_reward(action)
        self._cumulative_reward = round(self._cumulative_reward + reward, 4)

        # Get observation text
        observation = self._get_observation(action)

        # Track actions
        self._actions_taken.add(action)
        self._action_history.append({
            "step": self._steps,
            "action": action,
            "reward": reward,
            "observation_preview": observation[:120] + "..." if len(observation) > 120 else observation,
        })

        # Check termination
        self._check_done()

        return self._build_step_result(
            action=action,
            observation=observation,
            reward=reward,
            info="ok",
        )

    def state(self) -> dict:
        """Return full current environment state."""
        if self._task is None:
            return {"status": "uninitialized", "message": "Call /reset to start a task."}

        required = set(self._task.get("required_for_success", []))
        completed_required = required & self._actions_taken

        return {
            "task_id": self._task["task_id"],
            "difficulty": self._task["difficulty"],
            "title": self._task["title"],
            "ticket": self._task["ticket"],
            "system_facts": self._redact_system_facts(self._task["system_facts"]),
            "logs": self._task["logs"],
            "available_actions": self._task["valid_actions"] + self._task["invalid_actions"],
            "action_history": self._action_history,
            "actions_taken": list(self._actions_taken),
            "cumulative_reward": self._cumulative_reward,
            "steps": self._steps,
            "max_steps": self._task["max_steps"],
            "done": self._done,
            "success": self._success,
            "required_actions_total": len(required),
            "required_actions_completed": len(completed_required),
            "progress_pct": round(len(completed_required) / max(len(required), 1) * 100, 1),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_reward(self, action: str) -> float:
        """Compute deterministic reward for an action."""
        reward_map = self._task.get("reward_map", {})

        if action in reward_map:
            r = reward_map[action]
        else:
            r = reward_map.get("unknown_action", -0.05)

        # Penalty for repeated actions (diminishing returns after first use)
        if action in self._actions_taken and r > 0:
            r = round(r * 0.1, 4)  # Drastically reduced reward for repeating

        return round(r, 4)

    def _get_observation(self, action: str) -> str:
        """Return the observation text for a given action."""
        observations = self._task.get("observations", {})
        if action in observations:
            return observations[action]
        return (
            f"ACTION: {action}\n"
            f"Result: Unknown action. No system response recorded. "
            f"This action is not recognized as valid for this incident."
        )

    def _check_done(self):
        """Check if the episode is over."""
        required = set(self._task.get("required_for_success", []))
        required_done = required.issubset(self._actions_taken)

        # Success: all required actions taken AND ticket resolved
        if required_done and "resolve_ticket" in self._actions_taken:
            self._done = True
            self._success = True
            # Final completion bonus
            self._cumulative_reward = round(self._cumulative_reward + 0.1, 4)
            return

        # Failure: max steps exceeded
        if self._steps >= self._task.get("max_steps", 10):
            self._done = True
            self._success = False

    def _build_step_result(self, action: str, observation: str, reward: float, info: str) -> dict:
        return {
            "action": action,
            "observation": observation,
            "reward": reward,
            "cumulative_reward": self._cumulative_reward,
            "steps": self._steps,
            "max_steps": self._task["max_steps"],
            "done": self._done,
            "success": self._success,
            "action_history": self._action_history,
            "info": info,
        }

    def _redact_system_facts(self, facts: dict) -> dict:
        """Redact hidden root cause facts from system_facts for the agent."""
        redacted_keys = {"hidden_root_cause"}
        return {k: v for k, v in facts.items() if k not in redacted_keys}
