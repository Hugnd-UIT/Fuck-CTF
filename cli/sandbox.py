from .core import node, line

# Log container creation
def create(name):
    node("Sandbox", "Setup", "cyan")
    line(f"├─ Initializing container '{name}'...")

# Log creation success
def success():
    line("└─ Container ready", color="green")

# Log missing curl
def curlerr():
    line("└─ [Warning] Failed to verify curl in container", color="yellow")

# Log container output
def output(out):
    lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
    if lines:
        last_line = lines[-1][:60]
        line(f"│  Setting up: {last_line}...")