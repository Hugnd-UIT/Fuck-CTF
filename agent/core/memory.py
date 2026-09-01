import os
import time
import hashlib
import concurrent.futures
import chromadb
import cli.rag as rag_ui
from rag.github import search_github
from rag.firecrawl import scrape
from rag.duckduckgo import search_web

client = None
memory = None
knowledge = None

def init():
    # Initialize databases
    global client, memory, knowledge
    db = os.path.join(os.getcwd(), "db")
    os.makedirs(db, exist_ok=True)
    client = chromadb.PersistentClient(path=db)
    memory = client.get_or_create_collection(name="memory")
    knowledge = client.get_or_create_collection(name="knowledge")

def query(desc, stage, findings, tasks):
    memories = []
    try:
        # Format query parts
        parts = [
            desc[:200],
            stage,
            findings[:150],
            tasks[:200]
        ]
        q = " ".join(filter(None, parts)) or "vulnerability exploitation"

        # Query past memory
        mem = memory.query(query_texts=[q], n_results=3)
        if mem and "documents" in mem and mem["documents"] and mem["documents"][0]:
            for doc in mem["documents"][0]:
                memories.append(f"[MEMORY] {doc}")

        # Query external knowledge
        know = knowledge.query(query_texts=[q], n_results=50)
        if know and "documents" in know and know["documents"] and know["documents"][0]:
            for doc, dist in zip(know["documents"][0], know["distances"][0]):
                if dist < 1.5:
                    memories.append(f"[KNOWLEDGE] {doc}")
    except Exception as e:
        rag_ui.db(e)
        
    return memories

def execute(subtask, length):
    rag_ui.search()
    start = time.time()
    try:
        # Search GitHub issues
        def github():
            res = search_github(subtask)
            issues = res.get("github_issues", [])
            chunks = 0
            preview = ""

            if not issues:
                return 0, "No issues found."

            # Scrape issue content
            def scrape_store(issue):
                url = issue.get("url")
                text, err = scrape(url)
                if text:
                    parts = [text[i:i + 2000] for i in range(0, len(text), 2000)]
                    ids = [f"know_{hashlib.md5((url + str(i)).encode()).hexdigest()}" for i in range(len(parts))]
                    return parts, ids, text
                return [], [], ""

            # Run scrapers concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                results = list(ex.map(scrape_store, issues))

            # Store scraped knowledge
            for parts, ids, text in results:
                if parts:
                    knowledge.add(documents=parts, ids=ids)
                    chunks += len(parts)
                    if not preview:
                        preview = text[:1500]
            return chunks, preview

        # Search DuckDuckGo
        def web():
            res = search_web(subtask, max_results=5)
            if "docs" in res and res["docs"]:
                knowledge.add(documents=res["docs"], ids=res["ids"])
                return res["total_chunks"], res["preview"]
            return 0, res.get("error", "No web results.")

        # Run tasks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_gh = ex.submit(github)
            f_web = ex.submit(web)
            gh_chunks, gh_preview = f_gh.result()
            web_chunks, web_preview = f_web.result()

        rag_ui.done()

        step = f"step_{length + 1}"
        return {
            "step_id": step,
            "tactic": "RAG",
            "plan": subtask,
            "observation": f"Github chunks: {gh_chunks}, Web chunks: {web_chunks}. Preview: {gh_preview or web_preview}",
            "result": "success"
        }
    except Exception as e:
        elapsed = time.time() - start
        rag_ui.retrieve(elapsed, e)
        return None
