import hashlib
from ddgs import DDGS
from .firecrawl import scrape
import concurrent.futures
import cli.rag as rag_ui
_search_cache = {}

def search_web(query: str, max_results: int = 5) -> dict:
    # Check cache
    if query in _search_cache:
        return _search_cache[query]

    # Log query
    rag_ui.duckduckgo(query)

    try:
        # Perform search
        results = DDGS().text(query, max_results=max_results)
        urls = [r.get("href") for r in results if r.get("href")]
    except Exception as e:
        # Handle error
        rag_ui.fail('DuckDuckGo error', e)
        return {"error": str(e)}

    # Check empty
    if not urls:
        rag_ui.fail('DuckDuckGo', 'No URLs found')
        return {"error": "No URLs found from DuckDuckGo"}

    total_chunks = 0
    knowledge_preview = ""
    docs = []
    doc_ids = []

    # Scrape search results
    def scrape_web(url):
        md_text, err = scrape(url)

        if md_text:
            # Split content into chunks
            chunks = [
                md_text[i:i + 2000]
                for i in range(0, len(md_text), 2000)
            ]

            # Generate document IDs
            ids = [
                f"web_{hashlib.md5((url + str(i)).encode()).hexdigest()}"
                for i in range(len(chunks))
            ]

            return chunks, ids, md_text

        return [], [], ""

    # Scrape URLs concurrently
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_results
    ) as executor:
        scrape_results = list(executor.map(scrape_web, urls))

    # Collect scraped documents
    for chunks, ids, md_text in scrape_results:
        if chunks:
            docs.extend(chunks)
            doc_ids.extend(ids)
            total_chunks += len(chunks)

            if not knowledge_preview:
                knowledge_preview = md_text[:1500] + "...[truncated]"

    res = {
        "docs": docs,
        "ids": doc_ids,
        "total_chunks": total_chunks,
        "preview": knowledge_preview
    }
    _search_cache[query] = res
    return res