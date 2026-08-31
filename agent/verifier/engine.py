import json

from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT


class VerifierAgent(PentestAgent):
    def __init__(
        self,
        model,
        local=False,
        temperature=0.1,
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

    def verify(
        self,
        subtask,
        commands,
        indicator,
        output,
        hypothesis=None,
        facts=None
    ):
        hypothesis_str = (
            json.dumps(hypothesis, indent=2)
            if hypothesis
            else "None"
        )

        facts_str = json.dumps(facts, indent=2) if facts else "None"

        # Format user prompt
        user_content = USER_PROMPT.format(
            previous_facts=facts_str,
            hypothesis=hypothesis_str,
            subtask=subtask,
            commands=json.dumps(commands),
            indicator=indicator,
            output=output
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

            verify_data = json.loads(json_str)

        except json.JSONDecodeError as e:
            print(f"  ✗ Verifier   : JSON parse failed - {e}")

            verify_data = {
                "reason": {
                    "error": "Failed to parse JSON"
                },
                "result": "fail",
                "knowledge": [],
                "flag": False
            }

        else:
            print(
                f"  ✓ Verifier   : "
                f"{verify_data.get('result', 'unknown')}"
            )

        return {
            "verify_data": verify_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text
        }