from .core import node, line, error, clock

def plan(elapsed):
    node("Planning...", clock(elapsed), "cyan")

def think():
    line("├─ Thinking...")

def subtask(sub, rag=False):
    prefix = "├─ " if rag else "└─ "
    line(f"{prefix}{sub}")

def breaker(attempts):
    error(f"Guard: subtask repeated {attempts}x — skipped")

def execute(elapsed):
    node("Executing...", clock(elapsed), "magenta")

def command(cmd, last):
    prefix = "└─ " if last else "├─ "
    lines = cmd.split('\n')
    line(f"{prefix}$ {lines[0]}")
    for l in lines[1:]:
        char = "" if last else "│"
        line(f"     {l}", tree=char)

def passed():
    node("Verifying...", "[ Pass ]", "green")

def failed():
    node("Verifying...", "[ Fail ]", "red")

def knowledge(know):
    line(f"└─ {know}")

def evaluated(count):
    line(f"└─ Evaluated {count} command(s)")

def refine(retry, total):
    node("Refining...", f"Retry {retry} / {total}", "yellow")

def retry(ret):
    line(f"├─ Transient API error, retrying ({ret}/3)...")

def empty():
    line("└─ Failed to produce new commands")

def summarize(elapsed):
    node("Summarizing...", clock(elapsed), "cyan")
    line("Information updating...")

def contradict(count):
    error(f"Contradiction: {count} item(s) vanished or changed")

def clean():
    line("└─ ✓ No contradictions detected")

def reflect(elapsed):
    node("Reflecting...", clock(elapsed), "magenta")
    line("└─ Stuck state analyzed and replanned")
