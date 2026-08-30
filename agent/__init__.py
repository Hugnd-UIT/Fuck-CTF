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
        self.history_log = []
        self.compressed_history = ""
        self.attack_tree = {
            "stage": "reconnaissance",
            "done": [],
            "findings": ["Initial target mapped"],
            "next": ["Analyze target category and apply playbook"],
            "failed": []
        }

        self.tool_list = config.get("tools", "nmap, gobuster, curl, nc, python3, gdb")

    def execute_step(self, target, sandbox):
        
        # Call planner to generate plan
        print("\n[PLANNER] Thinking...")
        import json
        target_str = json.dumps(target, indent=2) if isinstance(target, dict) else target
        tree_str = json.dumps(self.attack_tree, indent=2) if isinstance(self.attack_tree, dict) else self.attack_tree
        
        plan_result = self.planner.plan(
            history=self.compressed_history,
            target=target_str,
            attack_tree=tree_str,
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
            history=self.compressed_history
        )
        exec_json = exec_result["parsed_exec"]
        commands = exec_json.get("commands", [])
        success_indicator = exec_json.get("success", "")

        # Execute commands in sandbox
        print(f"[SANDBOX] Running {len(commands)} command(s)...")
        full_output = ""
        for cmd in commands:
            cmd_timeout = exec_json.get("timeout", 30)
            try:
                wrapped_cmd = f'timeout {cmd_timeout} /bin/bash -c "{cmd}"'
                result = sandbox.exec_run(wrapped_cmd, stdout=True, stderr=True)
                out = result.output.decode("utf-8", errors="ignore")
                
                if result.exit_code == 124: # 124 is the standard exit code for the timeout command
                    out = f"[TIMEOUT] Command exceeded {cmd_timeout}s. Partial output:\n" + out
            except Exception as e:
                out = f"[TIMEOUT] Command execution failed: {e}"
            full_output += f"--- Output of '{cmd}' ---\n{out}\n"

        # Call verifier to evaluate output
        print("[VERIFIER] Evaluating results...")
        verify_result = self.verifier.verify(
            subtask=subtask,
            commands=commands,
            success_indicator=success_indicator,
            output=full_output,
            hypothesis=plan_json.get("reason", {}).get("hypothesis", {})
        )
        verify_json = verify_result["parsed_verify"]

        # Call refiner if verification failed
        MAX_REFINE_RETRIES = 1
        refine_attempts = 0
        while verify_json.get("result") == "fail" and refine_attempts < MAX_REFINE_RETRIES:
            print(f"[REFINER] Strategy failed, refining (Attempt {refine_attempts + 1}/{MAX_REFINE_RETRIES})...")
            refine_result = self.refiner.refine(
                target=target_str,
                subtask=subtask,
                failed_command=commands,
                error_output=full_output,
                history=self.compressed_history
            )
            
            parsed_refine = refine_result.get("parsed_refine", {})
            refined_commands = parsed_refine.get("commands", [])
            
            if not refined_commands:
                verify_json["knowledge"].append("Refinement failed to produce new commands.")
                break
                
            print(f"[SANDBOX] Running {len(refined_commands)} refined command(s)...")
            commands = refined_commands # Update for next verification
            full_output = ""
            for cmd in commands:
                raw_timeout = exec_json.get("timeout", 30)
                try:
                    cmd_timeout = min(int(raw_timeout), 120) # Cap timeout at 120s to prevent hanging
                except:
                    cmd_timeout = 30
                    
                try:
                    wrapped_cmd = ["timeout", "--preserve-status", "-k", "5", str(cmd_timeout), "/bin/bash", "-c", cmd]
                    result = sandbox.exec_run(wrapped_cmd, stdout=True, stderr=True)
                    out = result.output.decode("utf-8", errors="ignore")
                    
                    if result.exit_code == 124:
                        out = f"[TIMEOUT] Command exceeded {cmd_timeout}s. Partial output:\n" + out
                except Exception as e:
                    out = f"[TIMEOUT] Command execution failed: {e}"
                full_output += f"--- Output of '{cmd}' ---\n{out}\n"
                
            print("[VERIFIER] Evaluating refined results...")
            verify_result = self.verifier.verify(
                subtask=subtask,
                commands=commands,
                success_indicator=success_indicator,
                output=full_output,
                hypothesis=plan_json.get("reason", {}).get("hypothesis", {})
            )
            verify_json = verify_result.get("parsed_verify", verify_json)
            fix_strategy = parsed_refine.get('reason', {}).get('fix_strategy', 'Unknown')
            verify_json.setdefault("knowledge", []).append(f"Refinement applied: {fix_strategy}")
            
            refine_attempts += 1

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
            attack_tree=tree_str,
            latest_step=latest_step
        )
        summary_json = summary_result["parsed_summary"]

        # Update attack tree
        self.attack_tree = summary_json.get("attack_tree", self.attack_tree)
        
        # Update history log
        step_id = f"step_{len(self.history_log) + 1}"
        self.history_log.append({
            "step_id": step_id,
            "tactic": plan_json.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown"),
            "plan": subtask,
            "observation": summary_json.get("summary", ""),
            "result": verify_json.get("result", "unknown")
        })
        
        # Update compressed history
        new_obs = summary_json.get("summary", "")
        self.compressed_history += f"\n[{step_id}] {new_obs}"
        if len(self.compressed_history) > 3000:
            self.compressed_history = "...[truncated]\n" + self.compressed_history[-3000:]

        return summary_json.get("summary", ""), exec_json
