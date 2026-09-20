from .core import node, line

# Log container creation
def create(name):
    node("Sandbox", "Setup", "cyan")
    line(f"├─ Init container '{name}'...")

# Log creation success
def success():
    line("└─ Init container successfully", color="green")

# Log missing curl
def curlerr():
    line("└─ Curl failed", color="yellow")

# Log container output
def output(out):
    lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
    if lines:
        last_line = lines[-1][:60]
        line(f"│  Set up: {last_line}...")