import json
import hashlib
import re
import os
import concurrent.futures

import chromadb

from .planner.engine import PlannerAgent
from .executor.engine import ExecutorAgent
from .verifier.engine import VerifierAgent
from .refiner.engine import RefinerAgent
from .summarizer.engine import SummarizerAgent
from .reflector.engine import ReflectorAgent
from rag.github import search_github
from rag.firecrawl import scrape


class Orchestrator:
    def __init__(self, config, container=None):
        # Initialize Vector DB
        db_path = os.path.join(os.getcwd(), "db")
        os.makedirs(db_path, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.memory = self.chroma_client.get_or_create_collection(
            name="memory"
        )
        self.knowledge = self.chroma_client.get_or_create_collection(
            name="knowledge"
        )

        # Load agent-specific configs
        p_cfg = config.get("planner", {})
        e_cfg = config.get("executor", {})
        v_cfg = config.get("verifier", {})
        r_cfg = config.get("refiner", {})
        s_cfg = config.get("summarizer", {})
        ref_cfg = config.get("reflector", {})

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

        self.reflector = ReflectorAgent(
            model=ref_cfg.get("model"),
            local=ref_cfg.get("local", False),
            temperature=ref_cfg.get("temperature", 0.7),
            top=ref_cfg.get("top", 1.0),
            sample=ref_cfg.get("sample", False),
            tokens=ref_cfg.get("tokens", 4096)
        )

        # Load playbook
        try:
            with open("playbooks.json", "r") as f:
                self.playbooks = json.load(f)
        except:
            self.playbooks = {}

        category = config.get("target", {}).get("category", "default")

        self.playbook = {
            "category": category,
            **self.playbooks.get("playbooks", {}).get(
                category,
                self.playbooks.get("playbooks", {}).get("default", {})
            )
        }

        # Initialize state variables
        self.history = []
        self.compressed_history = ""

        # Seed attack tree
        initial_tactics = self.playbook.get(
            "tactics",
            ["Reconnaissance"]
        )
        initial_stage = (
            initial_tactics[0]
            if initial_tactics
            else "Reconnaissance"
        )

        self.tree = {
            "stage": initial_stage,
            "done": [],
            "findings": ["Initial target mapped"],
            "next": self.playbook.get("procedure", [])[:2],
            "failed": []
        }

        self.tools = self.playbooks.get(
            "tools",
            config.get(
                "tools",
                "nmap, gobuster, curl, nc, python3, gdb"
            )
        )

        self.hashes = set()
        self.fails = {}
        self.attempts = {}
        self.store = {}
        self.alerts = []
        self.locked = set()
        self.seen = {}
        self.snap_done = []

    def normalize(self, text: str) -> str:
        norm = re.sub(r"\s+", " ", text)
        return norm.strip().lower()

    def absorb(self, data: dict):
        if not isinstance(data, dict):
            return
        for k, v in data.items():
            if str(v).startswith("OVERRIDE:"):
                
                # Explicit override
                real = v[len("OVERRIDE:"):]
                self.store[k] = real
                self.locked.discard(k)
                self.seen[k] = 1
            elif k not in self.store or self.store[k] is None:
                self.store[k] = v
                self.seen[k] = 1
            elif self.store[k] == v:

                # Same value confirmed again
                count = self.seen.get(k, 1) + 1
                self.seen[k] = count
                if count >= 2:
                    self.locked.add(k)

    def diff(self, data: dict) -> list:
        out = []
        if not isinstance(data, dict):
            return out
        for k, v in data.items():
            if str(v).startswith("OVERRIDE:"):
                continue 
            old = self.store.get(k)
            if old is None or old == v:
                continue
            level = "CRITICAL" if k in self.locked else "WARNING"
            out.append(
                f"[{level}] CONTRADICTION: '{k}' was '{old}', "
                f"now '{v}'. Session-state may have changed!"
            )
        return out

    def guard(self, tree: dict) -> list:
        out = []
        done = tree.get("done", [])
        if isinstance(done, list) and self.snap_done:
            missing = set(self.snap_done) - set(done)
            if missing:
                out.append(
                    f"[WARNING] DONE LIST SHRANK: {len(missing)} item(s) "
                    f"vanished: {list(missing)[:3]}. "
                    "Likely a new server connection reset state!"
                )
        return out

    def snap(self, tree: dict):
        done = tree.get("done", [])
        if isinstance(done, list):
            self.snap_done = list(set(self.snap_done) | set(done))

    def execute(self, target, sandbox, time_left=None):
        print("\n╭─ PLANNER ────────────────────────────────────────────╮")
        print("│ Thinking...")
        print("╰──────────────────────────────────────────────────────╯")

        category = (
            target.get("category", "")
            if isinstance(target, dict)
            else ""
        )

        target = (
            json.dumps(target, indent=2)
            if isinstance(target, dict)
            else target
        )

        tree = self.tree

        # Memory retrieval
        memories = []

        try:
            target_desc = (
                target.get("description", "")
                if isinstance(target, dict)
                else str(target)
            )

            # Extract current stage and next tasks
            current_stage = self.tree.get("stage", "")

            next_tasks = self.tree.get("next", [])
            if isinstance(next_tasks, list):
                next_tasks_str = " ".join(next_tasks)
            else:
                next_tasks_str = str(next_tasks)

            # Extract findings
            findings = self.tree.get("findings", [])
            if isinstance(findings, list):
                findings_str = " ".join(findings)
            else:
                findings_str = str(findings)

            extracted = self.tree.get("data", {})
            findings_str += " " + str(extracted)

            # Combine query
            parts = [
                target_desc[:200],
                current_stage,
                findings_str[:150],
                next_tasks_str[:200]
            ]
            query = (
                " ".join(filter(None, parts))
                or "vulnerability exploitation"
            )

            # Query memory collection
            mem_res = self.memory.query(
                query_texts=[query],
                n_results=3
            )

            if (
                mem_res
                and "documents" in mem_res
                and mem_res["documents"]
                and mem_res["documents"][0]
            ):
                for doc in mem_res["documents"][0]:
                    memories.append(
                        f"[PAST_MEMORY] {doc}"
                    )

            # Query knowledge collection
            know_res = self.knowledge.query(
                query_texts=[query],
                n_results=50
            )

            if (
                know_res
                and "documents" in know_res
                and know_res["documents"]
                and know_res["documents"][0]
            ):
                for doc, dist in zip(
                    know_res["documents"][0],
                    know_res["distances"][0]
                ):
                    if dist < 1.5:  # Similarity threshold
                        memories.append(
                            f"[EXTERNAL_KNOWLEDGE] {doc}"
                        )

        except Exception as e:
            print(f"  ✗ Memory DB : {e}")

        memory = (
            "\n".join(memories)
            if memories
            else "No relevant memories found."
        )

        print(
            f"  ✓ Memory    : "
            f"{len(memories)} chunks injected"
        )

        last_raw = ""
        if self.history:
            last_raw = self.history[-1].get("raw", "")

        plan_res = self.planner.plan(
            history=self.history,
            fails=self.fails,
            target=target,
            tree=tree,
            tools=self.tools,
            playbook=self.playbook,
            memory=memory,
            time_left=time_left,
            facts=self.store,
            warns=self.alerts
        )

        plan_data = plan_res["plan_data"]

        if plan_data.get("plan", {}).get("finished", False):
            print("  ✓ Planner   : goal achieved")
            return "Goal Achieved", plan_data

        subtask = plan_data.get("plan", {}).get("subtask", "")
        tool_hint = plan_data.get("plan", {}).get("tool", "")

        tactic = plan_data.get(
            "reason",
            {}
        ).get(
            "hypothesis",
            {}
        ).get(
            "tactic",
            "Unknown"
        )

        # RAG
        if tactic == "Retrieval-Augmented-Generation":
            print(
                "\n╭─ RAG ─────────────────────────────────────────────────╮"
            )
            print("│ Activating GitHub + Web Scraping")
            print(f"│ Query: {subtask}")
            print(
                "╰──────────────────────────────────────────────────────╯"
            )

            try:
                from rag.duckduckgo import search_web

                def github():
                    gh_res = search_github(subtask)
                    issues = gh_res.get("github_issues", [])

                    total_gh_chunks = 0
                    preview = ""

                    if not issues:
                        return 0, "No GH issues found."

                    def scrape_store(issue):
                        url = issue.get("url")
                        md_text, err = scrape(url)

                        if md_text:
                            chunks = [
                                md_text[i:i + 2000]
                                for i in range(
                                    0,
                                    len(md_text),
                                    2000
                                )
                            ]

                            ids = [
                                f"know_{hashlib.md5((url + str(i)).encode()).hexdigest()}"
                                for i in range(len(chunks))
                            ]

                            return chunks, ids, md_text

                        return [], [], ""

                    # Run Firecrawl for Github issues in parallel
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=5
                    ) as ex:
                        results = list(
                            ex.map(
                                scrape_store,
                                issues
                            )
                        )

                    for chunks, ids, md_text in results:
                        if chunks:
                            self.knowledge.add(
                                documents=chunks,
                                ids=ids
                            )

                            total_gh_chunks += len(chunks)

                            if not preview:
                                preview = md_text[:1500]

                    return total_gh_chunks, preview

                def task_web():
                    res = search_web(
                        subtask,
                        max_results=5
                    )

                    if "docs" in res and res["docs"]:
                        self.knowledge.add(
                            documents=res["docs"],
                            ids=res["ids"]
                        )

                        return (
                            res["total_chunks"],
                            res["preview"]
                        )

                    return (
                        0,
                        res.get(
                            "error",
                            "No web results."
                        )
                    )

                # Run both Github and Web searches
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=2
                ) as main_executor:
                    future_gh = main_executor.submit(github)
                    future_web = main_executor.submit(task_web)

                    gh_chunks, gh_preview = future_gh.result()
                    web_chunks, web_preview = future_web.result()

                knowledge_gathered = (
                    f"Scraped GitHub ({gh_chunks} chunks) "
                    f"and Web ({web_chunks} chunks). "
                    f"Total: {gh_chunks + web_chunks} chunks "
                    "saved to DB."
                )

                print(f"  ✓ RAG       : {knowledge_gathered}")

                step_id = f"step_{len(self.history) + 1}"

                self.history.append(
                    {
                        "step_id": step_id,
                        "tactic": tactic,
                        "plan": subtask,
                        "observation": (
                            f"[Knowledge Gathered] "
                            f"{knowledge_gathered} "
                            f"Preview: "
                            f"{gh_preview or web_preview}"
                        ),
                        "result": "success"
                    }
                )

                # Skip executor, sandbox, verifier
                return (
                    "Knowledge Retrieval Completed",
                    {
                        "commands": [],
                        "success": "none"
                    }
                )

            except Exception as e:
                print(f"  ✗ RAG       : {e}")

        norm_subtask = self.normalize(subtask)

        self.attempts[norm_subtask] = (
            self.attempts.get(norm_subtask, 0) + 1
        )

        if self.attempts[norm_subtask] > 3:
            print(
                f"  ⚠ Guard     : "
                f"subtask repeated "
                f"{self.attempts[norm_subtask]}x — skipped"
            )

            exec_json = {
                "commands": [],
                "success": "none"
            }

            verify_data = {
                "result": "fail",
                "knowledge": [
                    "Circuit breaker: "
                    "subtask repeated too many times."
                ]
            }

            tactic = plan_data.get(
                "reason",
                {}
            ).get(
                "hypothesis",
                {}
            ).get(
                "tactic",
                "Unknown"
            )

            self.fails[tactic] = (
                self.fails.get(tactic, 0) + 1
            )

            output = "[SKIPPED - circuit breaker]"
            commands = []

        else:
            print("\n╭─ EXECUTOR ───────────────────────────────────────────╮")
            print(f"│ Translating: {subtask}")
            print("╰──────────────────────────────────────────────────────╯")

            exec_result = self.executor.execute_plan(
                target=target,
                subtask=subtask,
                tool_hint=tool_hint,
                history=self.history
            )

            exec_json = exec_result["exec_data"]
            commands = exec_json.get("commands", [])
            indicator = exec_json.get("success", "")

            print(
                f"  → Sandbox   : "
                f"running {len(commands)} command(s)..."
            )

            output = ""

            for cmd in commands:

                raw_timeout = exec_json.get("timeout", 30)

                try:
                    max_timeout = 3600 if category == "crypto" else 120
                    cmd_timeout = min(
                        int(raw_timeout),
                        max_timeout
                    )
                except:
                    cmd_timeout = 30

                try:
                    wrapped_cmd = [
                        "timeout",
                        "--preserve-status",
                        "-k",
                        "5",
                        str(cmd_timeout),
                        "/bin/bash",
                        "-c",
                        cmd
                    ]

                    result = sandbox.exec_run(
                        wrapped_cmd,
                        stdout=True,
                        stderr=True
                    )

                    out = result.output.decode(
                        "utf-8",
                        errors="ignore"
                    )

                    if result.exit_code == 124:
                        out = (
                            f"[TIMEOUT] Command exceeded "
                            f"{cmd_timeout}s. Partial output:\n"
                            f"{out}"
                        )

                except Exception as e:
                    out = (
                        f"[TIMEOUT] Command execution failed: "
                        f"{e}"
                    )

                output += (
                    f"--- Output of '{cmd}' ---\n"
                    f"{out}\n"
                )

            import re
            FLAG = re.compile(r"[A-Za-z0-9_]{0,10}CTF\{[^}\s]{1,200}\}")
            flag_match = FLAG.search(output)
            if flag_match:
                print(f"\n╭─ ORCHESTRATOR ───────────────────────────────────────╮")
                print("│ Flag Detected in Output!")
                print("╰──────────────────────────────────────────────────────╯")
                return flag_match.group(0), {"flag_captured": flag_match.group(0)}

            print("\n╭─ VERIFIER ───────────────────────────────────────────╮")
            print("│ Evaluating results...")
            print("╰──────────────────────────────────────────────────────╯")

            verify_res = self.verifier.verify(
                subtask=subtask,
                commands=commands,
                indicator=indicator,
                output=output,
                hypothesis=plan_data.get(
                    "reason",
                    {}
                ).get(
                    "hypothesis",
                    {}
                ),
                facts=self.store
            )

            verify_data = verify_res["verify_data"]

            refine_tries = 0

            while (
                verify_data.get("result") == "fail"
                and refine_tries < 2
            ):
                print(
                    f"\n╭─ REFINER ────────────────────────────────────────────╮"
                )
                print(
                    f"│ Strategy failed — retry "
                    f"{refine_tries + 1}/2"
                )
                print(
                    "╰──────────────────────────────────────────────────────╯"
                )

                retry = 0
                while retry < 3:
                    refine_res = self.refiner.refine(
                        target=target,
                        subtask=subtask,
                        failed=commands,
                        error=output,
                        history=self.compressed_history,
                        discovered="Findings:\n" + "\n".join(
                            self.tree.get("findings", [])
                        ) + "\nExtracted Data:\n" + str(
                            self.tree.get(
                                "data",
                                {}
                            )
                        )
                    )
                    raw = refine_res.get("raw", "")
                    if "API Error" in raw or "API Exception" in raw:
                        print(f"  ↻ REFINER : Transient API error, retrying ({retry+1}/3)...")
                        retry += 1
                        import time
                        time.sleep(2 * retry)
                        continue
                    break

                refine_data = refine_res.get(
                    "refine_data",
                    {}
                )

                refined_commands = refine_data.get(
                    "commands",
                    []
                )

                if not refined_commands:
                    verify_data.setdefault(
                        "knowledge",
                        []
                    ).append(
                        "Refinement failed to produce "
                        "new commands."
                    )
                    break

                print(
                    f"  → Sandbox   : "
                    f"running {len(refined_commands)} "
                    f"refined command(s)..."
                )

                commands = refined_commands
                output = ""

                for cmd in commands:

                    raw_timeout = refine_data.get(
                        "timeout",
                        exec_json.get("timeout", 30)
                    )

                    try:
                        max_timeout = 3600 if category == "crypto" else 120
                        cmd_timeout = min(
                            int(raw_timeout),
                            max_timeout
                        )
                    except:
                        cmd_timeout = 30

                    try:
                        wrapped_cmd = [
                            "timeout",
                            "--preserve-status",
                            "-k",
                            "5",
                            str(cmd_timeout),
                            "/bin/bash",
                            "-c",
                            cmd
                        ]

                        result = sandbox.exec_run(
                            wrapped_cmd,
                            stdout=True,
                            stderr=True
                        )

                        out = result.output.decode(
                            "utf-8",
                            errors="ignore"
                        )

                        if result.exit_code == 124:
                            out = (
                                f"[TIMEOUT] Command exceeded "
                                f"{cmd_timeout}s. "
                                f"Partial output:\n{out}"
                            )

                    except Exception as e:
                        out = (
                            f"[TIMEOUT] Command execution "
                            f"failed: {e}"
                        )

                    output += (
                        f"--- Output of '{cmd}' ---\n"
                        f"{out}\n"
                    )

                print(
                    "  → Verifier  : "
                    "evaluating refined results..."
                )

                verify_res = self.verifier.verify(
                    subtask=subtask,
                    commands=commands,
                    indicator=indicator,
                    output=output,
                    hypothesis=plan_data.get(
                        "reason",
                        {}
                    ).get(
                        "hypothesis",
                        {}
                    ),
                    facts=self.store
                )

                verify_data = verify_res.get(
                    "verify_data",
                    verify_data
                )

                strategy = refine_data.get(
                    "reason",
                    {}
                ).get(
                    "strategy",
                    "No strategy provided."
                )

                verify_data.setdefault(
                    "knowledge",
                    []
                ).append(
                    f"Refinement applied: {strategy}"
                )

                refine_tries += 1

            tactic = plan_data.get(
                "reason",
                {}
            ).get(
                "hypothesis",
                {}
            ).get(
                "tactic",
                "Unknown"
            )

            if verify_data.get("result") == "fail":
                self.fails[tactic] = (
                    self.fails.get(tactic, 0) + 1
                )
            else:
                self.fails[tactic] = 0

        step = {
            "subtask": subtask,
            "commands": commands,
            "output_summary": output[-8000:],
            "verification": verify_data
        }

        print(
            "\n╭─ SUMMARIZER ──────────────────────────────────────────╮"
        )
        print("│ Updating Attack Tree and History...")
        print(
            "╰──────────────────────────────────────────────────────╯"
        )

        summary_res = self.summarizer.summarize(
            tree=tree,
            step=step
        )

        summary_data = summary_res["summary_data"]

        self.tree = summary_data.get(
            "tree",
            self.tree
        )

        new_tree = summary_data.get("tree", {})
        new_data = new_tree.get("data", {})

        data_alerts = self.diff(new_data)    
        tree_alerts = self.guard(new_tree)  
        self.alerts = data_alerts + tree_alerts

        self.absorb(new_data)   
        self.snap(new_tree)    

        if self.alerts:
            print(
                f"  ⚠ Detector  : "
                f"{len(self.alerts)} contradiction(s) detected"
            )
            for alert in self.alerts:
                print(f"    → {alert}")
        else:
            print("  ✓ Detector  : no contradictions")

        step_id = f"step_{len(self.history) + 1}"

        self.history.append(
            {
                "step_id": step_id,
                "tactic": plan_data.get(
                    "reason",
                    {}
                ).get(
                    "hypothesis",
                    {}
                ).get(
                    "tactic",
                    "Unknown"
                ),
                "plan": subtask,
                "observation": summary_data.get(
                    "summary",
                    ""
                ),
                "result": verify_data.get(
                    "result",
                    "unknown"
                ),
                "raw": output[:3000]
            }
        )

        new_obs = summary_data.get(
            "summary",
            ""
        )

        self.compressed_history += (
            f"\n[{step_id}] {new_obs}"
        )

        if len(self.compressed_history) > 3000:
            self.compressed_history = (
                "...[truncated]\n"
                + self.compressed_history[-3000:]
            )

        step_count = len(self.history)
        consecutive_fails = max(self.fails.values()) if self.fails else 0
        if step_count in [3, 6, 9] and consecutive_fails >= 2:
            time_used = str(int(3600 - (time_left or 3600)))
            time_total = "3600"
            
            print("\n╭─ REFLECTOR ───────────────────────────────────────────╮")
            print("│ Analyzing stuck state and replanning...")
            print("╰──────────────────────────────────────────────────────╯")
            
            ref_res = self.reflector.review(
                history=self.history,
                facts=self.store,
                target=target,
                time_used=time_used,
                time_total=time_total
            )
            review_data = ref_res["review_data"]
            advice = review_data.get("advice", "")
            tactic = review_data.get("tactic", "")
            if advice or tactic:
                self.alerts.append(f"[REFLECTOR ADVICE] {tactic} - {advice}")

        return (
            summary_data.get("summary", ""),
            exec_json
        )