"""
Graders for the IT Helpdesk OpenEnv tasks.

Each grader takes the environment state and returns a score in [0.0, 1.0]
with deterministic, explainable partial credit logic.
"""

from __future__ import annotations

from models import GraderResult


def _base_grade(state: dict, task_def: dict) -> tuple[float, str]:
    """
    Shared grading logic with partial progress signals.

    Scoring components:
      - Required action coverage (0–0.5):  proportion of required actions completed
      - Reward signal (0–0.3):             normalized cumulative reward
      - Efficiency bonus (0–0.1):          reward fewer steps used vs max
      - Completion bonus (0.1):            flat bonus if task fully resolved
    Returns (score 0.0–1.0, feedback string).
    """
    required = set(task_def.get("required_for_success", []))
    actions_taken = set(state.get("actions_taken", []))
    cumulative_reward = state.get("cumulative_reward", 0.0)
    steps = state.get("steps", 0)
    max_steps = task_def.get("max_steps", 10)
    success = state.get("success", False)

    # --- Component 1: Required action coverage (0.0 – 0.50) ---
    completed_required = required & actions_taken
    coverage = len(completed_required) / max(len(required), 1)
    coverage_score = round(coverage * 0.50, 4)

    # --- Component 2: Reward signal normalized (0.0 – 0.30) ---
    # Theoretical max reward = sum of all positive rewards in reward_map
    reward_map = task_def.get("reward_map", {})
    max_possible_reward = sum(v for v in reward_map.values() if v > 0)
    reward_score = min(max(cumulative_reward / max(max_possible_reward, 0.01), 0.0), 1.0)
    reward_score = round(reward_score * 0.30, 4)

    # --- Component 3: Efficiency bonus (0.0 – 0.10) ---
    if steps > 0 and success:
        efficiency = max(0.0, 1.0 - (steps / max(max_steps, 1)))
        efficiency_score = round(efficiency * 0.10, 4)
    else:
        efficiency_score = 0.0

    # --- Component 4: Completion bonus (0.10) ---
    completion_score = 0.10 if success else 0.0

    total = round(min(coverage_score + reward_score + efficiency_score + completion_score, 1.0), 4)

    # Build feedback
    feedback_parts = []
    feedback_parts.append(f"Required actions completed: {len(completed_required)}/{len(required)} ({round(coverage*100)}%)")
    feedback_parts.append(f"Coverage score: {coverage_score:.3f}/0.500")
    feedback_parts.append(f"Reward score: {reward_score:.3f}/0.300 (cumulative reward: {cumulative_reward:.3f})")
    feedback_parts.append(f"Efficiency score: {efficiency_score:.3f}/0.100 ({steps}/{max_steps} steps used)")
    feedback_parts.append(f"Completion bonus: {completion_score:.3f}/0.100")
    feedback_parts.append(f"Total score: {total:.4f}")
    if success:
        feedback_parts.append("STATUS: PASSED — incident resolved successfully.")
    else:
        missing = required - actions_taken
        if missing:
            feedback_parts.append(f"STATUS: FAILED — missing required actions: {', '.join(sorted(missing))}")
        else:
            feedback_parts.append("STATUS: FAILED — max steps exceeded or ticket not resolved.")

    return total, "\n".join(feedback_parts)


def grade_easy(state: dict, task_def: dict) -> GraderResult:
    """
    Grader for Easy — Locked VPN Account.

    Partial credit for:
    - Inspecting account (+coverage)
    - Correctly identifying lockout (+coverage)
    - Unlocking account (+coverage, big reward)
    - Resolving ticket (+coverage, completion)
    Penalties for:
    - Unnecessary destructive actions (reboot, restart vpn)
    - Wrong diagnosis path
    """
    score, feedback = _base_grade(state, task_def)
    passing_score = task_def.get("passing_score", 0.7)

    return GraderResult(
        task_id=task_def["task_id"],
        difficulty=task_def["difficulty"],
        score=score,
        passed=score >= passing_score,
        passing_score=passing_score,
        cumulative_reward=state.get("cumulative_reward", 0.0),
        steps_taken=state.get("steps", 0),
        max_steps=task_def.get("max_steps", 10),
        required_actions_completed=len(
            set(task_def.get("required_for_success", [])) & set(state.get("actions_taken", []))
        ),
        required_actions_total=len(task_def.get("required_for_success", [])),
        actions_taken=state.get("actions_taken", []),
        feedback=feedback,
    )


def grade_medium(state: dict, task_def: dict) -> GraderResult:
    """
    Grader for Medium — Disk Full Service Outage.

    Partial credit for:
    - Checking logs and service status (+coverage)
    - Inspecting disk usage — identifies root cause (+coverage)
    - Clearing temp files — resolves root cause (+coverage, big reward)
    - Restarting portal service (+coverage)
    - Resolving ticket (+coverage, completion)
    Penalties for:
    - Full server reboot (-0.25 — dangerous and unnecessary)
    - Wrong subsystem investigation
    """
    score, feedback = _base_grade(state, task_def)
    passing_score = task_def.get("passing_score", 0.7)

    return GraderResult(
        task_id=task_def["task_id"],
        difficulty=task_def["difficulty"],
        score=score,
        passed=score >= passing_score,
        passing_score=passing_score,
        cumulative_reward=state.get("cumulative_reward", 0.0),
        steps_taken=state.get("steps", 0),
        max_steps=task_def.get("max_steps", 15),
        required_actions_completed=len(
            set(task_def.get("required_for_success", [])) & set(state.get("actions_taken", []))
        ),
        required_actions_total=len(task_def.get("required_for_success", [])),
        actions_taken=state.get("actions_taken", []),
        feedback=feedback,
    )


def grade_hard(state: dict, task_def: dict) -> GraderResult:
    """
    Grader for Hard — Expired SSL Certificate on Billing Service.

    Partial credit for:
    - Checking logs (+coverage)
    - Inspecting SSL certificate — identifies expiry (+coverage)
    - Checking gateway status — identifies cascade (+coverage)
    - Renewing SSL certificate — core fix (+coverage, large reward)
    - Deploying new certificate (+coverage)
    - Restarting gateway — activates fix (+coverage)
    - Verifying billing access — confirms fix (+coverage)
    - Resolving ticket with RCA (+coverage, completion)
    Penalties for:
    - Server reboot (-0.25)
    - Irrelevant subsystem actions
    """
    score, feedback = _base_grade(state, task_def)
    passing_score = task_def.get("passing_score", 0.75)

    return GraderResult(
        task_id=task_def["task_id"],
        difficulty=task_def["difficulty"],
        score=score,
        passed=score >= passing_score,
        passing_score=passing_score,
        cumulative_reward=state.get("cumulative_reward", 0.0),
        steps_taken=state.get("steps", 0),
        max_steps=task_def.get("max_steps", 20),
        required_actions_completed=len(
            set(task_def.get("required_for_success", [])) & set(state.get("actions_taken", []))
        ),
        required_actions_total=len(task_def.get("required_for_success", [])),
        actions_taken=state.get("actions_taken", []),
        feedback=feedback,
    )


GRADER_MAP = {
    "easy_vpn_lock": grade_easy,
    "medium_disk_full": grade_medium,
    "hard_ssl_expiry": grade_hard,
}


def run_grader(task_id: str, state: dict, task_def: dict) -> GraderResult:
    """Dispatch to the correct grader for a task."""
    grader = GRADER_MAP.get(task_id)
    if grader is None:
        raise ValueError(f"No grader found for task_id '{task_id}'")
    return grader(state, task_def)
