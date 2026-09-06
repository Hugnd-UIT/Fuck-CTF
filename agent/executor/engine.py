import json
import json_repair

from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT


class ExecutorAgent(PentestAgent):
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

    def execute(
        self,
        target,
        subtask,
        tool_hint,
        history,
        facts=None,
        tree=None,
        obs=None,
        messages=None
    ):

        # Handle multi-turn dialogue
        if messages:
            msg_list = list(messages)
            obs_content = str(obs) if obs else "[No command output]"
            turn_prompt = (
                f"Observation:\n{obs_content}\n\n"
                "Analyze this observation:\n"
                "- If the subtask objective is accomplished, set \"done\": true and \"commands\": [].\n"
                "- If an error occurred or further action is required, self-correct: set \"done\": false and output the next surgical commands."
            )
            msg_list.append({
                "role": "user",
                "content": turn_prompt
            })

        else:
            # Format history
            slim = []

            # Get 5 history recently
            for entry in (history[-5:] if isinstance(history, list) else []):
                item = {}
                for k, v in entry.items():

                    # Truncate raw output to 3000 characters
                    if k == "raw":
                        if entry.get("result") not in ("pass", "success"):
                            item["raw"] = str(v)[-3000:]
                    else:
                        item[k] = v
                slim.append(item)
            history_str = json.dumps(slim, indent=2) if isinstance(slim, (list, dict)) else str(slim)

            # Format facts
            if isinstance(facts, dict) and facts:
                # Truncate facts to 25000 characters
                slim_facts = {
                    k: (str(v)[:25000] + "...[truncated]") if len(str(v)) > 25000 else v
                    for k, v in facts.items()
                }
                facts_str = json.dumps(slim_facts, indent=2)
            else:
                facts_str = json.dumps(facts, indent=2) if isinstance(facts, dict) else (str(facts) if facts else "{}")

            # Format tree
            tree_str = json.dumps(tree, indent=2) if isinstance(tree, (dict, list)) else (str(tree) if tree else "{}")

            # Format observation
            obs_str = f"\nObservation: {obs}" if obs else ""

            # Format user prompt
            user = USER_PROMPT.format(
                target=target,
                tree=tree_str,
                facts=facts_str,
                subtask=subtask,
                tool_hint=tool_hint,
                history=history_str,
                observation=obs_str
            )

            msg_list = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user
                }
            ]

        # Call model
        text, in_tokens, out_tokens = self.call(msg_list)

        # Append assistant response
        msg_list.append({
            "role": "assistant",
            "content": text
        })

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

            exec_data = json_repair.loads(json_str)
            if isinstance(exec_data, list):
                exec_data = exec_data[0] if exec_data else {}
            if not isinstance(exec_data, dict):
                exec_data = {}

            commands = exec_data.get("commands", [])

        except Exception as e:

            exec_data = {
                "reason": {
                    "analysis": "Failed to parse JSON"
                },
                "commands": [
                    "echo 'Executor failed to parse JSON'"
                ],
                "done": True,
                "timeout": 10,
                "success": "false",
                "avoids": "none",
                "rag": None
            }

        return {
            "exec_data": exec_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text,
            "messages": msg_list
        }