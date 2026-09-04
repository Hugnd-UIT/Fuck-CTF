import json
import re
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

    def quick(self, subtask, commands, indicator, output):
        # Quick timeout check
        if not output or output.startswith("[TIMEOUT]"):
            data = {
                "reason": {
                    "analysis": "Command produced no output or timed out",
                    "discovery": "none",
                    "unmet": "No output observed"
                },
                "result": "fail",
                "knowledge": ["Execution produced no output or hit timeout."],
                "flag": False
            }
            return {"verify_data": data, "in_tokens": 0, "out_tokens": 0, "raw": "[FAST_FAIL]"}

        # Quick indicator match
        if indicator and len(indicator) >= 3 and indicator.lower() in output.lower():
            data = {
                "reason": {
                    "analysis": f"Indicator matched verbatim in output: {indicator[:80]}",
                    "discovery": indicator[:120],
                    "unmet": ""
                },
                "result": "success",
                "knowledge": [f"Indicator confirmed: {indicator[:120]}"],
                "flag": False
            }
            return {"verify_data": data, "in_tokens": 0, "out_tokens": 0, "raw": "[FAST_MATCH]"}

        # Quick crash check
        if "segmentation fault" in output.lower() or "sigsegv" in output.lower():
            data = {
                "reason": {
                    "analysis": "Process crashed with SIGSEGV (memory corruption / buffer overflow triggered)",
                    "discovery": "SIGSEGV crash observed",
                    "unmet": ""
                },
                "result": "success" if ("crash" in str(subtask).lower() or "overflow" in str(subtask).lower() or "offset" in str(subtask).lower()) else "partial",
                "knowledge": ["Binary crashed with SIGSEGV (memory corruption)."],
                "flag": False
            }
            return {"verify_data": data, "in_tokens": 0, "out_tokens": 0, "raw": "[FAST_CRASH]"}

        return None

    def verify(
        self,
        subtask,
        commands,
        indicator,
        output,
        hypothesis=None,
        facts=None
    ):
        # Fast verification
        fast = self.quick(subtask, commands, indicator, output)
        if fast:
            return fast

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

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": text
            }
        ]

        # Call model
        raw, in_tokens, out_tokens = self.call(messages)

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
            if isinstance(verify_data, list):
                verify_data = verify_data[0] if verify_data else {}
            if not isinstance(verify_data, dict):
                verify_data = {}

        except Exception as e:

            verify_data = {
                "reason": {
                    "analysis": "Failed to parse JSON",
                    "discovery": "none",
                    "unmet": "Failed to parse JSON"
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