from .core import line, error, node, clock

def db(err):
    error(f"Memory DB: {err}")

def retrieve(elapsed, err):
    node("Retrieving...", clock(elapsed), "blue")
    error(str(err))

def search():
    line("├─ Searching...")

def done():
    line("│  └─ Completed!")

def duckduckgo(query):
    line(f"│  │  ├─ DuckDuckGo: {query}")

def issue(url):
    line(f"│  │  ├─ Github: {url}")

def firecrawl(url):
    line(f"│  │  ├─ Firecrawl: {url}")

def retry(attempt, retries):
    line(f"│  │  ├─ Firecrawl retry: {attempt}/{retries}")

def fail(source, msg):
    line(f"│  │  ├─ {source}: {msg}")
