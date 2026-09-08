import os
import time
import hashlib
import concurrent.futures
import chromadb
import cli.rag as rag_ui
from rag.duckduckgo import search_web

client = None
memory = None
knowledge = None
_model = None

def init(model=None):
    # Initialize databases
    global client, memory, knowledge, _model
    _model = model
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
        know = knowledge.query(query_texts=[q], n_results=5)
        if know and "documents" in know and know["documents"] and know["documents"][0]:
            for doc, dist in zip(know["documents"][0], know["distances"][0]):
                if dist < 1.2:
                    snippet = doc[:2000] + ("..." if len(doc) > 2000 else "")
                    memories.append(f"[KNOWLEDGE] {snippet}")
                    if len(memories) >= 6:
                        break
        
    except Exception as e:
        rag_ui.db(e)
        
    return memories[:6]

def execute(subtask, length):
    rag_ui.search()
    start = time.time()
    try:
        # Search web via DuckDuckGo and scrape pages via Firecrawl
        res = search_web(subtask, max_results=5)
        chunks = 0
        preview = "No web results."
        if "docs" in res and res["docs"]:
            knowledge.add(documents=res["docs"], ids=res["ids"])
            chunks = res.get("total_chunks", len(res["docs"]))
            preview = res.get("preview", "")

        rag_ui.done()

        step = f"step_{length + 1}"
        return {
            "step_id": step,
            "tactic": "RAG",
            "plan": subtask,
            "observation": f"Web chunks: {chunks}. Preview: {preview}",
            "result": "success"
        }

    except Exception as e:
        elapsed = time.time() - start
        rag_ui.retrieve(elapsed, e)
        return None