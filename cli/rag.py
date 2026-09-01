from .core import line, error, node, clock

# Log database error
def db(err):
    error(f"Memory DB: {err}")

# Log retrieval error
def retrieve(elapsed, err):
    node("Retrieving...", clock(elapsed), "blue")
    error(str(err))

# Log search start
def search():
    line("├─ Searching...")

# Log search complete
def done():
    line("│  └─ Completed!")

# Log web query
def duckduckgo(query):
    line(f"│  │  ├─ DuckDuckGo: {query}")

# Log GitHub issue
def issue(url):
    line(f"│  │  ├─ Github: {url}")

# Log URL scrape
def firecrawl(url):
    line(f"│  │  ├─ Firecrawl: {url}")

# Log API retry
def retry(attempt, retries):
    line(f"│  │  ├─ Firecrawl retry: {attempt}/{retries}")

# Log search error
def fail(source, msg):
    line(f"│  │  ├─ {source}: {msg}")
