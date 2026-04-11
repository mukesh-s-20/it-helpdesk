"""
Graders for the IT Helpdesk OpenEnv tasks.

Each grader returns a score STRICTLY between 0 and 1 (exclusive).
Never 0.0, never 1.0.
"""

from __future__ import annotations

from models import GraderResult


def _safe_score(x: float) -> float:
    """
    Clamp score to strictly open interval (0.0001, 0.9999).
    Handles all edge cases including floating point rounding surprises.
    """
    x = float(x)
    # Hard clamp first
    x = max(0.0001, min(x, 0.9999))
    # Round to 4 decimal places
    x = round(x, 4)
    # Post-round safety (round(0.99995, 4) can become 1.0 in Python)
    if x <= 0.0:
        return 0.0001
    if x >= 1.0:
        return 0.9999
    return x


def _base_grade(state: dict, task_def: dict) -> tuple[float, str]:
    """
    Shared grading logic with partial progress signals.

    Scoring components:
      - Required action coverage  0.0 – 0.50
      - Reward signal normalized  0.0 – 0.30
      - Efficiency bonus          0.0 – 0.10  (only on success)
      - Completion bonus          0.10         (only on success)
    """
    required = set(task_def.get("required_for_success", []))
    actions_taken = set(state.get("actions_taken", []))
    cumulative_reward = state.get("cumulative_reward", 0.0)
    steps = state.get("steps", 0)
    max_steps = task_def.get("max_steps", 10)
    success = state.get("success", False)

    # Component 1 — required action coverage (0.0 – 0.50)
    completed_required = required & actions_taken
    coverage = len(completed_required) / max(len(required), 1)
    coverage_score = round(coverage * 0.50, 4)

    # Component 2 — normalized reward signal (0.0 – 0.30)
    reward_map = task_def.get("reward_map", {})
    max_possible_reward = sum(v for v in reward_map.values() if v > 0)
    reward_ratio = 0.0
    if max_possible_reward > 0:
        reward_ratio = cumulative_reward / max_possible_reward
    reward_ratio = max(0.0, min(reward_ratio, 1.0))
    reward_score = round(reward_ratio * 0.30, 4)

    # Component 3 — efficiency bonus (0.0 – 0.10, only on success)
    efficiency_score = 0.0
    if steps > 0 and success:
        efficiency = max(0.0, 1.0 - (steps / max(max_steps, 1)))
        efficiency_score = round(efficiency * 0.10, 4)

    # Component 4 — completion bonus (0.10, only on success)
    completion_score = 0.10 if success else 0.0

    # Sum components — theoretical max = 0.50+0.30+0.10+0.10 = 1.0
    raw_total = coverage_score + reward_score + efficiency_score + completion_score

    # Clamp with margin BEFORE _safe_score to survive rounding
    raw_total = max(0.0002, min(raw_total, 0.9998))

    # Final safe score — guaranteed strictly in (0, 1)
    total = _safe_score(raw_total)

    # Build feedback text
    feedback_parts = [
        f"Required actions completed: {len(completed_required)}/{len(required)} ({round(coverage * 100)}%)",
        f"Coverage score:    {coverage_score:.4f} / 0.5000",
        f"Reward score:      {reward_score:.4f} / 0.3000  (cumulative reward: {cumulative_reward:.4f})",
        f"Efficiency score:  {efficiency_score:.4f} / 0.1000  ({steps}/{max_steps} steps used)",
        f"Completion bonus:  {completion_score:.4f} / 0.1000",
        f"Final score:       {total:.4f}",
    ]
    if success:
        feedback_parts.append("STATUS: PASSED — incident resolved successfully.")
    else:
        missing = required - actions_taken
        if missing:
            feedback_parts.append(
                f"STATUS: FAILED — missing required actions: {', '.join(sorted(missing))}"
            )
        else:
            feedback_parts.append("STATUS: FAILED — max steps exceeded or ticket not resolved.")

    return total, "\n".join(feedback_parts)


def grade_easy(state: dict, task_def: dict) -> GraderResult:
    score, feedback = _base_grade(state, task_def)
    score = _safe_score(score)
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
    score, feedback = _base_grade(state, task_def)
    score = _safe_score(score)
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
    score, feedback = _base_grade(state, task_def)
    score = _safe_score(score)
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
    "easy_vpn_lock":    grade_easy,
    "medium_disk_full": grade_medium,
    "hard_ssl_expiry":  grade_hard,
}


def run_grader(task_id: str, state: dict, task_def: dict) -> GraderResult:
    """Dispatch to the correct grader for a task."""
    grader = GRADER_MAP.get(task_id)
    if grader is None:
        raise ValueError(f"No grader found for task_id '{task_id}'")
    return grader(state, task_def)
