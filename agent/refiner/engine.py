import json

from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT


class RefinerAgent(PentestAgent):
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

    def refine(
        self,
        target,
        subtask,
        failed_command,
        error_output,
        history
    ):

        # Format history
        if isinstance(history, (list, dict)):
            history_str = json.dumps(history, indent=2)
        else:
            history_str = str(history)

        # Format commands
        if isinstance(failed_command, list):
            failed_command_str = json.dumps(failed_command)
        else:
            failed_command_str = str(failed_command)

        # Format user prompt
        user_content = USER_PROMPT.format(
            target=target,
            subtask=subtask,
            failed_command=failed_command_str,
            error_output=error_output,
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

            parsed_refine = json.loads(json_str)

            print("  ✓ Refiner    : command refined")

        except json.JSONDecodeError as e:
            print(f"  ✗ Refiner    : JSON parse failed - {e}")

            parsed_refine = {
                "reason": {
                    "error": "Failed to parse JSON"
                },
                "commands": []
            }

        return {
            "parsed_refine": parsed_refine,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw_output": text
        }