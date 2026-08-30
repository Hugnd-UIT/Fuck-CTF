import json
from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT

class VerifierAgent(PentestAgent):
    def __init__(self, model, local=False, temperature=0.1, top=1.0, sample=False, tokens=1024):
        
        # Initialize base agent
        super().__init__(
            model=model,
            local=local,
            temperature=temperature,
            top=top,
            sample=sample,
            tokens=tokens
        )

    def verify(self, subtask, commands, success_indicator, output, hypothesis=None):
        import json
        hypothesis_str = json.dumps(hypothesis, indent=2) if hypothesis else "None"
        
        # Format user prompt
        user_content = USER_PROMPT.format(
            hypothesis=hypothesis_str,
            subtask=subtask,
            commands=json.dumps(commands),
            success_indicator=success_indicator,
            output=output
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        # Call model to verify output
        text, in_tokens, out_tokens = self.call(messages)

        # Parse JSON output
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            else:
                json_str = text.strip()

            parsed_verify = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[!] Error parsing JSON from Verifier: {e}")
            parsed_verify = {
                "reason": {"error": "Failed to parse JSON"},
                "result": "fail",
                "knowledge": [],
                "flag": False
            }

        return {
            "parsed_verify": parsed_verify,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw_output": text
        }
