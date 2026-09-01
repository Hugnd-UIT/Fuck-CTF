# Cryptography Playbook

---

## Table of Contents

1. Scope and Goal Model
2. Master Workflow
3. Tactics Catalog
4. Procedure Detail
5. Forbidden Anti-Patterns

---

## 1. Scope and Goal Model

A cryptography challenge typically involves finding weaknesses in how an encryption, hashing, or signature algorithm is implemented, configured, or used.

Terminal objectives typically involve:
- Recovering a private key or plaintext.
- Forging a valid signature or MAC.
- Defeating a custom PRNG.
- Bypassing an authentication protocol.

---

## 2. Master Workflow

```
Cipher Identification
        |
Source Code Audit
        |
Parameter Extraction
        |
Weakness Analysis
        |
Attack Implementation
        |
Key Recovery
        |
Decryption / Forgery
        |
Session State Management
        |
Validation
```

---

## 3. Tactics Catalog

- **Cipher-Identification**
- **Source-Code-Audit**
- **Parameter-Extraction**
- **Weakness-Analysis**
- **Attack-Implementation**
- **Key-Recovery**
- **Decryption**
- **Session-State-Management**
- **Oracle-Reliability**
- **Validation**

*(Note: If you need to search for external writeups, references, or exploit examples, do not use a tactic. Instead, supply your search term in the `rag` field of your plan JSON).*

---

## 4. Procedure Detail

### 1. Cipher-Identification
Inspect all provided files/output to determine the cryptosystem precisely. Check for telltale signs: base64/hex/PEM encoding, `-----BEGIN` headers, explicit modulus/exponent/ciphertext values, ECC curve parameters, Diffie-Hellman parameters, block size and mode hints, an IV or nonce, or a fully custom/from-scratch algorithm given as source. Distinguish 'textbook primitive attacked directly' challenges from 'custom implementation with a deliberate bug' challenges early.

### 2. Source-Code-Audit
If source code is provided, read it completely line by line before forming any hypothesis. Specifically look for: parameters generated with insufficient entropy or a small/bounded range, a homemade primitive that resembles but subtly deviates from a standard one, a reused nonce/IV/key across multiple operations, a debug/test code path left enabled, an off-by-one or wrong-variable bug in a comparison/validation function, and any place where the server echoes back more information than intended.

### 3. Parameter-Extraction
Extract every numeric/byte parameter into a script-usable form. Explicitly record which parameters are reused across multiple connections/samples versus freshly regenerated each time, since reuse across sessions is itself frequently the exploited weakness.

### 4. Weakness-Analysis
Enumerate KNOWN structural weaknesses for the identified scheme and verify each candidate against the actual extracted parameters by direct computation, not assumption:
- **RSA**: small/low public exponent e, common-modulus attack, shared prime factor across two or more given moduli, Fermat factorization when p and q are numerically close, Wiener's attack or Boneh-Durfee for a small private exponent d relative to n, partial key exposure when some bits of p/q/d are leaked, related/stereotyped-message Coppersmith attacks when partial plaintext structure is known, Bleichenbacher's padding-oracle attack against PKCS#1 v1.5.
- **Diffie-Hellman / discrete-log**: small or smooth group order enabling Pohlig-Hellman, small subgroup confinement attacks, baby-step-giant-step or Pollard's rho.
- **ECC/ECDSA**: invalid-curve or small-subgroup attacks when point validation is missing, reused or predictable nonce `k` across two or more signatures, biased/partially-known nonce bits exploitable via lattice methods, use of a non-standard weak curve.
- **Classical/XOR/stream ciphers**: repeating-key XOR, nonce/keystream reuse, predictable/seeded PRNG-derived keys.
- **Block ciphers**: AES-ECB, CBC padding oracle, CBC bit-flipping, IV reuse or a predictable/attacker-supplied IV, and key/IV confusion.
- **Hashing/MAC**: length-extension attacks against unsalted MD5/SHA1/SHA256/SHA512, weak/short HMAC, hash-collision-based forgery.

### 5. Attack-Implementation
Write ONE python script that performs the FULL attack in one deterministic run. Where the correct weakness is not immediately certain, structure the script to try multiple candidate attacks in sequence within the same run rather than committing to one guess and stopping. For lattice-based attacks, construct the lattice basis explicitly and run LLL reduction as a single self-contained step within the script.

### 6. Key-Recovery
Once the attack yields raw numeric material, reconstruct the actual usable key object within the same script so decryption/signing/forgery can proceed immediately.

### 7. Decryption
Use the recovered key/plaintext/forged value to decrypt the target ciphertext, forge the target signature/token, or reconstruct the target message, and print the flag in cleartext to stdout.

### 8. Session-State-Management
Determine whether the server maintains per-connection state. If it does, ALL attack queries against that state MUST be sent within ONE persistent socket connection. Treat any dropped/closed connection as a full state reset requiring the attack to restart from scratch with newly generated secrets.

### 9. Oracle-Reliability
If an oracle's response is probabilistic or noisy, use statistical methods (repeated queries with majority voting, averaged timing samples with outlier rejection) to reach high confidence before progressing, and script this batching into the same attack run automatically.

### 10. Validation
Before submitting a final answer/flag to any check/validation endpoint, verify internal consistency of the recovered material locally (e.g., re-encrypt a recovered plaintext with the public key and confirm it reproduces the given ciphertext, re-verify a forged signature). Only submit once this self-check passes.

---

## 5. Forbidden Anti-Patterns

- Do NOT attempt brute-forcing an encryption key one candidate value per plan/execute cycle. Any keyspace search must be a single script iterating the full space internally.
- Do NOT skip Weakness-Analysis and jump to guessing; classical/RSA/XOR/ECC challenges almost always rely on a specific known mathematical weakness deliberately built into the challenge, not brute force.
- Do NOT assume AES/RSA/ECC are 'unbreakable' without first checking for the common CTF-style implementation flaws in Weakness-Analysis and reading any provided source code in full for the deliberate bug.
- Do NOT submit to a validation/check endpoint until the full secret is confidently recovered and self-verified. Failing a validation check usually resets the entire connection state.
- Do NOT reuse a locally-assumed parameter without re-extracting it from the actual challenge files; copied textbook parameters will not match the challenge instance.
- Do NOT treat a dropped or closed network connection as a resumable checkpoint for a stateful attack; assume secrets have been regenerated and restart the attack sequence.
- Do NOT rely on a single noisy oracle query when a statistical batching approach is available and the oracle's reliability has not already been confirmed.
