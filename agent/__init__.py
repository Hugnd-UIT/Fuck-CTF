import json
import re
import os
import time

from .planner.engine import PlannerAgent
from .executor.engine import ExecutorAgent
from .verifier.engine import VerifierAgent
from .refiner.engine import RefinerAgent
from .summarizer.engine import SummarizerAgent
from .reflector.engine import ReflectorAgent
from timeline import print_node, print_line, print_error, format_time

from .core.state import StateManager
from .core.memory import MemoryManager
from .core.sandbox import run_commands

class Orchestrator:
    def __init__(self, config, container=None):
        # Load agent-specific configs
        p_cfg = config.get("planner", {})
        e_cfg = config.get("executor", {})
        v_cfg = config.get("verifier", {})
        r_cfg = config.get("refiner", {})
        s_cfg = config.get("summarizer", {})
        ref_cfg = config.get("reflector", {})

        # Initialize agents
        self.planner = PlannerAgent(model=p_cfg.get("model"), local=p_cfg.get("local", False), temperature=p_cfg.get("temperature", 0.7), top=p_cfg.get("top", 1.0), sample=p_cfg.get("sample", False), tokens=p_cfg.get("tokens", 1024))
        self.executor = ExecutorAgent(model=e_cfg.get("model"), local=e_cfg.get("local", False), temperature=e_cfg.get("temperature", 0.2), top=e_cfg.get("top", 1.0), sample=e_cfg.get("sample", False), tokens=e_cfg.get("tokens", 1024))
        self.verifier = VerifierAgent(model=v_cfg.get("model"), local=v_cfg.get("local", False), temperature=v_cfg.get("temperature", 0.1), top=v_cfg.get("top", 1.0), sample=v_cfg.get("sample", False), tokens=v_cfg.get("tokens", 1024))
        self.refiner = RefinerAgent(model=r_cfg.get("model"), local=r_cfg.get("local", False), temperature=r_cfg.get("temperature", 0.2), top=r_cfg.get("top", 1.0), sample=r_cfg.get("sample", False), tokens=r_cfg.get("tokens", 1024))
        self.summarizer = SummarizerAgent(model=s_cfg.get("model"), local=s_cfg.get("local", False), temperature=s_cfg.get("temperature", 0.3), top=s_cfg.get("top", 1.0), sample=s_cfg.get("sample", False), tokens=s_cfg.get("tokens", 1024))
        self.reflector = ReflectorAgent(model=ref_cfg.get("model"), local=ref_cfg.get("local", False), temperature=ref_cfg.get("temperature", 0.7), top=ref_cfg.get("top", 1.0), sample=ref_cfg.get("sample", False), tokens=ref_cfg.get("tokens", 4096))

        # Load playbook
        try:
            with open("playbooks.json", "r") as f:
                self.playbooks = json.load(f)
        except:
            self.playbooks = {}

        category = config.get("target", {}).get("category", "default")
        self.playbook = {
            "category": category,
            **self.playbooks.get("playbooks", {}).get(category, self.playbooks.get("playbooks", {}).get("default", {}))
        }

        self.tools = self.playbooks.get("tools", config.get("tools", "nmap, gobuster, curl, nc, python3, gdb"))

        self.state = StateManager(self.playbook)
        self.memory_manager = MemoryManager()

    def execute(self, target, sandbox, time_left=None):
        start_plan = time.time()
        category = target.get("category", "") if isinstance(target, dict) else ""
        target_str = json.dumps(target, indent=2) if isinstance(target, dict) else target
        target_desc = target.get("description", "") if isinstance(target, dict) else str(target)

        # Check workspace empty
        workspace = os.path.join(os.getcwd(), 'workspace')
        if os.path.exists(workspace):
            files = os.listdir(workspace)
            if not files:
                self.state.absorb({"Environment": "Directory /data is EMPTY. This is a black-box challenge. DO NOT try to read files."})
            else:
                self.state.absorb({"Environment": f"Directory /data contains: {files}."})

        # Memory retrieval
        next_tasks_str = " ".join(self.state.tree.get("next", [])) if isinstance(self.state.tree.get("next"), list) else str(self.state.tree.get("next", ""))
        findings_str = " ".join(self.state.tree.get("findings", [])) if isinstance(self.state.tree.get("findings"), list) else str(self.state.tree.get("findings", ""))
        findings_str += " " + str(self.state.tree.get("data", {}))
        
        memories = self.memory_manager.query_context(target_desc, self.state.tree.get("stage", ""), findings_str, next_tasks_str)
        memory_str = "\n".join(memories) if memories else "No relevant memories found."

        # Planning
        plan_res = self.planner.plan(
            history=self.state.history, fails=self.state.fails, target=target_str, tree=self.state.tree,
            tools=self.tools, playbook=self.playbook, memory=memory_str, time_left=time_left,
            facts=self.state.store, warns=self.state.alerts
        )
        plan_data = plan_res["plan_data"]
        elapsed_plan = time.time() - start_plan

        if plan_data.get("plan", {}).get("finished", False):
            print_node("Planning...", format_time(elapsed_plan), "cyan")
            print_line("└─ Goal achieved")
            return "Goal Achieved", plan_data

        subtask = plan_data.get("plan", {}).get("subtask", "")
        print_node("Planning...", format_time(elapsed_plan), "cyan")
        if memories:
            print_line("├─ Thinking...")
        print_line(f"└─ {subtask}")

        tactic = plan_data.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown")

        # RAG
        if tactic == "Retrieval-Augmented-Generation":
            rag_result = self.memory_manager.execute_rag(subtask, len(self.state.history))
            if rag_result:
                self.state.history.append(rag_result)
            return "Knowledge Retrieval Completed", {"commands": [], "success": "none"}

        # Circuit Breaker
        norm_subtask = self.state.normalize(subtask)
        self.state.attempts[norm_subtask] = self.state.attempts.get(norm_subtask, 0) + 1
        if self.state.attempts[norm_subtask] > 3:
            print_error(f"Guard: subtask repeated {self.state.attempts[norm_subtask]}x — skipped")
            self.state.fails[tactic] = self.state.fails.get(tactic, 0) + 1
            exec_json = {"commands": [], "success": "none"}
            verify_data = {"result": "fail", "knowledge": ["Circuit breaker: subtask repeated too many times."]}
            output = "[SKIPPED - circuit breaker]"
            commands = []
        else:
            # Execution
            start_exec = time.time()
            exec_result = self.executor.execute_plan(target=target_str, subtask=subtask, tool_hint=plan_data.get("plan", {}).get("tool", ""), history=self.state.history)
            exec_json = exec_result["exec_data"]
            commands = exec_json.get("commands", [])
            indicator = exec_json.get("success", "")

            elapsed_exec = time.time() - start_exec
            print_node("Executing...", format_time(elapsed_exec), "magenta")
            
            for i, cmd in enumerate(commands):
                prefix = "└─ " if i == len(commands) - 1 else "├─ "
                print_line(f"{prefix}$ {cmd}")

            output = run_commands(sandbox, commands, category, exec_json.get("timeout", 30))

            FLAG = re.compile(r"(?:[a-zA-Z0-9_]{0,10}CTF|crypto|flag|HTB)\{[^}\s]{1,200}\}", re.IGNORECASE)
            flag_match = FLAG.search(output)
            if flag_match:
                return flag_match.group(0), {"flag_captured": flag_match.group(0)}

            # Verification
            start_verif = time.time()
            verify_res = self.verifier.verify(subtask=subtask, commands=commands, indicator=indicator, output=output, hypothesis=plan_data.get("reason", {}).get("hypothesis", {}), facts=self.state.store)
            verify_data = verify_res["verify_data"]
            elapsed_verif = time.time() - start_verif
            
            if verify_data.get("result") == "pass":
                print_node("Verifying...", "[ Pass ]", "green")
            else:
                print_node("Verifying...", "[ Fail ]", "red")
                
            knowledge = verify_data.get("knowledge", [])
            if knowledge:
                print_line(f"└─ {knowledge[0]}")
            else:
                print_line(f"└─ Evaluated {len(commands)} command(s)")

            # Refinement
            refine_tries = 0
            while verify_data.get("result") == "fail" and refine_tries < 2:
                print_node("Refining...", f"Retry {refine_tries + 1} / 2", "yellow")
                retry = 0
                while retry < 3:
                    refine_res = self.refiner.refine(
                        target=target_str, subtask=subtask, failed=commands, error=output, history=self.state.compressed_history,
                        discovered="Findings:\n" + "\n".join(self.state.tree.get("findings", [])) + "\nExtracted Data:\n" + str(self.state.tree.get("data", {}))
                    )
                    raw = refine_res.get("raw", "")
                    if "API Error" in raw or "API Exception" in raw:
                        print_line(f"├─ Transient API error, retrying ({retry+1}/3)...")
                        retry += 1
                        time.sleep(2 * retry)
                        continue
                    break

                refine_data = refine_res.get("refine_data", {})
                refined_commands = refine_data.get("commands", [])
                if not refined_commands:
                    verify_data.setdefault("knowledge", []).append("Refinement failed to produce new commands.")
                    print_line("└─ Failed to produce new commands")
                    break

                for i, cmd in enumerate(refined_commands):
                    prefix = "└─ " if i == len(refined_commands) - 1 else "├─ "
                    print_line(f"{prefix}$ {cmd}")

                commands = refined_commands
                output = run_commands(sandbox, commands, category, refine_data.get("timeout", exec_json.get("timeout", 30)))

                start_verif_retry = time.time()
                verify_res = self.verifier.verify(subtask=subtask, commands=commands, indicator=indicator, output=output, hypothesis=plan_data.get("reason", {}).get("hypothesis", {}), facts=self.state.store)
                verify_data = verify_res.get("verify_data", verify_data)
                
                if verify_data.get("result") == "pass":
                    print_node("Verifying...", "[ Pass ]", "green")
                else:
                    print_node("Verifying...", "[ Fail ]", "red")
                
                knowledge = verify_data.get("knowledge", [])
                if knowledge:
                    print_line(f"└─ {knowledge[0]}")
                else:
                    print_line(f"└─ Evaluated {len(commands)} command(s)")

                strategy = refine_data.get("reason", {}).get("strategy", "No strategy provided.")
                verify_data.setdefault("knowledge", []).append(f"Refinement applied: {strategy}")
                refine_tries += 1

            if verify_data.get("result") == "fail":
                self.state.fails[tactic] = self.state.fails.get(tactic, 0) + 1
            else:
                self.state.fails[tactic] = 0

        # Summarizing
        start_sum = time.time()
        step = {"subtask": subtask, "commands": commands, "output_summary": output[-8000:], "verification": verify_data}
        summary_res = self.summarizer.summarize(tree=self.state.tree, step=step)
        summary_data = summary_res["summary_data"]

        self.state.tree = summary_data.get("tree", self.state.tree)
        new_tree = summary_data.get("tree", {})
        new_data = new_tree.get("data", {})

        data_alerts = self.state.diff(new_data)    
        tree_alerts = self.state.guard()
        self.state.alerts = data_alerts + tree_alerts

        self.state.absorb(new_data)   
        self.state.snap()

        elapsed_sum = time.time() - start_sum
        print_node("Summarizing...", format_time(elapsed_sum), "cyan")
        print_line("Information updating...")

        if self.state.alerts:
            print_error(f"Contradiction: {len(self.state.alerts)} item(s) vanished or changed")
        else:
            print_line("└─ ✓ No contradictions detected")

        step_id = f"step_{len(self.state.history) + 1}"
        self.state.history.append({
            "step_id": step_id,
            "tactic": tactic,
            "plan": subtask,
            "observation": summary_data.get("summary", ""),
            "result": verify_data.get("result", "unknown"),
            "raw": output[:3000]
        })

        new_obs = summary_data.get("summary", "")
        self.state.compressed_history += f"\n[{step_id}] {new_obs}"
        if len(self.state.compressed_history) > 3000:
            self.state.compressed_history = "...[truncated]\n" + self.state.compressed_history[-3000:]

        # Reflecting
        step_count = len(self.state.history)
        consecutive_fails = max(self.state.fails.values()) if self.state.fails else 0
        if step_count in [3, 6, 9] and consecutive_fails >= 2:
            time_used = str(int(3600 - (time_left or 3600)))
            start_ref = time.time()
            ref_res = self.reflector.review(history=self.state.history, facts=self.state.store, target=target_str, time_used=time_used, time_total="3600")
            elapsed_ref = time.time() - start_ref
            print_node("Reflecting...", format_time(elapsed_ref), "magenta")
            print_line("└─ Stuck state analyzed and replanned")
            review_data = ref_res["review_data"]
            advice = review_data.get("advice", "")
            tactic_ref = review_data.get("tactic", "")
            if advice or tactic_ref:
                self.state.alerts.append(f"[REFLECTOR ADVICE] {tactic_ref} - {advice}")

        return summary_data.get("summary", ""), exec_json