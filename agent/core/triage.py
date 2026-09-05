import os


# Calculate directory score
def score(s, files):
    # Filter direct files
    direct = [f for f in files if os.path.dirname(f) == s]
    exts = ('.c', '.cpp', '.py', '.sh', '.bin', '.elf', '.asm')
    bonus = 0

    # Score file types
    for f in direct:
        base = os.path.basename(f)
        _, ext = os.path.splitext(base)
        if base.lower() in ('dockerfile', 'makefile', 'readme', 'readme.md', 'license'):
            bonus += 1
        elif ext in exts:
            bonus += 5
        elif ext == '' and not base.startswith('.'):
            bonus += 10
        else:
            bonus += 1

    # Add directory bonus
    if any(k in s.lower().split('/') for k in ('challenge', 'src', 'app', 'bin')):
        bonus += 3

    return bonus


# Triage challenge directory
def triage(workspace, target_dir):
    # Validate target directory
    work_dir = target_dir if target_dir and target_dir != "-" else "/data"
    if not (target_dir and target_dir != "-" and os.path.exists(workspace)):
        return work_dir, "No local directory or files provided!"

    # Initialize scan filters
    files = []
    ignored = {
        ".git", "__pycache__", "venv", ".venv",
        "env", ".env", "node_modules", "site-packages",
        ".idea", ".vscode"
    }

    # Walk directory tree
    for root, dirs, names in os.walk(workspace):
        dirs[:] = [
            d for d in dirs 
            if d not in ignored 
            and not d.endswith(".dist-info") 
            and not d.endswith(".egg-info")
        ]
        if any(part in ignored or part.endswith(".dist-info") or part.endswith(".egg-info") for part in root.replace("\\", "/").split("/")):
            continue

        # Collect valid files
        for f in names:
            if f == ".gitignore" or f.endswith(".pyc") or f.endswith(".pyo"):
                continue
            rel = os.path.relpath(os.path.join(root, f), workspace).replace("\\", "/")
            files.append(rel)

    # Check empty files
    if not files:
        return work_dir, "No local directory or files provided!"

    # Select best subdirectory
    if work_dir == "/data":
        subdirs = set()
        for f in files:
            if "/" in f:
                subdirs.add(os.path.dirname(f).replace("\\", "/"))
        if subdirs:
            best = max(subdirs, key=lambda s: score(s, files))
            work_dir = f"/data/{best}"

    # Build environment summary
    file_list = "\n".join(f"- /data/{f}" for f in files)
    env_str = f"Workspace challenge working directory: {work_dir}\nAll files in container (/data):\n{file_list}"

    return work_dir, env_str