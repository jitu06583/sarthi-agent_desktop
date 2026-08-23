import os, re, sys

if len(sys.argv) != 2:
    print("Usage: python rebrand_sarthi.py <path-to-hermes-checkout>")
    sys.exit(1)

ROOT = sys.argv[1]
if not os.path.isdir(ROOT):
    print(f"ERROR: '{ROOT}' is not a directory. Nothing to rebrand.")
    sys.exit(1)

# Patterns that must NEVER be touched (real external refs, not our branding)
PROTECTED = [
    r"hermes-parser",
    r"hermes-estree",
    r"nousresearch/hermes-agent",
    r"NousResearch/hermes-agent",
    r"hermes-agent\.nousresearch\.com",
    r"Hermes-4-405B", r"Hermes-3-\S*", r"hermes-4-405b", r"hermes-3-\S*",
]
PLACEHOLDER = "\x00PROT{}\x00"

BINARY_EXT = {".png",".jpg",".jpeg",".gif",".ico",".icns",".woff",".woff2",".ttf",".eot",
              ".zip",".tar",".gz",".pdf",".mp4",".mp3",".webp",".svgz",".exe",".dll",".so",
              ".pyc",".bin",".db",".sqlite",".jar",".class"}

def rebrand_text(text):
    protos = []
    def stash(m):
        protos.append(m.group(0))
        return PLACEHOLDER.format(len(protos)-1)
    combined = "(" + "|".join(PROTECTED) + ")"
    text = re.sub(combined, stash, text)
    text = text.replace("HERMES", "SARTHI")
    text = text.replace("Hermes", "Sarthi")
    text = text.replace("hermes", "sarthi")
    for i, orig in enumerate(protos):
        text = text.replace(PLACEHOLDER.format(i), orig)
    return text

changed_files = 0
skipped_binary = 0
renamed_paths = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    if os.sep + ".git" in dirpath or dirpath.endswith(os.sep + ".git"):
        continue
    for fn in filenames:
        ext = os.path.splitext(fn)[1].lower()
        full = os.path.join(dirpath, fn)
        if ext in BINARY_EXT:
            skipped_binary += 1
            continue
        try:
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, IsADirectoryError, PermissionError):
            skipped_binary += 1
            continue
        if "hermes" in content.lower():
            new_content = rebrand_text(content)
            if new_content != content:
                with open(full, "w", encoding="utf-8") as f:
                    f.write(new_content)
                changed_files += 1

print(f"Content rewritten in {changed_files} files. Skipped (binary/unreadable): {skipped_binary}")

paths_to_check = []
for dirpath, dirnames, filenames in os.walk(ROOT, topdown=False):
    for name in filenames + dirnames:
        if "hermes" in name.lower():
            paths_to_check.append(os.path.join(dirpath, name))

for old_path in paths_to_check:
    d, base = os.path.split(old_path)
    def case_replace(m):
        s = m.group(0)
        if s.isupper(): return "SARTHI"
        if s[0].isupper(): return "Sarthi"
        return "sarthi"
    new_base = re.sub("hermes", case_replace, base, flags=re.IGNORECASE)
    if new_base != base:
        new_path = os.path.join(d, new_base)
        os.rename(old_path, new_path)
        renamed_paths.append((old_path, new_base))

print(f"Renamed {len(renamed_paths)} files/dirs.")
