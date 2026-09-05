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
        "                                                                          \n"
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
_last_node = ""
_last_right = ""

# Print timeline node
def node(title, right="", color="blue"):
    global _first_node, _current_color, _last_node, _last_right
    
    if _last_node == title and _last_right == right:
        return
        
    if not _first_node:
        console.print(Text("│", style=f"bold {_current_color}"))
    _first_node = False
    _current_color = color
    _last_node = title
    _last_right = right
    
    left_part = Text(f"● {title}", style=f"bold {color}")
    right_part = Text(right, style="dim white")
    
    spaces = 78 - len(left_part.plain) - len(right_part.plain)
    if spaces < 0:
        spaces = 1
        
    line = left_part + Text(" " * spaces) + right_part
    console.print(line)

import textwrap

_last_was_empty = False

# Print timeline line
def line(content=None, tree="│", color=None):
    global _current_color, _last_was_empty
    use_color = color if color else _current_color

    if content is None or content == "" or content == "│":
        if _last_was_empty:
            return
        _last_was_empty = True
        prefix = f"{tree}  │" if tree else "   │"
        console.print(Text(prefix, style=f"bold {use_color}"))
        return

    _last_was_empty = False
        
    import shutil
    term = shutil.get_terminal_size().columns
    wrap = min(term - 10, 65) if term > 20 else 65

    base = ""
    for i, text in enumerate(content.split("\n")):
        if "├─ " in text or "└─ " in text or text.startswith("│  "):
            if "─ " in text:
                pos = text.find("─ ") + 2
                pref = text[:pos]
                base = pref.replace("├─ ", "│  ").replace("└─ ", "   ")
            else:
                pos = 3
                pref = "│  "
                base = "│  "
            
            # Extract the actual text body
            body = text[pos:]
            
            # Wrap just the body
            wrapped_body = textwrap.wrap(body, width=wrap - len(pref), drop_whitespace=False)
            if not wrapped_body:
                wrapped = [pref]
            else:
                wrapped = [pref + wrapped_body[0]]
                for chunk in wrapped_body[1:]:
                    wrapped.append(base + chunk.lstrip())
        else:
            if i == 0:
                base = " " * (len(text) - len(text.lstrip()))
            
            body = text.lstrip()
            if body:
                wrapped_body = textwrap.wrap(body, width=wrap - len(base), drop_whitespace=False)
                wrapped = [base + chunk.lstrip() for chunk in wrapped_body]
            else:
                wrapped = [base]
        
        prefix = f"{tree}  " if tree else "   "
        
        for chunk in wrapped:
            console.print(Text(prefix, style=f"bold {use_color}") + Text(chunk, style=f"bold {use_color}"))

# Print error message
def error(msg):
    global _current_color
    console.print(Text("│  ", style=f"bold {_current_color}") + Text(f"[Error]: {msg}", style="bold red"))

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