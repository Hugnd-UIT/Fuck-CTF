from .core import line, error, node, clock

_is_last = False

def set_last(last: bool = False):
    global _is_last
    _is_last = last

# Log database error
def db(err):
    error(f"Memory DB: {err}")

# Log retrieval error
def retrieve(elapsed, err):
    node("Retrieving...", clock(elapsed), "blue")
    error(str(err))

# Log search start
def search():
    pass

# Log search complete
def done():
    tree = "" if _is_last else "│"
    line("   └─ Completed!", tree=tree)

# Log web query
def duckduckgo(query):
    tree = "" if _is_last else "│"
    line(f"   ├─ DuckDuckGo: {query}", tree=tree)

# Log URL scrape
def firecrawl(url):
    tree = "" if _is_last else "│"
    display_url = url if len(url) <= 70 else url[:67] + "..."
    line(f"   ├─ Firecrawl: {display_url}", tree=tree)

# Log API retry
def retry(attempt, retries):
    tree = "" if _is_last else "│"
    line(f"   ├─ Firecrawl retry: {attempt}/{retries}", tree=tree)

# Log search error
def fail(source, msg):
    tree = "" if _is_last else "│"
    line(f"   ├─ {source}: {msg}", tree=tree)