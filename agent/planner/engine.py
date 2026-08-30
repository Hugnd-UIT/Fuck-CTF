import json
from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT

class PlannerAgent(PentestAgent):
    def __init__(self, model, local=False, temperature=0.7, top=1.0, sample=False, tokens=1024):
        
        # Initialize base agent
        super().__init__(
            model=model,
            local=local,
            temperature=temperature,
            top=top,
            sample=sample,
            tokens=tokens
        )

    def plan(self, history, target, attack_tree, tool_list, playbook=None):
        if playbook is None:
            playbook = {}
            
        # Format history
        if isinstance(history, (list, dict)):
            history_str = json.dumps(history, indent=2)
        else:
            history_str = str(history)

        # Build playbook parts
        tactics_str = ", ".join(playbook.get("tactics", []))
        procedure_str = "\n".join(playbook.get("procedure", []))
        forbidden_str = "\n".join(f"- {x}" for x in playbook.get("forbidden", []))

        # Format system prompts
        system_content = (
            SYSTEM_PROMPT
            .replace("<TOOL_LIST>", tool_list)
            .replace("<CATEGORY>", playbook.get("category", "default"))
            .replace("<TACTIC_LIST>", tactics_str)
            .replace("<PROCEDURE>", procedure_str)
            .replace("<FORBIDDEN>", forbidden_str)
        )
        user_content = USER_PROMPT.format(
            target=target,
            tool_list=tool_list,
            attack_tree=attack_tree,
            history=history_str
        )

        messages = [
            {"role": "system", "content": system_content},
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

            parsed_plan = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[!] Error parsing JSON from Planner: {e}")
            parsed_plan = {
                "reason": {"error": "Failed to parse JSON"},
                "plan": {"subtask": "Error parsing plan", "finished": False}
            }

        return {
            "parsed_plan": parsed_plan,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw_output": text
        }
