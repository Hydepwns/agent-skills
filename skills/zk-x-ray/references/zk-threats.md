---
title: ZK + EVM Hybrid Threat Profiles
impact: CRITICAL
impactDescription: Threat identification library used to classify ZK hybrid protocols, rank adversaries, and select the relevant attack surfaces during Phase 2 / Phase 3 of zk-x-ray. Also provides ZK-specific invariant taxonomy (PI-N, DT-N, VR-N, TS-N, REG-N, CRYP-N).
tags: zk, threats, adversaries, soundness, public-inputs, domain-tags, replay, audit
---

# ZK + EVM Hybrid Threat Profiles

> **HOW TO USE THIS FILE**
>
> Treat this as a threat *identification* library for ZK + EVM hybrids -- not a prose template.
>
> - **In Phase 2e**, use the detection signals to classify the protocol.
> - **In Phase 3**, use adversary rankings, attack patterns, and critical invariants to know *what to look for* in the threat model section. Translate -- don't copy exploit-chain prose verbatim into Key Attack Surfaces; follow pashov's DO-NOT-EXPLOIT framing rule.

## Classification Signals

Detect protocol type from circuit + Solidity signals during Phase 2 reads.

| ZK Hybrid Type | Detection Signals |
|----------------|-------------------|
| **ZK Verifier Router** | One Solidity contract maps an enum/uint to multiple generated verifier addresses. Each proofType -> distinct circuit. (e.g. erc-xochi-zkp.) |
| **ZK Compliance Oracle** | Verifier router + a registry layer that validates *public inputs* against on-chain state (allowed roots, allowed configs, pubkey hashes). Stores attestations keyed by `(subject, jurisdiction)` or similar. |
| **ZK Bridge / Light Client** | Circuit proves a state transition or signature aggregation on a foreign chain. Solidity verifies + reads merkle proofs. State root / message root commitments. |
| **ZK Mixer / Privacy Pool** | Nullifier-based deposits + withdrawals. Commitment merkle tree. Proof of inclusion + nullifier spend. |
| **ZK Rollup** | State-transition function in a circuit. Sequencer posts batches. Validity proof or fraud proof. Forced inclusion / escape hatch. |
| **ZK Identity / Attestation** | Issuer signs a credential off-chain; circuit proves possession + selective disclosure. EAS-style attestation registry on-chain. |
| **ZK Oracle (private query)** | Circuit proves a value derived from private inputs and a published commitment. On-chain reads the public output. (Subset of Compliance Oracle.) |

**Hybrid classification:** rank by signal density. Common combos: `Verifier Router + Compliance Oracle + Identity` (erc-xochi-zkp). State `Protocol classified as: ZK [Primary] with [Secondary] characteristics` in the report.

---

## Common Adversaries (across all ZK hybrids)

Ordered by historical impact and frequency:

1. **Soundness-bug exploiter against the verifier.** A bug in the proving system (`bb`, gnark, snarkjs) or in a circuit's constraint set lets an attacker forge a proof for an arbitrary public input. The on-chain `verify()` returns `true` with no recourse downstream. **Mitigation pattern:** per-proof-type pause + version revocation + redeploy via timelock.
2. **Public-input substitution attacker.** The proof verifies, but the *public input layout* the on-chain contract expects does not match the circuit's `pub` ordering. The attacker sends a malformed `publicInputs` blob whose bytes happen to satisfy length checks but place semantic fields at unexpected offsets. **Mitigation:** strict per-offset validation that ties each field to a domain-specific check.
3. **Cross-deployment proof replayer.** A signed payload, in-circuit commitment, or merkle proof is reused on a second deployment that shares the same verifier or signer registry. Mitigated only by binding chainid + contract address into either (a) the circuit's public inputs, OR (b) the off-chain digest the prover signs.
4. **Domain-tag drift attacker.** Hash digests committed in-circuit use a different domain separator than the off-chain entity that registers commitments on-chain. The on-chain commitment "registers fine" but the circuit's commitment never matches it -> all legitimate proofs revert (DoS), OR the attacker engineers a digest that matches under both domain tags (forgery).
5. **Trusted-setup compromise** *(applicable to ZK rollups / mixers using Groth16 / KZG with a setup ceremony)*. If the toxic waste from the trusted setup is retained, the holder can forge proofs. Less applicable to PLONK-family schemes (Halo2, UltraHonk) which use universal updatable setups.
6. **Off-chain prover compromise.** The prover holds private inputs (signals, balances, keys). A compromised prover can choose which honest inputs to NOT prove (DoS) or generate proofs against forged private inputs that still verify (because privacy = no on-chain truth check on the witness). Not a ZK soundness break -- a trust-model break.
7. **Registry curation compromise** *(Compliance Oracle / Identity)*. The role responsible for adding allowed roots / config hashes / pubkey hashes can register adversary-controlled commitments. Mitigated by role split + timelock.
8. **Nullifier collision / reuse attacker** *(Mixer / Privacy Pool)*. Forge a nullifier for a deposit you don't own. Reuse a nullifier across two proofs.
9. **State-root forgery** *(Bridge / Rollup)*. Submit a fake state root via a bug in the circuit or a compromised sequencer.
10. **MEV against proof submission.** Front-run a user's `submitProof()` to claim a reward, capture an attestation slot, or steal a withdrawal. Common in mixers and bridges.

---

## Adversary-Specific What-to-Look-For

### Soundness-bug exploiter

What to look for first:

1. Is the proving system + version pinned? `.tool-versions`, `flake.nix`, `nix shell` config, or equivalent. **An unpinned toolchain is the single biggest soundness-incident-response risk.**
2. Are generated verifiers checked in? They must be -- a regenerated verifier may differ byte-for-byte even from the same circuit on different `bb` versions.
3. Is there a per-proof-type pause + revocation flow? How fast does an emergency response take?
4. Are there integration tests covering "soundness bug discovered, mitigate, redeploy"? If not, the runbook is untested.

### Public-input substitution / layout drift

What to look for first:

1. The Solidity-side `_validate*Inputs(...)` -- does it check *each offset* against a specific domain (registry, msg.sender, chainid)? Or only a length check?
2. Compare to the circuit's `main()` `pub` declarations. Identical types adjacent to each other are the drift hazard: swap them and the count check passes.
3. Does the on-chain check assert the expected count matches what the generated verifier consumes (`NUMBER_OF_PUBLIC_INPUTS - 16` for UltraHonk, accounting for array flattening)? An off-by-N from array flattening is invisible until proof generation.

### Cross-deployment replay

What to look for first:

1. Does the circuit's public input list include `chain_id` (or `block.chainid` from the prover's view)?
2. Does the circuit include `oracle_address` or some equivalent contract-specific commitment?
3. Off-chain: does the prover daemon's replay-DB key on `(submitter, payloadHash)` only? Or `(submitter, payloadHash, chainid, oracleAddress)`?
4. Is there a documented "one signature, one attestation, one deployment" guarantee, OR is the cross-chain non-uniqueness explicitly acknowledged?

### Domain-tag drift

What to look for first:

1. Every in-circuit `pedersen_hash`, `poseidon`, `keccak256` call: what is the leading domain separator? Is it a literal byte string? A constant from `constants.nr`?
2. The off-chain code that computes the same hash: where is the domain tag defined? Is it imported from the same constants module? Or hardcoded separately?
3. The on-chain registry that stores the commitment: any test that proves the on-chain hash matches the off-chain hash matches the in-circuit hash? `test/<X>Parity.t.sol` is the right pattern.

### Trusted-setup compromise

(Skip if the protocol uses UltraHonk / Halo2 / similar transparent or universal-updatable setup. Only relevant for Groth16 / per-circuit trusted setup.)

What to look for first:

1. What proving system? If Groth16 -> who participated in the setup? Public ceremony? Hardware-attested?
2. Are there published proofs of toxic-waste destruction?
3. Is the protocol upgradeable to a different proving system if soundness is doubted?

### Off-chain prover compromise

What to look for first:

1. What does the prover actually hold? Map the witness / private input set per proof type.
2. Can the prover generate proofs about inputs they don't hold? (Should be no -- the witness check is the soundness primitive.)
3. Does the proof structure rely on off-chain replay tracking (e.g. a DB)? What happens if that DB is wiped or compromised?
4. Multi-prover setups: does horizontal scaling share replay state correctly? Race conditions on duplicate-detection?

### Registry curation compromise

What to look for first:

1. Who can add to each registry (allowed roots, configs, pubkey hashes)? Role + timelock?
2. Are removals / revocations instant or delayed? In a soundness-bug-equivalent scenario, instant revoke is critical; in a "we accidentally registered the wrong hash" scenario, delayed revoke is fine.
3. Is the registry append-only or replace-allowed? Append-only registries with explicit revoke are safer than mutable mappings.
4. What atomicity guarantees exist when one registry write must be paired with another? (e.g. `updateProviderConfig` + `registerProviderConfigExpansion` -- if the pair is non-atomic, an interstitial state might bypass denials.)

---

## Critical Invariants (ZK hybrid universal)

These hold for nearly every ZK + EVM hybrid; specific protocol types add more.

- **PI-1 (Public Input Match):** for every accepted proof, the public inputs the on-chain contract validates byte-for-byte equal the public inputs the circuit committed to.
- **PI-2 (Length Match):** `validatePublicInputs(p, blob)` length check matches the circuit's compiled physical public input count from `target/*.json`.
- **PI-3 (Submitter Binding):** if `submitter` is a public input, then `proof.submitter == msg.sender` is checked on-chain. If submitter is also bound in any in-circuit signature digest, then the off-chain signer also commits to it.
- **DT-1 (Domain Tag Parity):** every in-circuit hash with a domain tag uses the same tag as the off-chain code that computes the same hash for registry registration.
- **VR-1 (Verifier Routing):** `_verifiers[proofType]` maps to a non-zero contract address with `code.length > 0` for every supported proofType.
- **VR-2 (Append-Only Verifier History):** verifier upgrades push to history; previous versions remain queryable but revoke-flagged versions are not.
- **TS-1 (Toolchain Pinning):** `bb` and `nargo` versions are pinned and reproducible.
- **REG-1 (Registry Mutability):** every registry that can be removed-from has a role + delay model documented.
- **CRYP-1 (Hash Scheme Stability):** the hashing primitive used in-circuit (Pedersen / Poseidon / Keccak) does NOT change across upgrades without a coordinated migration.

---

## Phase Detection

Apply pashov's temporal phase detection. Two ZK-specific additions:

| Phase | When relevant |
|-------|---------------|
| **Trusted Setup Ceremony** *(Groth16 only)* | Always include if Groth16. Skip for UltraHonk / Halo2 / transparent setups. |
| **Verifier Migration** | Include if the protocol has a `proposeVerifier` / `executeVerifierUpdate` flow OR if the circuit has been revised at least once. The window between proposal and execution is the migration risk window. |

---

## Composability Threats (ZK-specific additions)

Pashov's composability threats apply. Three ZK-specific additions:

### Verifier-as-Oracle composability

Other protocols may read `verifyProof(proof, inputs)` as an oracle of correctness. They trust the verifier's `bool valid` return. If the verifier is upgraded, the meaning of "valid" changes silently for these dependent protocols.

What to look for: external contracts that call `verify*` on the protocol's verifier. Are they aware of the version? Do they cache verifier addresses?

### Cross-circuit aliasing

Two circuits in the workspace share a `proof_type` ID, OR the on-chain library and Noir constants module disagree on a `proof_type` ID. The wrong verifier is selected; the wrong public input layout is validated.

What to look for: every `proof_type` constant declaration in Solidity AND in Noir. They must come from a single source (or have a parity test).

### Public-input ABI dependency

Off-chain SDKs (TypeScript / Python / Rust) build the public input blob from a typed structure. If the circuit changes its public input layout, the SDK must change in lockstep. SDK pinning vs circuit pinning matters.

What to look for: `package.json` dependencies on the protocol's SDK. Pin versions? Pin to git SHA?

---

## Anti-patterns to flag

- **Verifier address is mutable but not timelocked.** A single key can swap in a malicious verifier instantly.
- **Single role gates registry adds AND verifier swaps.** Compromise of one key cascades.
- **Off-chain hash code copy-pasted from in-circuit code, not imported.** Drift inevitable.
- **No `Parity.t.sol` test ensuring circuit-side and Solidity-side hashes agree.** Implicit invariant -> silent break.
- **`MAX_BATCH_SIZE` larger than mainnet block gas can fit.** Documented batch cap that no real submitter can use.
- **Circuit `main()` has `pub` fields with the same type adjacent.** Reordering passes count check, breaks semantics.
- **Generated verifier files are not in git, only the build pipeline produces them.** A regenerated verifier may not match the deployed bytecode -> can't reproduce, can't audit.
