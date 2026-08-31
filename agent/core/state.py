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
    tactics = playbook.get("tactics", ["Reconnaissance"])
    stage = tactics[0] if tactics else "Reconnaissance"

    tree = {
        "stage": stage,
        "done": [],
        "findings": ["Initial target mapped"],
        "next": playbook.get("procedure", [])[:2],
        "failed": []
    }

def normalize(text: str) -> str:
    norm = re.sub(r"\s+", " ", text)
    return norm.strip().lower()

def absorb(data: dict):
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

def diff(data: dict) -> list:
    out = []
    if not isinstance(data, dict):
        return out
    for k, v in data.items():
        if str(v).startswith("OVERRIDE:"):
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
    out = []
    dn = tree.get("done", [])
    if isinstance(dn, list) and done:
        missing = set(done) - set(dn)
        if missing:
            out.append(
                f"[WARNING] DONE LIST SHRANK: {len(missing)} item(s) "
                f"vanished: {list(missing)[:3]}. "
                "Likely a new server connection reset state!"
            )
    return out

def snap():
    global done
    dn = tree.get("done", [])
    if isinstance(dn, list):
        done = list(set(done) | set(dn))
