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
from .core.triage import triage
from .core.flag import sniff, valid
from .core.loop import (
    read,
    rag,
    plan_loop,
    exec_loop,
    verif_loop,
    refine_loop,
    sum_loop,
    ref_loop
)


class Orchestrator:

    def __init__(self, config, container=None):
        p = config.get("planner", {})
        e = config.get("executor", {})
        v = config.get("verifier", {})
        r = config.get("refiner", {})
        s = config.get("summarizer", {})
        ref = config.get("reflector", {})

        # Initialize agents
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

        # Load playbook
        category = config.get("target", {}).get("category", "crypto")
        book_path = os.path.join("books", f"{category}.md")
        if not os.path.exists(book_path):
            book_path = os.path.join("books", "crypto.md")

        try:
            with open(book_path, "r", encoding="utf-8") as f:
                self.book = f.read()
        except:
            self.book = "Failed to load playbook!"

        # Tools list
        self.tools = (
            "nmap, rustscan, ffuf, gobuster, dirsearch, curl, wget, sqlmap, "
            "nc, socat, python3, php, perl, gdb, pwndbg, checksec, ldd, "
            "strace, ltrace, objdump, readelf, strings, xxd, ropper, ROPgadget, "
            "radare2, ghidra, angr, one_gadget, seccomp-tools, patchelf, upx, "
            "john, hashcat, binwalk, exiftool, steghide, linpeas, pwntools, "
            "pycryptodome, sympy, gmpy2, sagemath"
        )
        self.category = category
        self.workspace = os.path.join(os.getcwd(), 'workspace')
        self.target_dir = "/data"
        self.fails = 0

        state.init(self.book)
        memory.init()

    @property

    # Get history
    def history(self):
        return state.history

    # Handle read
    def read(self, target, sandbox, base_dir=None):
        base = base_dir or self.target_dir or "/data"
        return sb.read(sandbox, target, base_dir=base)

    # Handle sniff
    def sniff(self, out, target):
        return sniff(out, target)

    # Handle warning
    def warning(self, text):
        state.alerts.append(text)

    # Handle execute
    def execute(self, target, sandbox, time_left=None):
        req_dir = target.get("dir", "/data") if isinstance(target, dict) else "/data"
        self.target_dir, env_str = triage(self.workspace, req_dir)
        state.absorb({"Environment": env_str})

        plan, done, target_str, sub, action = plan_loop(
            self.planner, sandbox, target, state, memory,
            self.target_dir, self.tools, self.book, time_left
        )

        if done:
            return "Goal Achieved", plan

        if action == "read":
            return "Read completed!", {"commands": [], "success": "none"}

        if action == "rag":
            return "RAG completed!", {"commands": [], "success": "none"}

        if not plan:
            return "Step completed", {"commands": [], "success": "none"}

        plan_dict = plan.get("plan", {}) if isinstance(plan.get("plan"), dict) else {}
        plan_reflect = plan_dict.get("reflect", False) or plan.get("reflect", False)
        tool_hint = plan_dict.get("hint", "") or plan.get("hint", "") or plan_dict.get("tool", "") or plan.get("tool", "")
        tactic = plan.get("reason", {}).get("hypothesis", {}).get("tactic", "Unknown") if isinstance(plan.get("reason"), dict) else "Unknown"

        norm = state.normalize(sub)
        state.attempts[norm] = state.attempts.get(norm, 0) + 1
        r_abort = False

        if state.attempts[norm] > 3:
            agent_ui.breaker(state.attempts[norm])
            state.fails[tactic] = state.fails.get(tactic, 0) + 1
            self.fails += 1
            exec_json = {"commands": [], "success": "none"}
            verif = {"result": "fail", "knowledge": ["subtask repeated too many times!"]}
            out = "[SKIPPED]"
            cmds = []

        else:
            cmds, out, ind, fast_flag, exec_json = exec_loop(
                self.executor, sandbox, target_str, sub, tool_hint,
                state, memory, self.category, self.target_dir, target
            )
            if fast_flag:
                return fast_flag, {"captured": fast_flag}

            verif, flag, is_rag = verif_loop(
                self.verifier, sandbox, sub, cmds, ind, out,
                plan, state, memory, self.target_dir, target
            )
            if is_rag:
                return "RAG completed!", {"commands": cmds, "success": ind}

            if flag:
                return flag, {"captured": flag}

            if verif.get("result") == "fail":
                cmds, out, verif, fast_flag, r_abort = refine_loop(
                    self.refiner, self.verifier, sandbox, target_str, sub,
                    cmds, out, ind, plan, state, self.category,
                    self.target_dir, target, exec_json
                )
                if fast_flag:
                    return fast_flag, {"captured": fast_flag}

            if verif.get("result") == "fail":
                state.fails[tactic] = state.fails.get(tactic, 0) + 1
                self.fails += 1
            elif verif.get("result") in ("pass", "success", "partial"):
                state.fails[tactic] = 0
                self.fails = 0

        obs = sum_loop(
            self.summarizer, sub, cmds, out, verif, tactic, state
        )

        ref_loop(
            self.reflector, sandbox, state, memory, target_str,
            time_left, plan_reflect, r_abort, self.fails, self.target_dir
        )

        return obs, exec_json