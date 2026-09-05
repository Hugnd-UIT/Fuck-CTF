from .core import node, line, error, clock

# Log planning phase
def plan(elapsed):
    node("Planning...", clock(elapsed), "cyan")

# Log thinking phase
def think(rationale=None, header=False):
    if rationale:
        line(f"├─ {rationale}")
        line()

# Log verifying phase
def verify(elapsed):
    node("Verifying...", clock(elapsed), "red")

# Log current subtask
def subtask(sub, rag=False):
    if not rag:
        line()
        prefix = "└─ "
        line(f"{prefix}{sub}")
    else:
        prefix = "├─ "
        line(f"{prefix}Searching \"{sub}\"...")

# Log reading phase
def read(target, last=False):
    branch = "└─ " if last else "├─ "
    if isinstance(target, list):
        target_str = ", ".join(str(t) for t in target)
    else:
        target_str = str(target)
    line(f"{branch}Reading \"{target_str}\"...")
    if not last:
        line()

# Log circuit breaker
def breaker(attempts):
    error(f"Guard: subtask repeated {attempts}x — skipped")

# Log execution phase
def execute(elapsed=None):
    node("Executing...", clock(elapsed) if elapsed else "", "magenta")

# Log react phase
def react(turn=None, total=None):
    if turn and total and total > 1:
        node("Executing...", f"Step {turn} / {total}", "magenta")
    else:
        node("Executing...", "", "magenta")

# Log action phase
def action(act):
    if act:
        text = act if act.lower().startswith("action:") else f"Action: {act}"
        line(f"├─ {text}")
        line()

# Log stagnant execution
def stagnant(attempts):
    error(f"Guard: commands repeated {attempts}x — stopped")

# Log executed command
def command(cmd, last):
    from .core import console, _current_color
    from rich.text import Text
    import shutil, textwrap

    cmd = cmd.strip().replace('\\n', '\n').replace('\\t', '\t')
    rows = cmd.split('\n')
    branch = "└─ " if last else "├─ "
    
    wrap_width = min(shutil.get_terminal_size().columns - 10, 62)

    # First line
    head = textwrap.wrap(f"{branch}$ {rows[0]}", width=wrap_width)
    cont_prefix = "     " if last else "│    "
    for i, chunk in enumerate(head):
        prefix = cont_prefix if i > 0 else ""
        console.print(Text("│  ", style=f"bold {_current_color}") + Text(f"{prefix}{chunk}", style=f"bold {_current_color}"))

    # Heredoc body
    for row in rows[1:]:
        wrapped = textwrap.wrap(row, width=wrap_width) or [""]
        for chunk in wrapped:
            console.print(Text("│  ", style=f"bold {_current_color}") + Text(f"{cont_prefix}{chunk}", style=f"bold {_current_color}"))

    from . import core
    core._last_was_empty = False
    if not last:
        line()

# Log verification success
def passed():
    node("Verifying...", "[ Pass ]", "red")

# Log verification failure
def failed():
    node("Verifying...", "[ Fail ]", "red")

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
    line("Updating...")

# Log state contradictions
def contradict(count):
    error(f"Contradiction: {count} item(s) vanished or changed")

# Log clean state
def clean():
    line("└─ ✓ No contradictions detected")

# Log reflection phase
def reflect(elapsed, read=None):
    node("Reflecting...", clock(elapsed), "magenta")
    if read:
        read_str = ", ".join(str(r) for r in read) if isinstance(read, list) else str(read)
        line("├─ Stuck state analyzed and replanned")
        line(f"└─ Reading \"{read_str}\"...")
    else:
        line("└─ Stuck state analyzed and replanned")