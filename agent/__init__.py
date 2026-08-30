from .planner.engine import PlannerAgent
from .executor.engine import ExecutorAgent
from .verifier.engine import VerifierAgent
from .refiner.engine import RefinerAgent
from .summarizer.engine import SummarizerAgent

class Orchestrator:
    def __init__(self, config, container=None):
        
        # Default fallback config
        default_model = None
        
        # Load agent-specific configs
        p_cfg = config.get("planner", {})
        e_cfg = config.get("executor", {})
        v_cfg = config.get("verifier", {})
        r_cfg = config.get("refiner", {})
        s_cfg = config.get("summarizer", {})
        
        # Initialize agents
        self.planner = PlannerAgent(
            model=p_cfg.get("model"),
            local=p_cfg.get("local", False),
            temperature=p_cfg.get("temperature", 0.7),
            top=p_cfg.get("top", 1.0),
            sample=p_cfg.get("sample", False),
            tokens=p_cfg.get("tokens", 1024)
        )
        
        self.executor = ExecutorAgent(
            model=e_cfg.get("model"),
            local=e_cfg.get("local", False),
            temperature=e_cfg.get("temperature", 0.2),
            top=e_cfg.get("top", 1.0),
            sample=e_cfg.get("sample", False),
            tokens=e_cfg.get("tokens", 1024)
        )
        
        self.verifier = VerifierAgent(
            model=v_cfg.get("model"),
            local=v_cfg.get("local", False),
            temperature=v_cfg.get("temperature", 0.1),
            top=v_cfg.get("top", 1.0),
            sample=v_cfg.get("sample", False),
            tokens=v_cfg.get("tokens", 1024)
        )
        
        self.refiner = RefinerAgent(
            model=r_cfg.get("model"),
            local=r_cfg.get("local", False),
            temperature=r_cfg.get("temperature", 0.2),
            top=r_cfg.get("top", 1.0),
            sample=r_cfg.get("sample", False),
            tokens=r_cfg.get("tokens", 1024)
        )
        
        self.summarizer = SummarizerAgent(
            model=s_cfg.get("model"),
            local=s_cfg.get("local", False),
            temperature=s_cfg.get("temperature", 0.3),
            top=s_cfg.get("top", 1.0),
            sample=s_cfg.get("sample", False),
            tokens=s_cfg.get("tokens", 1024)
        )

        # Initialize state variables
        self.history = []
        self.attack_tree = "- Initial target mapped"

        self.tool_list = config.get("tools", "nmap, gobuster, curl, nc, python3, gdb")

    def execute_step(self, target, sandbox):
        
        # Call planner to generate plan
        print("\n[PLANNER] Thinking...")
        import json
        target_str = json.dumps(target, indent=2) if isinstance(target, dict) else target
        
        plan_result = self.planner.plan(
            history=self.history,
            target=target_str,
            attack_tree=self.attack_tree,
            tool_list=self.tool_list
        )
        plan_json = plan_result["parsed_plan"]
        
        # Return if plan is finished
        if plan_json.get("plan", {}).get("finished", False):
            return "Goal Achieved", plan_json
        
        subtask = plan_json.get("plan", {}).get("subtask", "")
        tool_hint = plan_json.get("plan", {}).get("tool", "")

        # Call executor to generate commands
        print(f"[EXECUTOR] Translating subtask: {subtask}")
        exec_result = self.executor.execute_plan(
            target=target_str,
            subtask=subtask,
            tool_hint=tool_hint,
            history=self.history
        )
        exec_json = exec_result["parsed_exec"]
        commands = exec_json.get("commands", [])
        success_indicator = exec_json.get("success", "")

        # Execute commands in sandbox
        print(f"[SANDBOX] Running {len(commands)} command(s)...")
        full_output = ""
        for cmd in commands:
            result = sandbox.exec_run(f'/bin/bash -c "{cmd}"', stdout=True, stderr=True)
            out = result.output.decode("utf-8", errors="ignore")
            full_output += f"--- Output of '{cmd}' ---\n{out}\n"

        # Call verifier to evaluate output
        print("[VERIFIER] Evaluating results...")
        verify_result = self.verifier.verify(
            subtask=subtask,
            commands=commands,
            success_indicator=success_indicator,
            output=full_output
        )
        verify_json = verify_result["parsed_verify"]

        # Call refiner if verification failed
        if verify_json.get("result") == "fail":
            print("[REFINER] Strategy failed, refining...")
            refine_result = self.refiner.refine(
                target=target_str,
                subtask=subtask,
                failed_command=commands,
                error_output=full_output,
                history=self.history
            )
            verify_json["knowledge"].append(f"Refinement suggestion: {refine_result['parsed_refine'].get('reason', {}).get('fix_strategy')}")

        # Format latest step
        latest_step = {
            "subtask": subtask,
            "commands": commands,
            "output_summary": full_output[:500],
            "verification": verify_json
        }

        # Call summarizer to update state
        print("[SUMMARIZER] Updating Attack Tree and History...")
        summary_result = self.summarizer.summarize(
            attack_tree=self.attack_tree,
            latest_step=latest_step
        )
        summary_json = summary_result["parsed_summary"]

        # Update attack tree
        self.attack_tree = summary_json.get("attack_tree", self.attack_tree)
        
        # Update history
        step_id = f"step_{len(self.history) + 1}"
        self.history.append({
            "step_id": step_id,
            "tactic": plan_json.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown"),
            "plan": subtask,
            "observation": summary_json.get("summary", ""),
            "result": verify_json.get("result", "unknown")
        })

        return summary_json.get("summary", ""), exec_json
