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

def read(sandbox, target):
    if not target or not isinstance(target, str):
        return "Invalid read target."

    target = target.strip().strip("'\"")
    for ch in [";", "&", "|", "`", "$", "\n", "\r", ">", "<", "(", ")"]:
        target = target.replace(ch, "")

    target = target.strip()
    if not target:
        return "Empty read target."

    path = target if target.startswith("/") else f"/data/{target}"

    script = f'''
        if [ ! -e "{path}" ]; then
            echo "File '{path}' does not exist."
            echo "Available in /data: $(ls -m /data 2>/dev/null)"
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
                echo "[TEXT PREVIEW (first 250 lines)]"
                head -n 250 "{path}"
                ;;
            *)
                case "{path}" in
                    *.zip)
                        echo "[ARCHIVE CONTENTS]"
                        unzip -v "{path}" 2>&1 | head -n 45
                        ;;
                    *.pcap|*.pcapng|*.cap)
                        echo "[PCAP PACKET SUMMARY]"
                        tshark -r "{path}" -c 20 2>&1 || tcpdump -r "{path}" -c 20 2>&1
                        ;;
                    *.txt|*.py|*.c|*.cpp|*.sh|*.php|*.html|*.log|*.dis)
                        echo "[TEXT PREVIEW (first 250 lines)]"
                        head -n 250 "{path}"
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
        if len(out) > 3000:
            out = out[:3000] + "\n...[TRUNCATED]"
        return out
    except Exception as e:
        return f"Failed to read '{target}': {e}"
