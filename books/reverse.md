# Reverse Engineering Playbook

## 1. Phased Workflow
1. File and Architecture Triage:
   - Identify format: file, readelf, and checksec.
   - Determine target architecture, bitness, endianness, and whether the binary is statically or dynamically linked.
   - Check for packing or protectors: UPX, custom packers, or high entropy sections.
2. Static Disassembly and Decompilation:
   - Locate entry point, main function, and string cross-references using objdump or radare2.
   - Identify input validation routines: comparison loops, cryptographic primitives, or state machines.
   - Trace dataflow from user input buffer to the success validation branch.
3. Dynamic Tracing and Behavioral Analysis:
   - Run strace or ltrace to capture library calls, file access, and comparison string arguments.
   - Trace branch decisions under GDB batch mode: set breakpoints before comparison instructions.
4. Constraint Modeling and Solving:
   - For invertible arithmetic: write direct Python reversal scripts.
   - For complex equations or multi-variable constraints: model conditions using z3 solver bitvectors.
5. Verification:
   - Feed recovered input into the original binary to confirm success output or flag extraction.

## 2. Target Architecture to Strategy Matrix
| Binary Type | Characteristics | Primary Reversal Strategy |
|---|---|---|
| Native ELF or PE | Compiled x86, x64, or ARM machine code | Disassemble via objdump; trace with GDB batch mode; model logic in z3 |
| Packed Binary | High entropy, missing symbol tables, UPX | Unpack via upx -d or trace execution to Original Entry Point and dump memory |
| Python Bytecode | .pyc file or pyinstaller executable | Extract via pyinstaller-extractor; decompile bytecode via pycdc or dis |
| Java or .NET | Intermediate bytecode with class structures | Decompile to source using jadx for Java or ilspycmd for .NET |
| WebAssembly | .wasm binary format | Disassemble with wasm2wat or convert to C code using wasm2c |
| VM Obfuscated | Custom virtual opcode dispatcher | Locate bytecode array, trace fetch-decode-execute loop, and map opcodes |

## 3. Toolchain and Decompilation Guidelines
- Static Reconnaissance:
  - Header inspection: `readelf -h -S ./bin`
  - Disassembly: `objdump -d -M intel ./bin | head -n 50`
  - String extraction: `strings -a -t x ./bin | grep -i flag`
- Dynamic Tracing:
  - Library calls: `ltrace -s 100 ./bin`
  - System calls: `strace -s 100 ./bin`
  - GDB batch register dump: `gdb -batch -ex 'break *main' -ex 'run' -ex 'info registers' ./bin`
- Constraint Solving:
  - Use z3 bitvectors: BitVec[name, size] to avoid precision mismatch with native machine integers.

## 4. Failure Diagnostics
| Symptom | Root Cause | Surgical Fix |
|---|---|---|
| Program exits immediately | Anti-debugging or ptrace detection | Patch ptrace call with NOPs; inspect signal handlers |
| Z3 returns unsat | Over-constrained model or wrong bounds | Remove constraints iteratively to find contradictory equation |
| Z3 hangs indefinitely | Non-linear integer constraints | Replace large non-linear operations with bitwise or table lookups |
| Decompiler output confusing | Struct fields interpreted as raw offsets | Reconstruct struct definition; map field offsets systematically |
| Input length check fails | String length calculation includes null byte | Verify whether validation uses strlen or read buffer length |

## 5. Rules and Anti-Patterns
- Never run untrusted binaries interactively; use isolated sandboxes with batch execution.
- Never write complex symbolic execution scripts before understanding high-level input flow.
- Always check strings and symbol tables before embarking on deep disassembly.
- Verify solver output by executing it against the binary directly.
