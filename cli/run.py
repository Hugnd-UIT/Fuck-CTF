from .core import header as core_header, footer as core_footer, line

# Log timeout error
def timeout(time):
    line(f"└─ [!] TIMEOUT: Reached {time} minutes!", color="red")

# Log crash limit
def crashes(crashes):
    line(f"└─ [!] ABORTED: {crashes} consecutive crashes!", color="red")

# Log missing flag
def noflag():
    line("└─ [!] Goal achieved, but no flag was found in the output!", color="red")

# Log user interrupt
def stop():
    line("└─ [!] STOPPED BY USER", color="red")
    
# Log execution header
def header(target, time):
    core_header(target, time)

# Log execution footer
def footer(flag, elapsed):
    core_footer(flag, elapsed)