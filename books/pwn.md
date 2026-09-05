# Pwn Playbook

## Mandatory Workflow

Execute checkpoints **in order**. Never skip.

```
1. READ SOURCE/DOCKERFILE FIRST (if available in /data)
   → Reveals: input protocol, credential handling, vuln location, flag path
   → Beware: .creds files are LOCAL MOCKUPS. Remote randomizes credentials.
     Never plan credential guessing. Exploit the binary vulnerability instead.

2. STATIC TRIAGE
   checksec --file=./bin
   file ./bin
   → Record: arch, NX, PIE, Canary, RELRO, stripped/not

3. READ INPUT PROTOCOL FROM SOURCE/DISASM
   → Identify EXACT input format before sending anything
   → Binary protocol? Custom struct? Text commands?
   → Never assume stdin is line-based text

4. IDENTIFY VULN MECHANISM (static, from source or disasm)
   → Name the exact dangerous operation: which function, which buffer, which copy

5. COMPUTE OFFSETS STATICALLY
   → Read stack frame layout from disasm or source variable declarations
   → offset to RIP = sum of local variable sizes above buf + 8 (saved RBP)
   → Only use GDB cyclic if static calculation is impossible

6. BUILD EXPLOIT
   → Use pwntools. Script all interaction. Never manual netcat.

7. TEST LOCAL → PORT TO REMOTE
```

---

## Protection → Strategy Matrix

| Protections | Technique |
|---|---|
| No NX | Shellcode on stack/heap, find `jmp rsp` or `call rax` |
| NX, no PIE, no Canary | ret2libc or ROP with static binary addresses |
| NX, PIE, no Canary | Need binary leak first, then compute base |
| Canary present | Need canary leak first (format string / adjacent read) |
| Full RELRO | No GOT overwrite; use stack/heap function pointer |
| seccomp | Dump filter first (`seccomp-tools dump`), use ORW if execve blocked |

---

## Input Protocol — Critical

Always identify the input protocol from source/disasm BEFORE sending payloads:

- **Binary protocol**: reads raw bytes, `int`/`struct` first — use `p32()`/`p64()`, NOT text
- **Multi-stage**: USER then PASS, command then data — each stage is a separate `read()`
- **Length-prefixed**: sends size before content — respect the framing
- **Null-terminated**: copy loop stops at `\0` — payload must not contain null bytes in padding

Failure to match the exact protocol = program exits before reaching the vuln.

---

## Offset Calculation — Static Method

Prefer static over cyclic when source is available:

```
Stack frame (grows downward, variables declared top-to-bottom):
  [highest addr] saved RIP  (8 bytes)
                 saved RBP  (8 bytes)
                 var_first_declared[N]   ← closest to saved RBP
                 var_second_declared[M]
                 ...
                 buf_overflow[K]         ← our write target
  [lowest addr]

offset = sum of all variables between buf and saved RBP + 8
```

**Cross-buffer overflow pattern** (common, often missed):
```c
while (buf[i] != '\0')      // loop reads buf[i]
    target[i-5] = buf[i];   // writes to target[]
```
If `buf` is full (all non-null bytes), `buf[sizeof(buf)]` reads the NEXT stack variable.
→ The copy continues past buf[] into adjacent variables.
→ RIP may be controlled by a DIFFERENT buffer than the one being copied into.
→ When `cyclic_find(rip_val) == -1`: the cyclic pattern is in the wrong buffer.
  Check which adjacent buffer's content ends up at RIP.

---

## Failure Diagnostics

| Symptom | Root Cause | Fix |
|---|---|---|
| Program exits before overflow | Wrong input protocol (missing cmd prefix, wrong byte order) | Read input handling in source/disasm; match protocol exactly |
| `cyclic_find(rip_val)` returns -1 | Cyclic is in wrong buffer; RIP comes from adjacent stack var | Check if copy loop reads past buffer bounds into next variable |
| GDB exits without crash, code 1 | Prerequisite check failed (missing file, wrong login, EOF) | Satisfy pre-conditions: create .creds, feed all expected inputs |
| Works locally, hangs/fails remote | Wrong libc, ASLR mismatch, or remote expects different input timing | Use exact supplied libc; use `p.clean()` not hardcoded delays |
| Offset found but no shell | ret address correct but args wrong (rdi not set, /bin/sh not pointed) | Check calling convention; use `pop rdi; ret` gadget before system |
| SIGSEGV at ROP chain | Stack misaligned (must be 16-byte aligned before `call`) | Insert extra `ret` gadget before `system`/`execve` call |
| GDB shows 260x "Invalid command" | GDB stdin mixed with binary stdin via pipe redirect | Use pwntools `process()` + `.sendafter()` instead of `run < file` |

---

## Decision Tree

```
Source/Dockerfile available?
  Yes → READ IT FIRST before touching binary

Input is binary protocol?
  Yes → Use pwntools to script exact byte sequence
  No  → Proceed with text commands

NX disabled?
  Yes → Shellcode + jmp/call reg gadget

Canary present?
  Yes → Need leak first

PIE enabled?
  Yes → Need binary address leak first

overflow target → RIP offset known?
  Yes → Build payload
  No, cyclic_find == -1 → Check adjacent stack variable is source of RIP

No gadgets in binary?
  → Search libc (if dynamic) or use ret2csu or SROP
```

---

## GDB Usage Rules

- **Never** use `run < payload_file` for binary-protocol programs — GDB reads stdin too.
- Use `gdb -batch -ex 'set follow-fork-mode child' -ex 'run' ./bin <<< $(python3 -c "...")` for simple cases.
- Prefer pwntools `process()` with `gdb.attach()` for interactive debugging.
- Disable ASLR: `echo 0 | sudo tee /proc/sys/kernel/randomize_va_space` (may not work in container — use `-no-pie` binary or PIE-disabled build instead).
- Key commands: `telescope $rsp 30`, `info frame`, `x/20gx $rsp`, `cyclic_find $rip` in pwndbg.