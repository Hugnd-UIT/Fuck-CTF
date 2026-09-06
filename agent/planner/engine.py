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

    def build(self, history, fails):
        dead_tactics = set()
        notices = []

        # Identify dead tactics
        for tactic, streak in fails.items():
            if streak >= 2:
                dead_tactics.add(tactic.lower().strip())
                notices.append(
                    {
                        "step_id": f"FAILED_{tactic.upper()}",
                        "tactic": tactic,
                        "plan": f"All attempts on {tactic}",
                        "observation": (
                            f"[FAILED HYPOTHESIS] Tactic '{tactic}' has been completely REJECTED "
                            f"by the target service after {streak} failed attempts. "
                            "This attack vector is DEAD. Do NOT repeat or propose minor variants of this tactic. "
                            "Pivot immediately to a completely new hypothesis or inspect source code from line 1."
                        ),
                        "result": "dead_end"
                    }
                )

        # Filter discredited history
        filtered = []
        for entry in history:
            e_tac = str(entry.get("tactic", "")).lower().strip()
            if any(dt in e_tac or e_tac in dt for dt in dead_tactics if dt):
                continue
            filtered.append(entry)

        # Return pruned history
        return notices + filtered[-6:]

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
        # Check playbook
        if playbook is None:
            playbook = {}

        # Check facts
        if facts is None:
            facts = {}

        # Check warns
        if warns is None:
            warns = []

        # Build history
        history = self.build(history, fails)
        
        # Get last output command
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

        # Format facts
        if isinstance(facts, dict) and facts:
            # Truncate facts to 25000 characters
            slim_facts = {
                k: (str(v)[:25000] + "...[truncated]") if len(str(v)) > 25000 else v
                for k, v in facts.items()
            }
            facts_str = json.dumps(slim_facts, indent=2)
        elif facts:
            facts_str = json.dumps(facts, indent=2)
        else:
            facts_str = "No facts collected yet!"
        
        # Format warns
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

        # Format memory
        if memory and isinstance(memory, str) and len(memory) > 3000:
            
            # Truncate memory to 3000 characters
            memory = memory[:3000] + "\n...[truncated]"

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
                    "target": "none",
                    "tool": "none",
                    "hint": None,
                    "read": None,
                    "rag": None,
                    "reflect": False,
                    "avoids": "none",
                    "safety": "safe",
                    "evidence": "none",
                    "finished": False,
                    "captured": None
                }
            }

        return {
            "plan_data": plan_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text
        }