from .core import node, line, error, clock

# Log planning phase
def plan(elapsed):
    node("Planning...", clock(elapsed), "cyan")

# Log thinking phase
def think(rationale=None, header=True):
    if header:
        line("├─ Thinking...")
    if rationale:
        line(f"├─ {rationale}")

# Log verifying phase
def verify(elapsed):
    node("Verifying...", clock(elapsed), "red")

# Log current subtask
def subtask(sub, rag=False):
    if not rag:
        line("│")
        prefix = "└─ "
        line(f"{prefix}{sub}")
    else:
        prefix = "├─ "
        line(f"{prefix}Searching \"{sub}\"...")

# Log reading phase
def read(target, last=True):
    branch = "└─ " if last else "├─ "
    line(f"{branch}Reading \"{target}\"...")

# Log circuit breaker
def breaker(attempts):
    error(f"Guard: subtask repeated {attempts}x — skipped")

# Log execution phase
def execute(elapsed):
    node("Executing...", clock(elapsed), "magenta")

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
        console.print(Text("│  ", style="bold blue") + Text(f"{prefix}{chunk}", style=f"bold {_current_color}"))

    # Heredoc body
    for row in rows[1:]:
        wrapped = textwrap.wrap(row, width=wrap_width) or [""]
        for chunk in wrapped:
            console.print(Text("│  ", style="bold blue") + Text(f"{cont_prefix}{chunk}", style=f"bold {_current_color}"))

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
def refine(retry, total):
    node("Refining...", f"Retry {retry} / {total}", "yellow")

# Log API retry
def retry(ret):
    line(f"├─ Transient API error, retrying ({ret}/3)...")

# Log missing commands
def empty():
    line("└─ Failed to produce new commands")

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
def reflect(elapsed):
    node("Reflecting...", clock(elapsed), "magenta")
    line("└─ Stuck state analyzed and replanned")
