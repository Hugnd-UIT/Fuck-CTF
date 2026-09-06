def run(sandbox, commands, category, timeout=30, workdir="/data"):
    output = ""
    wd = workdir.strip() if workdir and isinstance(workdir, str) and workdir.strip() and workdir.strip() != "-" else "/data"
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
            res = sandbox.exec_run(wrap, stdout=True, stderr=True, workdir=wd)
            out = res.output.decode("utf-8", errors="ignore")

            if res.exit_code == 124:
                out = f"[TIMEOUT] Command exceeded {time}s. Partial output:\n{out}"
        except Exception as e:
            out = f"[TIMEOUT] Command execution failed: {e}"

        output += f"--- Output of '{cmd}' ---\n{out}\n"

    # Save output.txt and append to log.txt
    try:
        import os
        ws = os.path.join(os.getcwd(), "workspace")
        rel = os.path.relpath(wd, "/data") if wd.startswith("/data") else ""
        host_target = os.path.join(ws, rel) if (rel and rel != ".") else ws
        if not os.path.exists(host_target):
            for root, dirs, files in os.walk(ws):
                if "server.py" in files or "solve.py" in files:
                    host_target = root
                    break

        if os.path.exists(host_target):
            out_file = os.path.join(host_target, "output.txt")
            cmd_text = "\n".join(commands) if isinstance(commands, list) else str(commands)
            content = f"[SCRIPT]\n{cmd_text}\n\n[OUTPUT]\n{output}\n"
            with open(out_file, "w", encoding="utf-8", errors="ignore") as f:
                f.write(content)

            log_file = os.path.join(host_target, "log.txt")
            with open(log_file, "a", encoding="utf-8", errors="ignore") as f:
                f.write(content + "\n")
    except Exception:
        pass

    return output

def read(sandbox, target, base_dir=None):
    if not target or not isinstance(target, str):
        return "Invalid read target."

    target = target.strip().strip("'\"")
    for ch in [";", "&", "|", "`", "$", "\n", "\r", ">", "<", "(", ")"]:
        target = target.replace(ch, "")

    target = target.strip()
    if not target:
        return "Empty read target."

    base = base_dir.strip().rstrip("/") if base_dir and isinstance(base_dir, str) and base_dir.strip() and base_dir.strip() != "-" else "/data"
    path = target if target.startswith("/") else f"{base}/{target}"

    script = f'''
        if [ ! -e "{path}" ]; then
            echo "File '{path}' does not exist."
            echo "Available in {base}: $(ls -m "{base}" 2>/dev/null)"
            exit 0
        fi

        echo "[METADATA]"
        ls -lh "{path}"
        echo -n "Type: "
        file -b "{path}"

        if [ -d "{path}" ]; then
            echo "[DIRECTORY CONTENT]"
            ls -lah "{path}" | head -n 40
            exit 0
        fi

        MIME=$(file --mime-type -b "{path}" 2>/dev/null)

        case "$MIME" in
            *zip*|*compressed*|*archive*)
                echo "[ARCHIVE CONTENTS]"
                unzip -v "{path}" 2>&1 | head -n 45 || tar -tvf "{path}" 2>&1 | head -n 45
                ;;
            *pcap*|*tcpdump*)
                echo "[PCAP PACKET SUMMARY]"
                tshark -r "{path}" -c 20 2>&1 || tcpdump -r "{path}" -c 20 2>&1
                ;;
            text/*|application/json|application/x-sh|application/javascript|application/xml)
                case "{path}" in
                    *log.txt|*.log)
                        echo "[CONTENT]"
                        tail -n 1000 "{path}"
                        ;;
                    *)
                        echo "[CONTENT]"
                        head -n 2000 "{path}"
                        ;;
                esac
                ;;
            *)
                case "{path}" in
                    *log.txt|*.log)
                        echo "[CONTENT]"
                        tail -n 1000 "{path}"
                        ;;
                    *.zip)
                        echo "[ARCHIVE CONTENTS]"
                        unzip -v "{path}" 2>&1 | head -n 45
                        ;;
                    *.pcap|*.pcapng|*.cap)
                        echo "[PCAP PACKET SUMMARY]"
                        tshark -r "{path}" -c 20 2>&1 || tcpdump -r "{path}" -c 20 2>&1
                        ;;
                    *.txt|*.py|*.c|*.cpp|*.h|*.sh|*.php|*.html|*.dis|*.go|*.java|*.json|*.yml|*.yaml|*.sql|*.md|*.env|*Makefile*|*Dockerfile*)
                        echo "[CONTENT]"
                        head -n 2000 "{path}"
                        ;;
                    *)
                        echo "[HEX/HEADER (first 256 bytes)]"
                        head -c 256 "{path}" | xxd | head -n 16
                        echo "[STRINGS SAMPLE]"
                        strings -n 8 "{path}" 2>/dev/null | head -n 25
                        ;;
                esac
                ;;
        esac
        '''
    try:
        res = sandbox.exec_run(["/bin/bash", "-c", script], stdout=True, stderr=True)
        out = res.output.decode("utf-8", errors="ignore").strip()
        if len(out) > 30000:
            if "log.txt" in target or target.endswith(".log"):
                out = "...[TRUNCATED TRACE]...\n" + out[-30000:]
            else:
                out = out[:30000] + "\n...[TRUNCATED]"
        return out
    except Exception as e:
        return f"Failed to read '{target}': {e}"
