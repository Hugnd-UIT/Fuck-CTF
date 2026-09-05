# Pwn Playbook

## 1. Phased Workflow
1. Environment Triage:
   - Inspect Dockerfile, source code, and run script first.
   - Note flag path, user privileges, exposed ports, and compile flags.
   - Disregard local mockup credentials or mock flags; remote services use randomized values.
2. Static Binary Inspection:
   - Run: `checksec --file=./bin` and `file ./bin`.
   - Record: Architecture, NX, PIE, Stack Canary, RELRO, stripped status.
3. Protocol Reconstruction:
   - Analyze input handlers in source or disassembly before sending any bytes.
   - Distinguish binary struct packing from newline-delimited text.
4. Vulnerability Identification:
   - Identify dangerous operations: buffer overflow, format string, integer underflow, use-after-free.
   - Map memory layout and distance to saved frame pointer or return address.
5. Exploit Development:
   - Craft standalone Python script using pwntools process or remote.
   - Structure payload: padding, leaked addresses, ROP gadgets, shellcode, or target redirection.
6. Verification:
   - Test locally under debugger batch mode.
   - Verify control of instruction pointer or arbitrary read/write, then deploy against remote target.

## 2. Protection to Strategy Matrix
| Protections | Attack Vector | Primary Technique |
|---|---|---|
| No NX | Shellcode execution | Inject shellcode into stack or heap; redirect RIP to jmp rsp or call rax |
| NX, No PIE, No Canary | Static ROP or ret2libc | Chain gadgets from binary text; call puts or write to leak libc, then ret2libc |
| NX, PIE, No Canary | Info leak then ROP | Leak binary base address via partial overwrite or format string; compute gadget offsets |
| Canary present | Canary bypass | Leak canary via adjacent read or format string; preserve canary in overflow payload |
| Full RELRO | Pointer hijacking | Avoid GOT overwrite; target saved return address, hook pointers, or function pointers |
| Seccomp enabled | Restricted syscalls | Dump filter via seccomp-tools; use open-read-write chain if execve is blocked |

## 3. Protocol and Layout Guidelines
- Binary Protocol:
  - Binary reads raw bytes, structs, or fixed integers: use p32 or p64, never raw text.
  - Multi-stage interaction: send command opcode before payload data.
  - Length-prefixed data: compute exact payload length and pack it into the header.
- Stack Frame Layout:
  - Stack grows downward toward lower memory addresses.
  - Buffer distance to saved RIP = sum of intervening local variable sizes + saved frame pointer.
  - Check adjacent stack variables; an unbounded loop may read past buffer bounds into adjacent buffers.

## 4. Failure Diagnostics
| Symptom | Root Cause | Surgical Fix |
|---|---|---|
| Process exits before crash | Input framing mismatch | Match protocol opcodes, integer byte order, and length fields |
| Cyclic offset not found | RIP loaded from adjacent variable | Inspect disassembly to locate which stack variable controls return |
| GDB batch exits without crash | Missing prerequisites | Satisfy expected files, configuration parameters, or auth tokens |
| Works local, fails remote | Libc version or ASLR mismatch | Match target libc version; avoid hardcoded addresses; synchronize timing |
| SIGSEGV inside libc call | Stack misaligned on x86_64 | Insert extra ret gadget before system call to enforce 16-byte alignment |
| GDB invalid command spam | Raw payload piped to GDB stdin | Use pwntools process with gdb.attach or pipe payload directly to binary |

## 5. Rules and Anti-Patterns
- Never use interactive commands: no interactive shells, pagers, or text editors.
- Never pipe raw exploit bytes directly into GDB CLI via `run < payload`.
- Always verify tool availability before execution: `command -v ROPgadget >/dev/null || pip3 install ROPgadget`.
- Write standalone Python scripts via heredoc: `cat <<'EOF' > exploit.py` then `python3 exploit.py`.