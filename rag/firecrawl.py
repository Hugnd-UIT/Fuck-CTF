import os
import json
import urllib.request
from typing import Optional
import time

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
                    print(f"  ✓ Firecrawl  : {target}")
                    return data.get("data", {}).get("markdown"), None

                print("  ✗ Firecrawl  : API error")
                return None, "API_ERR"

        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < retries - 1:
                print(
                    f"  ↻ Firecrawl  : retry "
                    f"{attempt + 1}/{retries - 1}"
                )
                time.sleep(2 ** attempt)
                continue

            print(f"  ✗ Firecrawl  : HTTP {err.code}")
            return None, str(err.code)

        except Exception as err:
            print(f"  ✗ Firecrawl  : {type(err).__name__}")
            return None, type(err).__name__

    print("  ✗ Firecrawl  : HTTP 429")
    return None, "429"