---

title: IT Helpdesk
emoji: 🐳
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# IT Helpdesk Incident Triage — OpenEnv

> An OpenEnv-style environment where an AI agent acts as an IT Helpdesk / DevOps Incident Triage assistant that diagnoses and resolves employee or system issues using logs, tickets, commands, and policy constraints.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Why This Is a Real-World Environment](#why-this-is-a-real-world-environment)
3. [Environment Mechanics](#environment-mechanics)
4. [API Endpoint Documentation](#api-endpoint-documentation)
5. [Action Space](#action-space)
6. [Observation Space](#observation-space)
7. [Reward Function](#reward-function)
8. [Task Descriptions](#task-descriptions)
9. [Grader Explanation](#grader-explanation)
10. [Local Setup](#local-setup)
11. [Run Instructions](#run-instructions)
12. [Docker Instructions](#docker-instructions)
13. [Hugging Face Spaces Deployment](#hugging-face-spaces-deployment)
14. [Inference Script Usage](#inference-script-usage)
15. [Example API Requests & Responses](#example-api-requests--responses)
16. [Repository Structure](#repository-structure)
17. [Troubleshooting](#troubleshooting)

---

## Project Overview

This project simulates a realistic IT Helpdesk and DevOps incident triage workflow as an OpenEnv-compatible reinforcement learning environment. An AI agent receives a support ticket, system logs, and observable system facts, then must choose a sequence of diagnostic and remediation actions to resolve the incident.

The environment is:
- **Stateful** — action history and rewards accumulate across a session
- **Deterministic** — same actions always produce the same observations and rewards
- **Reproducible** — fixed task definitions with no randomness
- **Graded** — a per-task grader scores the agent's performance from 0.0 to 1.0
- **Partial-credit** — meaningful reward shaping rewards correct diagnosis steps even before resolution

---

## Why This Is a Real-World Environment

IT/DevOps incident triage is one of the highest-value applications of AI agents in enterprise settings:

- Real companies lose thousands of dollars per minute during service outages
- Triage requires multi-step reasoning: reading logs, understanding system state, choosing safe remediation steps
- Incorrect actions have real penalties (e.g. rebooting a server extends downtime for all users)
- Agents must distinguish root causes that produce similar symptoms (auth failure vs disk full vs SSL expiry)
- The three tasks model real incident types that occur daily in production infrastructure

---

## Environment Mechanics

### Episode Flow

```
POST /reset  →  agent receives ticket + logs + system facts + available actions
     ↓
POST /step   →  agent submits action  →  receives observation + reward
     ↓ (repeat)
GET  /grade  →  final score [0.0, 1.0] returned by task-specific grader
```

### State Fields

| Field | Type | Description |
|---|---|---|
| `task_id` | string | Active task identifier |
| `difficulty` | string | easy / medium / hard |
| `ticket` | object | Support ticket metadata and body |
| `logs` | list[str] | System log lines for the incident |
| `system_facts` | dict | Observable key/value system state |
| `available_actions` | list[str] | All actions the agent may submit |
| `action_history` | list | Ordered list of (step, action, reward, preview) |
| `actions_taken` | list[str] | Deduplicated set of executed actions |
| `cumulative_reward` | float | Running reward total |
| `steps` | int | Steps taken so far |
| `max_steps` | int | Step limit before forced termination |
| `done` | bool | Episode complete flag |
| `success` | bool | Task resolved correctly |
| `progress_pct` | float | Percent of required actions completed |

### Termination Conditions

- **Success**: All required actions completed AND `resolve_ticket` called → `done=True, success=True`
- **Failure**: `steps >= max_steps` → `done=True, success=False`

---

## API Endpoint Documentation

All endpoints are served by FastAPI. Interactive docs at `/docs`.

### `GET /`
Health check and environment info.

**Response:**
```json
{
  "status": "ok",
  "environment": "IT Helpdesk Incident Triage OpenEnv",
  "version": "1.0.0",
  "tasks_available": 3,
  "endpoints": ["..."]
}
```

---

### `GET /tasks`
List all available tasks with metadata.

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "easy_vpn_lock",
      "difficulty": "easy",
      "title": "Locked VPN Account",
      "description": "...",
      "max_steps": 10,
      "passing_score": 0.7
    }
  ]
}
```

---

### `POST /reset`
Start a new task episode. Resets all state.

**Request:**
```json
{ "task_id": "easy_vpn_lock" }
```

**Response:** Full `ResetResponse` with ticket, logs, system_facts, available_actions, initial observation, and empty history.

---

### `POST /step`
Execute one action. Returns updated observation and reward.

**Request:**
```json
{ "action": "inspect_account" }
```

**Response:**
```json
{
  "action": "inspect_account",
  "observation": "ACCOUNT INSPECTION RESULT:\n  Username: john.doe\n  Status: LOCKED\n  ...",
  "reward": 0.15,
  "cumulative_reward": 0.25,
  "steps": 2,
  "max_steps": 10,
  "done": false,
  "success": false,
  "action_history": [...],
  "info": "ok"
}
```

---

### `GET /state`
Return full current environment state.

---

### `GET /grade`
Run the grader for the current episode. Returns score in [0.0, 1.0].

**Response:**
```json
{
  "task_id": "easy_vpn_lock",
  "difficulty": "easy",
  "score": 0.8850,
  "passed": true,
  "passing_score": 0.7,
  "cumulative_reward": 0.85,
  "steps_taken": 6,
  "max_steps": 10,
  "required_actions_completed": 3,
  "required_actions_total": 3,
  "actions_taken": ["check_logs", "inspect_account", "identify_lock_reason", "unlock_account", "verify_vpn_access", "resolve_ticket"],
  "feedback": "Required actions completed: 3/3 (100%)\n..."
}
```

---

### `GET /ui`
Serves the interactive HTML demo interface.

---

## Action Space

Actions are discrete strings. Each task defines a set of valid (helpful) and invalid (irrelevant/harmful) actions. The agent submits any string — unknown actions incur a small penalty.

### Easy — Locked VPN Account

| Action | Type | Reward |
|---|---|---|
| `check_logs` | diagnostic | +0.10 |
| `inspect_account` | diagnostic | +0.15 ✓ required |
| `identify_lock_reason` | diagnostic | +0.15 |
| `unlock_account` | remediation | +0.35 ✓ required |
| `verify_vpn_access` | verification | +0.10 |
| `resolve_ticket` | completion | +0.15 ✓ required |
| `reset_password` | wrong | -0.10 |
| `reboot_server` | destructive | -0.20 |
| `restart_vpn_gateway` | disruptive | -0.15 |

### Medium — Disk Full Service Outage

| Action | Type | Reward |
|---|---|---|
| `check_logs` | diagnostic | +0.10 |
| `check_service_status` | diagnostic | +0.08 |
| `inspect_disk_usage` | diagnostic | +0.12 ✓ required |
| `identify_large_files` | diagnostic | +0.10 |
| `clear_temp_files` | remediation | +0.20 ✓ required |
| `clear_old_logs` | remediation | +0.10 |
| `restart_portal_service` | remediation | +0.15 ✓ required |
| `verify_service_health` | verification | +0.08 |
| `resolve_ticket` | completion | +0.07 ✓ required |
| `reboot_server` | destructive | -0.25 |

### Hard — Expired SSL Certificate

| Action | Type | Reward |
|---|---|---|
| `check_logs` | diagnostic | +0.08 |
| `check_service_status` | diagnostic | +0.06 |
| `inspect_ssl_certificate` | diagnostic | +0.12 ✓ required |
| `identify_cert_expiry` | diagnostic | +0.10 |
| `check_gateway_status` | diagnostic | +0.08 |
| `renew_ssl_certificate` | remediation | +0.20 ✓ required |
| `deploy_new_certificate` | remediation | +0.12 |
| `restart_gateway` | remediation | +0.10 ✓ required |
| `verify_ssl_handshake` | verification | +0.06 |
| `verify_billing_access` | verification | +0.04 ✓ required |
| `resolve_ticket` | completion | +0.04 ✓ required |
| `reboot_server` | destructive | -0.25 |

---

## Observation Space

Each action returns a natural language observation string describing the system's response. Observations include:

- **Log output** — timestamped system log excerpts
- **Command output** — simulated CLI results (disk usage, service status, cert info)
- **Status summaries** — structured text summarizing system state
- **Warning/error messages** — for wrong or harmful actions

The initial observation (after `/reset`) is the ticket body and a prompt to begin diagnosis.

---

## Reward Function

The reward system provides **partial progress signals** so the agent receives meaningful feedback at every step, not just on success.

### Per-Step Rewards

```
reward = reward_map[action]        # base reward from task definition
       × repeat_decay              # 10% if action already taken (prevents looping)
```

### Grader Score (0.0 – 1.0)

The grader combines four components:

| Component | Weight | Description |
|---|---|---|
| Required action coverage | 0.50 | Fraction of required actions completed |
| Normalized cumulative reward | 0.30 | Cumulative reward / theoretical max |
| Efficiency bonus | 0.10 | Fewer steps used on success = higher score |
| Completion bonus | 0.10 | Flat bonus for `success=True` |

**Formula:**
```
score = (completed_required / total_required) × 0.50
      + min(cumulative_reward / max_possible_reward, 1.0) × 0.30
      + (1 - steps/max_steps) × 0.10   [only if success]
      + 0.10                            [only if success]
```

### Reward Design Rationale

- **Small diagnostics reward**: encourages the agent to gather information before acting
- **Large remediation reward**: incentivizes finding and fixing the actual root cause
- **Penalties for wrong subsystem**: discourages shotgun approaches
- **Large penalty for destructive actions**: models real-world consequences of reboots
- **Repeat decay**: prevents reward hacking by repeating the same action

---

## Task Descriptions

### Task 1 — Easy: Locked VPN Account
**Ticket ID:** TICKET-1001 | **Max Steps:** 10 | **Passing Score:** 0.70

A remote employee cannot connect to the corporate VPN and receives "Authentication failed". The root cause is an ActiveDirectory account lockout after 5 consecutive failed login attempts. The agent must inspect the account, identify the lockout, unlock the account, and resolve the ticket.

**Required actions:** `inspect_account` → `unlock_account` → `resolve_ticket`

**Common wrong paths:** resetting the password (not the issue), restarting the VPN gateway (unnecessary and disruptive), rebooting the server.

---

### Task 2 — Medium: Disk Full Service Outage
**Ticket ID:** TICKET-2047 | **Max Steps:** 15 | **Passing Score:** 0.70

An automated alert reports the internal employee portal is returning HTTP 503 for 22 minutes. The root cause is the production disk at 98% capacity (42GB of accumulated temp upload files) causing the portal service to crash with an ENOSPC error. The service itself is healthy — it simply cannot write session data to disk. The agent must diagnose the disk usage, clear temp files, restart the service, and resolve.

**Required actions:** `inspect_disk_usage` → `clear_temp_files` → `restart_portal_service` → `resolve_ticket`

**Common wrong paths:** rebooting the server (highly penalized), investigating SSL or auth (irrelevant).

---

### Task 3 — Hard: Expired SSL Certificate on Billing Service
**Ticket ID:** TICKET-3182 | **Max Steps:** 20 | **Passing Score:** 0.75

A critical business escalation: the billing service at billing.company.com is inaccessible to customers and internal teams. The root cause is a two-part cascade: (1) the Let's Encrypt SSL certificate expired (auto-renewal was disabled during a past maintenance window), and (2) the Kong API gateway entered an unhealthy state due to the SSL handshake failure, blocking all HTTPS traffic. The billing application itself is running fine on port 8443 internally. The agent must trace the cascade, renew the cert, redeploy it to Kong, restart the gateway, verify access end-to-end, and deliver a full RCA.

**Required actions:** `inspect_ssl_certificate` → `renew_ssl_certificate` → `restart_gateway` → `verify_billing_access` → `resolve_ticket`

**Common wrong paths:** rebooting the server, investigating disk or auth, restarting the wrong service.

---

## Grader Explanation

Each task has a dedicated grader function in `graders.py`:

- `grade_easy(state, task_def)` → `GraderResult`
- `grade_medium(state, task_def)` → `GraderResult`
- `grade_hard(state, task_def)` → `GraderResult`

All graders use the same `_base_grade()` function with the four-component scoring formula described above. Scores are always in `[0.0, 1.0]`. The `passed` field is `True` when `score >= passing_score`.

The grader can be called at any time via `GET /grade` — mid-episode grading shows partial progress. Final grading is called automatically by `inference.py` at episode end.

---

## Local Setup

### Prerequisites

- Python 3.10 or higher
- pip

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/mukesh-s-20/it-helpdesk.git
cd it-helpdesk-openenv

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file
cp .env.example .env
# Edit .env if you want to configure LLM inference
```

---

## Run Instructions

```bash
# Start the environment server
python main.py

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 7860 --reload

# Open in browser
open http://localhost:7860/ui      # Interactive demo UI
open http://localhost:7860/docs    # OpenAPI docs
```

### Quick API Test

```bash
# Health check
curl http://localhost:7860/

# List tasks
curl http://localhost:7860/tasks

# Start easy task
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy_vpn_lock"}'

# Take an action
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action": "inspect_account"}'

# Get state
curl http://localhost:7860/state

# Grade episode
curl http://localhost:7860/grade
```

### Run Inference Script (heuristic fallback — no LLM needed)

```bash
# With server running in another terminal:
python inference.py
```

### Run Inference Script with LLM

```bash
# Using Hugging Face Inference API
export API_BASE_URL=http://localhost:7860
export LLM_API_BASE=https://api-inference.huggingface.co/v1
export MODEL_NAME=meta-llama/Meta-Llama-3-8B-Instruct
export HF_TOKEN=hf_your_token_here
python inference.py

# Using OpenAI API
export LLM_API_BASE=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
export OPENAI_API_KEY=sk-your-key
python inference.py
```

---

## Docker Instructions

### Build

```bash
docker build -t it-helpdesk-openenv .
```

### Run

```bash
docker run -p 7860:7860 it-helpdesk-openenv
```

### Run with LLM environment variables

```bash
docker run -p 7860:7860 \
  -e LLM_API_BASE=https://api-inference.huggingface.co/v1 \
  -e MODEL_NAME=meta-llama/Meta-Llama-3-8B-Instruct \
  -e HF_TOKEN=hf_your_token \
  it-helpdesk-openenv
```

### Run inference against Docker container

```bash
# In one terminal
docker run -p 7860:7860 it-helpdesk-openenv

# In another terminal
API_BASE_URL=http://localhost:7860 python inference.py
```

---

## Hugging Face Spaces Deployment

This project is fully compatible with Hugging Face Spaces using the **Docker SDK**.

### Steps

```bash
# 1. Create a new Space at https://huggingface.co/spaces
#    - SDK: Docker
#    - Hardware: CPU Basic (2 vCPU, 16 GB RAM)
#    - Visibility: Public (for hackathon submission)

# 2. Add your Space as a git remote
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/it-helpdesk-openenv

# 3. Push
git push space main

# The Space will build and deploy automatically.
# Your environment will be live at:
# https://YOUR_USERNAME-it-helpdesk-openenv.hf.space
```

### Optional: Add HF_TOKEN as a Space Secret

In your Space settings → Variables and Secrets, add:
- `HF_TOKEN` — your Hugging Face API token (for LLM inference)
- `LLM_API_BASE` — OpenAI-compatible endpoint
- `MODEL_NAME` — model to use

### Run inference against Hugging Face Space

```bash
API_BASE_URL=https://YOUR_USERNAME-it-helpdesk-openenv.hf.space python inference.py
```

---

## Inference Script Usage

`inference.py` runs all three tasks sequentially and prints structured logs.

### Log Format

```
[START] IT Helpdesk Incident Triage — OpenEnv Inference
[START] env_url=http://localhost:7860 model=(heuristic fallback)

============================================================
[START] Running task: easy_vpn_lock
============================================================
[START] task_id=easy_vpn_lock difficulty=easy title='Locked VPN Account'
[START] ticket_id=TICKET-1001 priority=medium
[START] max_steps=10 available_actions=11
[STEP] step=1 action='check_logs' source=heuristic reward=+0.1000 cumulative=0.1000 done=False success=False obs='LOGS RETRIEVED...'
[STEP] step=2 action='inspect_account' source=heuristic reward=+0.1500 cumulative=0.2500 done=False success=False obs='ACCOUNT INSPECTION RESULT...'
[STEP] step=3 action='identify_lock_reason' source=heuristic reward=+0.1500 cumulative=0.4000 done=False success=False obs='LOCK REASON IDENTIFIED...'
[STEP] step=4 action='unlock_account' source=heuristic reward=+0.3500 cumulative=0.7500 done=False success=False obs='ACTION EXECUTED: Account unlock...'
[STEP] step=5 action='verify_vpn_access' source=heuristic reward=+0.1000 cumulative=0.8500 done=False success=False obs='VPN ACCESS VERIFICATION...'
[STEP] step=6 action='resolve_ticket' source=heuristic reward=+0.1500 cumulative=1.1000 done=True success=True obs='TICKET-1001 RESOLVED...'
[END] task_id=easy_vpn_lock score=0.9400 passed=True steps=6

============================================================
[END] INFERENCE COMPLETE — SUMMARY
============================================================
[END] easy_vpn_lock                    score=0.9400  passed=True
[END] medium_disk_full                 score=0.8750  passed=True
[END] hard_ssl_expiry                  score=0.8200  passed=True
[END] average_score=0.8783  tasks_run=3
```

### Behavior

- If `LLM_API_BASE` and `MODEL_NAME` are set: uses LLM to choose actions
- If LLM call fails or returns invalid action: falls back to heuristic sequence
- If no LLM configured: uses heuristic sequence entirely
- Never crashes regardless of LLM availability

---

## Example API Requests & Responses

### Full walkthrough — Easy task

```bash
# Reset
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy_vpn_lock"}'

# Response (truncated):
{
  "task_id": "easy_vpn_lock",
  "difficulty": "easy",
  "title": "Locked VPN Account",
  "ticket": {
    "id": "TICKET-1001",
    "priority": "medium",
    "subject": "Cannot connect to VPN",
    "body": "Hi IT, I've been trying to connect to the VPN..."
  },
  "observation": "NEW INCIDENT RECEIVED\nTicket: TICKET-1001\nPriority: MEDIUM\n...",
  "cumulative_reward": 0.0,
  "steps": 0,
  "max_steps": 10,
  "done": false,
  "success": false
}

# Step 1: inspect account
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action": "inspect_account"}'

# Response:
{
  "action": "inspect_account",
  "observation": "ACCOUNT INSPECTION RESULT:\n  Username: john.doe\n  Status: LOCKED\n  Failed Attempts: 5\n  Lockout Reason: Exceeded failed login threshold",
  "reward": 0.15,
  "cumulative_reward": 0.15,
  "steps": 1,
  "done": false,
  "success": false
}

# Step 2: unlock
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action": "unlock_account"}'

# Step 3: resolve
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action": "resolve_ticket"}'

# Response includes done=true, success=true

# Grade
curl http://localhost:7860/grade

# Response:
{
  "task_id": "easy_vpn_lock",
  "score": 0.8725,
  "passed": true,
  "passing_score": 0.7,
  "feedback": "Required actions completed: 3/3 (100%)\nCoverage score: 0.500/0.500\n..."
}
```

---

## Repository Structure

```
it-helpdesk-openenv/
│
├── main.py                    # FastAPI application — all routes
├── models.py                  # Pydantic request/response models
├── graders.py                 # Per-task grader functions
├── inference.py               # Baseline inference script (LLM + heuristic)
├── openenv.yaml               # OpenEnv specification
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker / HF Spaces compatible
├── .env.example               # Environment variable template
├── .gitignore
├── README.md
│
├── env/
│   ├── __init__.py
│   ├── incident_env.py        # Core environment: reset(), step(), state()
│   └── tasks.py               # Task loader and registry
│
├── tasks/
│   ├── easy_vpn_lock.json     # Easy task definition
│   ├── medium_disk_full.json  # Medium task definition
│   └── hard_ssl_expiry.json   # Hard task definition
│
├── templates/
│   └── index.html             # Jinja2 HTML template for demo UI
│
└── static/
    ├── style.css              # UI stylesheet
    └── app.js                 # UI JavaScript
```

---

## Troubleshooting

### Server won't start

**Problem:** `ModuleNotFoundError`
```bash
# Fix: Ensure you're in the virtual environment and installed dependencies
source .venv/bin/activate
pip install -r requirements.txt
```

**Problem:** `Port 7860 already in use`
```bash
# Fix: Use a different port
uvicorn main:app --port 8080
# Update API_BASE_URL accordingly in .env
```

---

### Inference script errors

**Problem:** `Connection refused` when running `inference.py`
```bash
# Fix: Start the server first
python main.py &
sleep 2
python inference.py
```

**Problem:** LLM returning invalid actions
```
# This is handled automatically — inference.py falls back to heuristic sequences
# You will see source=heuristic in [STEP] logs when this happens
```

---

### Docker issues

**Problem:** `permission denied` on Hugging Face Spaces
```dockerfile
# Already handled in Dockerfile — non-root user appuser is created and used
# Port 7860 is used as required by HF Spaces
```

**Problem:** Build fails
```bash
# Try clearing Docker cache
docker build --no-cache -t it-helpdesk-openenv .
```

---

### Grader returns 0.0

This means no required actions were completed. Ensure you call at minimum:
- Easy: `inspect_account` + `unlock_account` + `resolve_ticket`
- Medium: `inspect_disk_usage` + `clear_temp_files` + `restart_portal_service` + `resolve_ticket`
- Hard: `inspect_ssl_certificate` + `renew_ssl_certificate` + `restart_gateway` + `verify_billing_access` + `resolve_ticket`

---

### UI not loading actions

```bash
# Check the browser console for API errors
# Ensure the server is running and accessible at the correct port
# Try refreshing after clicking Reset
```

---

## License

MIT License — free to use for hackathon submissions and research.
=======
title: It Helpdesk
emoji: 🦀
colorFrom: pink
colorTo: pink
sdk: docker
pinned: false
license: mit
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
>>>>>>> 826e11a809a70d662e15102a5c2aba8a3c7b57b0
