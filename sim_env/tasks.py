import json
import os
from pathlib import Path

TASKS_DIR = Path(__file__).parent.parent / "tasks"


def load_task(task_id: str) -> dict:
    """Load a task definition from JSON file."""
    task_file = TASKS_DIR / f"{task_id}.json"
    if not task_file.exists():
        raise ValueError(f"Task '{task_id}' not found in {TASKS_DIR}")
    with open(task_file, "r") as f:
        return json.load(f)


def list_tasks() -> list[dict]:
    """Return metadata for all available tasks."""
    tasks = []
    for task_file in sorted(TASKS_DIR.glob("*.json")):
        with open(task_file, "r") as f:
            data = json.load(f)
        tasks.append({
            "task_id": data["task_id"],
            "difficulty": data["difficulty"],
            "title": data["title"],
            "description": data["description"],
            "max_steps": data["max_steps"],
            "passing_score": data["passing_score"],
        })
    return tasks


TASK_IDS = ["easy_vpn_lock", "medium_disk_full", "hard_ssl_expiry"]
