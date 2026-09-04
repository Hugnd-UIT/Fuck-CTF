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
        # Extract config
        p = config.get("planner", {})
        e = config.get("executor", {})
        v = config.get("verifier", {})
        r = config.get("refiner", {})
        s = config.get("summarizer", {})
        ref = config.get("reflector", {})

        # Initialize Planner
        self.planner = PlannerAgent(
            model=p.get("model"), 
            local=p.get("local", False), 
            temperature=p.get("temperature", 0.7), 
            top=p.get("top", 1.0), 
            sample=p.get("sample", False), 
            tokens=p.get("tokens", 1024)
        )
        
        # Initialize Executor
        self.executor = ExecutorAgent(
            model=e.get("model"), 
            local=e.get("local", False), 
            temperature=e.get("temperature", 0.2), 
            top=e.get("top", 1.0), 
            sample=e.get("sample", False), 
            tokens=e.get("tokens", 1024)
        )
        
        # Initialize Verifier
        self.verifier = VerifierAgent(
            model=v.get("model"), 
            local=v.get("local", False), 
            temperature=v.get("temperature", 0.1), 
            top=v.get("top", 1.0), 
            sample=v.get("sample", False), 
            tokens=v.get("tokens", 1024)
        )
        
        # Initialize Refiner
        self.refiner = RefinerAgent(
            model=r.get("model"), 
            local=r.get("local", False), 
            temperature=r.get("temperature", 0.2), 
            top=r.get("top", 1.0), 
            sample=r.get("sample", False), 
            tokens=r.get("tokens", 1024)
        )
        
        # Initialize Summarizer
        self.summarizer = SummarizerAgent(
            model=s.get("model"), 
            local=s.get("local", False), 
            temperature=s.get("temperature", 0.3), 
            top=s.get("top", 1.0), 
            sample=s.get("sample", False), 
            tokens=s.get("tokens", 1024)
        )
        
        # Initialize Reflector
        self.reflector = ReflectorAgent(
            model=ref.get("model"), 
            local=ref.get("local", False), 
            temperature=ref.get("temperature", 0.7), 
            top=ref.get("top", 1.0), 
            sample=ref.get("sample", False), 
            tokens=ref.get("tokens", 4096)
        )

        # Load playbooks
        category = config.get("target", {}).get("category", "default")
        book_path = os.path.join("books", f"{category}.md")
        if not os.path.exists(book_path):
            book_path = os.path.join("books", "default.md")
            
        try:
            with open(book_path, "r", encoding="utf-8") as f:
                self.book = f.read()
        except:
            self.book = "Failed to load playbook."

        self.tools = "nmap, rustscan, ffuf, gobuster, dirsearch, curl, wget, sqlmap, nc, socat, python3, php, perl, gdb, pwndbg, checksec, ldd, strace, ltrace, objdump, readelf, strings, xxd, ropper, ROPgadget, radare2, ghidra, angr, one_gadget, seccomp-tools, patchelf, upx, john, hashcat, binwalk, exiftool, steghide, linpeas, pwntools, pycryptodome, sympy, gmpy2, sagemath"

        # Initialize state
        state.init(self.book)
        memory.init()
        self.fails = 0

    # Get history
    @property
    def history(self):
        return state.history

    def read(self, target, sandbox, base_dir=None):
        base = base_dir or getattr(self, "target_dir", "/data") or "/data"
        return sb.read(sandbox, target, base_dir=base)

    def execute(self, target, sandbox, time_left=None):
        # Start execution
        start = time.time()
        
        # Check workspace
        workspace = os.path.join(os.getcwd(), 'workspace')
        target_dir = target.get("dir", "/data") if isinstance(target, dict) else "/data"
        self.target_dir = target_dir if target_dir and target_dir != "-" else "/data"
        
        if target_dir and target_dir != "-" and os.path.exists(workspace):
            all_files = []
            for root, dirs, filenames in os.walk(workspace):
                dirs[:] = [d for d in dirs if d != ".git" and d != "__pycache__"]
                for f in filenames:
                    if f == ".gitignore" or f.endswith(".pyc"):
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), workspace).replace("\\", "/")
                    all_files.append(rel_path)

            if not all_files:
                state.absorb({"Environment": "No local directory or files provided!"})
            else:
                if self.target_dir == "/data":
                    subdirs = set()
                    for f in all_files:
                        if "/" in f:
                            subdirs.add(os.path.dirname(f).replace("\\", "/"))
                    if subdirs:
                        def score(s):
                            count = sum(1 for f in all_files if f.startswith(s + "/"))
                            bonus = sum(2 for f in all_files if f.startswith(s + "/") and any(f.endswith(ext) for ext in (".c", ".cpp", ".py", ".sh", ".txt", ".bin", "")))
                            return (s.count("/"), count + bonus)
                        best_sub = max(subdirs, key=score)
                        self.target_dir = f"/data/{best_sub}"

                file_list = "\n".join(f"- /data/{f}" for f in all_files)
                state.absorb({"Environment": f"Workspace challenge working directory: {self.target_dir}\nAll files in container (/data):\n{file_list}"})
        else:
            state.absorb({"Environment": "No local directory or files provided!"})

        # Parse target
        category = target.get("category", "") if isinstance(target, dict) else ""
        
        if isinstance(target, dict):
            clean = {k: v for k, v in target.items() if v}
            clean["dir"] = self.target_dir
            if "host" not in clean and "port" not in clean:
                clean["network"] = "This is a local challenge!"
            target_str = json.dumps(clean, indent=2)
        else:
            target_str = str(target)
        
        desc = target.get("description", "") if isinstance(target, dict) else str(target)

        # Build memory query
        next_str = " ".join(state.tree.get("next", [])) if isinstance(state.tree.get("next"), list) else str(state.tree.get("next", ""))
        
        findings = " ".join(state.tree.get("findings", [])) if isinstance(state.tree.get("findings"), list) else str(state.tree.get("findings", ""))
        findings += " " + str(state.tree.get("data", {}))
        
        # Query memory
        memories = memory.query(desc, state.tree.get("stage", ""), findings, next_str)
        mem_str = "\n".join(memories) if memories else "No relevant memories found."

        # Plan next steps
        plan_res = self.planner.plan(
            history=state.history, fails=state.fails, target=target_str, tree=state.tree,
            tools=self.tools, playbook=self.book, memory=mem_str, time_left=time_left,
            facts=state.store, warns=state.alerts
        )
        
        plan = plan_res["plan_data"]
        elapsed = time.time() - start

        plan_dict = plan.get("plan", {}) if isinstance(plan.get("plan"), dict) else {}
        sub = plan_dict.get("subtask", "") or plan.get("subtask", "")
        if not sub:
            sub = "Thinking..."

        rag_query = plan_dict.get("rag", "") or plan.get("rag", "")
        plan_reflect = plan_dict.get("reflect", False) or plan.get("reflect", False)

        # Check completion
        if plan_dict.get("finished", False) or plan.get("finished", False):
            agent_ui.plan(elapsed)
            return "Goal Achieved", plan

        agent_ui.plan(elapsed)
        
        reason_dict = plan.get("reason", {}) if isinstance(plan.get("reason"), dict) else {}
        hypothesis = reason_dict.get("hypothesis", {}) if isinstance(reason_dict.get("hypothesis"), dict) else {}
        
        rationale = (
            hypothesis.get("rationale", "") or 
            reason_dict.get("rationale", "") or 
            plan.get("rationale", "") or 
            (plan.get("hypothesis", {}).get("rationale", "") if isinstance(plan.get("hypothesis"), dict) else "") or
            plan.get("raw_text", "")
        )
        
        if rationale:
            agent_ui.think(rationale)
        else:
            agent_ui.think(f"Output: {str(plan)[:200]}...")
            
        tactic = plan.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown")

        # Handle read
        plan_read = plan_dict.get("read") or plan.get("read")
        if plan_read and str(plan_read).lower() not in ("none", "null", "", "false", "[]"):
            if isinstance(plan_read, list):
                read_targets = [str(f).strip() for f in plan_read if str(f).strip()]
            elif "," in str(plan_read):
                read_targets = [p.strip() for p in str(plan_read).split(",") if p.strip()]
            else:
                read_targets = [str(plan_read).strip()]

            read_targets = [t for t in read_targets if t and t.lower() not in ("none", "null", "", "false")]
            if read_targets:
                read_key = "read_" + "_".join(read_targets)
                state.attempts[read_key] = state.attempts.get(read_key, 0) + 1
                if state.attempts[read_key] <= 2:
                    agent_ui.read(read_targets, last=False)
                    combined_obs = []
                    for t in read_targets:
                        out_t = self.read(t, sandbox)
                        state.absorb({f"Inspection ({t})": out_t})
                        combined_obs.append(f"[{t}]\n{out_t}")

                    read_summary = "\n\n".join(combined_obs)
                    id = f"step_{len(state.history) + 1}"
                    state.history.append({
                        "step_id": id,
                        "tactic": "Inspection",
                        "plan": f"Read {', '.join(read_targets)}",
                        "observation": read_summary[:8000],
                        "result": "pass",
                        "raw": read_summary[:15000]
                    })
                    return "Read completed!", {"commands": [], "success": "none"}

        # Handle RAG
        plan_rag = plan_dict.get("rag")
        if plan_rag and str(plan_rag).lower() not in ("none", "null", ""):
            agent_ui.subtask(plan_rag, rag=True)
            rag_out = memory.execute(plan_rag, len(state.history))
            if rag_out:
                state.history.append(rag_out)
            return "RAG completed!", {"commands": [], "success": "none"}
        else:
            agent_ui.subtask(sub, rag=False)

        # Track attempts
        norm = state.normalize(sub)
        state.attempts[norm] = state.attempts.get(norm, 0) + 1
        r_abort = False
        
        # Trigger circuit breaker
        if state.attempts[norm] > 3:
            agent_ui.breaker(state.attempts[norm])
            
            state.fails[tactic] = state.fails.get(tactic, 0) + 1
            self.fails += 1
            exec_json = {"commands": [], "success": "none"}
            verif = {"result": "fail", "knowledge": ["subtask repeated too many times!"]}
            out = "[SKIPPED]"
            cmds = []
            
        else:
            # Execute plan
            exec_start = time.time()
            
            tool_hint = plan_dict.get("hint", "") or plan.get("hint", "") or plan_dict.get("tool", "") or plan.get("tool", "")
            data = {**state.tree.get("data", {}), **state.store}
            exec_res = self.executor.execute_plan(target=target_str, subtask=sub, tool_hint=tool_hint, history=state.history, facts=data)
            
            exec_json = exec_res["exec_data"]
            
            # Handle RAG
            exec_rag = exec_json.get("rag")
            if exec_rag and str(exec_rag).lower() not in ("none", "null", ""):
                exec_time = time.time() - exec_start
                agent_ui.execute(exec_time)
                agent_ui.subtask(exec_rag, rag=True)
                rag_out = memory.execute(exec_rag, len(state.history))
                if rag_out:
                    state.history.append(rag_out)
                return "RAG completed!", {"commands": [], "success": "none"}
                
            cmds = exec_json.get("commands", [])
            ind = exec_json.get("success", "")

            exec_time = time.time() - exec_start
            agent_ui.execute(exec_time)
            
            exec_reason = exec_json.get("reason", {}) if isinstance(exec_json.get("reason"), dict) else {}
            exec_analysis = exec_reason.get("analysis", "") or exec_reason.get("construction", "")
            if exec_analysis:
                agent_ui.think(exec_analysis, header=False)
            
            for i, cmd in enumerate(cmds):
                agent_ui.command(cmd, i == len(cmds) - 1)

            # Run commands in sandbox
            out = sb.run(sandbox, cmds, category, exec_json.get("timeout", 30), workdir=self.target_dir)

            # Verify results
            v_start = time.time()
            
            v_res = self.verifier.verify(subtask=sub, commands=cmds, indicator=ind, output=out, hypothesis=plan.get("reason", {}).get("hypothesis", {}), facts=state.store)
            verif = v_res["verify_data"]
            if isinstance(verif, list):
                verif = verif[0]
            if not isinstance(verif, dict):
                verif = {}
                
            # Handle RAG
            verif_rag = verif.get("rag")
            if verif_rag and str(verif_rag).lower() not in ("none", "null", ""):
                v_time = time.time() - v_start
                agent_ui.verify(v_time)
                agent_ui.subtask(verif_rag, rag=True)
                rag_out = memory.execute(verif_rag, len(state.history))
                if rag_out:
                    state.history.append(rag_out)
                return "RAG completed!", {"commands": cmds, "success": ind}
            
            v_time = time.time() - v_start

            # Print verification status
            if verif.get("result") in ("pass", "success"):
                agent_ui.passed()
            else:
                agent_ui.failed()

            # Handle read
            verif_read = verif.get("read")
            if verif_read and str(verif_read).lower() not in ("none", "null", "", "false", "[]"):
                if isinstance(verif_read, list):
                    v_targets = [str(f).strip() for f in verif_read if str(f).strip()]
                elif "," in str(verif_read):
                    v_targets = [p.strip() for p in str(verif_read).split(",") if p.strip()]
                else:
                    v_targets = [str(verif_read).strip()]
                v_targets = [t for t in v_targets if t and t.lower() not in ("none", "null", "", "false")]
                if v_targets:
                    agent_ui.read(v_targets, last=False)
                    for t in v_targets:
                        read_out = self.read(t, sandbox)
                        verif.setdefault("knowledge", []).append(f"File {t}:\n{read_out[:2000]}")
                        state.absorb({f"Verified_File ({t})": read_out[:8000]})
                
            # Validate flag format
            flag = verif.get("flag", "")
            if flag and isinstance(flag, str):
                lower = flag.lower()
                skip = any(w in lower for w in ("dummy", "test", "fake", "local", "placeholder", "example"))
                
                if not skip:
                    expected = target.get("flag", "")
                    if expected:
                        # Check prefix
                        if "{" in expected:
                            prefix = expected.split("{")[0] + "{"
                            if not flag.startswith(prefix):
                                state.absorb({"Invalid": f"The flag '{flag}' is INVALID. It must start with '{prefix}'!"})
                                skip = True
                        
                        # Check placeholder
                        if not skip and flag == expected:
                            state.absorb({"Invalid": f"The flag '{flag}' is INVALID. You printed the placeholder instead of the real flag!"})
                            skip = True

                if not skip:
                    return flag, {"captured": flag}
                
            # Print knowledge
            know = verif.get("knowledge", [])
            
            if know:
                agent_ui.knowledge(know[0])
            else:
                agent_ui.evaluated(len(cmds))

            # Refine commands if failed
            if verif.get("result") == "fail":
                for tries in range(2):
                    agent_ui.refine(tries + 1, 2)
                    
                    retry = 0
                    while retry < 3:
                        extra_list = list(verif.get("knowledge", []))
                        v_reason = verif.get("reason", {})
                        if isinstance(v_reason, dict):
                            if v_reason.get("analysis"):
                                extra_list = [f"Analysis: {v_reason['analysis']}"] + extra_list
                            if v_reason.get("unmet"):
                                extra_list = [f"Unmet: {v_reason['unmet']}"] + extra_list
                        extra = "\n".join(extra_list)

                        data = {**state.tree.get("data", {}), **state.store}
                        discovered = (
                            "Findings:\n" + "\n".join(state.tree.get("findings", []))
                            + "\nData:\n" + (json.dumps(data, indent=2) if data else "{}")
                            + ("\nNotes:\n" + extra if extra else "")
                        )

                        # Request refinement
                        r_res = self.refiner.refine(
                            target=target_str, subtask=sub, failed=cmds, error=out, history=state.compressed,
                            discovered=discovered
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
                    r_abort = r_data.get("abort", False)
                    
                    # Handle read
                    r_read_files = r_data.get("read")
                    if r_read_files and str(r_read_files).lower() not in ("none", "null", "", "false", "[]"):
                        if isinstance(r_read_files, list):
                            ref_targets = [str(f).strip() for f in r_read_files if str(f).strip()]
                        elif "," in str(r_read_files):
                            ref_targets = [p.strip() for p in str(r_read_files).split(",") if p.strip()]
                        else:
                            ref_targets = [str(r_read_files).strip()]
                        ref_targets = [t for t in ref_targets if t and t.lower() not in ("none", "null", "", "false")]
                        if ref_targets:
                            agent_ui.read(ref_targets, last=False)
                            read_snippets = []
                            for t in ref_targets:
                                read_out = self.read(t, sandbox)
                                state.absorb({f"Inspection ({t})": read_out[:8000]})
                                read_snippets.append(f"File {t}:\n{read_out[:4000]}")

                            if not r_cmds and not r_abort:
                                more_discovered = discovered + "\n\nGround Truth Files Inspected:\n" + "\n".join(read_snippets)
                                r_res = self.refiner.refine(
                                    target=target_str, subtask=sub, failed=cmds, error=out,
                                    history=state.compressed, discovered=more_discovered
                                )
                                r_data = r_res.get("refine_data", {})
                                r_cmds = r_data.get("commands", [])
                                r_abort = r_data.get("abort", False)

                    r_reason = r_data.get("reason", {}) if isinstance(r_data.get("reason"), dict) else {}
                    r_analysis = r_reason.get("analysis", "") or r_reason.get("strategy", "")
                    if r_analysis:
                        agent_ui.think(r_analysis, header=False)
                    
                    if r_abort or not r_cmds:
                        if r_abort:
                            err_reason = r_reason.get("error") or "dead end detected"
                            agent_ui.abort(err_reason)
                            verif.setdefault("knowledge", []).append(f"Refiner aborted: {err_reason}.")
                        else:
                            agent_ui.empty()
                        break

                    for i, cmd in enumerate(r_cmds):
                        agent_ui.command(cmd, i == len(r_cmds) - 1)

                    # Execute refined commands
                    cmds = r_cmds
                    
                    out = sb.run(sandbox, cmds, category, r_data.get("timeout", exec_json.get("timeout", 30)), workdir=self.target_dir)

                    # Verify refined output
                    v_res = self.verifier.verify(subtask=sub, commands=cmds, indicator=ind, output=out, hypothesis=plan.get("reason", {}).get("hypothesis", {}), facts=state.store)
                    verif = v_res.get("verify_data", verif)
                    
                    if verif.get("result") in ("pass", "success"):
                        agent_ui.passed()
                    else:
                        agent_ui.failed()

                    # Handle read
                    r_read = verif.get("read")
                    if r_read and str(r_read).lower() not in ("none", "null", "", "false", "[]"):
                        if isinstance(r_read, list):
                            v_targets = [str(f).strip() for f in r_read if str(f).strip()]
                        elif "," in str(r_read):
                            v_targets = [p.strip() for p in str(r_read).split(",") if p.strip()]
                        else:
                            v_targets = [str(r_read).strip()]
                        v_targets = [t for t in v_targets if t and t.lower() not in ("none", "null", "", "false")]
                        if v_targets:
                            know_check = verif.get("knowledge", [])
                            agent_ui.read(v_targets, last=not bool(know_check))
                            for t in v_targets:
                                read_out = self.read(t, sandbox)
                                verif.setdefault("knowledge", []).append(f"File {t}:\n{read_out[:2000]}")
                                state.absorb({f"Verified_File ({t})": read_out[:8000]})
                    
                    know = verif.get("knowledge", [])
                    if know:
                        agent_ui.knowledge(know[0])
                    else:
                        agent_ui.evaluated(len(cmds))
                        
                    flag = verif.get("flag", "")
                    if flag and isinstance(flag, str):
                        lower = flag.lower()
                        skip = any(w in lower for w in ("dummy", "test", "fake", "local", "placeholder", "example"))
                        
                        if not skip:
                            expected = target.get("flag", "")
                            if expected:
                                # Check prefix
                                if "{" in expected:
                                    prefix = expected.split("{")[0] + "{"
                                    if not flag.startswith(prefix):
                                        state.absorb({"Invalid": f"The flag '{flag}' is INVALID. It must start with '{prefix}'!"})
                                        skip = True
                                
                                # Check placeholder
                                if not skip and flag == expected:
                                    state.absorb({"Invalid": f"The flag '{flag}' is INVALID. You printed the placeholder instead of the real flag!"})
                                    skip = True

                        if not skip:
                            return flag, {"captured": flag}

                    strat = r_data.get("reason", {}).get("strategy", "No strategy provided!")
                    verif.setdefault("knowledge", []).append(f"strategy: {strat}")
                    
                    if verif.get("result") in ("pass", "success"):
                        break

            if verif.get("result") == "fail":
                state.fails[tactic] = state.fails.get(tactic, 0) + 1
                self.fails += 1
            elif verif.get("result") in ("pass", "success", "partial"):
                state.fails[tactic] = 0
                self.fails = 0

        # Summarize step
        sum_start = time.time()
        
        step = {"subtask": sub, "commands": cmds, "output_summary": out[-8000:], "verification": verif}
        sum_res = self.summarizer.summarize(tree=state.tree, step=step)
        sum_data = sum_res["summary_data"]

        state.tree = sum_data.get("tree", state.tree)
        new_tree = sum_data.get("tree", {})
        new_data = new_tree.get("data", {})

        # Detect alerts
        alerts_d = state.diff(new_data)    
        alerts_t = state.guard()
        state.alerts = alerts_d + alerts_t

        # Absorb new knowledge
        state.absorb(new_data)   
        state.snap()

        sum_time = time.time() - sum_start
        agent_ui.summarize(sum_time)

        # Print alerts
        if state.alerts:
            agent_ui.contradict(len(state.alerts))
        else:
            agent_ui.clean()

        # Append to history
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
            state.compressed = "...[TRUNCATED]...\n" + state.compressed[-3000:]

        count = len(state.history)
        fails = max(state.fails.values()) if state.fails else 0
        
        # Reflect if stuck
        should_reflect = plan_reflect or r_abort or (self.fails >= 2) or (count in [2, 4, 6, 8] and fails >= 1) or (count > 8 and count % 3 == 0 and (fails >= 1 or self.fails >= 1))
        if should_reflect:
            used = str(int(3600 - (time_left or 3600)))
            ref_start = time.time()
            
            ref_res = self.reflector.review(history=state.history, facts=state.store, target=target_str, time_used=used, time_total="3600", tree=state.tree)
            
            ref_time = time.time() - ref_start
            review = ref_res["review_data"]
            adv = review.get("advice", "")
            tac = review.get("tactic", "")
            ref_read = review.get("read")
            if ref_read and str(ref_read).lower() not in ("none", "null", "", "false", "[]"):
                if isinstance(ref_read, list):
                    ref_targets = [str(f).strip() for f in ref_read if str(f).strip()]
                elif "," in str(ref_read):
                    ref_targets = [p.strip() for p in str(ref_read).split(",") if p.strip()]
                else:
                    ref_targets = [str(ref_read).strip()]
            else:
                ref_targets = []

            ref_targets = [t for t in ref_targets if t and t.lower() not in ("none", "null", "", "false")]
            has_read = bool(ref_targets)

            agent_ui.reflect(ref_time, read=ref_targets if has_read else None)

            if has_read:
                for t in ref_targets:
                    read_out = self.read(t, sandbox)
                    state.absorb({f"Inspection ({t})": read_out[:8000]})
                    state.alerts.append(f"[REFLECTOR READ] {t}:\n{read_out[:8000]}")
            
            if adv or tac:
                state.alerts.append(f"[ADVICE] {tac} - {adv}")
            
            self.fails = 0

        return sum_data.get("summary", ""), exec_json