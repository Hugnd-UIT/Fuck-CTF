import os
import json
import urllib.request
from typing import Optional
import time
import cli.rag as rag_ui

URL = "https://api.firecrawl.dev/v1/scrape"

# Scrape URL via Firecrawl
def scrape(target: str) -> tuple[Optional[str], Optional[str]]:
    api_key = os.environ.get('FIRECRAWL_API_KEY')
    if not api_key:
        return None, "MISSING_API_KEY"

    payload = json.dumps({
        "url": target,
        "formats": ["markdown"]
    }).encode("utf-8")

    # Configure retries
    retries = 3

    for attempt in range(retries):
        req = urllib.request.Request(
            URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0"
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

                # Handle successful response
                if data.get("success"):
                    rag_ui.firecrawl(target)
                    return data.get("data", {}).get("markdown"), None

                rag_ui.fail('Firecrawl error', 'API error')
                return None, "API_ERR"

        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < retries - 1:
                rag_ui.retry(attempt + 1, retries - 1)
                time.sleep(2 ** attempt)
                continue

            rag_ui.fail('Firecrawl error', f"HTTP {err.code}")
            return None, str(err.code)

        except Exception as err:
            rag_ui.fail('Firecrawl error', f"{type(err).__name__}")
            return None, type(err).__name__

    rag_ui.fail('Firecrawl error', 'HTTP 429')
    return None, "429"