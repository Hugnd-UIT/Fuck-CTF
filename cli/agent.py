from .core import node, line, error, clock

# Log planning phase
def plan(elapsed):
    node("Planning...", clock(elapsed), "cyan")

# Log thinking phase
def think():
    line("├─ Thinking...")

# Log current subtask
def subtask(sub, rag=False):
    prefix = "├─ " if rag else "└─ "
    line(f"{prefix}{sub}")

# Log circuit breaker
def breaker(attempts):
    error(f"Guard: subtask repeated {attempts}x — skipped")

# Log execution phase
def execute(elapsed):
    node("Executing...", clock(elapsed), "magenta")

# Log executed command
def command(cmd, last):
    from .core import console
    from rich.text import Text
    import shutil, textwrap

    rows = cmd.split('\n')
    branch = "└─ " if last else "├─ "
    wrap = min(shutil.get_terminal_size().columns - 10, 62)

    # Print first line
    head = textwrap.wrap(f"{branch}$ {rows[0]}", width=wrap, subsequent_indent="     ")
    for chunk in head:
        console.print(Text("│  ", style="bold blue") + Text(chunk, style="bold magenta"))

    # Print heredoc body
    for row in rows[1:]:
        wrapped = textwrap.wrap(row, width=wrap, subsequent_indent="     ") or [""]
        for chunk in wrapped:
            console.print(Text("│  ", style="bold blue") + Text(f"   {chunk}", style="bold magenta"))

# Log verification success
def passed():
    node("Verifying...", "[ Pass ]", "green")

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
    node("Summarizing...", clock(elapsed), "cyan")
    line("Information updating...")

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
