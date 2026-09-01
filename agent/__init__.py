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

import cli.agent as agent_ui

from .core import state
from .core import memory
from .core import sandbox as sb

class Orchestrator:
    def __init__(self, config, container=None):
        
        p = config.get("planner", {})
        e = config.get("executor", {})
        v = config.get("verifier", {})
        r = config.get("refiner", {})
        s = config.get("summarizer", {})
        ref = config.get("reflector", {})

        self.planner = PlannerAgent(
            model=p.get("model"), 
            local=p.get("local", False), 
            temperature=p.get("temperature", 0.7), 
            top=p.get("top", 1.0), 
            sample=p.get("sample", False), 
            tokens=p.get("tokens", 1024)
        )
        
        self.executor = ExecutorAgent(
            model=e.get("model"), 
            local=e.get("local", False), 
            temperature=e.get("temperature", 0.2), 
            top=e.get("top", 1.0), 
            sample=e.get("sample", False), 
            tokens=e.get("tokens", 1024)
        )
        
        self.verifier = VerifierAgent(
            model=v.get("model"), 
            local=v.get("local", False), 
            temperature=v.get("temperature", 0.1), 
            top=v.get("top", 1.0), 
            sample=v.get("sample", False), 
            tokens=v.get("tokens", 1024)
        )
        
        self.refiner = RefinerAgent(
            model=r.get("model"), 
            local=r.get("local", False), 
            temperature=r.get("temperature", 0.2), 
            top=r.get("top", 1.0), 
            sample=r.get("sample", False), 
            tokens=r.get("tokens", 1024)
        )
        
        self.summarizer = SummarizerAgent(
            model=s.get("model"), 
            local=s.get("local", False), 
            temperature=s.get("temperature", 0.3), 
            top=s.get("top", 1.0), 
            sample=s.get("sample", False), 
            tokens=s.get("tokens", 1024)
        )
        
        self.reflector = ReflectorAgent(
            model=ref.get("model"), 
            local=ref.get("local", False), 
            temperature=ref.get("temperature", 0.7), 
            top=ref.get("top", 1.0), 
            sample=ref.get("sample", False), 
            tokens=ref.get("tokens", 4096)
        )

        try:
            with open("playbooks.json", "r") as f:
                self.books = json.load(f)
        except:
            self.books = {}

        category = config.get("target", {}).get("category", "default")
        
        self.book = {
            "category": category,
            **self.books.get("playbooks", {}).get(category, self.books.get("playbooks", {}).get("default", {}))
        }

        self.tools = self.books.get("tools", config.get("tools", "nmap, gobuster, curl, nc, python3, gdb"))

        state.init(self.book)
        memory.init()

    @property
    def history(self):
        return state.history

    def execute(self, target, sandbox, time_left=None):
        start = time.time()
        
        category = target.get("category", "") if isinstance(target, dict) else ""
        
        target_str = json.dumps(target, indent=2) if isinstance(target, dict) else target
        
        desc = target.get("description", "") if isinstance(target, dict) else str(target)

        workspace = os.path.join(os.getcwd(), 'workspace')
        if os.path.exists(workspace):
            files = os.listdir(workspace)
            if not files:
                state.absorb({"Environment": "Directory /data is EMPTY. This is a black-box challenge. DO NOT try to read files."})
            else:
                state.absorb({"Environment": f"Directory /data contains: {files}."})

        next_str = " ".join(state.tree.get("next", [])) if isinstance(state.tree.get("next"), list) else str(state.tree.get("next", ""))
        
        findings = " ".join(state.tree.get("findings", [])) if isinstance(state.tree.get("findings"), list) else str(state.tree.get("findings", ""))
        findings += " " + str(state.tree.get("data", {}))
        
        memories = memory.query(desc, state.tree.get("stage", ""), findings, next_str)
        mem_str = "\n".join(memories) if memories else "No relevant memories found."

        plan_res = self.planner.plan(
            history=state.history, fails=state.fails, target=target_str, tree=state.tree,
            tools=self.tools, playbook=self.book, memory=mem_str, time_left=time_left,
            facts=state.store, warns=state.alerts
        )
        
        plan = plan_res["plan_data"]
        elapsed = time.time() - start

        if plan.get("plan", {}).get("finished", False):
            agent_ui.plan(elapsed)
            agent_ui.noflag()
            return "Goal Achieved", plan

        sub = plan.get("plan", {}).get("subtask", "")
        
        agent_ui.plan(elapsed)
        
        if memories:
            agent_ui.think()
            
        tactic = plan.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown")

        if tactic == "Retrieval-Augmented-Generation":
            agent_ui.subtask(sub, rag=True)
            rag = memory.execute(sub, len(state.history))
            if rag:
                state.history.append(rag)
            return "Knowledge Retrieval Completed", {"commands": [], "success": "none"}
        else:
            agent_ui.subtask(sub, rag=False)

        norm = state.normalize(sub)
        state.attempts[norm] = state.attempts.get(norm, 0) + 1
        
        if state.attempts[norm] > 3:
            agent_ui.breaker(state.attempts[norm])
            
            state.fails[tactic] = state.fails.get(tactic, 0) + 1
            exec_json = {"commands": [], "success": "none"}
            verif = {"result": "fail", "knowledge": ["Circuit breaker: subtask repeated too many times."]}
            out = "[SKIPPED - circuit breaker]"
            cmds = []
            
        else:
            exec_start = time.time()
            
            exec_res = self.executor.execute_plan(target=target_str, subtask=sub, tool_hint=plan.get("plan", {}).get("tool", ""), history=state.history)
            
            exec_json = exec_res["exec_data"]
            cmds = exec_json.get("commands", [])
            ind = exec_json.get("success", "")

            exec_time = time.time() - exec_start
            agent_ui.execute(exec_time)
            
            for i, cmd in enumerate(cmds):
                agent_ui.command(cmd, i == len(cmds) - 1)

            out = sb.run(sandbox, cmds, category, exec_json.get("timeout", 30))

            FLAG = re.compile(r"(?:[a-zA-Z0-9_]{0,10}CTF|crypto|flag|HTB)\{[^}\s]{1,200}\}", re.IGNORECASE)
            match = FLAG.search(out)
            
            if match:
                return match.group(0), {"flag_captured": match.group(0)}

            v_start = time.time()
            
            v_res = self.verifier.verify(subtask=sub, commands=cmds, indicator=ind, output=out, hypothesis=plan.get("reason", {}).get("hypothesis", {}), facts=state.store)
            verif = v_res["verify_data"]
            
            v_time = time.time() - v_start
            
            if verif.get("result") == "pass":
                agent_ui.passed()
            else:
                agent_ui.failed()
                
            know = verif.get("knowledge", [])
            
            if know:
                agent_ui.knowledge(know[0])
            else:
                agent_ui.evaluated(len(cmds))

            for tries in range(2):
                agent_ui.refine(tries + 1, 2)
                
                retry = 0
                while retry < 3:
                    r_res = self.refiner.refine(
                        target=target_str, subtask=sub, failed=cmds, error=out, history=state.compressed,
                        discovered="Findings:\n" + "\n".join(state.tree.get("findings", [])) + "\nExtracted Data:\n" + str(state.tree.get("data", {}))
                    )
                    
                    raw = r_res.get("raw", "")
                    
                    if "429" in ind:
                        agent_ui.retry(retry + 1)
                        retry += 1
                        time.sleep(2 * retry)
                        continue
                    break

                r_data = r_res.get("refine_data", {})
                r_cmds = r_data.get("commands", [])
                
                if not r_cmds:
                    agent_ui.empty()
                    break

                for i, cmd in enumerate(r_cmds):
                    agent_ui.command(cmd, i == len(r_cmds) - 1)

                cmds = r_cmds
                
                out = sb.run(sandbox, cmds, category, r_data.get("timeout", exec_json.get("timeout", 30)))

                v_res = self.verifier.verify(subtask=sub, commands=cmds, indicator=ind, output=out, hypothesis=plan.get("reason", {}).get("hypothesis", {}), facts=state.store)
                verif = v_res.get("verify_data", verif)
                
                if verif.get("result") == "pass":
                    agent_ui.passed()
                else:
                    agent_ui.failed()
                
                know = verif.get("knowledge", [])
                if know:
                    agent_ui.knowledge(know[0])
                else:
                    agent_ui.evaluated(len(cmds))

                strat = r_data.get("reason", {}).get("strategy", "No strategy provided.")
                verif.setdefault("knowledge", []).append(f"Refinement applied: {strat}")
                
                if verif.get("result") == "pass":
                    break

            if verif.get("result") == "fail":
                state.fails[tactic] = state.fails.get(tactic, 0) + 1
            else:
                state.fails[tactic] = 0

        sum_start = time.time()
        
        step = {"subtask": sub, "commands": cmds, "output_summary": out[-8000:], "verification": verif}
        sum_res = self.summarizer.summarize(tree=state.tree, step=step)
        sum_data = sum_res["summary_data"]

        state.tree = sum_data.get("tree", state.tree)
        new_tree = sum_data.get("tree", {})
        new_data = new_tree.get("data", {})

        alerts_d = state.diff(new_data)    
        alerts_t = state.guard()
        state.alerts = alerts_d + alerts_t

        state.absorb(new_data)   
        state.snap()

        sum_time = time.time() - sum_start
        agent_ui.summarize(sum_time)

        if state.alerts:
            agent_ui.contradict(len(state.alerts))
        else:
            agent_ui.clean()

        id = f"step_{len(state.history) + 1}"
        
        state.history.append({
            "step_id": id,
            "tactic": tactic,
            "plan": sub,
            "observation": sum_data.get("summary", ""),
            "result": verif.get("result", "unknown"),
            "raw": out[:3000]
        })

        obs = sum_data.get("summary", "")
        state.compressed += f"\n[{id}] {obs}"
        
        if len(state.compressed) > 3000:
            state.compressed = "...[truncated]\n" + state.compressed[-3000:]

        count = len(state.history)
        fails = max(state.fails.values()) if state.fails else 0
        
        if count in [3, 6, 9] and fails >= 2:
            used = str(int(3600 - (time_left or 3600)))
            ref_start = time.time()
            
            ref_res = self.reflector.review(history=state.history, facts=state.store, target=target_str, time_used=used, time_total="3600")
            
            ref_time = time.time() - ref_start
            agent_ui.reflect(ref_time)
            
            review = ref_res["review_data"]
            adv = review.get("advice", "")
            tac = review.get("tactic", "")
            
            if adv or tac:
                state.alerts.append(f"[REFLECTOR ADVICE] {tac} - {adv}")

        return sum_data.get("summary", ""), exec_json