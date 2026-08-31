import json
import json_repair

from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT


class SummarizerAgent(PentestAgent):
    def __init__(
        self,
        model,
        local=False,
        temperature=0.3,
        top=1.0,
        sample=False,
        tokens=4096
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

    def summarize(self, tree, step):

        # Format prompts
        user_content = USER_PROMPT.format(
            tree=tree,
            step=(
                step
                if isinstance(step, str)
                else json.dumps(step, indent=2)
            )
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

            summary_data = json_repair.loads(json_str)

            print(
                f"  ✓ Summarizer : "
                f"{summary_data.get('summary', 'completed')}"
            )

        except Exception as e:
            print(f"  ✗ Summarizer : JSON parse failed - {e}")

            summary_data = {
                "reason": {
                    "error": "Failed to parse JSON"
                },
                "tree": tree,
                "summary": "Error parsing summary"
            }

        return {
            "summary_data": summary_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text
        }