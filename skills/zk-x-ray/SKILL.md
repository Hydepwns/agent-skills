---
name: zk-x-ray
description: >
  Pre-audit report generator for ZK + EVM hybrid protocols (Noir circuits +
  Solidity verifier / oracle layers). Produces an x-ray report, a classified
  entry-points map, an invariant catalog with a Circuit↔Solidity Consistency
  section, a per-circuit map, and an EIP-readiness verdict.
  TRIGGER when: project has both `foundry.toml` (or hardhat config) AND a
  `Nargo.toml` workspace; user asks for "zk-x-ray", "audit zk", "audit zkp",
  "zk readiness", "pre-eip review", "circuit-solidity audit", or "zk
  pre-audit"; EIP/ERC draft is being prepared for submission and a hybrid
  Solidity + Noir codebase needs a structural readiness check.
  DO NOT TRIGGER when: protocol is Solidity-only (use solidity-audit skill or
  pashov's x-ray); deep circuit-design questions without Solidity integration
  (use noir skill); general Ethereum tooling questions (use ethskills); when a
  full external audit is the goal rather than a pre-audit briefing.
metadata:
  author: DROOdotFOO
  version: "0.1.0"
  tags: zk, zero-knowledge, audit, noir, solidity, hybrid, eip, x-ray, pre-audit, ultrahonk, barretenberg
---

# zk-x-ray

Pashov's `x-ray` methodology adapted for ZK + EVM hybrids: Noir circuits +
Solidity verifier contracts + an oracle / registry layer that validates circuit
public inputs.

## What You Get

One invocation populates `[project-root]/zk-x-ray/` with:

- **x-ray report** -- protocol overview, ZK-aware threat model, attack surfaces, EIP-readiness verdict
- **entry-points map** -- Solidity entry points classified by access level (permissionless / role-gated / admin) with call chains
- **invariants catalog** -- guards + single-contract + cross-contract + economic + Circuit↔Solidity Consistency (CSC)
- **circuit map** -- per-circuit table covering public inputs (logical / physical / Solidity-expected / generated verifier `NUMBER_OF_PUBLIC_INPUTS`), hashing scheme, in-circuit signature checks, domain tags
- **architecture diagram** (optional SVG)

Plus a `parity-check.py` CI gate that verifies Noir circuit, generated verifier,
and Solidity expected public-input arities all agree -- the #1 silent-fail mode
in ZK + EVM hybrids.

## Why this skill exists

Pashov's `x-ray` covers Solidity-only protocols brilliantly. ZK + EVM hybrids
have a class of silent-fail modes that no Solidity-only audit catches:

1. **Public-input layout drift.** A circuit's `main()` adds a `pub` field; the regenerated verifier accepts the new layout; the on-chain `validatePublicInputs` length check still expects the old count -- every legitimate proof reverts. Worse: re-ordering of two same-typed `pub` fields silently swaps semantic meaning, count unchanged.
2. **Domain-tag mismatch.** Off-chain key registration computes a Pedersen / Poseidon hash with one domain tag; the in-circuit version uses another. The on-chain registry accepts the off-chain hash; every legitimate proof reverts at the registry check.
3. **Unpinned toolchains.** `bb` and `nargo` have multiple beta releases per quarter. A verifier deployed under one `bb` version may not be reproducible from the same circuit under a later version. Soundness fixes only propagate to deployed contracts if the team can rebuild the exact verifier they shipped.
4. **Cross-deployment proof replay.** ZK proofs do not bind to a chain or contract address unless the circuit explicitly commits them in a public input. Replay-resistance reduces to off-chain replay DBs + on-chain `submitter == msg.sender` checks -- easy to miss until you trace a proof through two Oracle deployments.

zk-x-ray's invariant catalog adds a Circuit↔Solidity Consistency (CSC) section
that calls out each of these explicitly with `On-chain enforced? Yes/No` flags.

## Tips

- **Start with the circuit-map.** The first place a hybrid protocol breaks is the circuit↔solidity boundary. If the public-input parity table has any drift rows, fix those before reading anything else.
- **Treat the EIP-readiness verdict as a gate.** Any High-impact finding open at submission grades the protocol EXPOSED regardless of test coverage. The verdict is opinionated by design.
- **Pair with `solidity-audit` + `noir`.** zk-x-ray surfaces *what to look at*; the deep methodology for each side lives in those skills.

## See also

- `noir` -- ZK circuit design, constraint optimization, Aztec integration
- `solidity-audit` -- Foundry-first audit methodology + vulnerability taxonomy for the Solidity side
- `ethskills` -- EIP / ERC standards lookup, RPC providers, framework selection
- `blockscout` -- on-chain data queries when validating deployment state

This skill **complements** all four. For Solidity-only projects, defer to
`solidity-audit` plus pashov's public `x-ray`; for circuit-only design
questions, defer to `noir`. zk-x-ray's value is the seam where the two meet.

## Reading guide

| Working on | Read |
|------------|------|
| ZK threat profiles, adversary ranking, ZK invariant taxonomy | [references/zk-threats.md](references/zk-threats.md) |
| Output file structure, CSC invariant template, EIP-readiness verdict format | [references/templates.md](references/templates.md) |

## Pipeline

3 phases, sequential. `$SKILL_DIR` = the directory containing this `SKILL.md`
(resolve from the load path the same way pashov's x-ray does).

Track progress with TaskCreate before running -- create three tasks
(`Phase 1: Enumerate`, `Phase 2: Read & classify`, `Phase 3: Write outputs`),
mark exactly one `in_progress` at a time.

---

## Phase 1: Enumerate

Detect project layout. Two flavors:

- **Solidity-only**: `foundry.toml` or `hardhat.config.*` at root, no `Nargo.toml`. Fall back to pashov's x-ray methodology in this case -- this skill's value-add is for hybrid projects.
- **Hybrid (the target)**: `foundry.toml` + `circuits/Nargo.toml` (workspace) or `circuits/*/Nargo.toml` (single).

Run enumeration + parity check (single Bash call, sequential):

```bash
mkdir -p [project-root]/zk-x-ray && \
  bash $SKILL_DIR/scripts/enumerate.sh [project-root] && \
  python3 $SKILL_DIR/scripts/parity-check.py [project-root]
```

`enumerate.sh` outputs labeled sections: `=== Solidity Source ===`,
`=== Noir Circuits ===`, `=== Noir Public Inputs (logical) ===`,
`=== Noir Public Inputs (physical) ===`, `=== Generated verifier
NUMBER_OF_PUBLIC_INPUTS ===`, `=== Solidity expectedPublicInputCount ===`,
`=== Tests ===`, `=== Toolchain Pins ===`, `=== Git ===`.

`parity-check.py` produces a single table that consolidates the four
public-input arity sources (logical / physical / Solidity expected / generated
verifier `NUMBER_OF_PUBLIC_INPUTS`) into one row per circuit and exits 1 if any
drift is detected. **A drift exit is a P0 finding** -- it must be resolved
before the rest of the audit can proceed (the Oracle's input validation will
reject every legitimate proof, or worse, accept proofs against an off-layout
input blob).

In the same message (parallel), launch:

1. **Foundry coverage** (background): `cd [root] && forge coverage 2>&1 || forge coverage --ir-minimum 2>&1`. Don't wait.
2. **Circuit test run** (background): if `circuits/Nargo.toml` exists, `cd circuits && nargo test --workspace 2>&1`.
3. **Reference reads** (foreground, parallel):
   - `$SKILL_DIR/references/zk-threats.md` -- ZK-specific threat profiles
   - `$SKILL_DIR/references/templates.md` -- output templates
4. **Spec/EIP detection** (Glob): `**/{eip,erc,spec,whitepaper,protocol,architecture,README,THREAT*}*.{md,pdf}` excluding `node_modules/`, `lib/`, `target/`, `out/`, `cache/`, `zk-x-ray/`. If size-aware: ≤5 files & ≤300 lines each, read directly in Phase 2's parallel batch; else delegate to a sonnet subagent for structured extraction (same prompt as pashov's templates.md spec extractor).

Proceed to Phase 2 without waiting for coverage / nargo test.

---

## Phase 2: Read sources + classify

In **one message**, parallel-call:

### 2a. Solidity source reads

Same logic as pashov: ≤20 files -> direct Read calls; >20 files -> sonnet subagents
grouped by subsystem. Per-file extraction includes the standard pashov fields
(type, inheritance, roles, state vars, external calls, fund flows, guards,
delta-writes, enum/one-shot transitions) **plus**:

- **Public-input decoders**: every `_validate*Inputs(...)` / `decodePublicInputs(...)` function. For each, record the offset layout (e.g. `[0:32] = jurisdiction`, `[32:64] = providerSetHash`, ...). This is the on-chain side of the circuit↔solidity contract; the circuit side comes from 2b.
- **Hash schemes**: every `keccak256(abi.encode/encodePacked(...))` or call into `EIP712*` libraries. Note what is committed (chainid? this-address? msg.sender? caller-supplied param?).
- **Signature recovery**: every `ecrecover(...)` or wrapper. Note malleability protection (low-s check) and v handling.

### 2b. Circuit source reads

If `circuits/` exists, read every `circuits/*/src/main.nr` and `circuits/shared/src/lib.nr`
(plus any sub-modules). For each circuit, extract:

- **`main` signature**: every `pub` parameter with its type. This is the *logical* public input list. Count: `N`.
- **Constraint count and complexity hints**: any `assert` / `assert_eq` / `verify` calls.
- **Hashing primitives**: `pedersen_hash`, `poseidon`, `keccak256`, `SHA-256` -- whichever the circuit uses. Note the inputs.
- **In-circuit signature checks**: e.g. `secp256k1::verify_signature` or equivalent. Record which payload is signed.
- **Domain tags**: any string/byte-array constants used as separator inputs to hashes.
- **Submitter binding**: whether `submitter` is a public input AND whether it is committed in any in-circuit hash.

### 2c. Public-input ABI parity

If circuits have been compiled (`circuits/*/target/*.json` exists), parse each
target JSON and extract the `abi.parameters` array -- specifically the `visibility:
"public"` entries. The count of these is the **physical** public input count, not
the logical count. (Noir flattens arrays into individual field elements: a `pub
[Field; 8]` is 8 physical inputs, 1 logical input. UltraHonk's
`NUMBER_OF_PUBLIC_INPUTS` constant in the generated verifier reflects the
physical count.)

For each circuit produce a row:

| Circuit | Logical pub count (from `main.nr`) | Physical pub count (from target JSON) | Solidity expected count (from on-chain library) |
|---------|------:|------:|------:|

The skill flags any row where the Solidity expected count does NOT match the
logical count, OR where the physical count and the generated verifier's
`NUMBER_OF_PUBLIC_INPUTS` disagree. This is the most common silent-fail mode in
ZK + EVM hybrids: the circuit changes its `pub` arity, the regenerated verifier
accepts the new layout, but the Oracle-level `validatePublicInputs` length check
still expects the old count and rejects every legitimate proof.

### 2d. Entry-point grep scan

Same as pashov's x-ray (POSIX-portable single-line + multiline grep, exclude
interfaces/mocks/views/pures). Classify into permissionless / role-gated /
admin-only.

### 2e. ZK threat profile

Use [references/zk-threats.md](references/zk-threats.md) to assign threat profiles. Most ZK protocols are
hybrids of multiple types -- common combinations:

- **Verifier router + Oracle**: Solidity contract holds a registry of generated
  ZK verifier addresses and validates public inputs before forwarding to the
  selected verifier. (e.g. erc-xochi-zkp.) Adversaries: soundness-bug exploiter,
  cross-deployment replayer, registry-curation compromise.
- **Bridge with ZK proof of state**: classic bridge adversaries plus
  circuit-soundness adversary.
- **Privacy mixer**: nullifier-based; commitment tree integrity adversary plus
  classic merkle-root manipulation adversaries.
- **ZK rollup**: state-transition function in a circuit; adversaries include
  circuit soundness, sequencer compromise, validity-proof forgery.

State the protocol's classification explicitly: `Protocol classified as: ZK
[type] with [secondary] characteristics`.

### 2f. Invariant synthesis

Run pashov's invariant synthesis (Conservation / Bound / Ratio / StateMachine /
Temporal -- two-pass guard extract + lift) over the Solidity sources. **Add a
sixth category** specific to ZK hybrids:

**Circuit↔Solidity Consistency** (CSC). Each row pairs a Solidity-side commitment
with a circuit-side commitment that the proof must satisfy:

| ID | Property | Solidity side | Circuit side | On-chain enforced? |
|----|----------|---------------|--------------|--------------------|
| CSC-1 | `proofType` constants match between Solidity library and circuit module | `ProofTypes.sol:9-19` | `circuits/shared/src/constants.nr` | Yes via length check, NO via value collision check (see CSC-3) |
| CSC-2 | Public input *layout* expected by Solidity matches circuit `main()` ordering | `_validate*Inputs:[offsets]` | `circuits/*/src/main.nr` `pub` order | NO -- only the count is checked; mis-ordered fields silently pass |
| CSC-3 | Hash domain tags committed in-circuit match domain tags expected by registries | `compute_signer_pubkey_hash` callsite | `circuits/shared/src/sig.nr` | NO -- commitments are equal-or-revert at the boundary, but mismatch only manifests when the registry rejects every legitimate proof |
| CSC-4 | `submitter` public input is bound in any in-circuit signature digest | `proofSubmitter != msg.sender` revert | `compute_payload_hash` includes `submitter` | Yes if both sides agree |

A CSC row is **the highest-signal output for ZK hybrids** -- ordering or
domain-tag drift between circuit and Solidity is the #1 silent-fail mode and
neither audit pass alone catches it.

---

## Phase 3: Write outputs

In **one message**, parallel-write:

1. **x-ray report** at zk-x-ray/x-ray.md -- top-level report. Sections per the templates reference:
   - Overview + scope table (separating Solidity contracts, circuits, generated verifiers, libraries)
   - Threat & Trust Model (using ZK-aware adversary ranking from the threats reference)
   - Attack surfaces (cross-link to the invariants and circuit-map files)
   - **Pre-EIP Findings** -- if the project has an EIP / ERC draft, this section is required: concrete pre-submission action items, severity-tagged.
   - Verdict (FORTIFIED / HARDENED / ADEQUATE / FRAGILE / EXPOSED)
2. **entry-points map** at zk-x-ray/entry-points.md -- pashov-style classified entry points
3. **invariants catalog** at zk-x-ray/invariants.md -- pashov-style §1-4 PLUS §5 (Circuit↔Solidity Consistency)
4. **circuit map** at zk-x-ray/circuit-map.md -- per-circuit table covering public-input parity,
   hashing scheme, in-circuit signature checks, domain tags. **This file is
   unique to zk-x-ray** and the deliverable that purely-Solidity audits miss.

Optional 5th file: if the project warrants a diagram, generate an architecture
SVG via the same generator flow as pashov's skill (port that script in if/when
the skill is upgraded beyond a draft).

### Verdict tier signals (ZK-specific overrides)

The pashov tier-calculation rules apply, with two ZK-specific additions:

- **Public-input parity:** any drift (CSC-2 / CSC-3 with On-chain=No) drops the
  verdict by one tier.
- **Toolchain pinning:** if `bb` and `nargo` versions are NOT pinned (no
  `.tool-versions`, `flake.nix`, or equivalent), drop one tier. Soundness fixes
  in `bb` only propagate if the team can reproduce the exact verifier they
  deployed; unpinned toolchains break this guarantee.

### Pre-EIP gate (additional, for EIP submissions only)

If `eip-draft*.md` or `erc-*.md` is present, the Verdict section MUST include a
"Pre-EIP punch list" with concrete action items in priority order. The skill is
opinionated: an EIP submission with any High-impact finding open is graded
EXPOSED regardless of the test/docs/access-control tier.

---

## Constraints

- Under 500 lines for the x-ray report. Compress overview + repo metadata before threat
  model, invariants, or findings.
- No fabrication. Say "could not determine" when uncertain.
- Single pass. No partial outputs.
- Vendor-neutral framing. Do not reference audit firms, contests, or bounty
  programs in the report itself.
- Solidity-only projects: defer to pashov's x-ray. State this and exit early.

---

Before doing anything else, print this exactly:

```
zk-x-ray
========
ZK + EVM hybrid pre-audit report generator.
Sources: pashov/skills/x-ray (methodology), tailored for Noir + Solidity hybrids.
```
