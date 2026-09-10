from .core import line, error, node, clock, empty_line

_is_last = False

def set_last(last: bool = False):
    global _is_last
    _is_last = last

def _get_branch_prefix(branch="├─ "):
    parent_bar = "   " if _is_last else "│  "
    return f"{parent_bar}{branch}"

# Log database error
def db(err):
    error(f"Memory DB: {err}")

# Log retrieval error
def retrieve(elapsed, err):
    node("Retrieving...", clock(elapsed), "blue")
    line(f"└─ [Error]: {err}", color="red")

# Log search start
def search():
    pass

# Log search complete
def done():
    line(f"{_get_branch_prefix('└─ ')}Completed!")
    if not _is_last:
        empty_line()

# Log web query
def duckduckgo(query):
    line(f"{_get_branch_prefix('├─ ')}DuckDuckGo: {query}")

# Log URL scrape
def firecrawl(url):
    display_url = url if len(url) <= 70 else url[:67] + "..."
    line(f"{_get_branch_prefix('├─ ')}Firecrawl: {display_url}")

# Log API retry
def retry(attempt, retries):
    line(f"{_get_branch_prefix('├─ ')}Firecrawl retry: {attempt}/{retries}")

# Log search error
def fail(source, msg):
    line(f"{_get_branch_prefix('├─ ')}{source}: {msg}")