# Cryptography Playbook

## 1. Phased Workflow
1. Artifact and Parameter Triage:
   - Identify cryptographic primitive: RSA, ECC, AES, stream cipher, hash, or custom PRNG.
   - Extract public parameters: modulus, exponent, elliptic curve coefficients, IV, and ciphertext.
   - Check source code for hardcoded seeds, weak key generation, or repeated nonces.
2. Flaw Identification:
   - RSA: Small exponent, shared modulus, small private exponent, smooth factors, or Wiener susceptibility.
   - Symmetric Ciphers: ECB mode pattern leakage, CBC padding oracle, or CBC bit-flipping.
   - Stream Ciphers: Multi-time pad key reuse, known-plaintext XOR, or linear feedback register flaws.
   - Discrete Log and ECC: Weak prime order, small subgroup confinement, or ECDSA nonce reuse.
   - PRNG: Predictable seeds, Mersenne Twister state recovery, or linear congruential parameters.
3. Mathematical Modeling:
   - Formulate equations over finite fields or modular rings.
   - Apply standard reduction methods: Chinese Remainder Theorem, Baby-step Giant-step, or LLL lattice reduction.
4. Solver Implementation:
   - Develop automated Python solvers using pycryptodome, gmpy2, sympy, or SageMath.
   - Handle endianness, padding conventions, and byte-to-integer conversions cleanly.
5. Verification:
   - Verify decrypted plaintext contains standard printable text or target flag formatting.

## 2. Algorithm to Strategy Matrix
| Primitive | Vulnerability Pattern | Exploit Technique |
|---|---|---|
| RSA e=3 | Small public exponent, no padding | Compute integer cube root of ciphertext directly |
| RSA shared N | Common modulus with coprime exponents | Extended Euclidean algorithm to recover plaintext without private key |
| RSA small d | Private exponent d < N^0.292 | Continued fractions via Wiener or Boneh-Durfee lattice attack |
| RSA factorable | Close primes or smooth p-1 | Fermat factorization, Pollard p-1, or factordb query |
| AES-ECB | Block-independent encryption | Byte-at-a-time chosen-plaintext decryption or block shuffling |
| AES-CBC | Padding oracle or unauthenticated ciphertext | Decrypt bytes via error oracle; bit-flip ciphertext to alter decrypted text |
| AES-GCM | Nonce reuse | Recover authentication key via polynomial root finding over GF[2^128] |
| Stream XOR | Keystream reuse across multiple messages | XOR ciphertexts together to recover keystream via crib dragging |
| ECDSA | Nonce reuse across two signatures | Compute private key algebraically from duplicate k values |
| MT19937 PRNG | 624 consecutive 32-bit outputs leaked | Untwist state array to predict all future and past random values |

## 3. Toolchain and Scripting Guidelines
- Conversions:
  - Use bytes_to_long and long_to_bytes from Crypto.Util.number.
  - Modular inverse: use pow[a, -1, m] in Python 3.8+.
- Factorization and Oracles:
  - Query factordb via curl before launching expensive local factorization.
  - Sockets: maintain persistent socket sessions when querying live decryption oracles.
- Lattice and Advanced Algebra:
  - Use SageMath for matrix lattice reduction, polynomial roots, and elliptic curve operations.

## 4. Failure Diagnostics
| Symptom | Root Cause | Surgical Fix |
|---|---|---|
| Decrypted output is garbage | Wrong endianness or inverted key | Try reverse byte order; check whether key or IV requires hex decoding |
| Factorization hangs | Modulus too large with no special form | Stop brute force; check for parameter reuse or alternative algebraic flaws |
| Padding oracle connection drops | Remote rate limiting or timeout | Reconnect automatically; preserve oracle state across reconnections |
| Small root solver yields 0 roots | Bounds set too tight or epsilon too large | Expand root bound parameters; verify polynomial normalization |
| Chinese Remainder Theorem fails | Moduli are not pairwise coprime | Factor greatest common divisor between moduli first; reduce system |

## 5. Rules and Anti-Patterns
- Never brute-force 128-bit or 256-bit symmetric keys.
- Never write manual modular arithmetic loops when gmpy2 or pow provide optimized C primitives.
- Always check factordb before running long factorizations.
- Preserve persistent socket sessions across multiple oracle requests.