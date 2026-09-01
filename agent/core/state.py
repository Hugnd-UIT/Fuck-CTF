import re

history = []
compressed = ""
tree = {}
hashes = set()
fails = {}
attempts = {}
store = {}
alerts = []
locked = set()
seen = {}
done = []

def init(playbook):
    # Initialize state
    global tree
    
    stage = "Reconnaissance"
    next_steps = ["Follow workflow in the playbook!"]

    tree = {
        "stage": stage,
        "done": [],
        "findings": ["Initial target mapped"],
        "next": next_steps,
        "failed": []
    }

def normalize(text: str) -> str:
    # Normalize text
    norm = re.sub(r"\s+", " ", text)
    return norm.strip().lower()

def absorb(data: dict):
    # Absorb new data
    if not isinstance(data, dict):
        return
    for k, v in data.items():
        if str(v).startswith("OVERRIDE:"):
            real = v[len("OVERRIDE:"):]
            store[k] = real
            locked.discard(k)
            seen[k] = 1
        elif k not in store or store[k] is None:
            store[k] = v
            seen[k] = 1
        elif store[k] == v:
            count = seen.get(k, 1) + 1
            seen[k] = count
            if count >= 2:
                locked.add(k)

_NOISE = {"path", "binary", "filename", "file", "dir"}

def diff(data: dict) -> list:
    # Detect data changes
    out = []
    if not isinstance(data, dict):
        return out
    for k, v in data.items():
        if str(v).startswith("OVERRIDE:"):
            continue
        # Skip path changes
        if any(noise in k.lower() for noise in _NOISE):
            continue
        old = store.get(k)
        if old is None or old == v:
            continue
        level = "CRITICAL" if k in locked else "WARNING"
        out.append(
            f"[{level}] CONTRADICTION: '{k}' was '{old}', "
            f"now '{v}'. Session-state may have changed!"
        )
    return out

def guard() -> list:
    # Monitor state regressions
    out = []
    dn = tree.get("done", [])
    if isinstance(dn, list) and done:
        missing = set(done) - set(dn)
        if missing:
            out.append(
                f"[WARNING] done list shrunk: {len(missing)} item(s) "
                f"lost: {list(missing)[:3]}. "
                "New server connection reset the state!"
            )
    return out

def snap():
    # Snapshot completed tasks
    global done
    dn = tree.get("done", [])
    if isinstance(dn, list):
        done = list(set(done) | set(dn))
