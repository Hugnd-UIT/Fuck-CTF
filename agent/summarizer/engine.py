import json
from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT

class SummarizerAgent(PentestAgent):
    def __init__(self, model, local=False, temperature=0.3, top=1.0, sample=False, tokens=4096):
        
        # Initialize base agent
        super().__init__(
            model=model,
            local=local,
            temperature=temperature,
            top=top,
            sample=sample,
            tokens=tokens
        )

    def summarize(self, attack_tree, latest_step):
        
        # Format prompts
        user_content = USER_PROMPT.format(
            attack_tree=attack_tree,
            latest_step=latest_step if isinstance(latest_step, str) else json.dumps(latest_step, indent=2)
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

            parsed_summary = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[!] Error parsing JSON from Summarizer: {e}")
            parsed_summary = {
                "reason": {"error": "Failed to parse JSON"},
                "attack_tree": attack_tree, # Fallback to original
                "summary": "Error parsing summary"
            }

        return {
            "parsed_summary": parsed_summary,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw_output": text
        }
