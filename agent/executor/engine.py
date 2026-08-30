import json
from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT

class ExecutorAgent(PentestAgent):
    def __init__(self, model, local=False, temperature=0.2, top=1.0, sample=False, tokens=1024):
        
        # Initialize base agent
        super().__init__(
            model=model,
            local=local,
            temperature=temperature,
            top=top,
            sample=sample,
            tokens=tokens
        )

    def execute_plan(self, target, subtask, tool_hint, history):
        
        # Format history
        if isinstance(history, (list, dict)):
            history_str = json.dumps(history, indent=2)
        else:
            history_str = str(history)

        # Format user prompt
        user_content = USER_PROMPT.format(
            target=target,
            subtask=subtask,
            tool_hint=tool_hint,
            history=history_str
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        # Call model
        text, in_tokens, out_tokens = self.call(messages)

        # Parse JSON
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            else:
                json_str = text.strip()

            parsed_exec = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[!] Error parsing JSON from Executor: {e}")
            parsed_exec = {
                "reason": {"error": "Failed to parse JSON"},
                "commands": ["echo 'Executor failed to parse JSON'"],
                "timeout": 10,
                "success": "false"
            }

        return {
            "parsed_exec": parsed_exec,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw_output": text
        }
