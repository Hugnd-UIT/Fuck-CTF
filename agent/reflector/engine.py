import json
import json_repair
from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT

class ReflectorAgent(PentestAgent):
    def __init__(
        self,
        model,
        local=False,
        temperature=0.7,
        top=1.0,
        sample=True,
        tokens=4096
    ):
        super().__init__(
            model=model,
            local=local,
            temperature=temperature,
            top=top,
            sample=sample,
            tokens=tokens
        )

    def review(
        self,
        history,
        facts,
        target,
        time_used,
        time_total,
        tree=None
    ):
        
        recent = history[-10:] if len(history) > 10 else history
        history_str = json.dumps(recent, indent=2)
        if isinstance(facts, dict) and facts:
            slim_facts = {
                k: (str(v)[:500] + "...[truncated]") if len(str(v)) > 500 else v
                for k, v in facts.items()
            }
            facts_str = json.dumps(slim_facts, indent=2)
        else:
            facts_str = json.dumps(facts, indent=2) if facts else "None"
        target_str = json.dumps(target, indent=2) if isinstance(target, dict) else str(target)
        tree_str = json.dumps(tree, indent=2) if tree else "None"
        
        user_content = USER_PROMPT.format(
            target=target_str,
            facts=facts_str,
            tree=tree_str,
            history=history_str,
            time_used=time_used,
            time_total=time_total
        )
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]
        
        text, in_tokens, out_tokens = self.call(messages)
        
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            else:
                json_str = text.strip()
                
            review_data = json_repair.loads(json_str)
            if isinstance(review_data, list):
                review_data = review_data[0] if review_data else {}
            if not isinstance(review_data, dict):
                review_data = {}
            
        except Exception as e:
            review_data = {
                "reason": {
                    "cause": "Failed to parse"
                },
                "tactic": "Backtrack and try a different approach.",
                "advice": "Review the last outputs carefully"
            }
            
        return {
            "review_data": review_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text
        }
