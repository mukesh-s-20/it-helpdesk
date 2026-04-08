"""
inference.py — IT Helpdesk Incident Triage OpenEnv
Baseline inference script for evaluation.

Supports:
  - OpenAI-compatible LLM via API_BASE_URL + MODEL_NAME + API_KEY / HF_TOKEN
  - Deterministic heuristic fallback if LLM is unavailable

Structured stdout logging:
  [START] — episode begin
  [STEP]  — each action step
  [END]   — episode complete with final score

Usage:
  python inference.py
  API_BASE_URL=https://llm-proxy/v1 MODEL_NAME=... API_KEY=... python inference.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# The evaluator injects:
#   API_BASE_URL  — the LiteLLM proxy endpoint for LLM calls
#   MODEL_NAME    — the model to use
#   API_KEY       — the API key for the LLM proxy
#   HF_TOKEN      — alternative API key (Hugging Face)
#
# ENV_SERVER_URL is the OpenEnv FastAPI backend (running locally in Docker).
# ---------------------------------------------------------------------------

# LLM proxy config — injected by evaluator
API_BASE_URL: str = os.getenv("API_BASE_URL", "")
MODEL_NAME:   str = os.getenv("MODEL_NAME", "")
API_KEY:      str = os.getenv("API_KEY", "") or os.getenv("HF_TOKEN", "")

# OpenEnv environment server (local FastAPI, always on 7860 inside Docker)
ENV_SERVER_URL: str = os.getenv("ENV_SERVER_URL", "http://localhost:7860")
ENV_BASE: str = ENV_SERVER_URL.rstrip("/")

TASK_IDS = ["easy_vpn_lock", "medium_disk_full", "hard_ssl_expiry"]

# ---------------------------------------------------------------------------
# Deterministic heuristic action sequences
# (used when LLM is unavailable or returns invalid actions)
# ---------------------------------------------------------------------------

HEURISTIC_SEQUENCES = {
    "easy_vpn_lock": [
        "check_logs",
        "inspect_account",
        "identify_lock_reason",
        "unlock_account",
        "verify_vpn_access",
        "resolve_ticket",
    ],
    "medium_disk_full": [
        "check_logs",
        "check_service_status",
        "inspect_disk_usage",
        "identify_large_files",
        "clear_temp_files",
        "clear_old_logs",
        "restart_portal_service",
        "verify_service_health",
        "resolve_ticket",
    ],
    "hard_ssl_expiry": [
        "check_logs",
        "check_service_status",
        "inspect_ssl_certificate",
        "identify_cert_expiry",
        "check_gateway_status",
        "renew_ssl_certificate",
        "deploy_new_certificate",
        "restart_gateway",
        "verify_ssl_handshake",
        "verify_billing_access",
        "resolve_ticket",
    ],
}


# ---------------------------------------------------------------------------
# Environment API helpers
# ---------------------------------------------------------------------------

def env_reset(task_id: str) -> dict:
    resp = requests.post(f"{ENV_BASE}/reset", json={"task_id": task_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def env_step(action: str) -> dict:
    resp = requests.post(f"{ENV_BASE}/step", json={"action": action}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def env_state() -> dict:
    resp = requests.get(f"{ENV_BASE}/state", timeout=30)
    resp.raise_for_status()
    return resp.json()


def env_grade() -> dict:
    resp = requests.get(f"{ENV_BASE}/grade", timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# LLM helpers — uses API_BASE_URL + API_KEY as required by evaluator
# ---------------------------------------------------------------------------

def build_llm_client():
    """
    Build OpenAI client using evaluator-injected API_BASE_URL and API_KEY.
    Returns None (triggers heuristic fallback) if config is missing.
    """
    if not API_BASE_URL or not MODEL_NAME:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=API_BASE_URL,
            api_key=API_KEY if API_KEY else "dummy",
        )
        return client
    except ImportError:
        return None
    except Exception:
        return None


def llm_choose_action(
    client,
    model: str,
    task_title: str,
    ticket_body: str,
    observation: str,
    available_actions: list[str],
    action_history: list[dict],
) -> Optional[str]:
    """Ask the LLM to choose the next action. Returns action string or None on failure."""
    if client is None or not model:
        return None

    history_text = ""
    if action_history:
        lines = [f"  Step {e['step']}: {e['action']} (reward: {e['reward']})" for e in action_history[-5:]]
        history_text = "\nRecent action history:\n" + "\n".join(lines)

    prompt = f"""You are an expert IT Helpdesk and DevOps engineer triaging a live incident.

INCIDENT: {task_title}
TICKET: {ticket_body}

CURRENT OBSERVATION:
{observation}
{history_text}

AVAILABLE ACTIONS (pick EXACTLY one, return only the action string, nothing else):
{chr(10).join(f'  - {a}' for a in available_actions)}

Choose the single most effective next action to diagnose or resolve this incident.
Respond with ONLY the action string, no explanation, no punctuation."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=32,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip().lower().replace(" ", "_")
        # Validate it's in available actions
        if raw in [a.lower() for a in available_actions]:
            return raw
        # Try partial match
        for a in available_actions:
            if raw in a or a in raw:
                return a
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main inference loop
# ---------------------------------------------------------------------------

def run_task(task_id: str, client, model: str) -> dict:
    """Run a full episode for one task. Returns grade result."""

    # Reset
    obs = env_reset(task_id)
    ticket = obs.get("ticket", {})
    available_actions = obs.get("available_actions", [])

    print(f"[START] task_id={task_id} difficulty={obs.get('difficulty')} title={obs.get('title')!r}")
    print(f"[START] ticket_id={ticket.get('id')} priority={ticket.get('priority')}")
    print(f"[START] max_steps={obs.get('max_steps')} available_actions={len(available_actions)}")
    sys.stdout.flush()

    current_observation = obs.get("observation", "")
    heuristic_seq = HEURISTIC_SEQUENCES.get(task_id, [])
    heuristic_idx = 0
    use_llm = client is not None and bool(model)

    step_num = 0
    done = False

    while not done:
        step_num += 1

        # Choose action: LLM first, then heuristic fallback
        action = None
        action_source = "heuristic"

        if use_llm:
            state = env_state()
            action_history = state.get("action_history", [])
            action = llm_choose_action(
                client=client,
                model=model,
                task_title=obs.get("title", task_id),
                ticket_body=ticket.get("body", ""),
                observation=current_observation,
                available_actions=available_actions,
                action_history=action_history,
            )
            if action:
                action_source = "llm"

        if action is None:
            # Heuristic fallback
            if heuristic_idx < len(heuristic_seq):
                action = heuristic_seq[heuristic_idx]
                heuristic_idx += 1
            else:
                action = "resolve_ticket"

        # Execute step
        try:
            result = env_step(action)
        except Exception as e:
            print(f"[STEP] step={step_num} action={action} ERROR={e}")
            sys.stdout.flush()
            break

        current_observation = result.get("observation", "")
        reward = result.get("reward", 0.0)
        cumulative = result.get("cumulative_reward", 0.0)
        done = result.get("done", False)
        success = result.get("success", False)

        obs_preview = current_observation[:80].replace("\n", " ") + ("..." if len(current_observation) > 80 else "")

        print(
            f"[STEP] step={step_num} action={action!r} source={action_source} "
            f"reward={reward:+.4f} cumulative={cumulative:.4f} "
            f"done={done} success={success} obs={obs_preview!r}"
        )
        sys.stdout.flush()

        if done:
            break

    # Grade
    try:
        grade_result = env_grade()
    except Exception as e:
        grade_result = {"score": 0.0, "passed": False, "feedback": str(e)}

    score = grade_result.get("score", 0.0)
    passed = grade_result.get("passed", False)
    feedback = grade_result.get("feedback", "")

    print(f"[END] task_id={task_id} score={score:.4f} passed={passed} steps={step_num}")
    print(f"[END] feedback_summary={feedback.splitlines()[0] if feedback else 'N/A'!r}")
    sys.stdout.flush()

    return grade_result


def main():
    print("[START] IT Helpdesk Incident Triage — OpenEnv Inference")
    print(f"[START] env_url={ENV_BASE} llm_api_base={API_BASE_URL or '(none)'} model={MODEL_NAME or '(heuristic fallback)'}")
    sys.stdout.flush()

    # Build LLM client using evaluator-injected API_BASE_URL + API_KEY
    client = build_llm_client()
    model = MODEL_NAME

    all_results = []
    for task_id in TASK_IDS:
        print(f"\n{'='*60}")
        print(f"[START] Running task: {task_id}")
        print(f"{'='*60}")
        sys.stdout.flush()

        try:
            result = run_task(task_id, client, model)
            all_results.append(result)
        except Exception as e:
            print(f"[END] task_id={task_id} ERROR={e}")
            sys.stdout.flush()
            all_results.append({"task_id": task_id, "score": 0.0, "passed": False, "error": str(e)})

    # Summary
    print(f"\n{'='*60}")
    print("[END] INFERENCE COMPLETE — SUMMARY")
    print(f"{'='*60}")
    total_score = 0.0
    for r in all_results:
        tid = r.get("task_id", "unknown")
        score = r.get("score", 0.0)
        passed = r.get("passed", False)
        total_score += score
        print(f"[END] {tid:30s} score={score:.4f}  passed={passed}")
    avg_score = total_score / max(len(all_results), 1)
    print(f"[END] average_score={avg_score:.4f}  tasks_run={len(all_results)}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()