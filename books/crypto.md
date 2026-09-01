# Cryptography Playbook

---

## Table of Contents

1. Scope and Goal Model
2. Required Background Knowledge
3. Master Workflow
4. Static Triage and Parameter Extraction
5. Classical Ciphers and Encodings
6. Symmetric Cryptography: Block Ciphers
7. Symmetric Cryptography: Stream Ciphers and OTP
8. Asymmetric Cryptography: RSA Deep Dive
9. Asymmetric Cryptography: Diffie-Hellman and Discrete Logarithms
10. Elliptic Curve Cryptography (ECC) and ECDSA
11. Hash Functions and MACs
12. Pseudo-Random Number Generators (PRNG)
13. Lattice-Based Cryptography and LLL
14. Advanced Protocols (JWT, ZKP, Homomorphic)
15. Side-Channel Attacks
16. Exploit Engineering Practices
17. Toolchain Reference
18. SageMath and Python Snippet Reference
19. Decision Tree
20. Failure Mode Diagnostics
21. Exploit Skeleton
22. Worked Methodology Example
23. Glossary
24. Forbidden Anti-Patterns

---

## 1. Scope and Goal Model

Cryptography challenges focus on finding and exploiting mathematical, logical, or implementation flaws in encryption, hashing, signature, or random number generation schemes. 

Terminal objectives typically involve:
- **Plaintext Recovery:** Decrypting a ciphertext to reveal the flag without knowing the key.
- **Key Recovery:** Extracting the private key (e.g., RSA `d`, ECDSA private key `d`, AES key) to decrypt multiple messages or forge signatures.
- **Forgery:** Generating a valid signature, MAC, or authentication token without the key.
- **State Recovery:** Reconstructing the internal state of a PRNG to predict past or future outputs.
- **Protocol Bypass:** Exploiting logical flaws in authentication handshakes or cryptographic exchanges.

---

## 2. Required Background Knowledge

- **Number Theory & Modular Arithmetic:** Congruences, inverses, Euler's Totient function ($\phi$), Fermat's Little Theorem, Chinese Remainder Theorem (CRT), prime factorization.
- **Abstract Algebra:** Groups, Rings, Fields (especially Finite Fields $GF(p)$ and $GF(2^n)$), generators, orders of elements.
- **Bitwise Operations:** XOR properties (commutative, associative, self-inverse $A \oplus A = 0$).
- **Algorithm Standards:** Exact mathematical definitions of RSA, Diffie-Hellman, ECDSA, AES, DES, RC4. 
- **Modes of Operation:** ECB, CBC, CFB, OFB, CTR, GCM. How padding (PKCS#7) works.
- **Programming for Math:** High proficiency in Python (`pycryptodome`, `gmpy2`, `sympy`) and **SageMath** (critical for lattices, elliptic curves, and polynomial roots).

---

## 3. Master Workflow

```text
Identify Artifacts (Source code, network capture, raw ciphertext/public key)
        |
Static Triage (Parse PEM/DER, identify algorithm structure)
        |
Parameter Extraction (Extract n, e, c, curve parameters, iv, etc.)
        |
Source Code Audit (Find the implementation flaw, weak parameter, or reuse)
        |
Weakness Hypothesis (Select attack vector based on extracted properties)
        |
Mathematical Modeling (Translate the flaw into equations / lattice / Sage code)
        |
Local Implementation and Testing (Verify math on dummy parameters)
        |
Exploit Execution (Run against target parameters / remote server)
        |
Key / Plaintext Recovery
        |
Validation and Flag Formatting
```

---

## 4. Static Triage and Parameter Extraction

Before writing any exploit, you must extract all parameters accurately.

- **Identify Encodings:** Base64, Base32, Hex, URL-encoding.
- **Key Formats:** Parse `.pem` or `.der` files using `Crypto.PublicKey.RSA` or `openssl rsa -pubin -in key.pem -text -noout`. Extract modulus `n` and exponent `e` precisely.
- **Network Captures:** If provided a `.pcap`, extract the TLS handshake, custom cryptographic exchange, or transmitted ciphertexts.
- **Source Code:** Isolate the exact encryption and decryption routines. Identify what library is used (if any). If custom, map every mathematical operation.
- **Constants Check:** Identify curves (NIST P-256, secp256k1), primes, or generator values. Verify if they are standard or maliciously crafted (e.g., a backdoored Dual_EC_DRBG or a singular curve).

---

## 5. Classical Ciphers and Encodings

Used primarily in introductory challenges or as layers in complex challenges.

- **Substitution Ciphers (Caesar, ROT13, Monoalphabetic):** Use frequency analysis. Tools: `quipqiup`, CyberChef.
- **Vigenere / Autokey:** Find key length via Index of Coincidence (IoC) or Kasiski examination. Break columns with frequency analysis.
- **XOR and Repeating-Key XOR:** Use Hamming distance to find key length. Exploit via crib dragging (guessing known plaintext parts like `flag{`).
- **Playfair, Hill, Affine:** Requires known-plaintext attacks to recover the key matrix or linear coefficients.
- **Custom Base Encodings:** Layered Base64/Base32/Base85/Hex.

---

## 6. Symmetric Cryptography: Block Ciphers

Flaws in AES, DES, 3DES, or custom block ciphers are almost always in the **Mode of Operation** or padding, rarely the primitive itself.

- **ECB (Electronic Codebook):**
  - *Vulnerability:* Identical plaintext blocks produce identical ciphertext blocks.
  - *Attack:* Byte-at-a-time ECB decryption oracle. By shifting attacker-controlled input, align the unknown secret byte at the end of a block boundary and brute-force the single byte via oracle feedback.
- **CBC (Cipher Block Chaining):**
  - *Vulnerability:* Padding Oracle Attack. If a server reveals whether decryption failed due to invalid PKCS#7 padding, an attacker can decrypt ciphertexts byte-by-byte by modifying the previous block (or IV).
  - *Vulnerability:* Bit-Flipping Attack. Flipping a bit in ciphertext block $C_{i}$ flips the exact same bit in plaintext block $P_{i+1}$ (while randomizing $P_i$). Used to bypass filters and inject `admin=true`.
  - *Vulnerability:* IV Reuse. If IV is reused across messages, CBC loses semantic security for the first block.
- **GCM (Galois/Counter Mode):**
  - *Vulnerability:* Nonce Reuse. If a nonce is reused, the polynomial authentication key $H$ can be recovered by factoring the difference of the tags over $GF(2^{128})$. This completely breaks authentication and allows arbitrary forgery.
- **Meet-in-the-Middle:** Exploited in Double DES or custom 2-round ciphers. Encrypt from plaintext, decrypt from ciphertext, find the collision in the middle state to recover the keys.

---

## 7. Symmetric Cryptography: Stream Ciphers and OTP

- **One-Time Pad (OTP):** Unbreakable if the key is truly random, same length as the message, and NEVER reused.
  - *Vulnerability:* Key Reuse (Two-Time Pad). $C_1 \oplus C_2 = P_1 \oplus P_2$. Crib drag to recover plaintexts.
- **RC4:** 
  - *Vulnerability:* Weak key scheduling. The first few bytes of keystream are heavily biased. Often exploitable via FMS attack or related-key attacks.
- **CTR Mode:** 
  - Functions as a stream cipher. Nonce reuse means repeating keystream, vulnerable to the same attacks as OTP key reuse.

---

## 8. Asymmetric Cryptography: RSA Deep Dive

RSA is defined by $N = p \cdot q$, $\phi(N) = (p-1)(q-1)$, $e \cdot d \equiv 1 \pmod{\phi(N)}$, $c \equiv m^e \pmod N$. 

**Factorization Attacks:**
- **Factordb:** Always check if $N$ is already factored on factordb.com.
- **Fermat's Factorization:** Works if $p$ and $q$ are very close ($|p - q|$ is small).
- **Pollard's p-1:** Works if $p-1$ is smooth (composed of only small prime factors).
- **Williams' p+1:** Works if $p+1$ is smooth.
- **Twin Primes / Multi-prime:** If $N$ has 3+ prime factors, adjust $\phi(N)$ accordingly.
- **Common Factor (GCD):** If multiple moduli $N_1, N_2$ are provided, check $gcd(N_1, N_2)$. If $> 1$, both are factored instantly.

**Small Exponent ($e$) Attacks:**
- **Cube Root Attack:** If $e=3$ and $m^3 < N$ (no padding), $m = \sqrt[3]{c}$ over integers.
- **Håstad's Broadcast Attack:** If the same $m$ is encrypted to $e$ different moduli $N_1, N_2, ... N_e$, use CRT to find $m^e \pmod{N_1 N_2 ...}$ and take the $e$-th root.
- **Franklin-Reiter Related Message:** If $m_1$ and $m_2$ are linearly related ($m_1 = a \cdot m_2 + b$) and encrypted under the same $N$ and $e=3$, $m$ can be recovered via polynomial GCD.

**Small Private Key ($d$) Attacks:**
- **Wiener's Attack:** Works if $d < \frac{1}{3} N^{0.25}$. Uses continued fractions of $e/N$.
- **Boneh-Durfee Attack:** Extension of Wiener's using lattice reduction (Coppersmith's method). Works if $d < N^{0.292}$.

**Coppersmith and Lattice Attacks:**
- **Partial Key Exposure:** If you know MSBs or LSBs of $p, q$, or $d$, Coppersmith's method via SageMath can recover the rest.
- **Stereotyped Messages:** If the plaintext format is known except for a small missing chunk (e.g., `flag{...}`), use Coppersmith's theorem to find small roots of polynomials modulo $N$.

**Implementation Attacks:**
- **LSB Oracle (Parity Oracle):** If the server decrypts $c$ and tells you the lowest bit of $m$, you can multiply $c \cdot 2^e \pmod N$ repeatedly and narrow the bounds of $m$ using binary search.
- **Bleichenbacher's Padding Oracle:** Exploits servers that leak whether PKCS#1 v1.5 padding is valid. Allows full decryption or signing by adaptively querying forged ciphertexts.
- **Common Modulus:** If two messages are encrypted with the same $N$ but different $e_1, e_2$ (where $gcd(e_1, e_2) = 1$), use the Extended Euclidean Algorithm to recover $m$.

---

## 9. Asymmetric Cryptography: Diffie-Hellman and Discrete Logarithms

Defined by $g^a \pmod p$, $g^b \pmod p$, shared secret $S = g^{ab} \pmod p$. The hardness relies on the Discrete Logarithm Problem (DLP).

- **Pohlig-Hellman Attack:** Works if the group order $p-1$ (or subgroup order) is smooth (factors into small primes). Solves DLP in smaller subgroups and recombines via CRT.
- **Baby-Step Giant-Step (BSGS):** Generic DLP solver. Time/memory tradeoff $O(\sqrt{N})$. Use for primes or subgroup orders up to ~40 bits.
- **Pollard's Rho:** Generic DLP solver with $O(\sqrt{N})$ time but $O(1)$ memory.
- **Index Calculus:** Best for large prime fields $GF(p)$ if $p$ is moderately sized (e.g., 512-bit). Not applicable to Elliptic Curves.
- **Subgroup Confinement / Small Subgroup Attack:** If the server doesn't validate that a provided public key is in the correct large prime-order subgroup, send a point of small order $q$. The resulting shared secret will have only $q$ possible values, leaking the server's private key modulo $q$.
- **Backdoored Primes:** If $p$ is not prime, or if $p = r^k + s$ (Special Number Field Sieve applicable).

---

## 10. Elliptic Curve Cryptography (ECC) and ECDSA

Elliptic curves $y^2 = x^3 + a x + b \pmod p$. Hardness relies on Elliptic Curve Discrete Logarithm Problem (ECDLP).

- **Invalid Curve Attack:** If the server performs point multiplication $d \cdot G$ but doesn't check if $G$ is actually on the curve, provide a point $G'$ on a weaker curve (with the same $x, y$ coordinates). The scalar $d$ leaks modulo the order of the new curve.
- **ECDSA Nonce ($k$) Reuse:** ECDSA signature is $(r, s)$. If the same random nonce $k$ is used for two different messages, $k$ can be calculated, which immediately yields the private key $d$.
- **ECDSA Nonce ($k$) Leakage / Bias (Hidden Number Problem):** If even a few bits of the nonce $k$ are known across multiple signatures, the private key $d$ can be recovered using lattice reduction (LLL/BKZ algorithms).
- **Smart's Attack / Anomalous Curves:** If the number of points on the curve exactly equals the prime $p$ (i.e., trace of Frobenius is 1), ECDLP becomes trivially solvable in linear time using p-adic elliptic logarithms.
- **MOV Attack:** If the curve has a small embedding degree, the Weil or Tate pairing can map the ECDLP to a standard DLP in a finite field extension, making it solvable via Index Calculus.
- **Singular Curves:** If the discriminant $4a^3 + 27b^2 \equiv 0 \pmod p$, the curve is singular (has a cusp or node). The group maps to the additive or multiplicative group of $GF(p)$, making DLP trivial.

---

## 11. Hash Functions and MACs

- **Length Extension Attack:** Affects MD5, SHA-1, SHA-256, SHA-512 (hashes based on Merkle-Damgård without truncation). If the server verifies $H(secret || message)$, an attacker can append data and calculate a valid $H(secret || message || appended\_data)$ without knowing the secret. Tool: `hashpump`.
- **Hash Collisions:** MD5 and SHA-1 have known collision generation attacks. Use existing tools (`fastcoll`) to generate two files with different contents but the same hash.
- **Chosen-Prefix Collisions:** Creating a collision where the prefixes of the two messages are different and chosen by the attacker.
- **Weak HMAC / Timing Attacks:** If a server validates HMAC using early-exit string comparison (`==`), measure the response time. Each correctly guessed byte adds a slight delay.

---

## 12. Pseudo-Random Number Generators (PRNG)

Security of many schemes relies on unpredictable nonces/keys. If the PRNG is predictable, the crypto fails.

- **Mersenne Twister (MT19937 - Python's `random`):** Outputs 32-bit integers. If you collect 624 consecutive outputs, you can completely clone the internal state and predict all future and past numbers. Tool: `randcrack`.
- **Linear Congruential Generators (LCG):** $X_{n+1} = (a \cdot X_n + c) \pmod m$. If $a, c, m$ are unknown, they can be recovered from 3 or 4 consecutive outputs using basic algebra or lattice reduction if outputs are truncated.
- **Time-Based Seeding:** If `random.seed(time.time())` is used, the search space is massively reduced. Brute-force the seed locally by iterating through timestamps around the time of the transaction.
- **Insufficient Entropy:** `os.urandom` or `/dev/urandom` are secure, but if a developer mistakenly uses `random` or a short seed for key generation, brute-force the seed space.

---

## 13. Lattice-Based Cryptography and LLL

Lattices are the core tool for advanced cryptanalysis and post-quantum crypto.

- **Lenstra-Lenstra-Lovász (LLL) Algorithm:** Finds short, nearly orthogonal vectors in a lattice. Used extensively in Coppersmith's method, Knapsack attacks, and Hidden Number Problem.
- **Subset Sum / Knapsack:** Given a set of public weights and a target sum, find the binary combination. Map to a lattice and use LLL to find the short vector containing the binary solution.
- **Coppersmith's Method:** Finding small roots of polynomials modulo an integer. Implemented in SageMath as `small_roots()`. Essential for RSA partial key exposure and stereotyped messages.
- **LWE (Learning With Errors):** Post-quantum schemes. Look for poorly chosen parameters (small noise, too many samples) and attack via lattice reduction (BKZ) or Arora-Ge algorithm.

---

## 14. Advanced Protocols (JWT, ZKP, Homomorphic)

- **JWT (JSON Web Tokens):**
  - *Algorithm Confusion:* Change `RS256` (Asymmetric) to `HS256` (Symmetric). If the server is flawed, it will use the public key as the symmetric HMAC key.
  - *None Algorithm:* Set alg to `none` and strip the signature.
  - *Key Leakage:* Brute-force weak HMAC secrets using `hashcat`.
- **Zero-Knowledge Proofs (ZKP):**
  - *Fiat-Shamir Flaws:* If the challenge $e$ in a non-interactive proof is generated without hashing the entire transcript (including the public key and commitments), the proof can be forged.
  - *Weak Parameters:* Reusing nonces across proofs.
- **Homomorphic Encryption:**
  - *Noise Flooding / Decryption Failures:* Deliberately causing noise overflow to leak information about the private key when the server returns a decryption failure.

---

## 15. Side-Channel Attacks

- **Timing Attacks:** The execution time of a cryptographic function depends on the secret data. Common in string comparisons (HMACs), modular exponentiation (if square-and-multiply is not constant time), and ECC scalar multiplication.
  - *Exploitation:* Perform statistical analysis over hundreds of requests. The correct guess will have a higher average response time.
- **Power/EM Analysis:** Usually provided as numeric traces (arrays of power consumption values) in CTFs.
  - *Exploitation:* Correlation Power Analysis (CPA) or Differential Power Analysis (DPA). Guess a key byte, calculate the expected power (using Hamming Weight/Distance model), and correlate with the provided traces.

---

## 16. Exploit Engineering Practices

- **Script Everything in Python/SageMath:** Do not use online tools like CyberChef for the core math if it requires looping or conditions. Write robust, deterministic scripts.
- **Local Testing First:** Always test your math against a dummy set of parameters (generate your own RSA key, your own ECC curve) before attacking the target. If your math is wrong, hitting the remote server won't fix it.
- **Use SageMath for Heavy Math:** Python is too slow/clunky for lattices, elliptic curves, and polynomial arithmetic. Use SageMath scripts (`.sage`) and run them directly.
- **Manage Remote State:** Use `pwntools` to handle network interactions efficiently. If the server is a padding oracle, multi-thread the byte guessing to save time, but respect connection limits.
- **Isolate the Flaw:** Don't get overwhelmed by a 1000-line crypto implementation. Trace the exact path of the flag and identify the 10 lines that actually encrypt it.

---

## 17. Toolchain Reference

| Tool | Purpose |
|---|---|
| **SageMath** | The absolute standard for advanced CTF crypto. Solves LLL, ECC, Coppersmith, DLP. |
| **pwntools** | Network interaction, remote scripting, bitwise utilities. |
| **pycryptodome** | Standard Python crypto library (AES, RSA, PKCS#7). |
| **sympy** / **gmpy2** | Fast prime generation, modular inverse, discrete log (for simple cases). |
| **RsaCtfTool** | Automated tool for common RSA attacks (Wiener's, Hastad, etc.). Good for triage. |
| **Z3 Theorem Prover** | SMT solver for reversing complex custom PRNGs or convoluted bitwise logic. |
| **hashpump** | Automated length extension attack tool. |
| **randcrack** | Predicts Python's random (MT19937) after observing 624 outputs. |
| **CyberChef** | Quick base conversions, simple XOR, data formatting. Not for complex math. |

---

## 18. SageMath and Python Snippet Reference

**SageMath - Coppersmith Small Roots:**
```python
P.<x> = PolynomialRing(Zmod(N))
# Example: Stereotyped message f = (prefix + x)^e - c
f = (prefix + x)^e - c
f = f.monic()
roots = f.small_roots(X=2^80, beta=1)
if roots:
    print(roots[0])
```

**SageMath - Elliptic Curve Instantiation:**
```python
p = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff
a = -3
b = 0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b
E = EllipticCurve(GF(p), [a, b])
G = E(0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296, 
      0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5)
print(E.order())
```

**Python - AES CBC Decryption:**
```python
from Crypto.Cipher import AES
cipher = AES.new(key, AES.MODE_CBC, iv)
pt = cipher.decrypt(ct)
```

---

## 19. Decision Tree

```text
Is the source code provided?
  No -> Treat as black-box oracle. Look for Padding Oracle, Length Extension, ECB block shifting.
  Yes -> Identify the cryptographic primitive.

What is the primitive?
  Block Cipher (AES/DES) -> Check mode of operation. IV reused? ECB? Padding Oracle?
  Stream Cipher (RC4/XOR) -> Key reused? Keystream reused? Nonce static?
  RSA -> Extract N, e. Is N factored? e small? d small? Partial bits known?
  Diffie-Hellman -> Is p prime? Is p-1 smooth (Pohlig-Hellman)? Subgroup validated?
  ECC -> Is the curve standard? Point validated? Nonce k reused in ECDSA?
  Custom Math / LCG -> Can it be modeled as a system of equations? Use Z3 or LLL.
```

---

## 20. Failure Mode Diagnostics

| Symptom | Likely cause | Resolution |
|---|---|---|
| Padding oracle script hangs or loops | Connection limits / Server timeout | Use threading, add retries, reduce connection rate. |
| Coppersmith `small_roots` returns empty | Root bounds `X` or `beta` are wrong | Increase `epsilon`, adjust `X` to the exact upper bound of the missing data. |
| Z3 hangs indefinitely | Math is too non-linear (e.g., modular exponentiation, hashing) | Do not use Z3 for heavy crypto. Use SageMath or specific algorithms. |
| SageMath scripts fail syntax | Python 2/3 mixing or integer division | Use `Integer()` to ensure Sage types, use `//` for floor division in Python 3. |
| AES decryption yields gibberish | Wrong IV or Key format | Check if hex/bytes mismatch. Check if key is hashed before use. |

---

## 21. Exploit Skeleton

```python
from pwn import *
import json

HOST, PORT = 'remote.host', 1337

def start():
    if args.REMOTE:
        return remote(HOST, PORT)
    return process(['python3', 'server.py'])

io = start()

# Stage 1: Parameter Extraction
# io.recvuntil(b'N = ')
# N = int(io.recvline().strip())
# log.info(f"Extracted N: {N}")

# Stage 2: Mathematical Attack (Often done offline via SageMath first)
# p, q = factor_modulus(N) ...
# d = inverse(e, (p-1)*(q-1))

# Stage 3: Decryption / Forgery
# payload = pow(target_msg, d, N)

# Stage 4: Interaction
# io.sendlineafter(b'> ', str(payload).encode())
io.interactive()
```

---

## 22. Worked Methodology Example

1. **Identify Artifacts:** Provided `server.py` and a remote endpoint.
2. **Static Triage:** `server.py` uses ECDSA for authentication. It signs a random challenge.
3. **Source Code Audit:** We notice that the nonce `k` is generated as `k = random.getrandbits(128)` instead of 256 bits, or `k` is reused if we send the same message twice. Let's assume nonce reuse.
4. **Weakness Hypothesis:** ECDSA nonce reuse allows recovery of the private key.
5. **Mathematical Modeling:** $k = (z_1 - z_2) / (s_1 - s_2) \pmod n$. $d = (s_1 \cdot k - z_1) / r \pmod n$.
6. **Local Testing:** Write a Python script using `gmpy2` to perform the modular inverse and verify on dummy signatures.
7. **Exploit Execution:** Connect to the remote server using `pwntools`, request two signatures for the same message, extract $r, s_1, s_2, z_1, z_2$.
8. **Key Recovery:** Compute $d$ using the script.
9. **Validation:** Use $d$ to sign the "admin" command, send it, and retrieve the flag.

---

## 23. Glossary

| Term | Definition |
|---|---|
| **Plaintext/Ciphertext** | The unencrypted/encrypted message. |
| **Nonce / IV** | Number Used Once / Initialization Vector. Randomness added to ensure identical plaintexts yield different ciphertexts. |
| **Oracle** | A system (usually the remote server) that answers queries, inadvertently leaking information (e.g., padding validity, parity). |
| **CRT (Chinese Remainder Theorem)** | Theorem used to reconstruct a number from its remainders modulo several pairwise coprime numbers. |
| **LLL** | Lenstra-Lenstra-Lovász lattice reduction algorithm. |
| **ECDLP** | Elliptic Curve Discrete Logarithm Problem. The core hard problem ECC relies on. |
| **HMAC** | Hash-based Message Authentication Code. Prevents length-extension attacks. |
| **PRNG / CSPRNG** | (Cryptographically Secure) Pseudo-Random Number Generator. |

---

## 24. Forbidden Anti-Patterns

- **Do NOT attempt brute-forcing keys larger than ~40 bits.** CTF cryptography is almost never about brute force. Look for the math flaw.
- **Do NOT skip Weakness Analysis and jump to guessing.** Cryptography is exact. If you don't understand the vulnerability mathematically, your exploit will fail.
- **Do NOT assume AES/RSA/ECC are 'unbreakable'** without first checking for common implementation flaws (padding oracles, small exponents, invalid curves).
- **Do NOT write heavy math solvers in Python if SageMath is available.** SageMath handles polynomial rings, finite fields, and lattices natively. Python will frustrate you.
- **Do NOT reuse locally-assumed parameters.** Extract the exact `N`, `e`, `curve` from the actual challenge instance.
- **Do NOT submit to a validation endpoint until the secret is self-verified locally.** Failing a validation check usually resets the server state, losing your progress.
- **Do NOT ignore the constraints.** If a challenge restricts input characters or length, factor those constraints into your mathematical model immediately.