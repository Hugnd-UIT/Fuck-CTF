from .core import node, line, error, clock, console, _current_color

def empty_line():
    from . import core
    if core._last_was_empty:
        return
    core._last_was_empty = True
    from rich.text import Text
    console.print(Text("│  ", style=f"bold {core._current_color}") + Text("│", style=f"bold {core._current_color}"))

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
    if not rag:
        prefix = "└─ "
        line(f"{prefix}{sub}")
    else:
        prefix = "└─ " if last else "├─ "
        line(f"{prefix}Searching \"{sub}\"...")
        if not last:
            empty_line()

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
    error(f"Guard: subtask repeated {attempts}x — skipped")

# Log execution phase
def execute():
    node("Executing...", "", "magenta")

# Log action phase
def action(act):
    if act:
        text = act if act.lower().startswith("action:") else f"Action: {act}"
        line(f"├─ {text}")
        empty_line()

# Log stagnant execution
def stagnant(attempts):
    error(f"Guard: commands repeated {attempts}x — stopped")

# Log executed command
def command(cmd, last):
    from .core import console, _current_color, line
    from rich.text import Text
    import shutil, textwrap

    cmd = cmd.strip()
    rows = cmd.split('\n')
    branch = "└─ " if last else "├─ "
    cont_prefix = "     " if last else "│    "

    term_cols = shutil.get_terminal_size().columns
    wrap_width = max(68, min(term_cols - 10, 80))

    # First line
    head = textwrap.wrap(f"{branch}$ {rows[0]}", width=wrap_width) or [f"{branch}$ {rows[0]}"]
    for i, chunk in enumerate(head):
        prefix = cont_prefix if i > 0 else ""
        console.print(Text("│  ", style=f"bold {_current_color}") + Text(f"{prefix}{chunk}", style=f"bold {_current_color}"))

    # Heredoc body
    for row in rows[1:]:
        wrapped = textwrap.wrap(row, width=wrap_width, drop_whitespace=False) or [""]
        for chunk in wrapped:
            console.print(Text("│  ", style=f"bold {_current_color}") + Text(f"{cont_prefix}{chunk}", style=f"bold {_current_color}"))

    from . import core
    core._last_was_empty = False
    if not last:
        empty_line()

# Log verification success
def passed(know=None):
    node("Verifying...", "[ Pass ]", "green")
    if know:
        line(f"└─ {know}")

# Log verification partial
def partial(reason=None):
    node("Verifying...", "[ Partial ]", "yellow")
    if reason:
        line(f"└─ {reason}")

# Log verification failure
def failed(reason=None):
    node("Verifying...", "[ Fail ]", "red")
    if reason:
        line(f"└─ {reason}")

# Log verified knowledge
def knowledge(know):
    line(f"└─ {know}")

# Log evaluated count
def evaluated(count):
    line(f"└─ Evaluated {count} command(s)")

# Log refine phase
def refine(retry=None, total=None):
    if retry and total and total > 1:
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
    line(f"└─ Contradiction: {count} item(s) vanished or changed", color="red")

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