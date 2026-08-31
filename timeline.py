import re
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.style import Style

console = Console()

def print_header(target, minutes):
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

    info = (
        f"  Category      : {str(target.get('category', '-')).capitalize()}\n"
        f"{details}\n"
        f"  Host          : {target.get('host', '-')}\n"
        f"  Port          : {target.get('port', '-')}\n"
        f"  Directory     : {target.get('dir', '-')}\n"
        f"  Time          : {minutes} minutes"
    )

    content = Text(art, style="bold cyan") + Text("\n") + Text(info)
    
    panel = Panel(
        content,
        width=78,
        border_style="cyan",
        padding=(0, 0)
    )
    console.print(panel)

def print_node(title, right, color="blue"):
    left_part = Text(f"● {title}", style=f"bold {color}")
    right_part = Text(right, style="dim white")
    
    spaces = 78 - len(left_part.plain) - len(right_part.plain)
    if spaces < 0:
        spaces = 1
        
    line = left_part + Text(" " * spaces) + right_part
    console.print(line)

import textwrap

def print_line(content, tree="│", color="blue"):
    if content is None:
        console.print(Text("│", style=f"bold {color}"))
        return
        
    for line in content.split("\n"):
        if line.lstrip().startswith("├─ ") or line.lstrip().startswith("└─ "):
            pos = line.find("─ ") + 2
            sub_indent = " " * pos
        else:
            sub_indent = " " * (len(line) - len(line.lstrip()))
            
        wrapped = textwrap.wrap(line, width=74, subsequent_indent=sub_indent)
        
        if not wrapped:
            console.print(Text("│  ", style=f"bold {color}"))
            continue
            
        for chunk in wrapped:
            console.print(Text(f"│  {chunk}", style=f"bold {color}"))

def print_error(msg):
    console.print(Text(f"│  [Error]: {msg}", style="bold red"))

def print_footer(flag, elapsed):
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

def format_time(seconds):
    if seconds < 0:
        seconds = 0
    return f"{seconds:.1f}s"
