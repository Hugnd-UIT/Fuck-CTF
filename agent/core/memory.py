import os
import time
import hashlib
import concurrent.futures
import chromadb
from timeline import print_node, print_line, print_error, format_time
from rag.github import search_github
from rag.firecrawl import scrape
from rag.duckduckgo import search_web

client = None
memory = None
knowledge = None

def init():
    global client, memory, knowledge
    db = os.path.join(os.getcwd(), "db")
    os.makedirs(db, exist_ok=True)
    client = chromadb.PersistentClient(path=db)
    memory = client.get_or_create_collection(name="memory")
    knowledge = client.get_or_create_collection(name="knowledge")

def query(desc, stage, findings, tasks):
    memories = []
    try:
        parts = [
            desc[:200],
            stage,
            findings[:150],
            tasks[:200]
        ]
        q = " ".join(filter(None, parts)) or "vulnerability exploitation"

        mem = memory.query(query_texts=[q], n_results=3)
        if mem and "documents" in mem and mem["documents"] and mem["documents"][0]:
            for doc in mem["documents"][0]:
                memories.append(f"[PAST_MEMORY] {doc}")

        know = knowledge.query(query_texts=[q], n_results=50)
        if know and "documents" in know and know["documents"] and know["documents"][0]:
            for doc, dist in zip(know["documents"][0], know["distances"][0]):
                if dist < 1.5:
                    memories.append(f"[EXTERNAL_KNOWLEDGE] {doc}")
    except Exception as e:
        print_error(f"Memory DB: {e}")
        
    return memories

def execute(subtask, length):
    start = time.time()
    try:
        def github():
            res = search_github(subtask)
            issues = res.get("github_issues", [])
            chunks = 0
            preview = ""

            if not issues:
                return 0, "No GH issues found."

            def scrape_store(issue):
                url = issue.get("url")
                text, err = scrape(url)
                if text:
                    parts = [text[i:i + 2000] for i in range(0, len(text), 2000)]
                    ids = [f"know_{hashlib.md5((url + str(i)).encode()).hexdigest()}" for i in range(len(parts))]
                    return parts, ids, text
                return [], [], ""

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                results = list(ex.map(scrape_store, issues))

            for parts, ids, text in results:
                if parts:
                    knowledge.add(documents=parts, ids=ids)
                    chunks += len(parts)
                    if not preview:
                        preview = text[:1500]
            return chunks, preview

        def web():
            res = search_web(subtask, max_results=5)
            if "docs" in res and res["docs"]:
                knowledge.add(documents=res["docs"], ids=res["ids"])
                return res["total_chunks"], res["preview"]
            return 0, res.get("error", "No web results.")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_gh = ex.submit(github)
            f_web = ex.submit(web)
            gh_chunks, gh_preview = f_gh.result()
            web_chunks, web_preview = f_web.result()

        elapsed = time.time() - start
        print_node("Retrieving...", format_time(elapsed), "blue")
        print_line("Searching...")
        print_line(f"├─ Github: found {gh_chunks} chunks")
        print_line(f"├─ Web: found {web_chunks} chunks")
        print_line("└─ Saved!")

        step = f"step_{length + 1}"
        return {
            "step_id": step,
            "tactic": "Retrieval-Augmented-Generation",
            "plan": subtask,
            "observation": f"[Knowledge Gathered] Github chunks: {gh_chunks}, Web chunks: {web_chunks}. Preview: {gh_preview or web_preview}",
            "result": "success"
        }
    except Exception as e:
        elapsed = time.time() - start
        print_node("Retrieving...", format_time(elapsed), "blue")
        print_error(str(e))
        return None
