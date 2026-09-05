import json
import time
import cli.agent as agent_ui
from . import sandbox as sb
from .flag import sniff, valid


def read(sandbox, target, base_dir=None, role=None):
    # Set base directory
    base = base_dir or "/data"
    if not target or str(target).lower() in ("none", "null", "", "false", "[]"):
        return {}

    # Format targets list
    if isinstance(target, list):
        targets = [str(f).strip() for f in target if str(f).strip()]
    elif "," in str(target):
        targets = [p.strip() for p in str(target).split(",") if p.strip()]
    else:
        targets = [str(target).strip()]

    # Filter empty targets
    targets = [t for t in targets if t and t.lower() not in ("none", "null", "", "false")]
    if not targets:
        return {}

    # Display read UI
    agent_ui.read(targets, last=False)
    out_map = {}

    # Read files from sandbox
    for t in targets:
        if any(b in t.lower() for b in ("venv", ".venv", "site-packages", "node_modules")):
            content = "Cannot read virtual environment or dependency packages."
        else:
            content = sb.read(sandbox, t, base_dir=base)
        out_map[t] = content

    return out_map


def rag(query, memory, state):
    # Check query
    if not query or str(query).lower() in ("none", "null", ""):
        return None

    # Display subtask UI
    agent_ui.subtask(query, rag=True)

    # Execute memory search
    rag_out = memory.execute(query, len(state.history))
    if rag_out:
        state.history.append(rag_out)

    return rag_out


def plan_loop(planner, sandbox, target, state, memory, target_dir, tools, book, time_left):
    # Get target description
    desc = target.get("description", "") if isinstance(target, dict) else str(target)

    # Format target string
    if isinstance(target, dict):
        clean = {k: v for k, v in target.items() if v}
        clean["dir"] = target_dir
        if "host" not in clean and "port" not in clean:
            clean["network"] = "This is a local challenge!"
        target_str = json.dumps(clean, indent=2)
    else:
        target_str = str(target)

    # Extract tree context
    next_str = " ".join(state.tree.get("next", [])) if isinstance(state.tree.get("next"), list) else str(state.tree.get("next", ""))
    findings = " ".join(state.tree.get("findings", [])) if isinstance(state.tree.get("findings"), list) else str(state.tree.get("findings", ""))
    findings += " " + str(state.tree.get("data", {}))

    # Query long-term memory
    memories = memory.query(desc, state.tree.get("stage", ""), findings, next_str)
    mem_str = "\n".join(memories) if memories else "No relevant memories found."

    # Call planner agent
    start = time.time()
    plan_res = planner.plan(
        history=state.history, fails=state.fails, target=target_str, tree=state.tree,
        tools=tools, playbook=book, memory=mem_str, time_left=time_left,
        facts=state.store, warns=state.alerts
    )
    plan = plan_res["plan_data"]
    elapsed = time.time() - start

    # Extract subtask
    plan_dict = plan.get("plan", {}) if isinstance(plan.get("plan"), dict) else {}
    sub = plan_dict.get("subtask", "") or plan.get("subtask", "")
    if not sub:
        sub = "Analyzing next step..."

    # Check finished status
    if plan_dict.get("finished", False) or plan.get("finished", False):
        agent_ui.plan(elapsed)
        return plan, True, target_str, sub, None

    # Display plan UI
    agent_ui.plan(elapsed)

    # Display thinking rationale
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

    # Handle read inspection
    plan_read = plan_dict.get("read") or plan.get("read")
    if plan_read and str(plan_read).lower() not in ("none", "null", "", "false", "[]"):
        read_key = "read_" + str(plan_read)
        state.attempts[read_key] = state.attempts.get(read_key, 0) + 1
        if state.attempts[read_key] <= 2:
            out_map = read(sandbox, plan_read, target_dir, role="Planner")
            if out_map:
                combined = []
                for t, text in out_map.items():
                    state.absorb({f"Inspection ({t})": text})
                    combined.append(f"[{t}]\n{text}")
                obs = "\n\n".join(combined)
                id = f"step_{len(state.history) + 1}"
                state.history.append({
                    "step_id": id,
                    "tactic": "Inspection",
                    "plan": f"Read {plan_read}",
                    "observation": obs[:8000],
                    "result": "pass",
                    "raw": obs[:15000]
                })
                return None, False, target_str, sub, "read"

    # Handle RAG search
    plan_rag = plan_dict.get("rag")
    if plan_rag and str(plan_rag).lower() not in ("none", "null", ""):
        rag(plan_rag, memory, state)
        return None, False, target_str, sub, "rag"
    else:
        agent_ui.subtask(sub, rag=False)

    return plan, False, target_str, sub, None


def exec_loop(executor, sandbox, target_str, sub, tool_hint, state, memory, category, target_dir, target):
    # Prepare facts and state
    data = {**state.tree.get("data", {}), **state.store}
    cmds = []
    out = ""
    obs = ""
    prev = ""
    stagnant = 0
    turn = 0
    cap = 5
    exec_json = {"commands": [], "success": "none"}

    # Start ReAct loop
    while turn < cap:
        agent_ui.execute()

        # Call executor agent
        res = executor.execute(
            target=target_str, subtask=sub, tool_hint=tool_hint,
            history=state.compressed, facts=data, tree=state.tree, obs=obs
        )
        exec_json = res.get("exec_data") or res.get("action_data", {})
        cmds = exec_json.get("commands", [])
        ind = exec_json.get("success", "")

        # Handle RAG search
        exec_rag = exec_json.get("rag")
        if exec_rag and str(exec_rag).lower() not in ("none", "null", ""):
            rag(exec_rag, memory, state)

        # Display action UI
        reason_dict = exec_json.get("reason", {}) if isinstance(exec_json.get("reason"), dict) else {}
        action = reason_dict.get("action", "") or exec_json.get("action", "")
        if action:
            agent_ui.action(action)

        # Check empty commands
        if not cmds:
            agent_ui.empty()
            break

        # Display commands UI
        for i, cmd in enumerate(cmds):
            agent_ui.command(cmd, i == len(cmds) - 1)

        # Check stagnant commands
        cur_str = json.dumps(cmds)
        if cur_str == prev:
            stagnant += 1
            if stagnant >= 2:
                agent_ui.stagnant(stagnant)
                break
        else:
            stagnant = 0
        prev = cur_str

        # Run commands in sandbox
        timeout = exec_json.get("timeout", 60)
        out = sb.run(sandbox, cmds, category, timeout, workdir=target_dir)

        # Sniff fast flag
        fast_flag = sniff(out, target)
        if fast_flag:
            agent_ui.passed()
            return cmds, out, ind, fast_flag, exec_json

        # Check done status
        if exec_json.get("done", True):
            break

        obs = out[-3000:] if out.strip() else "[Command executed with empty output / no stdout]"
        turn += 1

    return cmds, out, ind, None, exec_json


def verif_loop(verifier, sandbox, sub, cmds, ind, out, plan, state, memory, target_dir, target):
    # Call verifier agent
    v_start = time.time()
    hypothesis = plan.get("reason", {}).get("hypothesis", {}) if isinstance(plan.get("reason"), dict) else {}
    v_res = verifier.verify(
        subtask=sub, commands=cmds, indicator=ind,
        output=out, hypothesis=hypothesis, facts=state.store
    )
    verif = v_res["verify_data"]
    if isinstance(verif, list):
        verif = verif[0]
    if not isinstance(verif, dict):
        verif = {}

    # Handle RAG query
    v_rag = verif.get("rag")
    if v_rag and str(v_rag).lower() not in ("none", "null", ""):
        v_time = time.time() - v_start
        agent_ui.verify(v_time)
        rag(v_rag, memory, state)
        return verif, None, True

    # Display verification result
    v_time = time.time() - v_start
    if verif.get("result") in ("pass", "success"):
        agent_ui.passed()
    else:
        agent_ui.failed()

    # Handle read verification
    v_read = verif.get("read")
    if v_read and str(v_read).lower() not in ("none", "null", "", "false", "[]"):
        out_map = read(sandbox, v_read, target_dir, role="Verifier")
        for t, text in out_map.items():
            verif.setdefault("knowledge", []).append(f"File {t}:\n{text[:2000]}")
            state.absorb({f"Verified_File ({t})": text[:8000]})

    # Check flag validity
    flag = verif.get("flag", "")
    if flag and valid(flag, target, state):
        return verif, flag, False

    # Display evaluated knowledge
    know = verif.get("knowledge", [])
    if know:
        agent_ui.knowledge(know[0])
    else:
        agent_ui.evaluated(len(cmds))

    return verif, None, False


def refine_loop(refiner, verifier, sandbox, target_str, sub, cmds, out, ind, plan, state, category, target_dir, target, exec_json):
    r_obs = None
    r_turn = 0
    r_cap = 5
    r_abort = False

    # Start refinement loop
    while r_turn < r_cap:
        agent_ui.refine(r_turn + 1, r_cap)

        # Prepare discovered context
        extra_list = list(verif.get("knowledge", [])) if "verif" in locals() else []
        data = {**state.tree.get("data", {}), **state.store}
        slim_data = {
            k: (str(v)[:500] + "...[truncated]") if len(str(v)) > 500 else v
            for k, v in data.items()
        }
        discovered = (
            "Findings:\n" + "\n".join(state.tree.get("findings", []))
            + "\nData:\n" + (json.dumps(slim_data, indent=2) if slim_data else "{}")
            + ("\nNotes:\n" + "\n".join(extra_list) if extra_list else "")
        )

        # Call refiner with retry
        retry = 0
        while retry < 3:
            r_res = refiner.refine(
                target=target_str, subtask=sub, failed=cmds, error=out,
                history=state.compressed, discovered=discovered, obs=r_obs
            )
            raw = r_res.get("raw", "")
            if "429" in raw:
                agent_ui.retry(retry + 1)
                retry += 1
                time.sleep(2 * retry)
                continue
            break

        # Extract refinement data
        r_data = r_res.get("refine_data", {})
        r_cmds = r_data.get("commands", [])
        r_abort = r_data.get("abort", False)
        r_done = r_data.get("done", True)

        # Handle ground truth inspection
        r_read = r_data.get("read")
        if r_read and str(r_read).lower() not in ("none", "null", "", "false", "[]"):
            out_map = read(sandbox, r_read, target_dir, role="Refiner")
            if out_map:
                snippets = []
                for t, text in out_map.items():
                    state.absorb({f"Inspection ({t})": text[:8000]})
                    snippets.append(f"File {t}:\n{text[:4000]}")
                if not r_cmds and not r_abort:
                    more_discovered = discovered + "\n\nGround Truth Files Inspected:\n" + "\n".join(snippets)
                    r_res = refiner.refine(
                        target=target_str, subtask=sub, failed=cmds, error=out,
                        history=state.compressed, discovered=more_discovered, obs=r_obs
                    )
                    r_data = r_res.get("refine_data", {})
                    r_cmds = r_data.get("commands", [])
                    r_abort = r_data.get("abort", False)
                    r_done = r_data.get("done", True)

        # Display thinking analysis
        r_reason = r_data.get("reason", {}) if isinstance(r_data.get("reason"), dict) else {}
        r_analysis = r_reason.get("analysis", "") or r_reason.get("strategy", "")
        if r_analysis:
            agent_ui.think(r_analysis)

        # Check abort condition
        if r_abort or not r_cmds:
            if r_abort:
                err_reason = r_reason.get("error") or "dead end detected"
                agent_ui.abort(err_reason)
            else:
                agent_ui.empty()
            break

        # Display refined commands
        for i, cmd in enumerate(r_cmds):
            agent_ui.command(cmd, i == len(r_cmds) - 1)

        # Execute refined commands
        cmds = r_cmds
        timeout = r_data.get("timeout", exec_json.get("timeout", 30))
        out = sb.run(sandbox, cmds, category, timeout, workdir=target_dir)

        # Sniff fast flag
        fast_flag = sniff(out, target)
        if fast_flag:
            agent_ui.passed()
            return cmds, out, {"result": "pass"}, fast_flag, False

        # Verify refined execution
        hypothesis = plan.get("reason", {}).get("hypothesis", {}) if isinstance(plan.get("reason"), dict) else {}
        v_res = verifier.verify(
            subtask=sub, commands=cmds, indicator=ind,
            output=out, hypothesis=hypothesis, facts=state.store
        )
        verif = v_res.get("verify_data", {})

        # Display verification verdict
        if verif.get("result") in ("pass", "success"):
            agent_ui.passed()
        else:
            agent_ui.failed()

        # Handle read verification
        vr_read = verif.get("read")
        if vr_read and str(vr_read).lower() not in ("none", "null", "", "false", "[]"):
            out_map = read(sandbox, vr_read, target_dir, role="Verifier")
            for t, text in out_map.items():
                verif.setdefault("knowledge", []).append(f"File {t}:\n{text[:2000]}")
                state.absorb({f"Verified file ({t})": text[:8000]})

        # Check flag validity
        flag = verif.get("flag", "")
        if flag and valid(flag, target, state):
            return cmds, out, verif, flag, False

        # Record refinement strategy
        strat = r_data.get("reason", {}).get("strategy", "No strategy provided!")
        verif.setdefault("knowledge", []).append(f"strategy: {strat}")

        # Break if passed
        if verif.get("result") in ("pass", "success"):
            break

        r_obs = out[-3000:] if out.strip() else "[Command produced empty output]"
        r_turn += 1

    return cmds, out, locals().get("verif", {"result": "fail"}), None, r_abort


def sum_loop(summarizer, sub, cmds, out, verif, tactic, state):
    # Deduplicate output lines
    t0 = time.time()
    t_out = out if not out.startswith("[TIMEOUT]") else "[TIMEOUT] Command timed out — no output produced. Treat this step as failed.\n" + out
    lines = t_out.splitlines()
    deduped = []
    prev_line = None
    rep = 0

    for l in lines:
        if l == prev_line:
            rep += 1
        else:
            if rep > 0:
                deduped.append(f"... [repeated {rep} more times] ...")
            deduped.append(l)
            prev_line = l
            rep = 0
    if rep > 0:
        deduped.append(f"... [repeated {rep} more times] ...")
    clean_out = "\n".join(deduped)

    # Format step payload
    step = {
        "subtask": sub,
        "commands": cmds,
        "output_summary": clean_out[-3000:],
        "verification": verif
    }

    # Call summarizer agent
    res = summarizer.summarize(tree=state.tree, step=step)
    sum_data = res["summary_data"]

    # Check contradictions and guard
    new_tree = sum_data.get("tree", {})
    new_data = new_tree.get("data", {})

    alerts_d = state.diff(new_data)
    alerts_t = state.guard()
    state.alerts = alerts_d + alerts_t

    # Merge state and attack tree
    state.merge(new_tree)
    state.update(task=sub, status=verif.get("result", "unknown"), data=new_data)
    state.snap()
    state.prune_store()

    # Display summarize UI
    agent_ui.summarize(time.time() - t0)
    if state.alerts:
        agent_ui.contradict(len(state.alerts))
    else:
        agent_ui.clean()

    # Append step history
    id = f"step_{len(state.history) + 1}"
    state.history.append({
        "step_id": id,
        "tactic": tactic,
        "plan": sub,
        "observation": sum_data.get("summary", ""),
        "result": verif.get("result", "unknown"),
        "raw": out[-3000:]
    })

    # Compress history observation
    obs = sum_data.get("summary", "")
    state.compressed += f"\n[{id}] {obs}"
    if len(state.compressed) > 3000:
        state.compressed = "...[TRUNCATED]...\n" + state.compressed[-3000:]

    return obs


def ref_loop(reflector, sandbox, state, memory, target_str, time_left, plan_reflect, r_abort, fails, target_dir):
    # Check reflection triggers
    count = len(state.history)
    max_fails = max(state.fails.values()) if state.fails else 0
    reflect = plan_reflect or (r_abort and count > 3) or (fails >= 5) or (count > 8 and count % 8 == 0 and max_fails >= 3)
    if not reflect:
        return False

    # Call reflector agent
    used = str(int(3600 - (time_left or 3600)))
    ref_start = time.time()
    ref_res = reflector.review(
        history=state.history, facts=state.slim_store(),
        target=target_str, time_used=used, time_total="3600",
        tree=state.tree
    )
    ref_time = time.time() - ref_start
    review = ref_res["review_data"]
    adv = review.get("advice", "")
    tac = review.get("tactic", "")

    # Handle ground truth inspection
    ref_read = review.get("read")
    if ref_read and str(ref_read).lower() not in ("none", "null", "", "false", "[]"):
        out_map = read(sandbox, ref_read, target_dir, role="Reflector")
        has_read = bool(out_map)
        agent_ui.reflect(ref_time, read=list(out_map.keys()) if has_read else None)
        for t, text in out_map.items():
            state.absorb({f"Inspection ({t})": text[:8000]})
            state.alerts.append(f"[REFLECTOR READ] {t}:\n{text[:8000]}")
    else:
        agent_ui.reflect(ref_time, read=None)

    # Handle RAG search
    ref_rag = review.get("rag")
    if ref_rag and str(ref_rag).lower() not in ("none", "null", ""):
        rag(ref_rag, memory, state)

    # Append advice alert
    if adv or tac:
        state.alerts.append(f"[ADVICE] {tac} - {adv}")

    return True