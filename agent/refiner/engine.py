import json
import json_repair

from agent.pentest import PentestAgent
from .prompt import SYSTEM_PROMPT, USER_PROMPT


class RefinerAgent(PentestAgent):
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

    def refine(
        self,
        target,
        subtask,
        failed,
        error,
        history,
        discovered="",
        time_left=None,
        obs=None,
        messages=None
    ):

        # Handle multi-turn dialogue
        if messages:
            msg_list = list(messages)
            obs_parts = []
            if obs:
                obs_parts.append(str(obs))
            if discovered and "Ground Truth Files Inspected:" in discovered:
                obs_parts.append(discovered)
            obs_content = "\n\n".join(obs_parts) if obs_parts else "[No command output]"
            turn_prompt = (
                f"Observation:\n{obs_content}\n\n"
                "Analyze this observation:\n"
                "- If the fix succeeded and the subtask is now accomplished, set \"done\": true and \"commands\": [].\n"
                "- If the fix produced a new error or needs further calibration, self-correct: set \"done\": false and output corrected commands."
            )
            msg_list.append({
                "role": "user",
                "content": turn_prompt
            })

        else:
            # Format history
            if isinstance(history, (list, dict)):
                history_str = json.dumps(history, indent=2)
            else:
                history_str = str(history)

            # Format commands
            if isinstance(failed, list):
                failed_command_str = json.dumps(failed)
            else:
                failed_command_str = str(failed)

            time_left_str = str(int(time_left)) if time_left is not None else "Unknown"
            obs_str = f"\nObservation: {obs}" if obs else ""

            # Format user prompt
            user_content = USER_PROMPT.format(
                target=target,
                discovered=discovered or "Not yet collected.",
                subtask=subtask,
                failed=failed_command_str,
                error=error,
                history=history_str,
                time_left=time_left_str,
                observation=obs_str
            )

            msg_list = [
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

            refine_data = json_repair.loads(json_str)
            if isinstance(refine_data, list):
                refine_data = refine_data[0] if refine_data else {}
            if not isinstance(refine_data, dict):
                refine_data = {}
                
        except Exception as e:

            refine_data = {
                "reason": {
                    "analysis": "Failed to parse JSON",
                    "error": "syntax",
                    "strategy": "none",
                    "risk": "none"
                },
                "abort": True,
                "commands": [],
                "done": True,
                "read": None,
                "timeout": 10,
                "success": "false"
            }

        return {
            "refine_data": refine_data,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "raw": text,
            "messages": msg_list
        }