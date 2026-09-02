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
    global tree
    
    # Set stage
    stage = "Reconnaissance"
    next_steps = ["Follow workflow in the playbook!"]

    # Init tree
    tree = {
        "stage": stage,
        "done": [],
        "findings": ["Initial target mapped"],
        "next": next_steps,
        "failed": []
    }

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
                f"lost: {list(missing)[:3]}. "
                "New server connection reset the state!"
            )
    return out

def snap():
    global done
    
    # Snapshot state
    dn = tree.get("done", [])
    if isinstance(dn, list):
        done = list(set(done) | set(dn))
