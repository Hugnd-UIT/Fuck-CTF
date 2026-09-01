import re
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.style import Style

console = Console()

# Print CLI header
def header(target, minutes):
    art = (
        "      ███████╗██╗   ██╗ ██████╗██╗  ██╗     ██████╗████████╗███████╗      \n"
        "      ██╔════╝██║   ██║██╔════╝██║ ██╔╝    ██╔════╝╚══██╔══╝██╔════╝      \n"
        "      █████╗  ██║   ██║██║     █████╔╝     ██║        ██║   █████╗        \n"
        "      ██╔══╝  ██║   ██║██║     ██╔═██╗     ██║        ██║   ██╔══╝        \n"
        "      ██║     ╚██████╔╝╚██████╗██║  ██╗    ╚██████╗   ██║   ██║           \n"
        "      ╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝     ╚═════╝   ╚═╝   ╚═╝           \n"
    )

    desc = target.get('desc', '-')
    words = []
    line = ""
    for word in desc.split():
        if len(line) + len(word) + 1 > 55:
            words.append(line)
            line = word
        else:
            line += (" " if line else "") + word
    if line:
        words.append(line)

    details = f"  Description   : {words[0]}" if words else "  Description   : -"
    for i in range(1, len(words)):
        details += f"\n                  {words[i]}"

    path = target.get('dir')
    display = path if path and path != '-' else "Black-box challenge"

    info_lines = [
        f"  Category      : {str(target.get('category', '-')).capitalize()}",
        details,
    ]
    if target.get('host'):
        info_lines.append(f"  Host          : {target['host']}")
    if target.get('port'):
        info_lines.append(f"  Port          : {target['port']}")
        
    info_lines.extend([
        f"  Directory     : {display}",
        f"  Time          : {minutes} minutes"
    ])
    
    info = "\n".join(info_lines)

    content = Text(art, style="bold cyan") + Text("\n") + Text(info)
    
    from rich import box
    panel = Panel(
        content,
        width=78,
        border_style="cyan",
        padding=(0, 0),
        box=box.DOUBLE
    )
    console.print(panel)

_first_node = True
_current_color = "blue"

# Print timeline node
def node(title, right, color="blue"):
    global _first_node, _current_color
    if not _first_node:
        console.print(Text("│", style="bold blue"))
    _first_node = False
    _current_color = color
    
    left_part = Text(f"● {title}", style=f"bold {color}")
    right_part = Text(right, style="dim white")
    
    spaces = 78 - len(left_part.plain) - len(right_part.plain)
    if spaces < 0:
        spaces = 1
        
    line = left_part + Text(" " * spaces) + right_part
    console.print(line)

import textwrap

# Print timeline line
def line(content, tree="│", color=None):
    global _current_color
    use_color = color if color else _current_color

    if content is None:
        console.print(Text("│", style="bold blue"))
        return
        
    for line_text in content.split("\n"):
        if line_text.lstrip().startswith("├─ ") or line_text.lstrip().startswith("└─ "):
            pos = line_text.find("─ ") + 2
            sub_indent = " " * pos
        else:
            sub_indent = " " * (len(line_text) - len(line_text.lstrip()))
            
        import shutil
        term = shutil.get_terminal_size().columns
        wrap = min(term - 10, 65) if term > 20 else 65
        wrapped = textwrap.wrap(line_text, width=wrap, subsequent_indent=sub_indent, drop_whitespace=False)
        
        prefix = f"{tree}  " if tree else "   "
        
        if not wrapped:
            console.print(Text(prefix, style="bold blue"))
            continue
            
        for chunk in wrapped:
            console.print(Text(prefix, style="bold blue") + Text(chunk, style=f"bold {use_color}"))

# Print error message
def error(msg):
    global _current_color
    console.print(Text("│  ", style="bold blue") + Text(f"[Error]: {msg}", style="bold red"))

# Print CLI footer
def footer(flag, elapsed):
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    
    time_text = ""
    if minutes > 0:
        time_text += f"{minutes} minute{'s' if minutes > 1 else ''} "
    time_text += f"{seconds} second{'s' if seconds > 1 else ''}"

    content = (
        f"\n"
        f"  Flag: {flag}\n"
        f"  Time: {time_text}\n"
    )
    
    panel = Panel(
        Text(content, style="bold green"),
        width=78,
        border_style="green",
        padding=(0, 0)
    )
    console.print(panel)

# Format elapsed time
def clock(seconds):
    if seconds < 0:
        seconds = 0
    return f"{seconds:.1f}s"
