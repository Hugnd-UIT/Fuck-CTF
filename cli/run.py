from .core import header as core_header, footer as core_footer, line

def timeout(time):
    line(f"└─ 🛑 TIMEOUT: Reached {time} minutes.", color="red")

def crashes(crashes):
    line(f"└─ 🛑 ABORTED: {crashes} consecutive crashes.", color="red")

def noflag():
    line("└─ 🛑 Goal achieved, but no flag was found in the output.", color="red")

def stop():
    line("└─ 🛑 STOPPED BY USER", color="red")
    
def header(target, time):
    core_header(target, time)

def footer(flag, elapsed):
    core_footer(flag, elapsed)
