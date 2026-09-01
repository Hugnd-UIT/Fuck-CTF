def run(sandbox, commands, category, timeout=30):
    output = ""
    for cmd in commands:
        try:
            limit = 3600 if category == "crypto" else 120
            time = min(int(timeout), limit)
        except Exception:
            time = 30

        try:
            wrap = [
                "timeout",
                "--preserve-status",
                "-k",
                "5",
                str(time),
                "/bin/bash",
                "-c",
                cmd
            ]
            res = sandbox.exec_run(wrap, stdout=True, stderr=True)
            out = res.output.decode("utf-8", errors="ignore")

            if res.exit_code == 124:
                out = f"[TIMEOUT] Command exceeded {time}s. Partial output:\n{out}"
        except Exception as e:
            out = f"[TIMEOUT] Command execution failed: {e}"

        output += f"--- Output of '{cmd}' ---\n{out}\n"
    return output
