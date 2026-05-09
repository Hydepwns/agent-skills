#!/usr/bin/env bash
# zk-x-ray Phase 1 enumeration.
# Outputs labeled sections covering Solidity sources, Noir circuits, public-input
# ABI parity, tests (forge + nargo), toolchain pins, and git history.
#
# Usage: enumerate.sh <project-root>

set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

# ─── Toolchain detection ──────────────────────────────────────────────────────

echo "=== Toolchain ==="
SOLIDITY_TOOL="unknown"
[ -f foundry.toml ] && SOLIDITY_TOOL="foundry"
[ -f hardhat.config.js ] || [ -f hardhat.config.ts ] && SOLIDITY_TOOL="hardhat"
echo "solidity: $SOLIDITY_TOOL"

NOIR_LAYOUT="none"
[ -f circuits/Nargo.toml ] && NOIR_LAYOUT="workspace"
if [ "$NOIR_LAYOUT" = "none" ] && [ -d circuits ]; then
  if find circuits -maxdepth 2 -name 'Nargo.toml' 2>/dev/null | grep -q .; then
    NOIR_LAYOUT="multi"
  fi
fi
echo "noir: $NOIR_LAYOUT"

# ─── Source-directory detection ───────────────────────────────────────────────

SRC="src"
if [ -f foundry.toml ]; then
  detected=$(grep -E '^\s*src\s*=' foundry.toml 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)".*/\1/' || true)
  [ -n "${detected:-}" ] && SRC="$detected"
fi
[ ! -d "$SRC" ] && [ -d contracts ] && SRC="contracts"
echo "src_dir: $SRC"

# ─── Solidity Source ──────────────────────────────────────────────────────────

echo "=== Solidity Source (with line counts) ==="
find "$SRC" -name '*.sol' \
  -not -path '*/test/*' -not -path '*/tests/*' -not -path '*/script/*' \
  -not -path '*/lib/*' -not -path '*/node_modules/*' -not -path '*/forge-std/*' \
  -not -path '*/out/*' -not -path '*/broadcast/*' -not -path '*/artifacts/*' \
  -not -path '*/cache/*' -not -path '*/generated/*' 2>/dev/null \
  | sort | xargs wc -l 2>/dev/null || true

echo "=== Solidity Generated Verifiers ==="
find "$SRC/generated" -name '*.sol' 2>/dev/null | sort | xargs wc -l 2>/dev/null || echo "(none)"

# ─── Solidity nSLOC ───────────────────────────────────────────────────────────

echo "=== Solidity nSLOC ==="
sum=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  t=$(grep -cE '\S' "$f" || true)
  c=$(grep -cE '^[[:space:]]*(//|/\*|\*|\*/)' "$f" || true)
  n=$((t - c))
  printf "%s: %d\n" "$f" "$n"
  sum=$((sum + n))
done < <(find "$SRC" -name '*.sol' \
  -not -path '*/test/*' -not -path '*/tests/*' -not -path '*/script/*' \
  -not -path '*/lib/*' -not -path '*/node_modules/*' -not -path '*/forge-std/*' \
  -not -path '*/out/*' -not -path '*/broadcast/*' -not -path '*/artifacts/*' \
  -not -path '*/cache/*' -not -path '*/generated/*' 2>/dev/null | sort)
echo "TOTAL: $sum"

# ─── Noir Circuits ────────────────────────────────────────────────────────────

echo "=== Noir Circuits ==="
if [ "$NOIR_LAYOUT" != "none" ]; then
  find circuits -name '*.nr' -not -path '*/target/*' 2>/dev/null | sort | xargs wc -l 2>/dev/null || true
else
  echo "(no circuits/ directory)"
fi

echo "=== Noir Workspace Members ==="
if [ -f circuits/Nargo.toml ]; then
  grep -E '^\s*"[^"]+"' circuits/Nargo.toml || true
fi

echo "=== Noir Public Inputs (logical, from main.nr) ==="
# Noir syntax is `<name>: pub <type>` -- the pub keyword sits between the colon and the type.
# Match every line inside fn main(...) that declares a public parameter.
if [ -d circuits ]; then
  for f in $(find circuits -path '*/src/main.nr' -not -path '*/target/*' 2>/dev/null | sort); do
    circuit_name=$(echo "$f" | sed -E 's|circuits/([^/]+)/src/main.nr|\1|')
    pubs=$(grep -nE ':[[:space:]]*pub[[:space:]]' "$f" 2>/dev/null || true)
    if [ -z "$pubs" ]; then
      pub_count=0
    else
      pub_count=$(printf '%s\n' "$pubs" | grep -c .)
    fi
    echo "[$circuit_name] logical pub count: $pub_count"
    [ -n "$pubs" ] && printf '%s\n' "$pubs" | sed 's/^/  /'
  done
fi

echo "=== Noir Public Inputs (physical, from compiled target/*.json) ==="
# Physical count = generated verifier's NUMBER_OF_PUBLIC_INPUTS - 16 (UltraHonk overhead).
# We extract by counting "visibility":"public" entries in target/<circuit>.json's abi.parameters.
if [ -d circuits ] && command -v jq >/dev/null 2>&1; then
  for f in $(find circuits -path '*/target/*.json' -not -path '*/target/proof' 2>/dev/null | sort); do
    circuit_name=$(echo "$f" | sed -E 's|circuits/([^/]+)/target/.*|\1|')
    # jq filter: extract abi.parameters[].visibility, count "public" entries
    public_count=$(jq -r '.abi.parameters // [] | map(select(.visibility == "public")) | length' "$f" 2>/dev/null || echo "?")
    echo "[$circuit_name] physical public param count: $public_count (file: $f)"
  done
else
  echo "(jq not available OR target/ not built; skip and parse manually in Phase 2c)"
fi

echo "=== Generated verifier NUMBER_OF_PUBLIC_INPUTS ==="
if [ -d "$SRC/generated" ]; then
  for f in $(find "$SRC/generated" -name '*_verifier.sol' 2>/dev/null | sort); do
    n=$(grep -E 'NUMBER_OF_PUBLIC_INPUTS\s*=' "$f" 2>/dev/null | head -1 | sed -E 's/.*=\s*([0-9]+).*/\1/' || echo "?")
    echo "[$(basename "$f")] NUMBER_OF_PUBLIC_INPUTS = $n"
  done
fi

# ─── Solidity expected counts ─────────────────────────────────────────────────

echo "=== Solidity expectedPublicInputCount (per proofType) ==="
# Heuristic: grep for 'return [N];' inside an expectedPublicInputCount-shaped function.
grep -rEn 'expectedPublicInputCount|expectedInputCount' "$SRC" --include='*.sol' 2>/dev/null | head -20 || true
echo "---"
grep -rEn 'if\s*\(proofType\s*==\s*[A-Z_]+\)\s*return\s*[0-9]+' "$SRC" --include='*.sol' 2>/dev/null | head -20 || true

# ─── NatSpec ──────────────────────────────────────────────────────────────────

echo "=== NatSpec annotations (total tags across in-scope sources) ==="
grep -rE '@notice|@dev|@param|@return' "$SRC" --include='*.sol' \
  --exclude-dir=generated 2>/dev/null | wc -l || true

echo "=== NatSpec annotation files ==="
grep -rlE '@notice|@dev|@param|@return' "$SRC" --include='*.sol' \
  --exclude-dir=generated 2>/dev/null | wc -l || true

# ─── Tests ────────────────────────────────────────────────────────────────────

echo "=== Solidity test files ==="
find . \( -name '*.sol' -o -name '*.js' -o -name '*.ts' \) -path '*/test*' \
  -not -path '*/node_modules/*' -not -path '*/lib/*' -not -path '*/out/*' \
  -not -path '*/cache/*' -not -path '*/dist/*' 2>/dev/null | wc -l || true

echo "=== Solidity test functions ==="
grep -rcE 'function\s+test' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=cache 2>/dev/null \
  | grep -E '/(test|tests|invariant|fuzz)/' | awk -F: '{s+=$NF}END{print s+0}'

echo "=== Stateless fuzz (testFuzz_) ==="
grep -rcE 'function\s+testFuzz' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=cache 2>/dev/null \
  | awk -F: '{s+=$NF}END{print s+0}'

echo "=== Stateful fuzz (invariant_) ==="
grep -rcE 'function\s+invariant_' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=cache 2>/dev/null \
  | awk -F: '{s+=$NF}END{print s+0}'

echo "=== Parity tests (heuristic) ==="
# Tests with "Parity" or "parity" in filename OR that import EIP712 + Pedersen helpers
find . -name '*Parity*.t.sol' -not -path '*/lib/*' 2>/dev/null | head -10 || true

echo "=== Noir tests ==="
if [ "$NOIR_LAYOUT" != "none" ]; then
  grep -rcE '^[[:space:]]*#\[test\]' circuits --include='*.nr' 2>/dev/null | grep -v ':0$' | wc -l || true
else
  echo "0"
fi

# ─── Toolchain Pins ───────────────────────────────────────────────────────────

echo "=== Toolchain Pins ==="
if [ -f .tool-versions ]; then
  echo "[.tool-versions]"
  cat .tool-versions
fi
if [ -f flake.nix ]; then
  echo "[flake.nix]"
  echo "(present)"
fi
echo "[foundry.lock]"
[ -f foundry.lock ] && cat foundry.lock || echo "(absent)"

echo "[bb pin (heuristic)]"
grep -rE 'bb[[:space:]]+[0-9]' .tool-versions Dockerfile* 2>/dev/null | head -3 || echo "(not pinned)"

echo "[nargo pin (heuristic)]"
grep -rE 'nargo[[:space:]]+[0-9]' .tool-versions Dockerfile* 2>/dev/null | head -3 || echo "(not pinned)"

# ─── Docs & Spec ──────────────────────────────────────────────────────────────

echo "=== Docs ==="
ls -d README.md docs/ doc/ THREAT*.md SECURITY.md 2>/dev/null || true
echo "=== EIP / ERC drafts ==="
find . -maxdepth 2 -type f \( -name 'eip-draft*.md' -o -name 'erc-*.md' -o -name 'EIP-*.md' \) \
  -not -path '*/node_modules/*' -not -path '*/lib/*' 2>/dev/null || true

# ─── Git ──────────────────────────────────────────────────────────────────────

echo "=== Git commit ==="
git rev-parse --short HEAD 2>/dev/null || echo "unknown"

echo "=== Git branch ==="
git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"

echo "=== Git unique authors ==="
git log --format='%aN' 2>/dev/null | sort -u | wc -l || echo "0"

echo "=== Git contributor breakdown ==="
git log --format='%aN' 2>/dev/null | sort | uniq -c | sort -rn | head -10 || true

echo "=== Git age ==="
git log --reverse --format='%aI' 2>/dev/null | head -1 || true
git log -1 --format='%aI' 2>/dev/null || true

echo "=== Git total commits ==="
git rev-list --count HEAD 2>/dev/null || echo "0"

echo "=== Git hotspots (src) ==="
git log --name-only --format='' -- "$SRC" 2>/dev/null | sort | uniq -c | sort -rn | head -10 || true

echo "=== Git hotspots (circuits) ==="
[ -d circuits ] && git log --name-only --format='' -- circuits 2>/dev/null | sort | uniq -c | sort -rn | head -10 || true

echo "=== Done ==="
