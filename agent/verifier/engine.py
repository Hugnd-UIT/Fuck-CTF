import json
import json_repair

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
        facts=None,
        img=None
    ):
        hyp = (
            json.dumps(hypothesis, indent=2)
            if hypothesis
            else "None"
        )

        fct = json.dumps(facts, indent=2) if facts else "None"

        # Format user prompt
        text = USER_PROMPT.format(
            previous_facts=fct,
            hypothesis=hyp,
            subtask=subtask,
            commands=json.dumps(commands),
            indicator=indicator,
            output=output
        )

        if img:
            content = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
            ]
        else:
            content = text

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": content
            }
        ]

        # Call model — fallback to text-only if vision not supported
        try:
            raw, in_tokens, out_tokens = self.call(messages)
        except Exception:
            fallback = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": text}
            ]
            raw, in_tokens, out_tokens = self.call(fallback)

        # Parse JSON
        try:
            if "```json" in raw:
                parsed = (
                    raw.split("```json")[1]
                    .split("```")[0]
                    .strip()
                )
            elif "```" in raw:
                parsed = (
                    raw.split("```")[1]
                    .split("```")[0]
                    .strip()
                )
            else:
                parsed = raw.strip()

            verify_data = json_repair.loads(parsed)

        except Exception as e:

            verify_data = {
                "reason": {
                    "error": "Failed to parse JSON"
                },
                "result": "fail",
                "knowledge": [],
                "flag": False
            }

        return {
            "verify_data": verify_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": raw
        }