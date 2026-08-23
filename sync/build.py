#!/usr/bin/env python3
"""
Build a branded SARTHI tree from pristine upstream Hermes.

    python sync/build.py [--out build] [--keep-clone]

Reads:
    sync/hermes.lock    the upstream commit this build is pinned to
    sync/identity.json  every branding rule (rename, protect, patch, drop)
    overlay/            files copied verbatim over the result, last

Writes:
    build/              the generated, branded, ready-to-build tree

Nothing in this repo is a fork of Hermes. Upstream is fetched fresh at build
time and never edited in place, so a sync is a one-line change to hermes.lock
instead of a 7,000-file merge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def load_config() -> dict:
    with open(os.path.join(HERE, "identity.json"), encoding="utf-8") as fh:
        return json.load(fh)


def read_lock() -> str:
    path = os.path.join(ROOT, "sync", "hermes.lock")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    raise SystemExit("sync/hermes.lock contains no commit sha")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def fetch_upstream(repo: str, sha: str, dest: str) -> None:
    """Clone upstream at exactly the pinned commit."""
    os.makedirs(dest, exist_ok=True)
    run(["git", "init", "--quiet", dest])
    run(["git", "-C", dest, "remote", "add", "origin", repo])
    run(["git", "-C", dest, "fetch", "--quiet", "--depth", "1", "origin", sha])
    run(["git", "-C", dest, "checkout", "--quiet", "FETCH_HEAD"])
    shutil.rmtree(os.path.join(dest, ".git"), ignore_errors=True)


class Rebrander:
    """Case-preserving hermes->sarthi swap that leaves protected strings alone.

    Protected matches are stashed behind placeholders before the swap and
    restored after, so a real model ID or npm package name can contain the
    word "hermes" and survive untouched.
    """

    def __init__(self, cfg: dict) -> None:
        self.rules = [
            (k, v) for k, v in cfg["rename"].items() if not k.startswith("_")
        ]
        pats = cfg["protected"]["patterns"]
        self.protected = re.compile("|".join(f"(?:{p})" for p in pats))

    def text(self, s: str) -> str:
        stash: list[str] = []

        def hide(m: re.Match) -> str:
            stash.append(m.group(0))
            return f"\x00PROTECTED{len(stash) - 1}\x00"

        s = self.protected.sub(hide, s)
        for old, new in self.rules:
            s = s.replace(old, new)
        for i, original in enumerate(stash):
            s = s.replace(f"\x00PROTECTED{i}\x00", original)
        return s

    def name(self, s: str) -> str:
        return self.text(s)


def rewrite_contents(root: str, rb: Rebrander) -> tuple[int, int]:
    changed = skipped = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    original = fh.read()
            except (UnicodeDecodeError, OSError):
                skipped += 1
                continue
            updated = rb.text(original)
            if updated != original:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(updated)
                changed += 1
    return changed, skipped


def rename_paths(root: str, rb: Rebrander) -> int:
    """Rename bottom-up so a parent rename never invalidates a queued child."""
    renamed = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if any(part in SKIP_DIRS for part in dirpath.split(os.sep)):
            continue
        for name in filenames + dirnames:
            new = rb.name(name)
            if new == name:
                continue
            src = os.path.join(dirpath, name)
            dst = os.path.join(dirpath, new)
            if os.path.exists(dst):
                continue
            os.rename(src, dst)
            renamed += 1
    return renamed


def apply_patches(root: str, cfg: dict) -> tuple[int, list[str]]:
    """Apply the explicit identity fixes. A miss is loud, never silent."""
    applied = 0
    misses: list[str] = []
    for rel, pairs in cfg["patches"].items():
        if rel.startswith("_"):
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            misses.append(f"{rel} (file not found)")
            continue
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        for find, replace in pairs:
            if find not in body:
                misses.append(f"{rel}: {find[:70]}")
                continue
            body = body.replace(find, replace)
            applied += 1
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(body)
    return applied, misses


def stamp_version(root: str, version: str) -> None:
    """Overwrite apps/desktop/package.json's version field.

    Upstream freezes this field — it does not track their own releases,
    so electron-builder's artifactName template
    (Hermes-${version}-${os}-${arch}.${ext}) resolves to the same stale
    string on every build no matter which commit sync/hermes.lock points
    at. This stamps our own release version in its place so each built
    filename increments with the tag that produced it.
    """
    path = os.path.join(root, "apps", "desktop", "package.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    old = data.get("version")
    data["version"] = version
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    print(f"      {old} -> {version}")


def drop_paths(root: str, cfg: dict) -> int:
    dropped = 0
    for rel in cfg["drop"]["paths"]:
        if rel.startswith("_"):
            continue
        target = os.path.join(root, rel)
        if os.path.isdir(target):
            shutil.rmtree(target)
            dropped += 1
        elif os.path.isfile(target):
            os.remove(target)
            dropped += 1
    return dropped


def apply_overlay(root: str) -> int:
    """Copy overlay/ verbatim over the generated tree. Overlay always wins."""
    src_root = os.path.join(ROOT, "overlay")
    if not os.path.isdir(src_root):
        return 0
    copied = 0
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    return copied


def verify(root: str, cfg: dict) -> list[str]:
    """Fail the build rather than ship a tree that would orphan user data."""
    problems: list[str] = []

    ud = cfg["user_data"]
    consts = os.path.join(root, "sarthi_constants.py")
    if not os.path.isfile(consts):
        problems.append("sarthi_constants.py missing — rename did not run?")
    else:
        with open(consts, encoding="utf-8") as fh:
            body = fh.read()
        if ud["home_env_var"] not in body:
            problems.append(
                f"{ud['home_env_var']} not found in sarthi_constants.py — "
                "user data location changed, installed configs would be orphaned"
            )
        if "HERMES_HOME" in body:
            problems.append(
                "HERMES_HOME still present in sarthi_constants.py — "
                "the app would read a different data directory than it writes"
            )

    for rel in cfg["force_add"]["paths"]:
        if not os.path.isfile(os.path.join(root, rel)):
            problems.append(f"{rel} missing — upstream force-adds it; build will fail")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build", help="output directory")
    ap.add_argument("--keep-clone", action="store_true")
    ap.add_argument(
        "--app-version",
        default=None,
        help=(
            "Stamp this into apps/desktop/package.json's \"version\" field "
            "before building. Upstream never bumps that field on their own "
            "main branch, or even on their own tagged releases, so left "
            "alone every SARTHI build ships under the same frozen version "
            "string forever regardless of which commit it is pinned to. "
            "Pass the release tag that triggered this build (e.g. 0.3.8)."
        ),
    )
    args = ap.parse_args()

    cfg = load_config()
    sha = read_lock()
    out = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out

    print(f"Pinned upstream commit: {sha}")

    # dir=ROOT keeps the clone on the same drive as the output.
    # On Windows runners the OS temp dir is C: while the checkout is
    # D:, so the final shutil.move() silently falls back to a
    # copy+rmtree and dies deleting read-only git pack files.
    tmp = tempfile.mkdtemp(prefix="sarthi-build-", dir=ROOT)
    clone = os.path.join(tmp, "upstream")
    try:
        print("[1/8] Fetching pristine upstream...")
        fetch_upstream(cfg["upstream"]["repo"], sha, clone)

        print("[2/8] Dropping upstream-only infrastructure...")
        dropped = drop_paths(clone, cfg)
        print(f"      removed {dropped} path(s)")

        rb = Rebrander(cfg)

        print("[3/8] Rewriting file contents...")
        changed, skipped = rewrite_contents(clone, rb)
        print(f"      rewrote {changed} file(s), skipped {skipped} binary/unreadable")

        print("[4/8] Renaming files and directories...")
        renamed = rename_paths(clone, rb)
        print(f"      renamed {renamed} path(s)")

        print("[5/8] Applying explicit identity patches...")
        applied, misses = apply_patches(clone, cfg)
        print(f"      applied {applied} patch(es)")
        if misses:
            print("\nERROR: these patches did not match. Upstream changed the")
            print("surrounding code, so a branding field is now silently wrong.")
            print("Fix sync/identity.json before shipping:\n")
            for m in misses:
                print(f"  - {m}")
            return 1

        if args.app_version:
            print(f"[6/8] Stamping app version -> {args.app_version} ...")
            stamp_version(clone, args.app_version)
        else:
            print("[6/8] No --app-version given, leaving upstream's frozen version as-is")

        print("[7/8] Applying overlay/ ...")
        copied = apply_overlay(clone)
        print(f"      copied {copied} overlay file(s)")

        print("[8/8] Verifying...")
        problems = verify(clone, cfg)
        if problems:
            print("\nERROR: build failed verification:\n")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("      ok")

        if os.path.exists(out):
            shutil.rmtree(out)
        shutil.move(clone, out)

    finally:
        if not args.keep_clone:
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("=" * 60)
    print(f" Built SARTHI from Hermes {sha}")
    print(f" Output: {out}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
