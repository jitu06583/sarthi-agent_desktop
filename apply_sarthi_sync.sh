#!/usr/bin/env bash
# Run this from inside your local sarthi-agent checkout, e.g.:
#   cd "/e/Hermes Agent/My_Hermes_Dev/Sathi_Hermes/sarthi-agent"
#   bash apply_sarthi_sync.sh
set -euo pipefail

# Windows Git Bash often has a fake "python3" that just opens the Microsoft
# Store and does nothing — detect a real, working Python instead.
PY=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" --version 2>&1 | grep -q "^Python 3"; then
      PY="$cand"
      break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: could not find a working Python 3 install. Is Python installed and on PATH?"
  exit 1
fi
echo "Using Python: $PY ($($PY --version))"
HERE="$(pwd)"
TMP="$(mktemp -d)"

echo "[1/5] Cloning current Hermes..."
git clone --depth 1 https://github.com/NousResearch/hermes-agent.git "$TMP/hermes" >/dev/null 2>&1
HERMES_SHA="$(git -C "$TMP/hermes" rev-parse HEAD)"
rm -rf "$TMP/hermes/.git"
echo "    Built from Hermes commit: $HERMES_SHA"

echo "[2/5] Rebranding (rename + text rewrite, protecting model IDs / npm packages / docker image refs)..."
${PY} "$HERE/rebrand_sarthi.py" "$TMP/hermes"

echo "[3/5] Copying rebranded Hermes into this checkout, preserving your Sarthi-only files..."
${PY} - "$TMP/hermes" "$HERE" << 'PYEOF'
import os, shutil, sys

src, dst = sys.argv[1], sys.argv[2]

# Paths (relative to repo root) that are yours, not Hermes's — never touched
PRESERVE = {
    "brand", "LICENSE", ".github/hermes-sync",
    ".github/workflows/hermes-forward-sync.yml",
    ".github/workflows/hermes-sync-validation.yml",
    ".github/workflows/build-desktop.yml",
    "scripts/hermes_sync.py",
    "tests/scripts/test_hermes_sync.py",
    "tests/scripts/test_hermes_sync_workflow.py",
    "docs/superpowers",
    "apps/desktop/public/apple-touch-icon.png",
    "apps/desktop/public/sarthi.png",
    "apps/desktop/public/sarthi-square2.png",
    "assets/banner.png",
    ".git",
    "rebrand_sarthi.py", "apply_sarthi_sync.sh",
}

def is_preserved(rel):
    parts = rel.replace(os.sep, "/")
    return any(parts == p or parts.startswith(p + "/") for p in PRESERVE)

# Remove old tracked files not present in fresh Hermes (except preserved paths)
for dirpath, dirnames, filenames in os.walk(dst, topdown=True):
    rel_dir = os.path.relpath(dirpath, dst)
    dirnames[:] = [d for d in dirnames if not is_preserved(os.path.join(rel_dir, d)) or rel_dir == "."]
    for fn in filenames:
        rel = os.path.join(rel_dir, fn) if rel_dir != "." else fn
        if is_preserved(rel):
            continue
        src_equiv = os.path.join(src, rel)
        if not os.path.exists(src_equiv):
            os.remove(os.path.join(dirpath, fn))

# Copy everything from fresh (rebranded) Hermes into destination
for dirpath, dirnames, filenames in os.walk(src):
    rel_dir = os.path.relpath(dirpath, src)
    dst_dir = os.path.join(dst, rel_dir) if rel_dir != "." else dst
    os.makedirs(dst_dir, exist_ok=True)
    for fn in filenames:
        rel = os.path.join(rel_dir, fn) if rel_dir != "." else fn
        if is_preserved(rel):
            continue
        shutil.copy2(os.path.join(dirpath, fn), os.path.join(dst_dir, fn))

print("    Copy complete.")
PYEOF

echo "[4/5] Patching apps/desktop/package.json branding fields..."
${PY} - "$HERE/apps/desktop/package.json" << 'PYEOF'
import json, sys
p = sys.argv[1]
with open(p) as f:
    pkg = json.load(f)
pkg["author"] = "Jitendra Singh Thakur"
pkg["homepage"] = "https://sarthi-agent.vercel.app"
pkg.pop("repository", None)
with open(p, "w") as f:
    json.dump(pkg, f, indent=2)
    f.write("\n")
PYEOF

echo "[5/5] Advancing the accepted baseline..."
echo "$HERMES_SHA" > "$HERE/.github/hermes-sync/baseline"

rm -rf "$TMP"
echo ""
echo "============================================"
echo " DONE. Built from Hermes commit: $HERMES_SHA"
echo " Next: git status, then commit and push."
echo "============================================"
