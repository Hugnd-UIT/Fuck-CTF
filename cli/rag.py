from .core import line, error, node, clock

def dberr(err):
    error(f"Memory DB: {err}")

def geterr(elapsed, err):
    node("Retrieving...", clock(elapsed), "blue")
    error(str(err))

def search():
    line("├─ Searching...")

def done():
    line("│  └─ Completed!")

def ddg(query):
    line(f"│  │  ├─ DuckDuckGo: {query}")

def ddgerr(err):
    line(f"│  │  ├─ DuckDuckGo error: {err}")

def ddgno():
    line("│  │  ├─ DuckDuckGo: No URLs found")

def gh(url):
    line(f"│  │  ├─ Github: {url}")

def gherr(err):
    line(f"│  │  ├─ Github error: {err}")

def ghserr(err):
    line(f"│  │  ├─ Github search: {err}")

def fc(url):
    line(f"│  │  ├─ Firecrawl: {url}")

def fcerr(err):
    line(f"│  │  ├─ Firecrawl error: {err}")

def fcretry(attempt, retries):
    line(f"│  │  ├─ Firecrawl retry: {attempt}/{retries}")
