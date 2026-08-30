import hashlib
from duckduckgo_search import DDGS
from .firecrawl import scrape
import concurrent.futures

def search_web(query: str, max_results: int = 5) -> dict:
    print(f"[RAG-WEB] Searching DuckDuckGo for: {query}")
    try:
        results = DDGS().text(query, max_results=max_results)
        urls = [r.get("href") for r in results if r.get("href")]
    except Exception as e:
        print(f"[RAG-WEB] DDGS Search failed: {e}")
        return {"error": str(e)}

    if not urls:
        return {"error": "No URLs found from DuckDuckGo"}

    total_chunks = 0
    knowledge_preview = ""
    docs = []
    doc_ids = []

    def scrape_job(url):
        print(f"[RAG-WEB] Scraping URL: {url}")
        md_text, err = scrape(url)
        if md_text:
            chunks = [md_text[i:i+2000] for i in range(0, len(md_text), 2000)]
            ids = [f"web_{hashlib.md5((url + str(i)).encode()).hexdigest()}" for i in range(len(chunks))]
            return chunks, ids, md_text
        return [], [], ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_results) as executor:
        scrape_results = list(executor.map(scrape_job, urls))

    for chunks, ids, md_text in scrape_results:
        if chunks:
            docs.extend(chunks)
            doc_ids.extend(ids)
            total_chunks += len(chunks)
            if not knowledge_preview:
                knowledge_preview = md_text[:1500] + "...[truncated]"

    return {
        "docs": docs,
        "ids": doc_ids,
        "total_chunks": total_chunks,
        "preview": knowledge_preview
    }
