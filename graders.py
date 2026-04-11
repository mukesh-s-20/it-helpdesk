from __future__ import annotations

from math import isfinite
from models import GraderResult


def _safe_score(x: float) -> float:
    """
    Guarantee a valid score strictly inside (0,1) and never NaN.
    """
    try:
        x = float(x)
    except Exception:
        return 0.0001

    if not isfinite(x):
        return 0.0001

    x = max(0.0001, min(x, 0.9999))
    x = round(x, 4)

    if x <= 0.0:
        return 0.0001
    if x >= 1.0:
        return 0.9999

    return x


def _base_grade(state: dict, task_def: dict) -> tuple[float, str]:
    
    required = set(task_def.get("required_actions", []))

    actions_taken = set(state.get("actions_taken", []))
    cumulative_reward = state.get("cumulative_reward", 0.0) or 0.0
    steps = state.get("steps", 0) or 0
    max_steps = task_def.get("max_steps", 10)
    success = bool(state.get("success", False))

    # 1. Required coverage (0–0.5)
    completed = required & actions_taken
    coverage = len(completed) / max(len(required), 1)
    coverage_score = coverage * 0.50

    # 2. Reward signal (0–0.3)
    reward_map = task_def.get("reward_map", {})
    max_reward = sum(v for v in reward_map.values() if v > 0)

    reward_ratio = 0.0
    if max_reward > 0:
        reward_ratio = cumulative_reward / max_reward

    reward_ratio = max(0.0, min(reward_ratio, 1.0))
    reward_score = reward_ratio * 0.30

    # 3. Efficiency (0–0.1)
    efficiency_score = 0.0
    if success and steps > 0:
        efficiency = max(0.0, 1.0 - steps / max(max_steps, 1))
        efficiency_score = efficiency * 0.10

    # 4. Completion bonus (0.1)
    completion_score = 0.10 if success else 0.0

    raw_total = coverage_score + reward_score + efficiency_score + completion_score
    total = _safe_score(raw_total)

    feedback = (
        f"Required completed: {len(completed)}/{len(required)}\n"
        f"Coverage score: {coverage_score:.4f}\n"
        f"Reward score: {reward_score:.4f}\n"
        f"Efficiency score: {efficiency_score:.4f}\n"
        f"Completion bonus: {completion_score:.4f}\n"
        f"Final score: {total:.4f}"
    )

    return total, feedback


def _wrap(task_def, state, score, feedback, passing):
    score = _safe_score(score)

    return GraderResult(
        task_id=task_def["task_id"],
        difficulty=task_def["difficulty"],
        score=score,
        passed=score >= passing,
        passing_score=passing,
        cumulative_reward=state.get("cumulative_reward", 0.0) or 0.0,
        steps_taken=state.get("steps", 0) or 0,
        max_steps=task_def.get("max_steps", 10),
        required_actions_completed=len(
            set(task_def.get("required_actions", [])) & set(state.get("actions_taken", []))
        ),
        required_actions_total=len(task_def.get("required_actions", [])),
        actions_taken=state.get("actions_taken", []),
        feedback=feedback,
    )


def grade_easy(state, task_def):
    s, f = _base_grade(state, task_def)
    return _wrap(task_def, state, s, f, task_def.get("passing_score", 0.7))


def grade_medium(state, task_def):
    s, f = _base_grade(state, task_def)
    return _wrap(task_def, state, s, f, task_def.get("passing_score", 0.7))


def grade_hard(state, task_def):
    s, f = _base_grade(state, task_def)
    return _wrap(task_def, state, s, f, task_def.get("passing_score", 0.75))


GRADER_MAP = {
    "easy_vpn_lock": grade_easy,
    "medium_disk_full": grade_medium,
    "hard_ssl_expiry": grade_hard,
}


def run_grader(task_id, state, task_def):
    grader = GRADER_MAP.get(task_id)
    if not grader:
        raise ValueError(f"No grader found for task_id '{task_id}'")
    return grader(state, task_def)
