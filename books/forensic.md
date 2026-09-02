# Forensics Playbook

---

## Table of Contents

1. Scope and Goal Model
2. Required Background Knowledge
3. Master Workflow
4. Artifact Identification and Triage
5. Disk Image Analysis
6. Memory Forensics
7. Network Capture Analysis
8. Steganography and Hidden Data
9. File Carving and Archive Recovery
10. Log and Metadata Analysis
11. Toolchain Reference
12. Decision Tree
13. Failure Mode Diagnostics
14. Worked Methodology Example
15. Glossary

---

## 1. Scope and Goal Model

Forensics challenges provide one or more artifact files — disk images, memory dumps, network captures, steganographic media, log files, or archives — without executable code to run. The attacker must analyze the artifact to recover hidden, embedded, or deleted data.

Terminal objectives, in order of typical prevalence:

- **Hidden Data Recovery:** Extract a flag embedded in a file using steganography, metadata, or alternate data streams.
- **File Carving:** Recover deleted or fragmented files from a raw disk image or memory dump.
- **Network Traffic Decoding:** Reconstruct and decode a flag from a packet capture stream.
- **Volume Decryption:** Decrypt an encrypted disk volume (BitLocker, LUKS, VeraCrypt) by finding key material in adjacent artifacts.
- **Memory Artifact Extraction:** Recover credentials, keys, or process output from a volatile memory dump.

Before running any tool, identify the artifact type precisely using `file` and `xxd`. Do not assume the format from the extension alone.

---

## 2. Required Background Knowledge

- **File Formats and Magic Bytes:** Know the magic bytes of common formats — `FF D8 FF` (JPEG), `89 50 4E 47` (PNG), `50 4B 03 04` (ZIP), `7F 45 4C 46` (ELF), `4D 5A` (PE/MZ). Extension and actual format often mismatch in CTFs.
- **Partition Tables:** MBR (Master Boot Record) and GPT. Partitions never start at byte offset 0 — the MBR occupies sector 0 and partition entries describe the starting LBA. Always compute: `byte_offset = start_sector × sector_size`.
- **Filesystem Structures:** FAT32, NTFS, EXT4. Understand inodes, directory entries, MFT records, and how deleted files leave recoverable traces.
- **Encoding Layers:** Base64, hex, ROT, XOR, or custom encodings frequently conceal data inside files or network streams. Always check whether visible strings are encoded.
- **Cryptography in Forensics:** BitLocker uses a recovery key (48-digit) or password to unlock the VMK; `dislocker` requires the correct partition byte offset. Wrong offset with the correct key produces the same `Unable to grab VMK/FVEK` error as a wrong key — these are distinct failure modes.
- **Volatility Memory Model:** Process list, loaded DLLs, handle table, network connections, registry hives, and raw page scanning are the primary analysis primitives.

---

## 3. Master Workflow

```text
Identify Artifact Type (file, xxd, binwalk)
        |
Inspect Container or Partition Structure
        |-- Disk image --> mmls / fdisk --> compute byte offset from start sector
        |-- Archive    --> unzip -l / 7z l
        |-- PCAP       --> capinfos, tshark -z io,phs
        |-- Memory     --> volatility imageinfo
        |
Mount or Extract Artifact (at the CORRECT offset)
        |
Bulk String and Pattern Search
        |-- strings | grep -iE 'flag|CTF|crypto\{'
        |-- bulk_extractor
        |
        +-- Flag Found --> Verify it originated from the target, not a script artifact
        |
        +-- Not Found --> Identify Sub-artifacts
                |
        Apply Category-Specific Analysis
        (stego / memory / network / log)
                |
        Reconstruct Key or Passphrase if Required
                |
        Decrypt --> Mount --> Search Again
                |
        Extract Flag
```

Each arrow is a checkpoint. Do not skip the partition or structure inspection step. A wrong byte offset invalidates every subsequent mount, decrypt, and carve operation.

---

## 4. Artifact Identification and Triage

Run in sequence on every artifact before doing anything else:

```bash
file ./artifact
xxd ./artifact | head -n 32
strings -n 8 ./artifact | grep -iE 'flag|CTF|key|password|secret'
binwalk ./artifact
sha256sum ./artifact
```

Extract from this pass:

- **Actual file type:** Confirms format regardless of the extension provided.
- **Embedded magic bytes:** `binwalk` shows all secondary formats hidden inside the artifact (ZIP appended to JPEG, ELF inside PNG, etc.).
- **Printable strings:** May directly contain the flag or a passphrase hint.
- **High-entropy regions:** Entropy > 7.5 indicates compression or encryption — investigate specifically.

---

## 5. Disk Image Analysis

### 5.1 Determine Partition Layout — Always First

**Never mount or decrypt using a hardcoded byte offset. Always find the real offset:**

```bash
mmls ./image.dd          # Sleuth Kit: shows each partition's start sector and length
fdisk -l ./image.dd      # Alternative: partition table with start sectors
```

Compute byte offset:

```bash
# mmls reports partition start at sector 2048, sector size 512 bytes
offset=$((2048 * 512))   # = 1,048,576 bytes
```

### 5.2 Mount a Raw Partition

```bash
sudo mount -o loop,ro,offset=$offset ./image.dd /mnt/target        # generic
sudo mount -t ntfs-3g -o loop,ro,offset=$offset ./image.dd /mnt/target  # NTFS
find /mnt/target -type f | xargs grep -lriE 'flag|CTF' 2>/dev/null
```

### 5.3 BitLocker Encrypted Volumes

- *Vulnerability:* Recovery key list available, but all keys fail with an identical error.
  - *Diagnosis:* `Unable to grab VMK/FVEK` for every key in a large list is a "uniform failure" — the byte offset is wrong, not the keys. These are different failure modes.
  - *Fix:* Re-run `mmls`, recompute offset. Never use `--offset 0` without verification.

```bash
# Confirm encryption
dislocker-metadata ./image.dd

# Find offset FIRST — mandatory step, not optional
mmls ./image.dd

# Unlock at the correct offset
sudo dislocker -V ./image.dd -p"XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX" \
    --offset $offset -- /mnt/dislocker

# Mount and search
sudo mount -o loop,ro /mnt/dislocker/dislocker-file /mnt/decrypted
find /mnt/decrypted -type f | xargs strings 2>/dev/null | grep -iE 'CTF\{|flag\{'
```

### 5.4 File Recovery from Filesystem

```bash
# List deleted files (Sleuth Kit)
fls -r -d -o $((offset/512)) ./image.dd      # -d: deleted files only

# Recover a specific deleted file by inode
icat -o $((offset/512)) ./image.dd <inode> > recovered_file

# Mass carving without filesystem metadata
foremost -i ./image.dd -o ./carved/
photorec ./image.dd
```

### 5.5 NTFS Alternate Data Streams

Flags are frequently hidden in ADS on NTFS images.

```bash
# List all named streams
fls -a -o $((offset/512)) ./image.dd | grep ':'

# Extract a specific stream by inode and stream name
icat -o $((offset/512)) ./image.dd <inode>:<stream_name>
```

---

## 6. Memory Forensics

### 6.1 Profile Identification

```bash
volatility2 -f ./memory.dmp imageinfo     # suggests OS profile candidates
volatility3 -f ./memory.dmp windows.info  # auto-detects for Volatility 3
```

### 6.2 Standard Analysis Sequence

```bash
PROFILE="Win10x64_19041"

# Process enumeration
volatility2 -f mem.dmp --profile=$PROFILE pslist
volatility2 -f mem.dmp --profile=$PROFILE pstree

# Network connections at capture time
volatility2 -f mem.dmp --profile=$PROFILE netscan

# DLLs loaded by a specific process
volatility2 -f mem.dmp --profile=$PROFILE dlllist -p <PID>

# Registry hives and key values
volatility2 -f mem.dmp --profile=$PROFILE hivelist
volatility2 -f mem.dmp --profile=$PROFILE printkey -K "SOFTWARE\Microsoft\..."

# Dump process memory and search for flag strings
volatility2 -f mem.dmp --profile=$PROFILE memdump -p <PID> -D ./dumps/
strings -n 8 ./dumps/<PID>.dmp | grep -iE 'flag|CTF|crypto\{'

# Extract process executable for static analysis
volatility2 -f mem.dmp --profile=$PROFILE procdump -p <PID> -D ./dumps/
```

### 6.3 Credential Extraction

```bash
volatility2 -f mem.dmp --profile=$PROFILE hashdump    # Windows NTLM hashes
volatility2 -f mem.dmp --profile=$PROFILE lsadump     # LSA secrets
volatility2 -f mem.dmp --profile=$PROFILE clipboard   # clipboard at capture time
```

---

## 7. Network Capture Analysis

### 7.1 Initial Triage

```bash
capinfos ./capture.pcap
tshark -r ./capture.pcap -z io,phs     # protocol hierarchy
tshark -r ./capture.pcap -z conv,tcp   # TCP conversations
```

### 7.2 Extract Data by Protocol

- **HTTP:**

```bash
tshark -r ./capture.pcap --export-objects http,./http_objects/
```

- **DNS tunneling (data encoded in subdomains):**

```bash
tshark -r ./capture.pcap -Y dns -T fields -e dns.qry.name | sort | uniq
# Long, high-entropy subdomains indicate tunneling -- decode them
```

- **FTP:**

```bash
tcpflow -r ./capture.pcap -o ./ftp_flows/
```

- **TLS with key log:**

```bash
tshark -r ./capture.pcap -o "ssl.keylog_file:./sslkeylog.log" \
    --export-objects http,./decrypted/
```

### 7.3 Follow TCP Streams

```bash
# List stream indices
tshark -r ./capture.pcap -T fields -e tcp.stream | sort -n | uniq

# Dump stream N as raw bytes
tshark -r ./capture.pcap -q -z follow,tcp,raw,<N>
```

### 7.4 Covert Channel Detection

- **DNS tunneling:** Decode base32/base64 labels in subdomains.
- **ICMP payload:** Data carried after the 8-byte ICMP header.
- **HTTP steganography:** Custom `X-` headers, oversized `User-Agent`, or cookie values.

```bash
tshark -r ./capture.pcap -Y icmp -T fields -e data.data
```

---

## 8. Steganography and Hidden Data

### 8.1 Initial Checks

```bash
file ./image.jpg
exiftool ./image.jpg          # metadata, GPS, embedded thumbnails, comments
strings -n 6 ./image.jpg
binwalk -e ./image.jpg        # embedded archives or executables
```

### 8.2 Image Steganography

- **LSB (Least Significant Bit):** Most common CTF technique. One bit of hidden data is stored in the lowest bit of each pixel channel value.

```bash
steghide extract -sf ./image.jpg       # password-protected LSB (JPEG/BMP)
stegoveritas ./image.png               # automated multi-technique sweep
zsteg ./image.png                      # PNG/BMP: checks all bit planes and channels
zsteg -a ./image.png
```

- **Manual channel analysis:**

```bash
python3 -c "
from PIL import Image
img = Image.open('image.png').convert('RGBA')
for name, ch in zip(['r','g','b','a'], img.split()):
    ch.save(f'channel_{name}.png')
"
```

### 8.3 Audio Steganography

- **Spectrogram:** Flags drawn visually in the frequency domain.

```bash
sox input.wav -n spectrogram -o spectrogram.png
```

- **DTMF / Morse:**

```bash
multimon-ng -a DTMF -a MORSE_CW -t wav input.wav
```

### 8.4 Document Steganography

```bash
# DOCX / XLSX / PPTX are ZIP archives
unzip -l ./file.docx
unzip ./file.docx -d ./docx_contents/
# Inspect: word/document.xml, custom XML properties, comments, tracked changes

# PDF
pdfinfo ./file.pdf
pdf-parser.py ./file.pdf
```

---

## 9. File Carving and Archive Recovery

```bash
# Carve specific types from raw image
foremost -t jpg,png,zip,pdf,docx -i ./image.dd -o ./carved/
photorec ./image.dd    # interactive, higher recovery rate

# Detect ZIP appended to another file (common CTF technique)
binwalk -e ./suspicious.jpg

# Repair damaged ZIP
zip -FF damaged.zip --out recovered.zip
7z t recovered.zip
```

### 9.1 Password-Protected Archives

```bash
zip2john archive.zip > hash.txt
rar2john archive.rar > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
hashcat -m 17200 hash.txt /usr/share/wordlists/rockyou.txt   # ZIP
hashcat -m 13000 hash.txt /usr/share/wordlists/rockyou.txt   # RAR5
```

---

## 10. Log and Metadata Analysis

```bash
# Web access logs
sort -k4 ./access.log | grep -iE 'POST|PUT|flag|admin'
awk '{print $1}' ./access.log | sort | uniq -c | sort -rn

# Exif timeline across multiple images
exiftool -csv *.jpg | sort -t',' -k5    # sort by DateTimeOriginal

# Windows Event Logs
python3 -m evtx2xml ./Security.evtx | grep -iE 'EventID|LogonType|SubjectUserName'

# Bulk extraction from entire disk image
bulk_extractor -o ./bulk_out ./image.dd
grep -iE 'CTF\{|flag\{|crypto\{' ./bulk_out/strings.txt
```

---

## 11. Toolchain Reference

| Category | Tool | Purpose |
|---|---|---|
| Identification | `file`, `xxd`, `binwalk` | Magic bytes, embedded files, entropy map |
| Disk — Structure | `mmls`, `fdisk` | Partition table, sector offsets |
| Disk — Mount | `mount -o offset=` | Mount partition at correct byte offset |
| Disk — Navigate | `fls`, `icat` (Sleuth Kit) | Enumerate and recover files by inode |
| Disk — Decrypt | `dislocker`, `cryptsetup` | BitLocker / LUKS volume decryption |
| File Carving | `foremost`, `photorec`, `scalpel` | Recover deleted or embedded files |
| Memory | `volatility2`, `volatility3` | Full memory artifact analysis |
| Network | `tshark`, `tcpflow`, `capinfos` | PCAP dissection and stream extraction |
| Stego (image) | `steghide`, `stegoveritas`, `zsteg`, `exiftool` | LSB, metadata, channel analysis |
| Stego (audio) | `sox`, `multimon-ng` | Spectrogram, DTMF, Morse |
| Metadata | `exiftool`, `pdfinfo`, `strings` | Embedded data and comment fields |
| Bulk | `bulk_extractor` | Mass string/artifact extraction |
| Password cracking | `john`, `hashcat`, `zip2john` | Archive and volume password recovery |

---

## 12. Decision Tree

```text
What is the artifact type?
|
+-- Disk image (.dd, .img, .vmdk, .vhd, .iso)
|   +-- 1. mmls / fdisk --> identify partition start sector --> compute byte offset
|   +-- 2. Check encryption: dislocker-metadata / file headers
|   |   +-- Encrypted --> find key in adjacent artifacts --> unlock with CORRECT offset
|   |   |               If all keys fail identically --> offset is WRONG, re-check mmls
|   |   +-- Not encrypted --> mount at offset --> search --> carve deleted files
|   +-- NTFS? --> check for Alternate Data Streams (fls -a | grep ':')
|
+-- Memory dump (.dmp, .mem, .raw, .lime)
|   +-- volatility imageinfo --> identify OS and profile
|   +-- pslist / pstree --> find suspicious process
|   +-- memdump + strings --> search for flag
|   +-- hashdump / lsadump --> extract credentials
|   +-- procdump --> extract binary for RE
|
+-- Network capture (.pcap, .pcapng)
|   +-- tshark protocol hierarchy --> dominant protocol?
|   +-- HTTP --> export objects
|   +-- DNS --> check for tunneling (base32/base64 subdomains)
|   +-- TLS --> decrypt with key log if available
|   +-- Follow TCP streams --> decode payload
|
+-- Image file (.jpg, .png, .bmp, .gif)
|   +-- exiftool --> metadata, GPS, embedded thumbnails
|   +-- binwalk -e --> embedded formats (polyglot)
|   +-- steghide / zsteg / stegoveritas --> LSB
|   +-- PIL channel split --> R, G, B, alpha separately
|
+-- Audio file (.wav, .mp3, .ogg)
|   +-- sox spectrogram --> visual patterns in frequency domain
|   +-- multimon-ng --> DTMF / Morse
|   +-- Hex inspect --> appended ZIP or other trailer
|
+-- Archive (.zip, .tar, .7z, .rar)
    +-- List contents --> suspicious file sizes or names
    +-- Password protected --> zip2john + john / hashcat
    +-- Damaged --> zip -FF / 7z repair
```

---

## 13. Failure Mode Diagnostics

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Unable to grab VMK/FVEK` for every key in a large list | Wrong partition byte offset — "uniform failure" signals a structural assumption error, not bad inputs | Run `mmls`; recalculate `offset = start_sector × 512`. Never use offset 0 without verification |
| All decryption attempts fail with the exact same error | Assumption at the base level is wrong (offset, tool flag, image format) | Stop iterating inputs; investigate the structural assumption first |
| `binwalk -e` extracts nothing | No embedded magic bytes; file is not a polyglot | Use `foremost` with raw-byte carving; manually inspect hex for file signatures |
| Volatility shows incorrect or empty process list | Wrong profile for the memory image | Run `imageinfo`; test the top 2-3 candidate profiles; compare `pslist` output |
| TLS streams show no cleartext | Encrypted; no key log available | Check for server private key in adjacent files; try to locate the TLS session key log |
| `steghide extract` fails without a password | Passphrase required | Run `stegcracker ./image.jpg /usr/share/wordlists/rockyou.txt` |
| Carved files are corrupt or truncated | Carving boundary misidentified | Locate the exact header and footer in `xxd`; extract with `dd if=image.dd bs=1 skip=<offset> count=<size>` |
| `strings` finds nothing useful | Flag is encoded (base64, hex, XOR) or stored as binary | Run `bulk_extractor`; try base64-decode and hex-decode on all long strings |

---

## 14. Worked Methodology Example

**Challenge type:** "Here is a disk image. Recover the flag."

```text
Step 1: file image.dd
        --> DOS/MBR boot sector

Step 2: mmls image.dd
        --> 002: 00:00  2048  204799  NTFS (202752 sectors)
        --> offset = 2048 x 512 = 1,048,576 bytes

Step 3: dislocker-metadata image.dd
        --> Confirms BitLocker encryption with recovery key protector

Step 4: Find key material in adjacent files
        --> recovery_keys.txt contains 100 candidate 48-digit recovery keys

Step 5: Test keys against the volume at the CORRECT offset
        for KEY in $(cat recovery_keys.txt); do
            sudo dislocker -V image.dd -p"$KEY" --offset 1048576 -- /mnt/dlock 2>&1
            [ -f /mnt/dlock/dislocker-file ] && echo "FOUND: $KEY" && break
        done

Step 6: Mount and search
        sudo mount -o loop,ro /mnt/dlock/dislocker-file /mnt/dec
        find /mnt/dec -type f | xargs strings 2>/dev/null | grep -iE 'CTF\{|flag\{'
```

---

## 15. Glossary

- **MBR:** Master Boot Record. 512-byte sector 0 of a disk; contains the partition table. Partitions start at non-zero LBA.
- **LBA:** Logical Block Address. Disk address in units of sectors (typically 512 bytes).
- **Byte offset:** `LBA x sector_size`. Pass to `mount -o offset=` or `dislocker --offset=`.
- **VMK:** Volume Master Key (BitLocker internal key, unlocked by recovery key, PIN, or TPM).
- **FVEK:** Full Volume Encryption Key (BitLocker; derived from VMK; directly encrypts disk sectors).
- **LSB steganography:** Hiding data in the least significant bits of pixel values or audio samples. Imperceptible to the human eye or ear.
- **Polyglot file:** A file simultaneously valid in two different formats (e.g., valid JPEG and valid ZIP). Detected by `binwalk`.
- **File carving:** Recovering file content by scanning for known magic byte headers and footers rather than using filesystem metadata.
- **Uniform failure:** When an entire set of inputs (key list, offset range, wordlist) produces the exact same error — a reliable signal that a lower-level structural assumption is wrong, not that the inputs are wrong.
- **Volatility profile:** OS-specific descriptor telling Volatility how to interpret kernel data structures in a memory dump.
