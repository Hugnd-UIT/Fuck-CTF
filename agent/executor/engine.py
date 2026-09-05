import json
import json_repair

from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT


class ExecutorAgent(PentestAgent):
    def __init__(
        self,
        model,
        local=False,
        temperature=0.2,
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

    def execute(
        self,
        target,
        subtask,
        tool_hint,
        history,
        facts=None,
        tree=None,
        obs=None
    ):

        # Format history
        slim = []

        # Get 5 history recently
        for entry in (history[-5:] if isinstance(history, list) else []):
            item = {}
            for k, v in entry.items():

                # Truncate raw output to 3000 characters 
                if k == "raw":
                    if entry.get("result") not in ("pass", "success"):
                        item["raw"] = str(v)[-3000:]
                else:
                    item[k] = v
            slim.append(item)
        history_str = json.dumps(slim, indent=2) if isinstance(slim, (list, dict)) else str(slim)

        # Format facts
        if isinstance(facts, dict) and facts:
            slim_facts = {}
            for k, v in facts.items():
                s = str(v)

                # Truncate facts to 4000 characters
                slim_facts[k] = (s[:4000] + "...[truncated]") if len(s) > 4000 else v
            facts_str = json.dumps(slim_facts, indent=2)
        else:
            facts_str = json.dumps(facts, indent=2) if isinstance(facts, dict) else (str(facts) if facts else "{}")

        # Format tree
        tree_str = json.dumps(tree, indent=2) if isinstance(tree, (dict, list)) else (str(tree) if tree else "{}")

        # Format observation
        obs_str = f"\nObservation: {obs}" if obs else ""

        # Format user prompt
        user = USER_PROMPT.format(
            target=target,
            tree=tree_str,
            facts=facts_str,
            subtask=subtask,
            tool_hint=tool_hint,
            history=history_str,
            observation=obs_str
        )

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user
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

            exec_data = json_repair.loads(json_str)
            if isinstance(exec_data, list):
                exec_data = exec_data[0] if exec_data else {}
            if not isinstance(exec_data, dict):
                exec_data = {}

            commands = exec_data.get("commands", [])

        except Exception as e:

            exec_data = {
                "reason": {
                    "analysis": "Failed to parse JSON"
                },
                "commands": [
                    "echo 'Executor failed to parse JSON'"
                ],
                "done": True,
                "timeout": 10,
                "success": "false",
                "avoids": "none",
                "rag": None
            }

        return {
            "exec_data": exec_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text
        }