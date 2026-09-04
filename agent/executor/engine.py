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

    def execute_plan(
        self,
        target,
        subtask,
        tool_hint,
        history,
        facts=None
    ):

        # Format history
        slim_history = [
            {
                k: v for k, v in entry.items()
                if k != "raw"
            }
            for entry in (history[-20:] if isinstance(history, list) else [])
        ]
        if isinstance(slim_history, (list, dict)):
            history_str = json.dumps(slim_history, indent=2)
        else:
            history_str = str(slim_history)

        facts_str = json.dumps(facts, indent=2) if isinstance(facts, dict) else (str(facts) if facts else "{}")

        # Format user prompt
        user_content = USER_PROMPT.format(
            target=target,
            facts=facts_str,
            subtask=subtask,
            tool_hint=tool_hint,
            history=history_str
        )

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
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

            exec_data = json_repair.loads(json_str)
            if isinstance(exec_data, list):
                exec_data = exec_data[0] if exec_data else {}
            if not isinstance(exec_data, dict):
                exec_data = {}

            commands = exec_data.get("commands", [])

        except Exception as e:

            exec_data = {
                "reason": {
                    "analysis": "Failed to parse JSON",
                    "construction": "none",
                    "scope": "none"
                },
                "commands": [
                    "echo 'Executor failed to parse JSON'"
                ],
                "timeout": 10,
                "success": "false"
            }

        return {
            "exec_data": exec_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text
        }