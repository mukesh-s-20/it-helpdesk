import os
import json
from openai import OpenAI

SYSTEM_PROMPT = """
You are an IT Helpdesk / DevOps Incident Triage agent.

Your job is to solve incident tasks by selecting the BEST next action.

Rules:
- Choose ONLY ONE action from the available_actions list.
- Return ONLY valid JSON.
- Format:
{"action": "action_name"}

Do not explain.
Do not add markdown.
"""

def choose_action(observation: dict) -> str:
    api_base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")

    if not api_base_url or not api_key:
        raise RuntimeError(
            "Missing API_BASE_URL or API_KEY environment variables."
        )

    client = OpenAI(
        base_url=api_base_url,
        api_key=api_key,
    )

    user_prompt = f"""
Current environment state:

Task Title: {observation.get("title")}
Ticket: {json.dumps(observation.get("ticket", {}), indent=2)}
Logs: {json.dumps(observation.get("logs", []), indent=2)}
System Facts: {json.dumps(observation.get("system_facts", {}), indent=2)}
Available Actions: {json.dumps(observation.get("available_actions", []), indent=2)}
Action History: {json.dumps(observation.get("action_history", []), indent=2)}

Observation:
{observation.get("observation", "")}

Choose the single best next action.

Return only JSON:
{{"action": "action_name"}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)
    return parsed["action"]