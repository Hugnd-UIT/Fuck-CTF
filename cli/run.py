from .core import header as core_header, footer as core_footer, node, line

# Log timeout error
def timeout(time):
    node("Timeout", f"{time}m limit", "red")
    line(f"└─ Reached execution time limit ({time} minutes)", color="red")

# Log crash limit
def crashes(crashes):
    node("Aborted", f"{crashes} crashes", "red")
    line(f"└─ Stopped after {crashes} consecutive crashes", color="red")

# Log missing flag
def noflag():
    node("No Flag", "Completed", "yellow")
    line("└─ Goal achieved, but no flag was found in the output!", color="yellow")

# Log user interrupt
def stop():
    node("Stopped", "Interrupt", "red")
    line("└─ Process interrupted by user", color="red")
    
# Log execution header
def header(target, time):
    core_header(target, time)

# Log execution footer
def footer(flag, elapsed):
    core_footer(flag, elapsed)