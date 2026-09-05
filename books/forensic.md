# Forensics Playbook

## 1. Phased Workflow
1. Artifact Identification:
   - Identify format using file and xxd; never rely on file extension alone.
   - Verify magic bytes: PNG, JPEG, ZIP, ELF, PCAP, or raw disk filesystems.
2. Remote Service Check:
   - If a remote host and port are provided, probe with socket or pwntools immediately.
   - Determine if service requires interactive Q and A based on evidence logs; script interaction deterministically.
3. Deep Artifact Analysis:
   - Network Captures: parse protocol streams with tshark; extract transferred files, credentials, and DNS records.
   - Disk Images: inspect partition tables with mmls; compute byte offsets before mounting or decrypting.
   - Memory Dumps: identify operating system profile; inspect process trees, command history, and network sockets via volatility3.
   - Steganography: inspect EXIF metadata, alternate data streams, and LSB planes via zsteg or steghide.
4. Data Carving and Decoding:
   - Carve embedded files using foremost or binwalk.
   - Decode layered encodings: base64, hex, XOR streams, or compressed archives.
5. Verification:
   - Confirm recovered artifact contains authentic flag text or valid answer key.

## 2. Artifact to Strategy Matrix
| Artifact Type | Evidence Characteristic | Primary Technique |
|---|---|---|
| PCAP Capture | HTTP, DNS, or custom TCP stream | Reassemble streams via tshark; export objects; inspect DNS tunnel queries |
| Raw Disk Image | Partitioned storage media | Run mmls to locate start sector; calculate byte offset for mounting or carving |
| BitLocker Volume | Encrypted NTFS partition | Use dislocker with exact partition byte offset and 48-digit recovery password |
| Memory Dump | Raw RAM snapshot | Run volatility3 windows.pslist, filescan, or dumpfiles to extract memory artifacts |
| PNG or BMP Media | Hidden visual data | Run zsteg to inspect least-significant-bit planes; check EXIF tags via exiftool |
| Corrupted Archive | Broken zip headers | Repair magic bytes in hex editor; test with zipfix or 7z |

## 3. Toolchain and Carving Guidelines
- Magic Byte Signatures:
  - PNG: `89 50 4E 47`
  - JPEG: `FF D8 FF`
  - ZIP: `50 4B 03 04`
  - PCAP: `D4 C3 B2 A1` or `0A 0D 0D 0A`
- Partition Offset Formula:
  - Byte offset = start sector number * sector size in bytes.
  - Mount command: `mount -o loop,offset=OFFSET image.raw /mnt`
- Network Extraction:
  - Tshark filter: `tshark -r capture.pcap -Y "http.request.method == POST" -T fields -e http.file_data`

## 4. Failure Diagnostics
| Symptom | Root Cause | Surgical Fix |
|---|---|---|
| Binwalk extracts nothing | File corrupted or header truncated | Inspect raw bytes in xxd; repair magic bytes or central directory manually |
| Dislocker cannot grab VMK | Partition byte offset missing | Run mmls; multiply start sector by 512 to set exact -O byte offset |
| Volatility returns no symbols | Mismatched OS symbol table | Use volatility3 banner plugin to identify exact kernel version and build |
| Zsteg shows garbage | Encryption applied prior to LSB embedding | Look for password or key in adjacent challenge text or metadata |
| Remote Q and A times out | Script waiting for unread prompt | Use pwntools recvuntil with explicit prompt string rather than sleeping |

## 5. Rules and Anti-Patterns
- Never trust file extensions; always inspect initial magic bytes.
- Never mount raw disk images at offset 0 without checking the partition table.
- Always automate remote questionnaire services with pwntools scripts.
- Check metadata and EXIF data before undertaking deep payload carving.
