# Pwn Playbook

---

## Table of Contents

1. Scope and Goal Model
2. Required Background Knowledge
3. Master Workflow
4. Static Triage
5. Protection Matrix and Its Implications
6. Vulnerability Class Catalog
7. Stack Exploitation Techniques
8. Format String Exploitation
9. Heap Exploitation
10. Integer Bugs
11. Race Conditions and TOCTOU
12. Statically Linked Binaries and Missing libc
13. Sandboxed Binaries — seccomp and Restricted Syscalls
14. Blind and Remote-Only Exploitation
15. Architecture Notes — 32-bit, 64-bit, ARM, MIPS
16. Protection Bypass Reference
17. Exploit Engineering Practices
18. Toolchain Reference
19. GDB / pwndbg Command Reference
20. Decision Tree
21. Failure Mode Diagnostics
22. pwntools Skeleton
23. Worked Methodology Example
24. Glossary

---

## 1. Scope and Goal Model

A pwn challenge provides a compiled binary, sometimes with a linked libc and dynamic linker, and a remote host:port where an instance of the binary runs against attacker-controlled input, usually over a raw TCP socket via stdin/stdout redirection through something like socat or xinetd.

Terminal objectives, in order of typical prevalence:

- Spawn an interactive shell on the remote host.
- Trigger a call to `execve("/bin/sh", NULL, NULL)` or equivalent via a `system` or `one_gadget` call.
- Perform an open/read/write ORW sequence to read a flag file directly, required when shell syscalls are blocked by seccomp.
- Call a pre-existing `win` function that the binary already contains.
- Leak a secret directly from memory, when the challenge is a pure information-disclosure task.

Before writing any exploit code, state explicitly: what is the final primitive needed, and what intermediate primitives must be chained to reach it. Do not begin scripting until this chain is fully specified.

---

## 2. Required Background Knowledge

- Process memory layout: text, rodata, data, bss, heap growing upward, stack growing downward, mmap region for shared libraries.
- Stack frame mechanics: saved rbp/ebp, return address placement, parameter passing order.
- Calling conventions: cdecl on x86, System V AMD64 ABI on x86-64 with integer arguments in rdi, rsi, rdx, rcx, r8, r9 in that order, return value in rax.
- ELF structure: `.text`, `.data`, `.bss`, `.rodata`, `.got`, `.got.plt`, `.plt`, `.dynsym`, `.dynstr`, `.rela.plt`, program headers, dynamic section.
- PLT/GOT resolution mechanics: lazy binding via `_dl_runtime_resolve`, and how full RELRO changes this at load time.
- Syscall mechanics: syscall numbers differ per architecture; `syscall` instruction on x86-64 versus `int 0x80` on x86.
- glibc heap internals: chunk header layout, size field low bits (prev_inuse, is_mmapped, non_main_arena), fastbin, tcache, unsorted bin, small bin, large bin, top chunk, consolidation rules.
- tcache internals post-2.26, and the safe-linking mitigation introduced in glibc 2.32 that XORs the `fd` pointer with a pointer-derived key.

Do not proceed to technique selection while any of the above is uncertain; verify against the actual binary and libc version supplied, since offsets and structure layouts are version-specific.

---

## 3. Master Workflow

```
Receive binary and any auxiliary files (libc, ld.so, Dockerfile, source)
        |
Static Triage (file, checksec, strings, symbols)
        |
Disassemble / Decompile
        |
Identify entry point, input handling, dangerous calls, hidden functions
        |
Classify the vulnerability precisely
        |
Define required primitive chain: leak -> corrupt -> control -> execute
        |
Cross-reference protection matrix against candidate techniques
        |
Select technique(s)
        |
Build exploit incrementally, verifying each primitive in isolation under GDB
        |
Validate full chain locally
        |
Port to remote, adjust for libc/env differences
        |
Extract flag
```

Each arrow is a checkpoint. Do not skip a checkpoint under the assumption that a technique will "probably work" — verify with concrete evidence (a memory dump, a register value, a crash address) before moving forward.

---

## 4. Static Triage

Run in sequence:

```
file ./chall
checksec --file=./chall
strings -n 8 ./chall | less
nm -D ./chall
objdump -d -M intel ./chall
readelf -h ./chall
readelf -d ./chall
```

Extract from this pass:

- Architecture and bitness.
- Whether the binary is statically or dynamically linked.
- Whether it is stripped — if so, function boundaries must be found through decompiler heuristics rather than symbol names.
- Any suspicious strings: `/bin/sh`, format specifiers, file paths, flag-related strings, debug print statements left in by mistake.
- Exported and imported dynamic symbols — presence of `system`, `execve`, `mprotect`, `read`, `gets`, `printf` family functions.
- Any non-standard sections indicating custom syscall filtering or embedded shellcode.

Decompile with Ghidra, IDA Pro, or Binary Ninja. Read in this order: `main`, functions directly reachable from `main`, then any unreferenced function reachable only via a computed call, symbol table entry, or leftover debug path — a common location for an intentional `win` function.

If a Dockerfile or source is provided, read it fully before touching the binary — it frequently reveals the seccomp policy, the exact libc version, file permissions, and the flag's exact path.
Beware of auxiliary credential files (.creds, passwords.txt, user:pass): in Pwn challenges, these are local development mockups. Remote deployments randomize credentials (often generated via `/dev/urandom` in the Dockerfile). Never plan benign logins or credential guessing; the target must be solved through binary vulnerability exploitation.

---

## 5. Protection Matrix and Its Implications

| Protection | Meaning | Effect on strategy |
|---|---|---|
| Canary | Stack cookie placed before saved return address | Overflow past canary requires either a leak of its exact value or a target that bypasses the check entirely, e.g. overwriting a function pointer inside the same frame before the epilogue runs |
| NX / DEP | Stack and heap non-executable | Injected shellcode on stack/heap will not execute; use ROP, ret2libc, or mprotect-based shellcode reactivation |
| NX Disabled | Stack/heap is executable | Injected shellcode executes directly. Check for direct register jumps (jmp/call rsp, jmp/call rsi, etc.) or preserved buffer pointers before attempting ROP |
| PIE | Binary base randomized per run | All internal addresses require a leaked binary-relative pointer before use; compute base as `leaked_addr - known_offset` |
| ASLR | Heap, stack, and shared library bases randomized | Any libc or heap address requires its own leak; a leak of one region does not imply knowledge of another unless a fixed offset relationship exists |
| RELRO Partial | GOT writable | GOT overwrite is viable as a control-flow hijack primitive |
| RELRO Full | GOT read-only after relocation | GOT overwrite is not viable; consider stack/heap function pointers, `__free_hook`/`__malloc_hook` where still present depending on libc version, FSOP via `_IO_FILE` structures, or `exit` handler arrays |
| FORTIFY_SOURCE | Adds bounds checks to certain libc calls, e.g. `__strcpy_chk` | Naive overflow via fortified call may abort instead of executing; look for a non-fortified call path or a size argument that can be forged |
| Stack canary + no leak available | No direct disclosure path | Consider a controlled crash/restart brute-force only when the target forks per connection and canary is stable across forks — one byte at a time, testing crash vs no-crash |
| Seccomp filter present | Syscalls restricted | Enumerate the exact allowed syscall list before choosing shellcode; do not assume `execve` is available |

Build this table explicitly for every challenge before selecting a technique. A technique that ignores an active protection will not work regardless of how correct its logic is otherwise.

---

## 6. Vulnerability Class Catalog

### 6.1 Stack Buffer Overflow
Unbounded write into a stack buffer via `gets`, unchecked `strcpy`/`sprintf`, or a `read`/`fgets` call whose length argument exceeds the buffer's declared size.

### 6.2 Format String Bug
User-controlled data passed as the format argument itself, e.g. `printf(buf)` instead of `printf("%s", buf)`, enabling arbitrary read via `%p`/`%s` and arbitrary write via `%n`/`%hn`/`%hhn` combined with positional parameters `%N$`.

### 6.3 Heap Corruption
- Use-After-Free: a freed pointer is dereferenced or written to again.
- Double Free: the same pointer passed to `free` twice without re-allocation between calls.
- Heap Overflow: a write into a heap chunk exceeds its usable size, corrupting adjacent chunk metadata.
- Uninitialized Read: a freshly allocated chunk is used before being written, potentially leaking stale heap data from a prior allocation.

### 6.4 Integer Overflow / Underflow
Signed/unsigned mismatch or arithmetic wraparound bypasses a length or bounds check, typically converting a negative size check into a very large unsigned value that then drives an oversized `memcpy` or `read`.

### 6.5 Out-of-Bounds Array Access
Missing or incorrect bounds check on an index used for both read and write, common in custom heap-like or menu-based challenges implementing their own object table.

### 6.6 Race Condition / TOCTOU
A gap between a permission or state check and its use, exploitable in multi-threaded challenges or where file operations are checked then acted on non-atomically.

### 6.7 Type Confusion / Logic Bug
Reinterpreting a memory region under an incompatible type, or a state machine bug that permits an operation in an invalid state, e.g. using an object after its "freed" flag was not properly checked.

---

## 7. Stack Exploitation Techniques

### 7.1 ret2shellcode
Applicable only when the stack or the writable buffer region is executable. Write shellcode into the buffer, overwrite the return address with the buffer's own address. Rare in modern challenges due to NX being default-on.

### 7.2 ret2libc
Applicable when NX is on, PIE is off or a libc leak is available. Overwrite the return address to point directly at `system` inside libc, with the stack arranged so the next value popped is the address of `/bin/sh` — via a `pop rdi; ret` gadget on x86-64, or directly on the stack on x86 cdecl.

### 7.3 ROP — Return Oriented Programming
Chain short instruction sequences ending in `ret`, called gadgets, already present in the binary or libc, to synthesize arbitrary logic without injecting new code. Typical end goal: set up registers for `execve("/bin/sh", NULL, NULL)` or `mprotect` followed by a jump into now-executable shellcode.

### 7.4 ret2syscall
A ROP variant that ends in the `syscall` instruction rather than calling a libc wrapper, used when libc symbols are unavailable or restricted, or to construct a syscall not exposed conveniently through libc, e.g. crafting an ORW sequence when execve is blocked by seccomp.

### 7.5 ret2csu — Universal Gadget
`__libc_csu_init`, present in nearly every glibc-linked binary regardless of stripping, contains a reusable gadget sequence that can set rbx, rbp, r12–r15 and perform a call through a register — valuable when gadget availability in the binary is otherwise minimal, e.g. in statically linked or heavily stripped binaries.

### 7.6 SROP — Sigreturn Oriented Programming
Applicable on Linux x86-64 when a `sigreturn` syscall can be triggered, e.g. after a signal handler returns, or directly via a crafted ROP chain calling `sigreturn`. The kernel restores an entire register context, including rax, from a forged `sigcontext` structure placed on the stack, allowing a single gadget to set every register at once and directly invoke any syscall. Requires precise `sigcontext` layout construction; `pwntools` provides `SigreturnFrame` for this.

### 7.7 ret2dlresolve
Applicable to dynamically linked binaries without a libc leak and without Full RELRO, where the dynamic linker's lazy resolution machinery is manipulated by forging a fake `Elf_Rel`/`Elf_Sym` entry so that `_dl_runtime_resolve` resolves and calls an arbitrary named symbol, most commonly `system`, without ever needing a libc base leak. Requires careful construction of fake relocation and symbol table entries at a writable, known address such as `.bss`.

### 7.8 Stack Pivoting
Used when the controllable overflow is too short to hold a full ROP chain. A gadget such as `leave; ret` or `pop rsp; ret` redirects the stack pointer into an attacker-controlled region, e.g. `.bss` or the heap, which then hosts the real ROP chain.

### 7.9 Partial Overwrite
When only the low bytes of a return address or saved pointer are controllable — common with a one-byte or two-byte overflow near canary/rbp — overwrite only those bytes to redirect execution to a nearby address within the same page or module, useful for landing inside an existing function at a different offset, or for a partial libc/PIE bypass when high-order bytes are constant across ASLR runs.

---

## 8. Format String Exploitation

### 8.1 Locating the Vulnerable Parameter Offset
Send a marker payload, e.g. `AAAA%p%p%p%p%p%p%p...`, and identify at which positional index `%N$p` the marker `0x41414141` appears — that index is the stack offset from which the controlled buffer itself can be referenced for chained reads and writes.

### 8.2 Arbitrary Read
Use `%N$s` to dereference a pointer already on the stack at position N and print the string it points to, or `%N$p` to leak a raw pointer value directly — used to leak canary, saved return address, libc pointers, or stack/heap addresses depending on what values are present near the format string call.

### 8.3 Arbitrary Write
Use `%N$n`/`%N$hn`/`%N$hhn` to write the number of bytes output so far into the address referenced at stack position N. Precompute the exact byte count needed per write chunk, and order writes from lowest target address to highest to avoid needing to emit a decreasing byte count, which is not directly possible — pad with additional characters instead. `pwntools`' `fmtstr_payload` automates offset, target address, and value calculation.

### 8.4 Common Targets for the Write Primitive
GOT entries when RELRO is not Full, a saved return address on the stack, `__free_hook`/`__malloc_hook` on libc versions where present, or any function pointer the program later calls.

---

## 9. Heap Exploitation

### 9.1 Chunk Layout Fundamentals
Each chunk has an 8- or 16-byte header containing `prev_size` — only meaningful if the previous chunk is free — and `size`, whose low three bits encode `PREV_INUSE`, `IS_MMAPPED`, and `NON_MAIN_ARENA`. Free chunks additionally store `fd`/`bk` pointers, and for large bins, `fd_nextsize`/`bk_nextsize`.

### 9.2 tcache Poisoning
Applicable to glibc 2.26+ on chunk sizes eligible for tcache, typically up to ~0x410 bytes with default tcache_count. A UAF or overflow that overwrites a freed chunk's `fd` pointer redirects the next allocation of that size to an attacker-chosen address. Since glibc 2.32, `fd` is protected by safe-linking — it is stored as `PROTECT_PTR(pos, ptr) = pos >> 12 XOR ptr` — so the target chunk's own storage address must be known to correctly forge the encoded pointer.

### 9.3 Fastbin Attack
Similar mechanism to tcache poisoning but against the fastbin free-list, generally requiring bypass of the fastbin size-sanity check, which validates that the target chunk's `size` field looks plausible for its bin.

### 9.4 Unlink Exploitation
Exploits the classic unsafe unlinking macro, forging `fd`/`bk` of a "free" chunk such that the unlink operation writes an attacker-controlled pointer relationship, historically yielding an arbitrary write of the form `*(bk+0x18) = fd` — largely mitigated in modern glibc by unlink sanity checks, but still relevant on older or custom allocators.

### 9.5 House-of Techniques
A named family of heap exploitation patterns, each abusing a specific allocator code path. Identify the applicable one by matching the primitive available (overflow, UAF, double free, or overlap) against the technique's precondition before attempting it, and verify the exact glibc version, since most of these techniques are version-sensitive:

- House of Force — corrupt the top chunk size to an arbitrarily large value, then request an allocation whose size drives the returned pointer to any target address.
- House of Spirit — trick `free` into treating a forged fake chunk on the stack or elsewhere as a legitimate heap chunk, inserting it into a bin for later controlled allocation.
- House of Orange — abuses top chunk consolidation into the unsorted bin via an overflow that corrupts the top chunk size, without a direct `free` call, often chained into `_IO_FILE` exploitation.
- House of Lore — targets the small bin linked list to insert a forged chunk via a corrupted `bk` pointer.
- Unsafe Unlink — see 9.4.

### 9.6 FSOP — File Stream Oriented Programming
Corrupt an `_IO_FILE` structure, e.g. `stdout`, so that its vtable pointer or internal function pointers redirect execution when the stream is next used, for example on the next `printf`/`exit` flush. Modern glibc validates vtable pointers against a known valid range, requiring the forged vtable to reside within that range or the check to be otherwise bypassed, e.g. via `_IO_str_jumps` on certain versions.

### 9.7 Leak Strategy on Heap Challenges
Before attempting corruption, look for a natural leak: an uninitialized chunk reused after free without clearing, a print-object function that discloses a heap or libc pointer, or a UAF read that exposes `fd`/`bk` of a freed chunk sitting in the unsorted bin, which point into libc.

---

## 10. Integer Bugs

Identify the exact comparison being bypassed: signed comparison where a negative user-supplied length passes a `< MAX` check but is later reinterpreted as unsigned in a `memcpy`/`malloc` call, or an addition that wraps a size calculation such as `count * size` in a custom allocator. Convert the integer bug into a concrete downstream primitive — almost always an oversized copy or an undersized allocation followed by an overflow — then treat it under the stack or heap technique sections above.

---

## 11. Race Conditions and TOCTOU

Identify the check and the use, and the operation that occurs between them. In multi-threaded challenges, look for shared state accessed without a lock, or a lock that is dropped between check and use. Exploitation typically requires firing many concurrent requests to win a narrow timing window; `pwntools` threads or raw concurrent socket connections are used to maximize the hit rate. Confirm the race is real by first reproducing the inconsistent state locally with an instrumented build before attempting it against the remote instance.

---

## 12. Statically Linked Binaries and Missing libc

When no libc is provided or the binary is statically linked:

- All library code, including `malloc`/`free`/`printf` internals, is embedded directly in the binary — ROP gadgets should be searched across the entire binary rather than a separate libc.
- Direct syscalls are frequently the only viable path to `execve` or ORW, since no dynamic `system` symbol exists to call.
- Tools: `ROPgadget --binary ./chall` across the full binary, and manual identification of a `syscall` instruction reachable via a controllable gadget chain.
- `ret2dlresolve` does not apply to statically linked binaries, since there is no dynamic linker involved.
- Pure Assembly / Minimalist Binaries (< 20KB): These binaries contain NO embedded glibc code, NO complex ROP gadgets (e.g. no `pop rdi; ret`), and execution starts directly at `_start` without a `main` function. Disassemble the entire binary (`objdump -d ./chall`) — it is typically only 20-50 instructions.
  - If NX is disabled: The primary intended exploit is direct shellcode execution. Look for `jmp/call <reg>` gadgets (`jmp rsi`, `jmp rsp`, `call rax`) or register pointers to the input buffer retained upon return.
  - If NX is enabled: Look for `syscall` instruction to set up SROP (Sigreturn Oriented Programming).

---

## 13. Sandboxed Binaries — seccomp and Restricted Syscalls

- Dump the seccomp-bpf filter with `seccomp-tools dump ./chall` to get the exact allow-list or deny-list of syscall numbers before choosing a payload.
- If `execve` is blocked, pivot to an ORW chain: `open` the flag path, `read` its contents into a buffer, `write` the buffer to stdout — each as a direct `syscall` gadget invocation with correctly set rax/rdi/rsi/rdx.
- If `open`/`openat` is also blocked, check whether a file descriptor to the flag is already open at a known low number, e.g. because the challenge's launcher script opened it before dropping privileges — in that case only `read`/`write`(fd) are needed, with no `open` call at all.
- Some filters restrict syscall arguments, not just the syscall number itself — read the BPF program carefully rather than assuming a syscall is either fully allowed or fully blocked.

---

## 14. Blind and Remote-Only Exploitation

When no binary is provided, exploitation must proceed purely through observable behavior:

- Infer the presence and rough shape of a stack overflow via crash-vs-no-crash boundary testing, sending increasing-length payloads and observing where the remote connection dies or hangs.
- Use timing differences or partial response differences as an oracle when direct memory disclosure is not available.
- Reconstruct offsets and structure incrementally, validating each hypothesis against observed remote behavior rather than local debugging, since no local binary exists to attach a debugger to.
- This is significantly slower and higher-risk than white-box exploitation; budget many more remote round-trips and expect to need reconnection logic in the exploit script to survive crashes during trial payloads.

---

## 15. Architecture Notes

| Architecture | Syscall invocation | Argument registers | Notes |
|---|---|---|---|
| x86 32-bit | `int 0x80` or `sysenter` | ebx, ecx, edx, esi, edi, ebp | Return address and args typically on stack for calling convention purposes; smaller address space makes brute-forcing ASLR more tractable |
| x86-64 | `syscall` instruction | rdi, rsi, rdx, r10, r8, r9 | Note `r10` replaces `rcx` as 4th syscall argument, unlike the AMD64 function-call ABI which uses `rcx` |
| ARM 32-bit | `svc 0` | r0, r1, r2, r3, r4, r5 | Syscall number in r7; Thumb vs ARM mode affects gadget encoding and search |
| ARM64 / AArch64 | `svc 0` | x0–x5 | Syscall number in x8; no traditional `ret`-chained ROP in the strict sense on some tooling due to link-register-based returns via `br`/`ret` on `x30` |
| MIPS | `syscall` | a0–a3 (stack for further args) | Delay slot after branch/jump instructions must be accounted for when building gadget chains |

For non-x86 targets, run and debug through `qemu-user` with the correct `-g` GDB stub flag, and confirm gadget search tools support the target architecture before relying on their output.

---

## 16. Protection Bypass Reference

### 16.1 Canary
- Leak it directly via a format string or an adjacent read primitive, then re-embed the exact leaked value at the correct offset in the overflow payload.
- If the target forks per connection without re-randomizing, and a crash is distinguishable from a non-crash, brute-force one byte at a time from the least significant byte, since the canary's lowest byte is always `0x00` and does not need guessing.

### 16.2 PIE / ASLR
- Requires at least one address leak of a known symbol; compute the module base as `leaked_address - known_static_offset`, then add that base to any other offset within the same module to get an absolute address.
- A leak in one module, e.g. the binary, does not resolve addresses in a different module, e.g. libc, unless a further leak or a fixed relationship is established.
- On 32-bit targets with low ASLR entropy, brute force may be practical when no leak primitive exists at all; confirm entropy bits before choosing this path, since 64-bit ASLR entropy makes brute force impractical in nearly all cases.

### 16.3 NX
- Redirect execution to existing code via ROP/ret2libc instead of injecting new code.
- Alternatively, use an `mprotect` ROP call to mark a controlled memory region executable, then jump into freshly written shellcode there — useful when only a small ROP chain is buildable but a larger shellcode payload can be staged separately.

### 16.4 Full RELRO
- GOT overwrite is not viable; redirect via a heap/stack function pointer, `_IO_FILE` vtable corruption where the vtable range check can be satisfied, or a program-specific function pointer table.

---

## 17. Exploit Engineering Practices

- Parameterize the exploit for both local and remote execution from a single script; never hardcode addresses that differ between environments.
- Compute offsets with pwntools `cyclic`/`cyclic_find` when buffer length is unrestricted. If read length is bounded or stack variables (e.g. loop index `i`) sit between buffer and return address, determine offsets statically from disassembly (e.g. `rbp - offset`) or GDB frame layout.
- Validate every leak immediately after obtaining it — print it, sanity-check it against expected alignment, e.g. libc addresses ending in a predictable low nibble, before using it in further computation.
- Build the exploit as a sequence of independently testable stages; confirm each stage's postcondition under GDB before writing the next stage.
- Always use the exact libc and loader supplied by the challenge when testing locally; patch the binary's interpreter and rpath with `patchelf` or `pwninit` so local testing matches remote behavior precisely.
- Keep a clear separation between "diagnostic" payloads used to discover offsets and the final production payload, and remove diagnostic code paths before the final remote run to avoid wasting connection attempts.

---

## 18. Toolchain Reference

| Tool | Purpose |
|---|---|
| pwntools | Payload construction, process/socket interaction, ROP helper, format string helper, ELF/libc symbol resolution |
| GDB with pwndbg or GEF | Interactive debugging, heap visualization, register/memory inspection |
| checksec | Protection matrix enumeration |
| ROPgadget / ropper | Gadget discovery across a binary or library |
| one_gadget | Locates single-instruction-pointer-redirect shell-spawning addresses within a given libc |
| radare2 / Ghidra / IDA Pro | Disassembly and decompilation |
| pwninit | Automates interpreter/rpath patching for a given libc and loader |
| patchelf | Manual interpreter/rpath modification |
| seccomp-tools | Dumps and disassembles seccomp-bpf filters |
| qemu-user | Emulates non-native architecture binaries for local testing and debugging |

---

## 19. GDB / pwndbg Command Reference

```
break *0xADDRESS         set a breakpoint at a raw address, useful when symbols are stripped
run < payload_file        run the target feeding a file as stdin
vmmap                     show memory mappings, confirm module base addresses
x/20gx $rsp                examine 20 giant words at the stack pointer
info registers             dump all register values
heap                       pwndbg command, summarize heap chunk layout
bins                       pwndbg command, show fastbin/tcache/unsorted bin contents
telescope $rsp 30          pwndbg command, dereference-chain view of stack memory
cyclic 200                 pwndbg/pwntools command, generate a De Bruijn pattern
cyclic -l 0x61616161       pwndbg/pwntools command, resolve a pattern back to an offset
```

---

## 20. Decision Tree

```
Is there a memory corruption primitive at all?
  No  -> re-examine logic bugs, integer bugs, and race conditions before concluding no bug exists
  Yes -> continue

Is NX enabled?
  No, and buffer is executable -> ret2shellcode
  Yes -> continue

Is PIE enabled?
  Yes -> need a leak of a binary-relative address before building any binary-internal ROP chain
  No  -> binary addresses are static and usable immediately

Is a libc provided or symbol resolvable at runtime?
  Yes -> need a libc leak (unless static addresses already known) -> ret2libc / ROP into system
  No, and dynamically linked, and RELRO not Full -> consider ret2dlresolve
  No, and statically linked -> search binary itself for gadgets and syscall instructions -> ret2syscall

Is a seccomp filter active?
  Yes -> dump filter, confirm allowed syscalls before finalizing payload; ORW likely required over direct shell
  No  -> shell-spawning primitives are unrestricted

Is the vulnerability on the heap?
  Yes -> identify glibc version precisely, classify UAF vs overflow vs double-free, select the matching tcache/fastbin/House-of technique
```

---

## 21. Failure Mode Diagnostics

| Symptom | Likely cause | Resolution |
|---|---|---|
| Works locally, fails or hangs remotely | Wrong libc version, environment mismatch | Use the exact libc/loader supplied by the challenge; patch and retest locally against that exact libc |
| Crash at an unexpected address | Miscalculated overflow offset | Recompute offset with `cyclic`/`cyclic_find`, or inspect stack frame disassembly (`rbp` offsets) if cyclic pattern corrupts adjacent locals |
| Canary value differs every run | Expected behavior of a properly randomized canary | Requires an explicit leak primitive, or brute force only if the process forks with a stable canary across attempts |
| No usable gadgets found | Binary too small, heavily stripped, or too few instructions | Search the paired libc, or use `ret2csu`, or search for gadgets that cross function boundaries in raw disassembly |
| Format string leak returns garbage or zero | Wrong positional offset | Re-derive the offset using the marker technique in section 8.1 before attempting the real leak |
| Heap technique corrupts unrelated memory | Wrong glibc version assumptions | Re-verify chunk size/metadata layout and safe-linking presence against the exact supplied libc |
| Exploit works once then fails on retry | Heap or environment state left inconsistent between runs | Ensure the exploit script fully re-initializes on each connection and does not depend on leftover state from a previous attempt |

---

## 22. pwntools Skeleton

```python
from pwn import *

context.binary = elf = ELF('./chall')
context.log_level = 'info'
libc = ELF('./libc.so.6')

HOST, PORT = 'remote.host', 1337

def start():
    if args.REMOTE:
        return remote(HOST, PORT)
    return process(elf.path)

io = start()

# Stage 1: trigger leak
# io.sendlineafter(b'prompt', payload)
# leak = u64(io.recvline().strip().ljust(8, b'\x00'))
# libc.address = leak - libc.symbols['known_function']

# Stage 2: build final chain
# rop = ROP(libc)
# rop.call('system', [next(libc.search(b'/bin/sh\x00'))])
# payload = flat(b'A' * offset, rop.chain())

# Stage 3: fire and interact
# io.sendline(payload)
io.interactive()
```

---

## 23. Worked Methodology Example

Generic walkthrough illustrating the reasoning process end to end, intentionally not tied to a specific real binary:

1. Protection matrix: NX on, PIE off, Canary off, RELRO Partial.
2. Decompilation shows `main` calling a function that reads user input via `read` with a length exceeding the destination buffer's declared size — classic stack buffer overflow.
3. Canary off removes any need for a canary leak or bypass.
4. PIE off means all binary addresses are static and usable directly without a leak.
5. NX on rules out ret2shellcode; select ret2libc.
6. A libc pointer leak is required. The binary happens to call `puts` on a libc function pointer before an unrelated crash point — use that as the leak.
7. Compute `libc.address = leaked_puts_got_value - libc.symbols['puts']`.
8. Compute `system` address and the address of the `/bin/sh` string inside the leaked libc.
9. Determine the exact overflow offset with `cyclic`/`cyclic_find`.
10. Build final payload: padding to offset, `pop rdi; ret` gadget, address of `/bin/sh`, address of `system`.
11. Validate locally under GDB, confirm shell spawns.
12. Repeat against remote with the `REMOTE` flag, confirm shell spawns, run `cat flag` or the challenge's specified retrieval command.

---

## 24. Glossary

| Term | Definition |
|---|---|
| Canary | Stack cookie placed to detect return-address overwrite |
| NX | Non-executable memory protection for stack/heap |
| PIE | Position-independent executable, randomized base address |
| ASLR | Address space layout randomization at the OS level |
| RELRO | Relocation read-only protection for GOT |
| GOT | Global Offset Table, holds resolved addresses of dynamic symbols |
| PLT | Procedure Linkage Table, stub used to call through the GOT |
| ROP | Return-oriented programming |
| Gadget | Short instruction sequence ending in a return, used to build a ROP chain |
| SROP | Sigreturn-oriented programming |
| Chunk | A unit of heap memory managed by glibc's allocator |
| tcache | Per-thread fast free-list cache for small chunk sizes in modern glibc |
| Safe-linking | Pointer-mangling mitigation applied to tcache/fastbin `fd` pointers since glibc 2.32 |
| UAF | Use-after-free |
| TOCTOU | Time-of-check to time-of-use race condition |
| ORW | Open-read-write syscall sequence used to exfiltrate a file when shell syscalls are blocked |
| seccomp | Linux kernel facility restricting the syscalls a process may invoke |
| FSOP | File stream oriented programming, corruption of `_IO_FILE` structures |