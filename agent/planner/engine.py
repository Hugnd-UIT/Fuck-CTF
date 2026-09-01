import json
import json_repair

from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT


class PlannerAgent(PentestAgent):
    def __init__(
        self,
        model,
        local=False,
        temperature=0.7,
        top=1.0,
        sample=False,
        tokens=1024
    ):

        # Initialize base agent
        super().__init__(
            model=model,
            local=local,
            temperature=temperature,
            top=top,
            sample=sample,
            tokens=tokens
        )

    def build_history(self, history, fails):
        notices = []

        for tactic, streak in fails.items():
            if streak >= 3:
                notices.append(
                    {
                        "step_id": "SYSTEM_NOTICE",
                        "tactic": tactic,
                        "plan": "N/A",
                        "observation": (
                            f"Tactic '{tactic}' has failed "
                            f"{streak} times in a row. "
                            "You are FORBIDDEN from proposing "
                            "this tactic next."
                        ),
                        "result": "forced_block"
                    }
                )

        return notices + history[-15:]

    def plan(
        self,
        history,
        fails,
        target,
        tree,
        tools,
        playbook=None,
        memory="None",
        time_left=None,
        facts=None,
        warns=None
    ):
        if playbook is None:
            playbook = {}
        if facts is None:
            facts = {}
        if warns is None:
            warns = []

        history = self.build_history(history, fails)
        last_output = ""
        for entry in reversed(history):
            raw = entry.get("raw", "")
            if raw:
                last_output = raw
                break


        # Format history
        if isinstance(history, (list, dict)):
            history_str = json.dumps(history, indent=2)
        else:
            history_str = str(history)

        # Format facts + warns
        facts_str = (
            json.dumps(facts, indent=2)
            if facts
            else "No facts collected yet."
        )
        warns_str = (
            "\n".join(f"- {w}" for w in warns)
            if warns
            else "None."
        )

        # Format system prompts
        system_content = (
            SYSTEM_PROMPT
            .replace("{playbook}", str(playbook))
        )

        user_content = USER_PROMPT.format(
            target=target,
            tools=tools,
            tree=tree,
            last_output=last_output or "No previous command output.",
            memory=memory,
            time_left=time_left if time_left is not None else "Unknown",
            history=history_str,
            facts=facts_str,
            warns=warns_str
        )

        messages = [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": user_content
            }
        ]

        # Call model
        text, in_tokens, out_tokens = self.call(messages)

        # Parse JSON
        try:
            if "```json" in text:
                json_str = (
                    text.split("```json")[1]
                    .split("```")[0]
                    .strip()
                )
            elif "```" in text:
                json_str = (
                    text.split("```")[1]
                    .split("```")[0]
                    .strip()
                )
            else:
                json_str = text.strip()

            plan_data = json_repair.loads(json_str)
            if isinstance(plan_data, list):
                plan_data = plan_data[0] if plan_data else {}
            if not isinstance(plan_data, dict):
                plan_data = {"raw_text": json_str}

            plan = plan_data.get("plan", {})
            subtask = plan.get("subtask", plan_data.get("raw_text", "plan generated"))


        except Exception as e:

            plan_data = {
                "reason": {
                    "observation": "Failed to parse JSON",
                    "alternatives": "none",
                    "hypothesis": {
                        "tactic": "Error parsing plan",
                        "rationale": "Failed to parse JSON"
                    },
                    "confidence": 0.0
                },
                "plan": {
                    "subtask": "Error parsing plan",
                    "finished": False
                }
            }

        return {
            "plan_data": plan_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text
        }