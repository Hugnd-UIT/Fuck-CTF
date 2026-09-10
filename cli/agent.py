from .core import node, line, error, clock, console, _current_color, empty_line, get_wrap_width

# Log planning phase
def plan(elapsed):
    node("Planning...", clock(elapsed), "cyan")

# Log thinking phase
def think(rationale=None, header=False):
    if rationale:
        line(f"├─ {rationale}")
        empty_line()

# Log verifying phase
def verify(elapsed):
    node("Verifying...", clock(elapsed), "yellow")

# Log current subtask
def subtask(sub, rag=False, last=False):
    branch = "└─ " if last else "├─ "
    if not rag:
        line(f"{branch}{sub}")
        if not last:
            empty_line()
    else:
        line(f"{branch}Searching \"{sub}\"...")
        from . import rag as rag_ui
        rag_ui.set_last(last)

# Log reading phase
def read(target, last=False):
    branch = "└─ " if last else "├─ "
    if isinstance(target, list):
        target_str = ", ".join(str(t) for t in target)
    else:
        target_str = str(target)
    line(f"{branch}Reading \"{target_str}\"...")
    if not last:
        empty_line()

# Log circuit breaker
def breaker(attempts):
    node("Guard", f"Repeated {attempts}x", "red")
    line("└─ Subtask repeated too many times — skipped", color="red")

# Log execution phase
def execute(turn=0):
    node("Executing...", "", "magenta")

# Log action phase
def action(act):
    if act:
        text = act if act.lower().startswith("action:") else f"Action: {act}"
        line(f"├─ {text}")
        empty_line()

# Log stagnant execution
def stagnant(attempts):
    node("Guard", f"Stagnant {attempts}x", "red")
    line("└─ Commands repeated with no progress — stopped", color="red")

# Log executed command
def command(cmd, last):
    from .core import console, _current_color, get_wrap_width, empty_line
    from rich.text import Text
    import textwrap

    cmd = cmd.strip()
    rows = cmd.split('\n')
    branch = "└─ " if last else "├─ "
    cont_prefix = "     " if last else "│    "

    wrap_text_width = max(45, get_wrap_width() - 8)

    # First line
    head = textwrap.wrap(rows[0], width=wrap_text_width) or [rows[0]]
    for i, chunk in enumerate(head):
        prefix = f"{branch}$ " if i == 0 else cont_prefix
        console.print(
            Text("│  ", style=f"bold {_current_color}") +
            Text(f"{prefix}{chunk}", style=f"bold {_current_color}")
        )

    # Heredoc body
    for row in rows[1:]:
        wrapped = textwrap.wrap(row, width=wrap_text_width, drop_whitespace=False) or [row]
        for chunk in wrapped:
            console.print(
                Text("│  ", style=f"bold {_current_color}") +
                Text(f"{cont_prefix}{chunk}", style=f"bold {_current_color}")
            )

    from . import core
    core._last_was_empty = False
    core._last_node = None
    if not last:
        empty_line()

def _log_verif_body(final_msg=None, read=None):
    msg_str = str(final_msg).strip() if final_msg is not None else None
    if msg_str:
        lines = msg_str.splitlines()
        if len(lines) > 4:
            msg_str = "\n".join(lines[:3]) + f"\n... [truncated {len(lines) - 3} lines]"
        elif len(msg_str) > 300:
            msg_str = msg_str[:297] + "..."

    if read:
        target_str = ", ".join(str(t) for t in read) if isinstance(read, list) else str(read)
        if msg_str:
            line(f"├─ Reading \"{target_str}\"...")
            empty_line()
            line(f"└─ {msg_str}")
        else:
            line(f"└─ Reading \"{target_str}\"...")
    elif msg_str:
        line(f"└─ {msg_str}")

# Log verification success
def passed(know=None, read=None):
    node("Verifying...", "[ Pass ]", "green")
    _log_verif_body(final_msg=know, read=read)

# Log verification partial
def partial(reason=None, read=None):
    node("Verifying...", "[ Partial ]", "yellow")
    _log_verif_body(final_msg=reason, read=read)

# Log verification failure
def failed(reason=None, read=None):
    node("Verifying...", "[ Fail ]", "red")
    _log_verif_body(final_msg=reason, read=read)

# Log verified knowledge
def knowledge(know):
    line(f"└─ {know}")

# Log evaluated count
def evaluated(count):
    line(f"└─ Evaluated {count} command(s)")

# Log refine phase
def refine(retry=None, total=None, step=None):
    if step and step > 1:
        node("Refining...", f"Retry {retry}/{total} (Turn {step})", "yellow")
    elif retry and total and total > 1:
        node("Refining...", f"Retry {retry} / {total}", "yellow")
    else:
        node("Refining...", "", "yellow")

# Log API retry
def retry(ret):
    line(f"├─ Transient API error, retrying ({ret}/3)...")

# Log missing commands
def empty():
    line("└─ Failed to produce new commands")

# Log refiner abort / dead end
def abort(reason=None):
    msg = f"└─ Aborted: {reason}" if reason else "└─ Aborted: dead end detected"
    line(msg)

# Log summarize phase
def summarize(elapsed):
    node("Summarizing...", clock(elapsed), "green")

# Log state contradictions
def contradict(count):
    line(f"└─ Contradiction: {count} item(s) vanished or changed")

# Log clean state
def clean():
    line("└─ ✓ No contradictions detected")

# Log reflection phase
def reflect(elapsed, has_children=False, read=None):
    node("Reflecting...", clock(elapsed), "magenta")
    if read:
        read_str = ", ".join(str(r) for r in read) if isinstance(read, list) else str(read)
        line("├─ Stuck state analyzed and replanned")
        empty_line()
        line(f"└─ Reading \"{read_str}\"...")
    elif has_children:
        line("├─ Stuck state analyzed and replanned")
        empty_line()
    else:
        line("└─ Stuck state analyzed and replanned")