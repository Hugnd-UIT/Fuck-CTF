import json
import time
import cli.agent as agent_ui
from . import sandbox as sb


def parse_targets(target):
    if not target or str(target).lower() in ("none", "null", "", "false", "[]"):
        return []
    if isinstance(target, list):
        items = [str(f).strip() for f in target if str(f).strip()]
    elif "," in str(target):
        items = [p.strip() for p in str(target).split(",") if p.strip()]
    else:
        items = [str(target).strip()]
    return [t for t in items if t and t.lower() not in ("none", "null", "", "false", "[]")]


def is_inspected(t, store):
    t_norm = t.strip("'\"").replace("\\", "/").rstrip("/")
    t_name = t_norm.split("/")[-1]
    if t_name in ("log.txt", "output.txt") or t_name.endswith(".log"):
        return False
    for k in store:
        if k.startswith("Inspection (") or k.startswith("Target Source ("):
            inner = k[k.find("(") + 1 : k.rfind(")")].strip().replace("\\", "/").rstrip("/")
            if inner == t_norm or inner.split("/")[-1] == t_name:
                return True
    return False


def format_target(target, target_dir):
    if isinstance(target, dict):
        clean = {k: v for k, v in target.items() if v}
        clean["dir"] = target_dir
        if "host" not in clean and "port" not in clean:
            clean["network"] = "This is a local challenge!"
        return json.dumps(clean, indent=2)
    return str(target)


def format_discovered(tree, store):
    data = {**tree.get("data", {}), **store}
    slim = {k: (str(v)[:25000] + "...[truncated]") if len(str(v)) > 25000 else v for k, v in data.items()}
    findings = tree.get("findings", [])
    data_str = json.dumps(slim, indent=2) if slim else "{}"
    return f"Findings:\n" + "\n".join(findings) + f"\nData:\n{data_str}"


def as_dict(val, key=None):
    if isinstance(val, dict) and key and isinstance(val.get(key), dict):
        return val[key]
    if isinstance(val, list) and val and isinstance(val[0], dict):
        return val[0]
    return val if isinstance(val, dict) else {}


def read(sandbox, target, base_dir=None, role=None, last=False, silent=False):
    base = base_dir or "/data"
    targets = parse_targets(target)
    if not targets:
        return {}

    if not silent:
        agent_ui.read(targets, last=last)
    out_map = {}
    for t in targets:
        if any(b in t.lower() for b in ("venv", ".venv", "site-packages", "node_modules")):
            content = "Cannot read virtual environment or dependency packages."
        else:
            content = sb.read(sandbox, t, base_dir=base)
        out_map[t] = content
    return out_map


def inspect_files(sandbox, target, target_dir, state, role="Inspection", alert_prefix=None, last=False, silent=False):
    out_map = read(sandbox, target, target_dir, role=role, last=last, silent=silent)
    if not out_map:
        return {}
    for t, text in out_map.items():
        state.absorb({f"{role} ({t})": text[:25000]})
        if alert_prefix:
            state.alerts.append(f"[{alert_prefix}] {t}:\n{text[:25000]}")
    return out_map


def rag(query, memory, state, last=False):
    if not query or str(query).lower() in ("none", "null", ""):
        return None

    agent_ui.subtask(query, rag=True, last=last)
    rag_out = memory.execute(query, len(state.history))
    if rag_out:
        state.history.append(rag_out)
    return rag_out


def plan_loop(planner, sandbox, target, state, memory, target_dir, tools, book, time_left):
    desc = (target.get("desc") or target.get("description", "")) if isinstance(target, dict) else str(target)
    target_str = format_target(target, target_dir)

    next_str = " ".join(state.tree.get("next", [])) if isinstance(state.tree.get("next"), list) else str(state.tree.get("next", ""))
    findings = " ".join(state.tree.get("findings", [])) if isinstance(state.tree.get("findings"), list) else str(state.tree.get("findings", ""))
    findings += " " + str(state.tree.get("data", {}))

    memories = memory.query(desc, state.tree.get("stage", ""), findings, next_str)
    mem_str = "\n".join(memories) if memories else "No relevant memories found."

    state.alerts = [a for a in state.alerts if "Re-inspect via tool read" not in a]
    start = time.time()
    plan_res = planner.plan(
        history=state.history, fails=state.fails, target=target_str, tree=state.tree,
        tools=tools, playbook=book, memory=mem_str, time_left=time_left,
        facts=state.store, warns=state.alerts
    )
    plan = plan_res["plan_data"]
    elapsed = time.time() - start

    plan_dict = as_dict(plan, "plan")
    sub = plan_dict.get("subtask") or plan.get("subtask", "Analyzing next step...")

    if plan_dict.get("finished", False) or plan.get("finished", False):
        agent_ui.plan(elapsed)
        return plan, True, target_str, sub, None

    agent_ui.plan(elapsed)

    reason_dict = as_dict(plan, "reason")
    hyp = as_dict(reason_dict, "hypothesis")
    rationale = (
        hyp.get("rationale") or reason_dict.get("rationale") or plan.get("rationale") or
        (plan.get("hypothesis", {}).get("rationale") if isinstance(plan.get("hypothesis"), dict) else "") or
        plan.get("raw_text", "")
    )
    agent_ui.think(rationale if rationale else f"Output: {str(plan)[:200]}...")

    # Handle read inspection
    plan_read = plan_dict.get("read") or plan.get("read")
    targets = parse_targets(plan_read)
    unread = [t for t in targets if not is_inspected(t, state.store)]

    if unread:
        recent_inspections = sum(1 for h in state.history[-2:] if h.get("tactic") == "Inspection")
        is_last = (recent_inspections < 1)
        out_map = read(sandbox, unread, target_dir, role="Planner", last=is_last)
        if out_map:
            combined = []
            for t, text in out_map.items():
                state.absorb({f"Inspection ({t})": text})
                combined.append(f"[{t}]\n{text}")
            obs = "\n\n".join(combined)
            state.history.append({
                "step_id": f"step_{len(state.history) + 1}",
                "tactic": "Inspection",
                "plan": f"Read {unread}",
                "observation": obs[:25000],
                "result": "pass",
                "raw": obs[:25000]
            })
            recent_inspections = sum(1 for h in state.history[-2:] if h.get("tactic") == "Inspection")
            if recent_inspections < 2:
                return None, False, target_str, sub, "read"

    # Handle RAG search
    plan_rag = plan_dict.get("rag")
    if plan_rag and str(plan_rag).lower() not in ("none", "null", ""):
        rag(plan_rag, memory, state, last=True)
        return None, False, target_str, sub, "rag"

    agent_ui.subtask(sub, rag=False)
    return plan, False, target_str, sub, None


def exec_loop(executor, sandbox, target_str, sub, tool_hint, state, memory, category, target_dir, target):
    data = {**state.tree.get("data", {}), **state.store}
    cmds, out, obs, prev = [], "", "", ""
    stagnant, turn, cap = 0, 0, 5
    exec_json = {"commands": [], "success": "none"}
    messages = None
    last_cmds, last_out, last_ind, last_exec_json = [], "", "", exec_json

    while turn < cap:
        agent_ui.execute()

        res = executor.execute(
            target=target_str, subtask=sub, tool_hint=tool_hint,
            history=state.compressed, facts=data, tree=state.tree, obs=obs,
            messages=messages
        )
        messages = res.get("messages")
        exec_json = res.get("exec_data") or res.get("action_data", {})
        cmds = exec_json.get("commands", [])
        ind = exec_json.get("success", "")

        # Handle rag query
        exec_rag = exec_json.get("rag")
        if exec_rag and str(exec_rag).lower() not in ("none", "null", ""):
            rag(exec_rag, memory, state)

        # Handle read inspection
        exec_read = exec_json.get("read")
        if parse_targets(exec_read):
            inspect_files(sandbox, exec_read, target_dir, state, role="Inspection", alert_prefix="EXECUTOR READ")
            data = {**state.tree.get("data", {}), **state.store}

        reason_dict = as_dict(exec_json, "reason")
        action = reason_dict.get("action") or exec_json.get("action", "")
        if action:
            agent_ui.action(action)

        if exec_json.get("done", False) and not cmds:
            break

        if not cmds:
            agent_ui.empty()
            break

        is_last_turn = exec_json.get("done", False) or (turn >= cap - 1)
        for i, cmd in enumerate(cmds):
            agent_ui.command(cmd, is_last_turn and (i == len(cmds) - 1))

        cur_str = json.dumps(cmds)
        if cur_str == prev:
            stagnant += 1
            if stagnant >= 2:
                agent_ui.stagnant(stagnant)
                break
        else:
            stagnant = 0
        prev = cur_str

        timeout = exec_json.get("timeout", 60)
        out = sb.run(sandbox, cmds, category, timeout, workdir=target_dir)

        last_cmds = cmds
        last_out = out

        if exec_json.get("done", False) and (turn > 0 or (ind and str(ind).lower() in out.lower())):
            break

        obs = out[-3000:] if out.strip() else "[Command executed with empty output]"
        turn += 1

    return last_cmds or cmds, last_out or out, ind, exec_json


def verif_loop(verifier, sandbox, sub, cmds, ind, out, plan, state, memory, target_dir, target):
    v_start = time.time()
    reason = as_dict(plan, "reason")
    hyp = as_dict(reason, "hypothesis")
    v_res = verifier.verify(
        subtask=sub, commands=cmds, indicator=ind,
        output=out, hypothesis=hyp, facts=state.store
    )
    verif = as_dict(v_res.get("verify_data"))

    v_rag = verif.get("rag")
    if v_rag and str(v_rag).lower() not in ("none", "null", ""):
        agent_ui.verify(time.time() - v_start)
        rag(v_rag, memory, state)
        return verif, None, True

    # Handle read verification
    v_read = verif.get("read")
    v_targets = parse_targets(v_read)
    if v_targets:
        out_map = read(sandbox, v_read, target_dir, role="Verifier", silent=True)
        for t, text in out_map.items():
            verif.setdefault("knowledge", []).append(f"File {t}:\n{text[:25000]}")
            state.absorb({f"Verified File ({t})": text[:25000]})

    v_reason = as_dict(verif, "reason")
    res = str(verif.get("result", "")).lower()
    if res in ("pass", "success"):
        know = verif.get("knowledge", [])
        final_msg = know[0] if know else f"Evaluated {len(cmds)} command(s)"
        agent_ui.passed(final_msg, read=v_targets)
    elif res == "partial":
        err_msg = v_reason.get("unmet") or v_reason.get("analysis")
        agent_ui.partial(err_msg, read=v_targets)
    else:
        err_msg = v_reason.get("unmet") or v_reason.get("analysis")
        agent_ui.failed(err_msg, read=v_targets)

    flag = verif.get("flag")
    if flag and str(flag).lower() not in ("false", "none", "null", ""):
        return verif, str(flag).strip(), False

    return verif, None, False


def refine_loop(refiner, verifier, sandbox, target_str, sub, cmds, out, ind, plan, state, category, target_dir, target, exec_json):
    max_retries = 2
    r_cap = 3
    r_abort = False
    last_cmds = cmds
    last_out = out
    verif = {"result": "fail"}

    for attempt in range(max_retries):
        agent_ui.refine(attempt + 1, max_retries)
        discovered = format_discovered(state.tree, state.store)

        if attempt > 0 and verif.get("result") in ("fail", "partial"):
            v_reason = as_dict(verif, "reason")
            unmet = v_reason.get("unmet") or v_reason.get("analysis", "")
            if unmet:
                discovered += f"\n\nPrevious Verification Feedback (Retry {attempt}): {unmet}"

        r_obs = None
        r_turn = 0
        r_messages = None

        while r_turn < r_cap:
            retry_api = 0
            while retry_api < 3:
                r_res = refiner.refine(
                    target=target_str, subtask=sub, failed=last_cmds, error=last_out,
                    history=state.compressed, discovered=discovered, obs=r_obs,
                    messages=r_messages
                )
                raw = r_res.get("raw", "")
                if "429" in raw:
                    agent_ui.retry(retry_api + 1)
                    retry_api += 1
                    time.sleep(2 * retry_api)
                    continue
                break

            r_messages = r_res.get("messages")
            r_data = r_res.get("refine_data", {})
            r_cmds = r_data.get("commands", [])
            r_abort = r_data.get("abort", False)

            # Inspect ground truth
            r_read = r_data.get("read")
            read_snippets = []
            if parse_targets(r_read):
                out_map = read(sandbox, r_read, target_dir, role="Refiner")
                if out_map:
                    for t, text in out_map.items():
                        state.absorb({f"Inspection ({t})": text[:25000]})
                        read_snippets.append(f"File {t}:\n{text[:25000]}")

                    discovered = format_discovered(state.tree, state.store)
                    if not r_cmds and not r_abort:
                        read_text = "Ground Truth Files Inspected:\n" + "\n".join(read_snippets)
                        r_obs = f"{r_obs}\n\n{read_text}" if r_obs else read_text
                        r_res = refiner.refine(
                            target=target_str, subtask=sub, failed=last_cmds, error=last_out,
                            history=state.compressed, discovered=discovered + "\n\n" + read_text, obs=r_obs,
                            messages=r_messages
                        )
                        r_messages = r_res.get("messages")
                        r_data = r_res.get("refine_data", {})
                        r_cmds = r_data.get("commands", [])
                        r_abort = r_data.get("abort", False)

            r_reason = as_dict(r_data, "reason")
            r_analysis = r_reason.get("analysis", "") or r_reason.get("strategy", "")
            if r_analysis:
                agent_ui.think(r_analysis)

            if r_data.get("done", False) and not r_cmds:
                break

            if r_abort or not r_cmds:
                if r_abort:
                    err_reason = r_reason.get("error") or "dead end detected"
                    agent_ui.abort(err_reason)
                    return last_cmds, last_out, {"result": "fail"}, None, r_abort
                agent_ui.empty()
                break

            is_last_rturn = r_data.get("done", False) or (r_turn >= r_cap - 1)
            for i, cmd in enumerate(r_cmds):
                agent_ui.command(cmd, is_last_rturn and (i == len(r_cmds) - 1))

            timeout = r_data.get("timeout", exec_json.get("timeout", 30))
            cur_out = sb.run(sandbox, r_cmds, category, timeout, workdir=target_dir)

            last_cmds = r_cmds
            last_out = cur_out

            if r_data.get("done", False):
                break

            cmd_obs = cur_out[-3000:] if cur_out.strip() else "[Command produced empty output]"
            r_obs = ("Inspected Files:\n" + "\n".join(read_snippets) + f"\n\nCommand Output:\n{cmd_obs}") if read_snippets else cmd_obs
            r_turn += 1

        # Verify refined execution
        reason = as_dict(plan, "reason")
        hyp = as_dict(reason, "hypothesis")
        v_res = verifier.verify(
            subtask=sub, commands=last_cmds, indicator=ind,
            output=last_out, hypothesis=hyp, facts=state.store
        )
        verif = as_dict(v_res.get("verify_data"))

        vr_read = verif.get("read")
        vr_targets = parse_targets(vr_read)
        if vr_targets:
            out_map = read(sandbox, vr_read, target_dir, role="Verifier", silent=True)
            for t, text in out_map.items():
                verif.setdefault("knowledge", []).append(f"File {t}:\n{text[:25000]}")
                state.absorb({f"Verified file ({t})": text[:25000]})

        res = str(verif.get("result", "")).lower()
        if res in ("pass", "success"):
            know = verif.get("knowledge", [])
            final_msg = know[0] if know else f"Evaluated {len(last_cmds)} command(s)"
            agent_ui.passed(final_msg, read=vr_targets)
        elif res == "partial":
            v_reason = as_dict(verif, "reason")
            err_msg = v_reason.get("unmet") or v_reason.get("analysis")
            agent_ui.partial(err_msg, read=vr_targets)
        else:
            v_reason = as_dict(verif, "reason")
            err_msg = v_reason.get("unmet") or v_reason.get("analysis")
            agent_ui.failed(err_msg, read=vr_targets)

        flag = verif.get("flag")
        if flag and str(flag).lower() not in ("false", "none", "null", ""):
            return last_cmds, last_out, verif, str(flag).strip(), False

        strat = r_data.get("reason", {}).get("strategy", "No strategy provided!")
        verif.setdefault("knowledge", []).append(f"strategy: {strat}")

        if verif.get("result") in ("pass", "success"):
            break

    return last_cmds, last_out, verif, None, r_abort


def dedup_output(text):
    lines = text.splitlines()
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
    return "\n".join(deduped)


def sum_loop(summarizer, sub, cmds, out, verif, tactic, state, sandbox=None, target_dir=None):
    t0 = time.time()
    t_out = out if not out.startswith("[TIMEOUT]") else "[TIMEOUT] Command timed out — no output produced. Treat this step as failed.\n" + out
    clean_out = dedup_output(t_out)

    step = {
        "subtask": sub,
        "commands": cmds,
        "output_summary": clean_out[-5000:],
        "verification": verif
    }

    res = summarizer.summarize(tree=state.tree, step=step)
    sum_data = res["summary_data"]
    sum_time = time.time() - t0

    agent_ui.summarize(sum_time)

    sum_read = sum_data.get("read")
    targets = parse_targets(sum_read) if sandbox else []
    if targets:
        inspect_files(sandbox, targets, target_dir or "/data", state, role="Summarizer", last=False)

    new_tree = sum_data.get("tree", {})
    new_data = new_tree.get("data", {})

    state.alerts = state.diff(new_data) + state.guard()
    state.merge(new_tree)
    state.update(task=sub, status=verif.get("result", "unknown"), data=new_data)
    state.snap()
    state.prune_store()

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
        "raw": out[-3000:]
    })

    obs = sum_data.get("summary", "")
    state.compressed += f"\n[{id}] {obs}"
    if len(state.compressed) > 15000:
        src_pins = [f"[PINNED {k}]\n{str(v)[:2000]}" for k, v in state.store.items() if k.startswith(("Inspection (", "Target Source ("))]
        pin_str = "\n".join(src_pins)
        state.compressed = "...[TRUNCATED]...\n" + state.compressed[-12000:]
        if pin_str:
            state.compressed += f"\n\nPINNED SOURCE FILES\n{pin_str}"
        state.alerts.append("[CONTEXT OVERFLOW] History truncated. Key source files are pinned above.")

    return obs


def ref_loop(reflector, sandbox, state, memory, target_str, time_left, plan_reflect, r_abort, fails, target_dir):
    count = len(state.history)
    max_fails = max(state.fails.values()) if state.fails else 0
    reflect = plan_reflect or (r_abort and count > 3) or (fails >= 3) or (count > 5 and count % 3 == 0)
    if not reflect:
        return False

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

    ref_read = review.get("read")
    targets = parse_targets(ref_read)
    ref_rag = review.get("rag")
    has_rag = bool(ref_rag and str(ref_rag).lower() not in ("none", "null", ""))
    has_read = bool(targets)

    # Output Reflecting node first
    has_children = has_read or has_rag
    agent_ui.reflect(ref_time, has_children=has_children)

    # Inspect files under Reflecting node
    if has_read:
        is_last = not has_rag
        inspect_files(sandbox, targets, target_dir, state, role="Reflector", alert_prefix="REFLECTOR READ", last=is_last)

    # Search RAG under Reflecting node
    if has_rag:
        rag(ref_rag, memory, state, last=True)

    rep = review.get("repeat")
    if rep and str(rep).lower() not in ("none", "null", ""):
        state.alerts.append(f"[FORBIDDEN] Discredited assumption: {rep}")
        failed_list = state.tree.setdefault("failed", [])
        if f"FORBIDDEN: {rep}" not in failed_list:
            failed_list.append(f"FORBIDDEN: {rep}")

    reason_dict = as_dict(review, "reason")
    cause = reason_dict.get("cause", "")
    if cause:
        state.alerts.append(f"[ROOT CAUSE] {cause}")

    if adv or tac:
        state.alerts.append(f"[ADVICE] {tac} - {adv}")

    return True