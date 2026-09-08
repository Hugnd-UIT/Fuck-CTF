from .core import line, error, node, clock

_last_empty = False

def empty_line():
    global _last_empty
    if _last_empty:
        return
    _last_empty = True
    from . import core
    from rich.text import Text
    core.console.print(Text("│  │  │", style=f"bold {core._current_color}"))

# Log database error
def db(err):
    error(f"Memory DB: {err}")

# Log retrieval error
def retrieve(elapsed, err):
    node("Retrieving...", clock(elapsed), "blue")
    error(str(err))

# Log search start
def search():
    global _last_empty
    _last_empty = False
    empty_line()

# Log search complete
def done():
    global _last_empty
    _last_empty = False
    line("│  └─ Completed!")

# Log web query
def duckduckgo(query):
    global _last_empty
    _last_empty = False
    line(f"│  ├─ DuckDuckGo: {query}")
    empty_line()

# Log URL scrape
def firecrawl(url):
    global _last_empty
    _last_empty = False
    display_url = url if len(url) <= 70 else url[:67] + "..."
    line(f"│  ├─ Firecrawl: {display_url}")
    empty_line()

# Log API retry
def retry(attempt, retries):
    global _last_empty
    _last_empty = False
    line(f"│  ├─ Firecrawl retry: {attempt}/{retries}")
    empty_line()

# Log search error
def fail(source, msg):
    global _last_empty
    _last_empty = False
    line(f"│  ├─ {source}: {msg}")
    empty_line()