import re

history = []
compressed = ""
tree = {}
nodes = {}
hashes = set()
fails = {}
attempts = {}
store = {}
alerts = []
locked = set()
seen = {}
done = []

def init(playbook):
    global tree, nodes, store, done, fails, attempts, alerts, locked, seen
    
    # Set stage
    stage = "Reconnaissance"
    step = ["Follow workflow in the playbook!"]

    # Init tree
    tree = {
        "stage": stage,
        "done": [],
        "findings": ["Initial target mapped"],
        "next": step,
        "failed": [],
        "data": {}
    }
    nodes = {}
    done = []

def link(task: str, kind: str = "task", parent: str = None, status: str = "todo", data: dict = None) -> str:
    global nodes
    if not task:
        return ""
    # Link node
    node = str(len(nodes) + 1)
    nodes[node] = {
        "id": node,
        "task": task,
        "kind": kind,
        "parent": parent,
        "status": status,
        "data": data or {}
    }
    return node

def update(task: str, status: str, data: dict = None):
    global tree, nodes
    if not task:
        return
    # Find node
    hit = None
    for item in nodes.values():
        if item.get("task") == task:
            hit = item
            break
    if not hit:
        link(task=task, status=status, data=data)
    else:
        hit["status"] = status
        if data:
            hit.setdefault("data", {}).update(data)

    # Update tree status
    if status in ("done", "pass", "success"):
        if task not in tree["done"]:
            tree["done"].append(task)
        if task in tree.get("next", []):
            tree["next"].remove(task)
    elif status == "fail":
        if task not in tree["failed"]:
            tree["failed"].append(task)
    if data:
        tree.setdefault("data", {}).update(data)
        absorb(data)

def merge(new_tree: dict):
    global tree
    if not isinstance(new_tree, dict):
        return

    # Merge stage
    stage = new_tree.get("stage")
    if stage:
        tree["stage"] = stage

    # Merge done
    raw_done = new_tree.get("done", [])
    if isinstance(raw_done, list):
        for item in raw_done:
            if item and item not in tree["done"]:
                tree["done"].append(item)

    # Merge findings
    raw_find = new_tree.get("findings", [])
    if isinstance(raw_find, list):
        for item in raw_find:
            if item and item not in tree["findings"]:
                tree["findings"].append(item)

    # Merge failed
    raw_fail = new_tree.get("failed", [])
    if isinstance(raw_fail, list):
        for item in raw_fail:
            if item and item not in tree["failed"]:
                tree["failed"].append(item)

    # Merge next
    raw_next = new_tree.get("next", [])
    if isinstance(raw_next, list):
        valid = [item for item in raw_next if item and item not in tree["done"]]
        if valid:
            tree["next"] = valid

    # Merge data
    raw_data = new_tree.get("data", {})
    if isinstance(raw_data, dict):
        tree.setdefault("data", {}).update(raw_data)
        absorb(raw_data)

def normalize(text: str) -> str:
    # Format text
    norm = re.sub(r"\s+", " ", text)
    return norm.strip().lower()

def absorb(data: dict):
    if not isinstance(data, dict):
        return
        
    # Process data
    for k, v in data.items():
        # Handle override
        if str(v).startswith("OVERRIDE:"):
            real = v[len("OVERRIDE:"):]
            store[k] = real
            locked.discard(k)
            seen[k] = 1
        # Store data
        elif k not in store or store[k] is None:
            store[k] = v
            seen[k] = 1
        # Lock confirmed
        elif store[k] == v:
            count = seen.get(k, 1) + 1
            seen[k] = count
            if count >= 2:
                locked.add(k)

_NOISE = {"path", "binary", "filename", "file", "dir"}

def diff(data: dict) -> list:
    out = []
    if not isinstance(data, dict):
        return out
        
    # Check changes
    for k, v in data.items():
        # Ignore noise
        if str(v).startswith("OVERRIDE:"):
            continue
        if any(noise in k.lower() for noise in _NOISE):
            continue
            
        # Check contradiction
        old = store.get(k)
        if old is None or old == v:
            continue
        if normalize(str(old)) == normalize(str(v)):
            continue
            
        # Flag changes
        level = "CRITICAL" if k in locked else "WARNING"
        out.append(
            f"[{level}] CONTRADICTION: '{k}' was '{old}', "
            f"now '{v}'. Session-state may have changed!"
        )
    return out

def guard() -> list:
    out = []
    
    # Check regression
    dn = tree.get("done", [])
    if isinstance(dn, list) and done:
        missing = set(done) - set(dn)
        if missing:
            out.append(
                f"[WARNING] done list shrunk: {len(missing)} item(s) "
                f"lost: {list(missing)[:3]}."
            )
    return out

def snap():
    global done
    
    # Snapshot state
    dn = tree.get("done", [])
    if isinstance(dn, list):
        done = list(dict.fromkeys(done + dn))

def view() -> str:
    # Format view
    lines = [f"Stage: {tree.get('stage', 'Unknown')}"]
    lines.append("Done: " + (", ".join(tree.get("done", [])) or "None"))
    lines.append("Next: " + (", ".join(tree.get("next", [])) or "None"))
    lines.append("Failed: " + (", ".join(tree.get("failed", [])) or "None"))
    facts = tree.get("data", {})
    if facts:
        lines.append("Facts: " + str(facts))
    return "\n".join(lines)

def get_slim_store(max_val_len: int = 8000) -> dict:
    slim = {}
    for k, v in store.items():
        s = str(v)
        limit = max_val_len if not any(w in k.lower() for w in ("inspect", "source", "code", "file")) else 15000
        if len(s) > limit:
            slim[k] = s[:limit] + "...[truncated]"
        else:
            slim[k] = v
    return slim

def prune_store():
    global store
    for k in list(store.keys()):
        val_str = str(store[k])
        limit = 15000 if any(w in k.lower() for w in ("inspect", "source", "code", "env", "file")) else 4000
        if len(val_str) > limit:
            store[k] = val_str[:limit] + "\n...[truncated]"

