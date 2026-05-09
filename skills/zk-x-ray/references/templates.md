---
title: zk-x-ray Output Templates
impact: HIGH
impactDescription: Output structure for `x-ray.md`, `circuit-map.md`, and §5 of `invariants.md` (Circuit↔Solidity Consistency). Used during Phase 3 (Write Outputs). Slim templates -- defers to pashov's templates for Solidity-only sections.
tags: zk, output, templates, x-ray, circuit-map, invariants, eip-readiness
---

# Output Templates

Slim templates focused on the ZK-hybrid-specific pieces. For Solidity-only sections (entry points, single-contract invariants, scope tables), follow pashov/x-ray's templates.md verbatim -- this file only documents the ZK-specific structure.

---

## `x-ray.md` (top-level)

```markdown
# ZK X-Ray Report

> [Protocol Name] | [N] in-scope nSLOC + [N] circuit nSLOC | `[short-hash]` (`[branch]`) | [Foundry + Nargo / Hardhat + Noir / etc.] | [DD/MM/YY]

---

## 1. Protocol Overview

**What it does:** [one sentence -- the core mechanism, framed as proof-of-X without revealing Y]

- **Subjects/callers**: [who interacts and why]
- **Provers/issuers**: [who generates proofs / signs commitments off-chain]
- **Core flow**: [the main proof-submit operation, in 3-5 arrow-chain lines]
- **Proof types**: [N circuits / proof types, listed]
- **Trust kernel**: [proving system + version, e.g. UltraHonk on bb 4.0.0-nightly.20260120]
- **Admin model**: [owner + role split + timelock posture]

### Scope

| Subsystem | Components | nSLOC | Role |
|-----------|------------|------:|------|
| Solidity contracts | [list] | [N] | [role] |
| Noir circuits | [list] | [N] | [role] |
| Generated verifiers | [N x UltraHonk verifier] | [out of scope] | regenerated from circuits |
| Libraries | [list] | [N] | [role] |
| **In-scope total** | | **[N]** | |

### Core Flow

[3-5 arrow chain diagrams. One MUST trace a proof from prover -> on-chain submission -> registry validation -> verifier call -> attestation storage. Use concrete contract names, not interfaces.]

---

## 2. Threat & Trust Model

[Apply pashov's bullet brevity rule. One tight sentence per bullet.]

### Protocol Classification

> Protocol classified as: **[Primary]** with **[Secondary]** characteristics

[1-2 sentences explaining why, citing detection signals from `references/zk-threats.md`.]

### Adversary Ranking

[Use ZK-specific adversary list from zk-threats.md. Rank by relevance to this protocol. Typical 4-6 entries. ONE sentence per entry naming WHO and WHY they matter to this protocol.]

1. **Soundness-bug exploiter** -- [why relevant, mitigation pattern]
2. **[etc.]**

### Trust Boundaries

[Each boundary as a one-line bullet: name, what's trusted, single worst instant action it leaves open, code ref. Max 2 lines.]

### Key Attack Surfaces

[Sorted by priority. Investigation pointers, NOT exploit writeups (DO-NOT-EXPLOIT rule). Cross-link to invariants.md and circuit-map.md when relevant.]

- **[Surface name]** &nbsp;&#91;[CSC-3](invariants.md#csc-3), [I-7](invariants.md#i-7)&#93; -- [code ref + concern + what to trace]

### Circuit-Specific Concerns

[Required section unique to ZK hybrids. 2-4 bullets. Each cites a specific circuit + line.]

- **[Concern]** -- [`circuits/<name>/src/main.nr:LN`] -- [the concern, max 2 lines]

### Public-Input Layout Concerns

[Cross-reference circuit-map.md. Surface any rows with parity drift (CSC-2 / CSC-3 = On-chain=No).]

### Toolchain & Reproducibility

[Required. Cite the pin status of `bb`, `nargo`, and the generated verifiers (in git or build-time?). Drop the verdict tier by one if unpinned.]

---

## 3. Invariants

> ### 📋 Full invariant map: **[invariants.md](invariants.md)**
>
> - **[N] Enforced Guards** (`G-1` … `G-N`)
> - **[N] Single-Contract** (`I-1` … `I-N`)
> - **[N] Cross-Contract** (`X-1` … `X-N`)
> - **[N] Economic** (`E-1` … `E-N`)
> - **[N] Circuit↔Solidity Consistency** (`CSC-1` … `CSC-N`) -- ZK-hybrid-specific

---

## 4. Documentation & Tests

[Same as pashov: documentation table + test depth table + gaps. Two ZK-specific rows in the test table:]

| Category | Count | Contracts/Circuits Covered |
|----------|------:|----------------------------|
| Circuit unit tests | [N nargo test functions] | [list] |
| Parity tests (circuit↔solidity hash agreement) | [N] | [list] |

---

## 5. Pre-EIP / Pre-Audit Findings

[Required section if `eip-draft*.md` or `erc-*.md` is present. Severity-tagged: High / Medium / Low / Informational. Each finding gets a stable F-N ID, code refs, and a recommendation.]

### F-1 -- [Title] ([Severity])

**Where:** [file:line refs]

**Issue:** [2-4 sentences -- the concern, the silent-fail mode, the impact]

**Recommendation:** [actionable, possibly multiple options if there's a tradeoff]

[Repeat for each finding.]

---

## 6. Developer & Git History

[Same as pashov, no ZK-specific changes.]

---

## ZK X-Ray Verdict

**[TIER]** -- [one sentence]

[Tier calculation: pashov's rules + two ZK-specific overrides:]
- **Public-input parity drift** (any CSC-2 / CSC-3 with On-chain=No) -> drop one tier
- **Unpinned `bb` / `nargo`** -> drop one tier
- **Open High-impact pre-EIP finding** when EIP submission is the goal -> tier = EXPOSED regardless

**Pre-EIP punch list** (if applicable):
1. [F-N] [one sentence]
2. ...

**Structural facts:**
1. [N nSLOC, N circuits, N proof types, etc.]
2. ...
```

---

## `circuit-map.md` (ZK-hybrid-specific deliverable)

```markdown
# Circuit Map

> [Protocol Name] | [N] circuits | [N] proof types | Proving system: [UltraHonk / Groth16 / Halo2]

---

## 1. Public Input Parity

The most important table in this document. If any row has drift, **fix it before reading anything else**.

| Circuit | proofType ID (sol const) | proofType ID (nr const) | Logical pub count (`main.nr`) | Physical pub count (`target/*.json`) | Solidity expected count (`expectedPublicInputCount`) | NUMBER_OF_PUBLIC_INPUTS (generated verifier) |
|---------|:------:|:------:|:-:|:-:|:-:|:-:|
| [name] | [0xNN] | [0xNN] | [N] | [N+16N_arr] | [N] | [N+16] |

**Acceptance rule:** physical = logical + 16×(array_count) where 16 is UltraHonk's array element flattening factor; Solidity expected = logical; generated verifier's NUMBER_OF_PUBLIC_INPUTS = physical. Any deviation is a finding.

---

## 2. Per-Circuit Layout

For each circuit, document:

### `circuits/[name]/src/main.nr`

**`main()` signature** (logical pub fields, in order):

| # | Field name | Type | Solidity offset | Domain check on Solidity side |
|---|-----------|------|-----------------|--------------------------------|
| 0 | [name] | [Field / [Field; N] / etc.] | `[0:32]` | [registry / msg.sender / chainid / NONE] |

**Hashing primitives in this circuit:**
- [pedersen_hash / poseidon / keccak256] called [N] times. Domain tag: [literal bytes / constant from shared/ / NONE].

**In-circuit signature checks:**
- [yes/no]. If yes: scheme = [secp256k1 ECDSA / EdDSA / Schnorr]. Payload = [verbatim list of inputs digested].

**Submitter binding:**
- Public input: [yes/no]. Bound in in-circuit signature digest: [yes/no]. Bound in any registry hash: [yes/no].

[Repeat per circuit.]

---

## 3. Hash Domain Tags

Every domain tag used in a hash that is also computed off-chain or on-chain. Drift here is a silent-fail mode.

| Tag | In-circuit location | Off-chain location | On-chain location | Match? |
|-----|---------------------|--------------------|-------------------|--------|
| [tag bytes] | `circuits/shared/src/X.nr:LN` | [SDK file:LN] | [Solidity file:LN] | Yes / No |

Any No row is a finding.

---

## 4. Toolchain Pin Status

| Component | Pinned? | Pin location |
|-----------|---------|--------------|
| `bb` | yes/no | `.tool-versions` / `flake.nix` / etc. |
| `nargo` | yes/no | [same] |
| Generated verifiers in git | yes/no | `src/generated/*.sol` |
| Verifier regeneration script | yes/no | `scripts/generate-fixtures.sh` |

Unpinned -> drop verdict tier.
```

---

## `invariants.md` (delta from pashov)

Use pashov's invariants.md template verbatim for §1 (Guards), §2 (Single-Contract), §3 (Cross-Contract), §4 (Economic). **Add §5:**

```markdown
## 5. Circuit↔Solidity Consistency (CSC)

Properties that must hold across the Solidity-side and circuit-side commitments. The highest-signal section for ZK hybrids -- a row with On-chain=No is simultaneously an invariant and a silent-fail mode.

---

#### CSC-1

On-chain: **Yes/No**

> [the property -- e.g. "every proofType ID in `ProofTypes.sol` matches a circuit's expected proofType constant in `circuits/shared/src/constants.nr`"]

**Solidity side** -- `ProofTypes.sol:LN-LN`

**Circuit side** -- `circuits/shared/src/constants.nr:LN-LN` (or per-circuit `main.nr` literal)

**If violated** -- [consequence, e.g. "wrong verifier routes for the affected proofType, all legitimate proofs revert"]

---

[Repeat #### CSC-N for every CSC invariant. Categories to cover:]
- ProofType ID parity (Solidity const ↔ circuit const)
- Public input count parity (Solidity expected ↔ circuit logical)
- Public input order parity (Solidity offset semantics ↔ circuit `main()` ordering)
- Domain tag parity (in-circuit hash tag ↔ off-chain registration tag)
- Submitter binding parity (Solidity check vs in-circuit hash digest)
- Hashing primitive consistency (Pedersen on both sides, etc.)
```

---

## Bullet brevity rule (applies everywhere)

Same as pashov's: one tight sentence per bullet, code refs carry the evidence, do not duplicate what `file:line` already shows. Cut "→ attacker drains X" exploit-chain prose; replace with "Worth checking..." / "Worth tracing..." / "Worth confirming..."
