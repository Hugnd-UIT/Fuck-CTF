import sys
import shutil
import re
import textwrap

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.style import Style
from rich import box

console = Console(legacy_windows=False)

def get_terminal_width():
    term = shutil.get_terminal_size().columns
    if term <= 20:
        return 78
    return max(60, min(term - 2, 78))

def get_wrap_width():
    return get_terminal_width() - 3

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
    line_buf = ""
    for word in desc.split():
        if len(line_buf) + len(word) + 1 > 55:
            words.append(line_buf)
            line_buf = word
        else:
            line_buf += (" " if line_buf else "") + word
    if line_buf:
        words.append(line_buf)

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
    
    width = get_terminal_width()
    panel = Panel(
        content,
        width=width,
        border_style="cyan",
        padding=(0, 0),
        box=box.DOUBLE
    )
    console.print(panel)

_first_node = True
_current_color = "blue"
_last_node = None

# Print timeline node
def node(title, right="", color="blue"):
    global _first_node, _current_color, _last_node
    
    node_key = f"{title}_{right}"
    if _last_node == node_key:
        return
        
    if not _first_node:
        console.print(Text("│", style=f"bold {_current_color}"))
    _first_node = False
    _current_color = color
    _last_node = node_key
    
    target_width = get_terminal_width()
    left_part = Text(f"● {title}", style=f"bold {color}")
    right_part = Text(right, style="dim white")
    
    spaces = target_width - len(left_part.plain) - len(right_part.plain)
    if spaces < 1:
        spaces = 1
        
    line_text = left_part + Text(" " * spaces) + right_part
    console.print(line_text)

_last_was_empty = False

# Print empty branch line
def empty_line():
    global _last_was_empty, _current_color
    if _last_was_empty:
        return
    _last_was_empty = True
    console.print(Text("│  ", style=f"bold {_current_color}") + Text("│", style=f"bold {_current_color}"))

# Print timeline line
def line(content=None, tree="│", color=None):
    global _current_color, _last_was_empty, _last_node
    use_color = color if color else _current_color

    if content is None or content == "" or content == "│":
        if _last_was_empty:
            return
        _last_was_empty = True
        prefix = f"{tree}" if tree else ""
        console.print(Text(prefix, style=f"bold {use_color}"))
        return

    _last_was_empty = False
    _last_node = None
        
    wrap = get_wrap_width()

    base = ""
    for i, text in enumerate(content.split("\n")):
        if "├─ " in text or "└─ " in text or "│  " in text:
            if "─ " in text:
                pos = text.find("─ ") + 2
                pref = text[:pos]
                base = pref.replace("├─ ", "│  ").replace("└─ ", "   ")
            else:
                pos = text.find("│  ") + 3
                pref = text[:pos]
                base = pref
            
            # Extract the actual text body
            body = text[pos:]
            wrap_sub = max(30, wrap - len(pref))
            
            # Wrap just the body
            wrapped_body = textwrap.wrap(body, width=wrap_sub, drop_whitespace=False)
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
                wrap_sub = max(30, wrap - len(base))
                wrapped_body = textwrap.wrap(body, width=wrap_sub, drop_whitespace=False)
                wrapped = [base + chunk.lstrip() for chunk in wrapped_body]
            else:
                wrapped = [base]
        
        prefix = f"{tree}  " if tree else "   "
        
        for chunk in wrapped:
            console.print(Text(prefix, style=f"bold {use_color}") + Text(chunk, style=f"bold {use_color}"))

# Print error message
def error(msg):
    global _current_color
    line(f"└─ [Error]: {msg}", color="red")

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
    
    width = get_terminal_width()
    panel = Panel(
        Text(content, style="bold green"),
        width=width,
        border_style="green",
        padding=(0, 0),
        box=box.ROUNDED
    )
    console.print(panel)

# Format elapsed time
def clock(seconds):
    if seconds < 0:
        seconds = 0
    return f"{seconds:.1f}s"