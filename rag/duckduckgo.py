import hashlib
from ddgs import DDGS
from .firecrawl import scrape
import concurrent.futures
import cli.rag as rag_ui

_search_cache = {}

def search_web(query: str, results: int = 5) -> dict:
    
    # Check cache
    if query in _search_cache:
        return _search_cache[query]

    rag_ui.duckduckgo(query)

    try:
        results = DDGS().text(query, max_results=results)
        urls = [r.get("href") for r in results if r.get("href")]
    except Exception as e:
        rag_ui.fail('DuckDuckGo error', e)
        return {"error": str(e)}

    # Check empty
    if not urls:
        rag_ui.fail('DuckDuckGo', 'No URLs found')
        return {"error": "No URLs found from DuckDuckGo"}

    urls = urls[:results]
    total = 0
    previews = ""
    docs = []
    doc_ids = []

    def scrape_web(url):
        md_text, err = scrape(url)

        if md_text:
            chunks = [
                md_text[i:i + 2000]
                for i in range(0, min(len(md_text), 6000), 2000)
            ]

            ids = [
                f"web_{hashlib.md5((url + str(i)).encode()).hexdigest()}"
                for i in range(len(chunks))
            ]

            return chunks, ids, md_text

        return [], [], ""

    # Scrape URLs
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=results
    ) as executor:
        scrape_results = list(executor.map(scrape_web, urls))

    # Collect results
    for parts, ids, md_text in scrape_results:
        if parts:
            docs.extend(parts)
            doc_ids.extend(ids)
            total += len(parts)

            if not previews:
                previews = md_text[:1500] + "...[truncated]"

    res = {
        "docs": docs,
        "ids": doc_ids,
        "total_chunks": total,
        "chunks": total,
        "preview": previews
    }
    
    _search_cache[query] = res
    return res