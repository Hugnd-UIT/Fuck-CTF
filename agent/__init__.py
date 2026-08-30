import json
import hashlib
import re
from .planner.engine import PlannerAgent
from .executor.engine import ExecutorAgent
from .verifier.engine import VerifierAgent
from .refiner.engine import RefinerAgent
from .summarizer.engine import SummarizerAgent
from rag.github import search_github
from rag.firecrawl import scrape

class Orchestrator:
    def __init__(self, config, container=None):
        
        # Load agent-specific configs
        p_cfg = config.get("planner", {})
        e_cfg = config.get("executor", {})
        v_cfg = config.get("verifier", {})
        r_cfg = config.get("refiner", {})
        s_cfg = config.get("summarizer", {})
        
        # Initialize agents
        self.planner = PlannerAgent(model=p_cfg.get("model"), local=p_cfg.get("local", False), temperature=p_cfg.get("temperature", 0.7), top=p_cfg.get("top", 1.0), sample=p_cfg.get("sample", False), tokens=p_cfg.get("tokens", 1024))
        self.executor = ExecutorAgent(model=e_cfg.get("model"), local=e_cfg.get("local", False), temperature=e_cfg.get("temperature", 0.2), top=e_cfg.get("top", 1.0), sample=e_cfg.get("sample", False), tokens=e_cfg.get("tokens", 1024))
        self.verifier = VerifierAgent(model=v_cfg.get("model"), local=v_cfg.get("local", False), temperature=v_cfg.get("temperature", 0.1), top=v_cfg.get("top", 1.0), sample=v_cfg.get("sample", False), tokens=v_cfg.get("tokens", 1024))
        self.refiner = RefinerAgent(model=r_cfg.get("model"), local=r_cfg.get("local", False), temperature=r_cfg.get("temperature", 0.2), top=r_cfg.get("top", 1.0), sample=r_cfg.get("sample", False), tokens=r_cfg.get("tokens", 1024))
        self.summarizer = SummarizerAgent(model=s_cfg.get("model"), local=s_cfg.get("local", False), temperature=s_cfg.get("temperature", 0.3), top=s_cfg.get("top", 1.0), sample=s_cfg.get("sample", False), tokens=s_cfg.get("tokens", 1024))

        # Load playbook
        try:
            with open("playbooks.json", "r") as f:
                self.playbooks = json.load(f)
        except:
            self.playbooks = {}
            
        category = config.get("target", {}).get("category", "default")
        self.active_playbook = {
            "category": category,
            **self.playbooks.get(category, self.playbooks.get("default", {}))
        }

        # Initialize state variables
        self.history_log = []
        self.compressed_history = ""
        
        # Seed attack tree
        initial_tactics = self.active_playbook.get("tactics", ["Reconnaissance"])
        initial_stage = initial_tactics[0] if initial_tactics else "Reconnaissance"
        
        self.attack_tree = {
            "stage": initial_stage,
            "done": [],
            "findings": ["Initial target mapped"],
            "next": self.active_playbook.get("procedure", [])[:2],
            "failed": []
        }

        self.tool_list = config.get("tools", "nmap, gobuster, curl, nc, python3, gdb")
        
        self.command_hashes = set()
        self.consecutive_fail_streak = {}
        self.subtask_attempts = {}

    def _normalize(self, text: str) -> str:
        norm = re.sub(r"'[^']*'|\"[^\"]*\"", "<STR>", text)
        norm = re.sub(r"\b\d+\b", "<NUM>", norm)
        return norm.strip().lower()

    def _is_duplicate_command(self, cmd: str) -> bool:
        h = hashlib.sha256(self._normalize(cmd).encode()).hexdigest()
        if h in self.command_hashes:
            return True
        self.command_hashes.add(h)
        return False

    def _build_history_for_planner(self):
        notices = []
        for tactic, streak in self.consecutive_fail_streak.items():
            if streak >= 3:
                notices.append({
                    "step_id": "SYSTEM_NOTICE",
                    "tactic": tactic,
                    "plan": "N/A",
                    "observation": (
                        f"Tactic '{tactic}' has failed {streak} times in a row. "
                        f"You are FORBIDDEN from proposing this tactic next."
                    ),
                    "result": "forced_block"
                })
        return notices + self.history_log[-15:]

    def execute_step(self, target, sandbox):
        print("\n[PLANNER] Thinking...")
        target_str = json.dumps(target, indent=2) if isinstance(target, dict) else target
        tree_str = json.dumps(self.attack_tree, indent=2) if isinstance(self.attack_tree, dict) else self.attack_tree
        
        # MEMORY RETRIEVAL
        retrieved_memory = []
        try:
            query_text = str(self.attack_tree.get("next", "")) or "Initial recon"
            # Query memory collection
            mem_res = self.memory_collection.query(query_texts=[query_text], n_results=3)
            if mem_res and "documents" in mem_res and mem_res["documents"] and mem_res["documents"][0]:
                for doc in mem_res["documents"][0]:
                    retrieved_memory.append(f"[PAST_MEMORY] {doc}")
            
            # Query knowledge collection
            know_res = self.knowledge_collection.query(query_texts=[query_text], n_results=50)
            if know_res and "documents" in know_res and know_res["documents"] and know_res["documents"][0]:
                for doc, dist in zip(know_res["documents"][0], know_res["distances"][0]):
                    if dist < 1.5: # Similarity threshold
                        retrieved_memory.append(f"[EXTERNAL_KNOWLEDGE] {doc}")
        except Exception as e:
            print(f"[!] Error retrieving from DB: {e}")
            
        memory_context = "\n".join(retrieved_memory) if retrieved_memory else "No relevant memories found."
        print(f"[MEMORY] Injected {len(retrieved_memory)} memory/knowledge chunks.")

        plan_result = self.planner.plan(
            history=self._build_history_for_planner(),
            target=target_str,
            attack_tree=tree_str,
            tool_list=self.tool_list,
            playbook=self.active_playbook,
            memory_context=memory_context
        )
        plan_json = plan_result["parsed_plan"]
        
        if plan_json.get("plan", {}).get("finished", False):
            return "Goal Achieved", plan_json
        
        subtask = plan_json.get("plan", {}).get("subtask", "")
        tool_hint = plan_json.get("plan", {}).get("tool", "")

        tactic = plan_json.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown")
        
        # RAG
        if tactic == "Retrieval-Augmented-Generation":
            print(f"[ORCHESTRATOR] RAG Intercept: Activating GitHub and Web Scraping for '{subtask}'")
            try:
                import concurrent.futures
                from rag.duckduckgo import search_web
                
                def task_github():
                    gh_res = search_github(subtask)
                    issues = gh_res.get("github_issues", [])
                    total_gh_chunks = 0
                    preview = ""
                    
                    if not issues: return 0, "No GH issues found."
                    
                    def scrape_and_store(issue):
                        url = issue.get("url")
                        from rag.firecrawl import scrape
                        md_text, err = scrape(url)
                        if md_text:
                            chunks = [md_text[i:i+2000] for i in range(0, len(md_text), 2000)]
                            import hashlib
                            ids = [f"know_{hashlib.md5((url + str(i)).encode()).hexdigest()}" for i in range(len(chunks))]
                            return chunks, ids, md_text
                        return [], [], ""

                    # Run Firecrawl for Github issues in parallel
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                        results = list(ex.map(scrape_and_store, issues))
                        
                    for chunks, ids, md_text in results:
                        if chunks:
                            self.knowledge_collection.add(documents=chunks, ids=ids)
                            total_gh_chunks += len(chunks)
                            if not preview: preview = md_text[:1500]
                    return total_gh_chunks, preview

                def task_web():
                    res = search_web(subtask, max_results=5)
                    if "docs" in res and res["docs"]:
                        self.knowledge_collection.add(documents=res["docs"], ids=res["ids"])
                        return res["total_chunks"], res["preview"]
                    return 0, res.get("error", "No web results.")

                # Run both Github and Web searches in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as main_executor:
                    future_gh = main_executor.submit(task_github)
                    future_web = main_executor.submit(task_web)
                    
                    gh_chunks, gh_preview = future_gh.result()
                    web_chunks, web_preview = future_web.result()

                knowledge_gathered = f"Scraped GitHub ({gh_chunks} chunks) and Web ({web_chunks} chunks). Total: {gh_chunks + web_chunks} chunks saved to DB."
                print(f"[ORCHESTRATOR] {knowledge_gathered}")
                
                step_id = f"step_{len(self.history_log) + 1}"
                self.history_log.append({
                    "step_id": step_id,
                    "tactic": tactic,
                    "plan": subtask,
                    "observation": f"[Knowledge Gathered] {knowledge_gathered} Preview: {gh_preview or web_preview}",
                    "result": "success"
                })
                # Skip executor, sandbox, verifier
                return "Knowledge Retrieval Completed", {"commands": [], "success": "none"}
                
            except Exception as e:
                print(f"[!] RAG Intercept failed: {e}")
                import traceback
                traceback.print_exc()
                
        norm_subtask = self._normalize(subtask)
        self.subtask_attempts[norm_subtask] = self.subtask_attempts.get(norm_subtask, 0) + 1
        if self.subtask_attempts[norm_subtask] > 3:
            print(f"[GUARD] Subtask repeated {self.subtask_attempts[norm_subtask]}x, forcing skip.")
            exec_json = {"commands": [], "success": "none"}
            verify_json = {"result": "fail", "knowledge": ["Circuit breaker: subtask repeated too many times."]}
            tactic = plan_json.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown")
            self.consecutive_fail_streak[tactic] = self.consecutive_fail_streak.get(tactic, 0) + 1
            full_output = "[SKIPPED - circuit breaker]"
            commands = []
        else:
            print(f"[EXECUTOR] Translating subtask: {subtask}")
            exec_result = self.executor.execute_plan(
                target=target_str,
                subtask=subtask,
                tool_hint=tool_hint,
                history=self._build_history_for_planner()
            )
            exec_json = exec_result["parsed_exec"]
            commands = exec_json.get("commands", [])
            success_indicator = exec_json.get("success", "")

            print(f"[SANDBOX] Running {len(commands)} command(s)...")
            full_output = ""
            for cmd in commands:
                if self._is_duplicate_command(cmd):
                    full_output += f"--- Output of '{cmd}' ---\n[SKIPPED - identical command already attempted this session]\n"
                    continue
                raw_timeout = exec_json.get("timeout", 30)
                try:
                    cmd_timeout = min(int(raw_timeout), 120)
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

            print("[VERIFIER] Evaluating results...")
            verify_result = self.verifier.verify(
                subtask=subtask,
                commands=commands,
                success_indicator=success_indicator,
                output=full_output,
                hypothesis=plan_json.get("reason", {}).get("hypothesis", {})
            )
            verify_json = verify_result["parsed_verify"]

            MAX_REFINE_RETRIES = 5
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
                    verify_json.setdefault("knowledge", []).append("Refinement failed to produce new commands.")
                    break
                    
                print(f"[SANDBOX] Running {len(refined_commands)} refined command(s)...")
                commands = refined_commands 
                full_output = ""
                for cmd in commands:
                    if self._is_duplicate_command(cmd):
                        full_output += f"--- Output of '{cmd}' ---\n[SKIPPED - identical command already attempted this session]\n"
                        continue
                    raw_timeout = exec_json.get("timeout", 30)
                    try:
                        cmd_timeout = min(int(raw_timeout), 120)
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

            tactic = plan_json.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown")
            if verify_json.get("result") == "fail":
                self.consecutive_fail_streak[tactic] = self.consecutive_fail_streak.get(tactic, 0) + 1
            else:
                self.consecutive_fail_streak[tactic] = 0

        latest_step = {
            "subtask": subtask,
            "commands": commands,
            "output_summary": full_output[:500],
            "verification": verify_json
        }

        print("[SUMMARIZER] Updating Attack Tree and History...")
        summary_result = self.summarizer.summarize(
            attack_tree=tree_str,
            latest_step=latest_step
        )
        summary_json = summary_result["parsed_summary"]

        self.attack_tree = summary_json.get("attack_tree", self.attack_tree)
        
        step_id = f"step_{len(self.history_log) + 1}"
        self.history_log.append({
            "step_id": step_id,
            "tactic": plan_json.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown"),
            "plan": subtask,
            "observation": summary_json.get("summary", ""),
            "result": verify_json.get("result", "unknown")
        })
        
        new_obs = summary_json.get("summary", "")
        self.compressed_history += f"\n[{step_id}] {new_obs}"
        if len(self.compressed_history) > 3000:
            self.compressed_history = "...[truncated]\n" + self.compressed_history[-3000:]

        return summary_json.get("summary", ""), exec_json
