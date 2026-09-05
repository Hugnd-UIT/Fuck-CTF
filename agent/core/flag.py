import re


def sniff(out, target):
    # Check output
    if not out or not isinstance(out, str):
        return None

    # Get expected flag
    expected = target.get("flag", "") if isinstance(target, dict) else ""
    prefix = ""
    if expected and "{" in expected:
        prefix = expected.split("{")[0] + "{"

    # Build patterns
    pats = []
    if prefix:
        pats.append(re.escape(prefix) + r"[A-Za-z0-9_\-!@#$%^&*+=?.,:]+\}")
    pats.extend([
        r"(?:HTB|flag|CTF|picoCTF|DUCTF|CSCG|seccon|hitcon)\{[A-Za-z0-9_\-!@#$%^&*+=?.,:]+\}",
        r"[A-Za-z0-9_]{3,15}\{[A-Za-z0-9_\-!@#$%^&*+=?.,:]+\}"
    ])

    # Search patterns
    for pat in pats:
        for hit in re.findall(pat, out, re.IGNORECASE):
            lower = hit.lower()
            skip = any(w in lower for w in ("dummy", "test", "fake", "local", "placeholder", "example", "mock"))
            if expected:
                if prefix and not hit.startswith(prefix):
                    skip = True
                if hit == expected and any(c in expected for c in ("*", "?", "...")):
                    skip = True
            if not skip:
                return hit

    return None


def valid(flag, target, state=None):
    # Check flag
    if not flag or not isinstance(flag, str):
        return False

    # Filter fake flags
    lower = flag.lower()
    skip = any(w in lower for w in ("dummy", "test", "fake", "local", "placeholder", "example"))
    if skip:
        return False

    # Check expected flag
    expected = target.get("flag", "") if isinstance(target, dict) else ""
    
    if expected:
        if "{" in expected:
            prefix = expected.split("{")[0] + "{"
            
            if not flag.startswith(prefix):
                
                if state:
                    state.absorb({"Invalid": f"The flag '{flag}' is INVALID. It must start with '{prefix}'!"})
                return False
        
        if flag == expected and any(c in expected for c in ("*", "?", "...")):
            
            if state:
                state.absorb({"Invalid": f"The flag '{flag}' is INVALID. You printed the placeholder instead of the real flag!"})
            return False
        
        if flag == expected and not any(c in expected for c in ("*", "?", "...")):
            pass
        
        elif flag == expected:
            if state:
                state.absorb({"Invalid": f"The flag '{flag}' is INVALID. You printed the placeholder instead of the real flag!"})
            return False

    return True