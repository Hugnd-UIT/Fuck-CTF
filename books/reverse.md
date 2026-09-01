# Reverse Engineering Playbook

---

## Table of Contents

1. Scope and Goal Model
2. Required Background Knowledge
3. Master Workflow
4. Static Triage
5. Anti-Analysis and Obfuscation Matrix
6. Toolchain and Language Specifics
7. Control Flow Analysis and Deobfuscation
8. Data Structure and Type Recovery
9. Cryptography Identification in Binaries
10. Dynamic Analysis and Instrumentation
11. Symbolic Execution and SMT Solving
12. Patching and Binary Modification
13. Exploit Engineering for Reverse
14. Toolchain Reference
15. Debugger and Instrumentation Command Reference
16. Decision Tree
17. Failure Mode Diagnostics
18. Z3 / Angr Skeleton
19. Worked Methodology Example
20. Glossary

---

## 1. Scope and Goal Model

A reverse engineering (RE) challenge provides one or more compiled artifacts (native binaries, bytecodes, scripts, or memory dumps). The attacker must understand the program's internal logic without source code.

Terminal objectives, in order of typical prevalence:

- Recover a hardcoded or dynamically generated flag from memory.
- Reconstruct an algorithm to write a keygen or input-solver that computes the correct flag.
- Defeat anti-analysis, packing, or DRM layers to access the core logic.
- Patch a binary to bypass licensing/authentication checks.
- Analyze malware to extract C2 domains, encryption keys, or specific behavioral triggers.

Before writing any solver script, state explicitly: what is the input validation logic, what are the constraints, and what is the required format of the solution. Do not begin writing a z3 script until the algorithm is fully mapped.

---

## 2. Required Background Knowledge

- Executable Formats: PE (Windows), ELF (Linux), Mach-O (macOS), DEX/APK (Android). Know the headers, sections (.text, .data, .bss, .rodata, .rdata), and import/export tables.
- Assembly Languages: x86/x64, ARM/AArch64, MIPS. Understand registers, stack operations, branching, and memory addressing.
- Calling Conventions: cdecl, stdcall, fastcall, System V AMD64 ABI (rdi, rsi, rdx, rcx, r8, r9), Microsoft x64 calling convention (rcx, rdx, r8, r9).
- OS Internals: Process memory maps, threading, PEB (Process Environment Block on Windows), syscall interfaces, dynamic linking, and loader behavior.
- High-Level Concepts: How compilers translate C/C++ structs, virtual tables, switch statements, and loops into assembly.

Do not proceed to dynamic analysis while any fundamental structural property of the binary (e.g., bitness, endianness, or linked libraries) is uncertain.

---

## 3. Master Workflow

```
Toolchain Identification
        |
Static Disassembly
        |
Anti-Analysis Check
        |
(If packed/protected) -> Anti-Analysis Bypass / Unpacking
        |
Identify Entry Point and Main Logic
        |
Control Flow Analysis
        |
Data Structure Recovery
        |
Algorithm Reconstruction
        |
Dynamic Verification
        |
Solution Synthesis
        |
Extract Flag
```

Each arrow is a checkpoint. Do not skip a checkpoint. Do not write a z3 script based on a guess of what a function does—verify its input and output dynamically first.

---

## 4. Static Triage

Run in sequence:

```
file ./chall
checksec --file=./chall
strings -n 8 ./chall | less
rabin2 -I ./chall
rabin2 -i ./chall
objdump -d -M intel ./chall
```

Extract from this pass:

- Architecture, bitness, and endianness.
- Whether it is stripped (no symbols) or dynamically/statically linked.
- Embedded strings: 'Correct', 'Wrong', 'Flag', Base64 alphabets, or specific error messages that indicate the validation path.
- Entropy: If `.text` or `.data` has entropy > 7.5, it is likely packed or encrypted.
- Imports: Look for `ptrace`, `IsDebuggerPresent`, `VirtualAlloc`, `mprotect`, crypto APIs.

Decompile with Ghidra or IDA Pro. Search for strings and find cross-references (XREFs) to them. If strings are encrypted, look for `.init_array` functions or a decryption routine called early in `main`.

---

## 5. Anti-Analysis and Obfuscation Matrix

| Technique | Meaning | Mitigation Strategy |
|---|---|---|
| Packing (UPX, Custom) | Code is compressed/encrypted and extracted at runtime. | Find the OEP (Original Entry Point) via tail jump, dump memory, and fix the Import Address Table (IAT). |
| Anti-Debugging | Checks if a debugger is attached (e.g., `ptrace`, `PEB.BeingDebugged`). | Patch the check (change `jnz` to `jmp`), use anti-anti-debug plugins (ScyllaHide), or hook the API. |
| Code Flattening / Opaque Predicates | CFG is destroyed into a giant switch statement with fake branches. | Use symbolic execution (angr, Triton) or DSE to trace the real path, or use specific deobfuscators (e.g., deflat). |
| Custom VM Obfuscation | Code is translated into a custom bytecode executed by a virtual machine. | Reverse the VM fetch-decode-execute loop, extract the handlers, map the custom opcodes, and write a disassembler for the bytecode. |
| Self-Modifying Code | Code decrypts or alters instructions right before executing them. | Use dynamic instrumentation (Frida/Pin) or a debugger to break after modification and dump the code. |
| Timing Checks | Detects analysis by checking if execution takes too long (`rdtsc`). | Patch the `rdtsc` instruction or hook it to return spoofed, consistent values. |

---

## 6. Toolchain and Language Specifics

Different languages require completely different RE approaches:

- **C/C++**: Standard decompilation. Focus on identifying structs and vtables. Standard library functions (printf, malloc) can bloat statically linked binaries; use FLIRT/FIDB signatures to identify them.
- **Rust**: Very heavy binaries. Look for `core::fmt`, `panic` handlers, and standard library bloat. Strings are not null-terminated; they are stored as (ptr, length) fat pointers.
- **Go**: Massive binaries due to runtime and garbage collector. Use `go_pclntab` to recover function names. Strings are (ptr, length). Calling convention passes arguments on the stack (older Go) or in registers (Go 1.17+).
- **.NET / C#**: Do not use IDA/Ghidra. Use dnSpy, ILSpy, or dotPeek. If obfuscated, use de4dot.
- **Java / Android**: Use jd-gui, CFR, or JADX for APKs. For Android, understand the JNI (Java Native Interface) if native libraries (`.so`) are included.
- **Python**: Compiled to `.pyc` or packed with PyInstaller. Extract with `pyinstxtractor` and decompile with `uncompyle6` or `decompyle3`. (Note: Python 3.9+ may require manual bytecode analysis via `dis`).

---

## 7. Control Flow Analysis and Deobfuscation

Identify the main validation logic. Usually, a CTF binary reads input, performs some transformation, and compares it to a desired state.

- Locate the comparison (e.g., `memcmp`, `strcmp`, or a manual loop).
- Trace backward from the comparison to see what transformations are applied to the user input.
- If the control flow is flattened (OLLVM), identify the state variable controlling the `switch` statement. Use angr or dynamic tracing to record the sequence of states executed for a given input.

---

## 8. Data Structure and Type Recovery

Attempting to reconstruct an algorithm using raw offset arithmetic (e.g., `*(int *)(rbp - 0x10)`) is error-prone. 

- In IDA/Ghidra, define C structs and apply them to variables and pointers.
- Identify arrays: Is it an array of bytes, ints, or pointers?
- Identify object orientation: If you see `rcx` or `rdi` being passed as the first argument consistently, it's likely a `this` pointer. Recover the vtable to understand virtual function calls.

---

## 9. Cryptography Identification in Binaries

Do not reverse engineer standard crypto algorithms manually. Identify them and use standard libraries to decrypt.

- Look for crypto constants using tools like `FindCrypt` or `signsrch`.
- AES: S-Box constants (`0x63, 0x7c, 0x77...`), `aesenc` / `aeskeygenassist` x86 instructions.
- DES: Specific permutation tables.
- RC4: Initialization loop of 256 iterations (`0` to `255`), followed by a PRGA loop doing swaps.
- Base64: Custom alphabets (check for 64-character strings).
- MD5/SHA: Specific initialization vectors (`0x67452301, 0xefcdab89` for MD5).

If a custom crypto algorithm is used, isolate the core round function and replicate it in Python/C.

---

## 10. Dynamic Analysis and Instrumentation

When static analysis is too slow (e.g., heavy obfuscation, dynamic decryption):

- **GDB/x64dbg**: Set breakpoints at the input read and the final comparison. Inspect memory to see the transformed input.
- **Frida**: Write JavaScript to hook functions, dump arguments, or bypass anti-debug checks dynamically without modifying the binary on disk.
- **Intel Pin / QBDI**: Use DBI to trace every executed instruction, count instructions, or implement Differential Fault Analysis (DFA).
- **LIEF**: Patch the binary format (e.g., add new sections or modify imports) to facilitate dynamic injection.

---

## 11. Symbolic Execution and SMT Solving

When the algorithm is complex but mathematically pure (no complex system calls or massive state explosions):

- **Z3**: If you can manually extract the math equations, write a Z3 python script to solve for the input variables. Use `BitVec` for modulo arithmetic, not `Int`.
- **angr**: Use when you want to execute the binary symbolically. Define a `find` address (the "Correct" block) and `avoid` addresses (the "Wrong" blocks). 
- *Warning*: Symbolic execution on unbounded loops or hash functions (like SHA256) will cause state explosion and hang. You must concretize sizes and bounds.

---

## 12. Patching and Binary Modification

Sometimes it is easier to patch a binary than to reverse the full algorithm.

- Patching a jump: Change `jz` (0x74) to `jnz` (0x75), or `jmp` (0xEB).
- NOPing code: Overwrite anti-debug checks or sleep functions with `nop` (0x90).
- If patching breaks a self-checksum, you must locate the checksum routine and patch that to return the expected value as well.

---

## 13. Exploit Engineering for Reverse

- Script everything. Do not do manual math.
- If using Z3, constrain the input characters to printable ASCII (`0x20` to `0x7E`) to massively speed up the solver.
- If the binary is a VM, write a disassembler in Python that takes the bytecode and prints it out. Do not read raw hex.

---

## 14. Toolchain Reference

| Tool | Purpose |
|---|---|
| IDA Pro / Ghidra / Binary Ninja | Core static analysis, decompilation, struct recovery. |
| x64dbg / GDB (pwndbg/GEF) | Core dynamic analysis, debugging, memory inspection. |
| dnSpy / ILSpy | .NET / C# decompilation and debugging. |
| JADX / jd-gui | Java / APK decompilation. |
| angr | Symbolic execution framework. |
| Z3 | SMT solver for mathematically reversing constraints. |
| Frida | Dynamic instrumentation and API hooking. |
| LIEF | Parsing and modifying ELF/PE/Mach-O formats. |
| Detect It Easy (DIE) | Packer and compiler identification. |
| Uncompyle6 / pyinstxtractor | Python reverse engineering. |

---

## 15. Debugger and Instrumentation Command Reference

```
gdb:
  catch syscall ptrace     Break when ptrace is called (anti-debug).
  display /10i $pc         Show the next 10 instructions automatically.
  set $eflags ^= (1 << 6)  Toggle the Zero Flag (ZF) to force a branch.

Frida:
  frida-trace -i "strcmp" ./chall
  frida -l hook.js -f ./chall
```

---

## 16. Decision Tree

```
What language/runtime is the binary?
  .NET/C# -> dnSpy
  Java/APK -> JADX
  Python -> pyinstxtractor + uncompyle
  Go/Rust -> Ghidra + language-specific scripts (go_pclntab)
  C/C++ -> continue

Is the binary packed or obfuscated?
  Yes, high entropy -> Find unpacking stub, dump memory at OEP, fix IAT.
  Yes, VM -> Reverse VM opcodes, write disassembler for bytecode.
  No -> continue

Is the logic mathematically invertible?
  Yes -> Write Python script to reverse the math.
  No, but constraints are clear -> Use Z3 to model the constraints.
  No, and constraints are heavily tangled -> Use angr to find a path to the success block.
```

---

## 17. Failure Mode Diagnostics

| Symptom | Likely cause | Resolution |
|---|---|---|
| Angr hangs forever | State explosion in loops or hashes | Concretize input length, constrain input bytes to ASCII, skip hash functions, or use Z3 manually. |
| Z3 returns "unsat" | Constraints are over-constrained or math is wrong | Check for signed/unsigned mismatch. Use `BitVec` instead of `Int`. Double-check constants. |
| Binary crashes in debugger but runs fine normally | Anti-debugging detected | Patch ptrace/IsDebuggerPresent checks, or use ScyllaHide/Frida. |
| Decompiler output looks like garbage | Code is obfuscated or packed | Do not trust decompiler blindly. Look at assembly. Dump unpacked memory. |
| Reconstructed algorithm produces wrong flag | Endianness or size mismatch | Verify whether memory reads are 8, 16, 32, or 64-bit. Check little-endian byte ordering. |

---

## 18. Z3 / Angr Skeleton

**Z3 Example:**
```python
from z3 import *

solver = Solver()
flag = [BitVec(f"flag_{i}", 8) for i in range(16)]

# Constrain to printable ASCII
for b in flag:
    solver.add(b >= 0x20, b <= 0x7e)

# Example constraint
solver.add(flag[0] ^ 0x55 == 0x11)
# ... add constraints based on RE ...

if solver.check() == sat:
    m = solver.model()
    result = "".join([chr(m[flag[i]].as_long()) for i in range(16)])
    print(f"Flag: {result}")
else:
    print("UNSAT")
```

**Angr Example:**
```python
import angr
import claripy

project = angr.Project('./chall', auto_load_libs=False)

# 16 byte flag
flag_chars = [claripy.BVS(f'flag_{i}', 8) for i in range(16)]
flag = claripy.Concat(*flag_chars)

state = project.factory.entry_state(stdin=flag)

for k in flag_chars:
    state.solver.add(k >= 0x20)
    state.solver.add(k <= 0x7e)

simgr = project.factory.simgr(state)
simgr.explore(find=0x401234, avoid=0x401256) # Replace with actual addresses

if simgr.found:
    found_state = simgr.found[0]
    print(found_state.posix.dumps(0))
else:
    print("No path found")
```

---

## 19. Worked Methodology Example

1. Toolchain: Run `file` and `strings`. Binary is 64-bit ELF, C/C++, not stripped.
2. Static Triage: Open in Ghidra. Find `main`.
3. Anti-Analysis: No obvious packing. Entropy is low.
4. CFG Analysis: `main` calls `read_input`, then `transform_input`, then compares the result to a hardcoded byte array using `memcmp`.
5. Data Recovery: The transformation loop operates on an array of 32 bytes (the flag).
6. Algorithm Reconstruction: The loop does `out[i] = (in[i] ^ 0x42) + 0x13`.
7. Dynamic Verification: Run in GDB, input 32 'A's. Break at `memcmp`. Verify the transformed buffer matches the mathematical expectation.
8. Solution Synthesis: The algorithm is perfectly invertible. `in[i] = (out[i] - 0x13) ^ 0x42`.
9. Final Verification: Write a python script to extract the target byte array from the binary and apply the inverse math. Run script. Flag is recovered.

---

## 20. Glossary

| Term | Definition |
|---|---|
| CFG | Control Flow Graph, a representation of all paths that might be traversed through a program. |
| OEP | Original Entry Point, where the actual program starts after a packer finishes unpacking. |
| SMT | Satisfiability Modulo Theories, a class of solvers (like Z3) used to find inputs that satisfy complex constraints. |
| Symbolic Execution | Exploring multiple paths of a program simultaneously using abstract symbols instead of concrete values. |
| DBI | Dynamic Binary Instrumentation, injecting monitoring code into an executing binary (e.g., Pin, Frida). |
| Obfuscation | Techniques used to make code harder to read without changing its functionality (flattening, dead code insertion). |
| Virtualization (VM) | Compiling the original logic into a custom bytecode that is interpreted by a proprietary runtime embedded in the binary. |
