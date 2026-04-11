"""
Graders for the IT Helpdesk OpenEnv tasks.

Each grader takes the environment state and returns a score strictly within (0, 1)
with deterministic, explainable partial credit logic.
"""

from __future__ import annotations

from models import GraderResult


def _safe_score(x: float) -> float:
    """
    Ensure score is STRICTLY between 0 and 1 (exclusive).
    Never allow exactly 0.0 or exactly 1.0.
    Uses 4 decimal places — min=0.0001, max=0.9999.
    """
    x = float(x)
    # Clamp to open interval (0, 1)
    x = max(0.0001, min(x, 0.9999))
    # Round to 4 decimal places
    x = round(x, 4)
    # Final safety check after rounding (round(0.99995, 4) could give 1.0)
    if x <= 0.0:
        return 0.0001
    if x >= 1.0:
        return 0.9999
    return x


def _base_grade(state: dict, task_def: dict) -> tuple[float, str]:
    """
    Shared grading logic with partial progress signals.
    """

    required = set(task_def.get("required_for_success", []))
    actions_taken = set(state.get("actions_taken", []))
    cumulative_reward = state.get("cumulative_reward", 0.0)
    steps = state.get("steps", 0)
    max_steps = task_def.get("max_steps", 10)
    success = state.get("success", False)

    # Required action coverage (0.0 – 0.50)
    completed_required = required & actions_taken
    coverage = len(completed_required) / max(len(required), 1)
    coverage_score = round(coverage * 0.50, 4)

    # Reward signal normalized (0.0 – 0.30)
    reward_map = task_def.get("reward_map", {})
    max_possible_reward = sum(v for v in reward_map.values() if v > 0)

    reward_ratio = 0.0
    if max_possible_reward > 0:
        reward_ratio = cumulative_reward / max_possible_reward

    reward_ratio = max(0.0, min(reward_ratio, 1.0))
    reward_score = round(reward_ratio * 0.30, 4)

    # Efficiency bonus (0.0 – 0.10)
    if steps > 0 and success:
        efficiency = max(0.0, 1.0 - (steps / max(max_steps, 1)))
        efficiency_score = round(efficiency * 0.10, 4)
    else:
        efficiency_score = 0.0

    # Completion bonus (0.10)
    completion_score = 0.10 if success else 0.0

    raw_total = coverage_score + reward_score + efficiency_score + completion_score

    # Force raw_total inside valid range before rounding
    raw_total = max(0.0002, min(raw_total, 0.9998))  # extra margin before rounding

    # Final safe score
    total = _safe_score(raw_total)

    feedback_parts = []
    feedback_parts.append(
        f"Required actions completed: {len(completed_required)}/{len(required)} ({round(coverage * 100)}%)"
    )
    feedback_parts.append(f"Coverage score: {coverage_score:.3f}/0.500")
    feedback_parts.append(
        f"Reward score: {reward_score:.3f}/0.300 (cumulative reward: {cumulative_reward:.3f})"
    )
    feedback_parts.append(
        f"Efficiency score: {efficiency_score:.3f}/0.100 ({steps}/{max_steps} steps used)"
    )
    feedback_parts.append(f"Completion bonus: {completion_score:.3f}/0.100")
    feedback_parts.append(f"Final clamped score: {total:.4f}")

    if success:
        feedback_parts.append("STATUS: PASSED — incident resolved successfully.")
    else:
        missing = required - actions_taken
        if missing:
            feedback_parts.append(
                f"STATUS: FAILED — missing required actions: {', '.join(sorted(missing))}"
            )
        else:
            feedback_parts.append(
                "STATUS: FAILED — max steps exceeded or ticket not resolved."
            )

    print(f"[GRADER DEBUG] raw_total={raw_total} total={total}")

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
            set(task_def.get("required_for_success", []))
            & set(state.get("actions_taken", []))
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
            set(task_def.get("required_for_success", []))
            & set(state.get("actions_taken", []))
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
            set(task_def.get("required_for_success", []))
            & set(state.get("actions_taken", []))
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
