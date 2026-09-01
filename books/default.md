# Default / Forensics / Web Playbook

---

## Table of Contents

1. Scope and Goal Model
2. Master Workflow
3. Tactics Catalog
4. Procedure Detail
5. Forbidden Anti-Patterns

---

## 1. Scope and Goal Model

This playbook applies when a challenge does not fit into binary exploitation (Pwn), reverse engineering, or cryptography, or when the category is completely unknown. This typically covers Web exploitation, Forensics, OSINT, and Misc.

Terminal objectives typically involve:
- Gaining initial access to a web server.
- Extracting hidden data from an image, pcap, or document.
- Escalating privileges.
- Finding exposed credentials.

---

## 2. Master Workflow

```
Reconnaissance
        |
Initial Access / Data Extraction
        |
Execution / Deep Inspection
        |
Privilege Escalation / Secondary Extraction
        |
Flag Collection
```

---

## 3. Tactics Catalog

- **Reconnaissance**
- **Initial-Access**
- **Execution**
- **Privilege-Escalation**
- **Defense-Evasion**
- **Collection**
- **Exfiltration**

*(Note: If you need to search for external writeups, references, or exploit examples, do not use a tactic. Instead, supply your search term in the `rag` field of your plan JSON).*

---

## 4. Procedure Detail

### 1. Reconnaissance
For network/web targets, scan for open ports, enumerate directories, and identify running services and versions. For files (forensics), run `file`, `binwalk`, `strings`, `exiftool`, and `zsteg` to understand the file type and embedded metadata.

### 2. Initial Access / Data Extraction
For web, test common vulnerabilities based on recon (SQLi on inputs, LFI on file parameters, XSS, SSRF). For forensics, extract embedded files (`binwalk -e`), follow TCP streams in PCAPs, or extract hidden steganographic payloads.

### 3. Execution / Deep Inspection
For web, convert LFI to RCE (e.g., via log poisoning) or upload a web shell. For forensics, use volatility to analyze memory dumps or write custom scripts to parse proprietary file formats.

### 4. Privilege Escalation / Secondary Extraction
If shell access is gained, run linpeas, check sudo permissions, SUID binaries, and cron jobs.

### 5. Collection and Exfiltration
Locate the flag (usually `flag.txt` in the web root, user home, or `/root/`). 

---

## 5. Forbidden Anti-Patterns

- Do NOT brute-force directories or passwords blindly without a targeted wordlist and throttling considerations.
- Do NOT skip basic file enumeration (file, strings, binwalk) on mystery files before attempting complex forensics.
