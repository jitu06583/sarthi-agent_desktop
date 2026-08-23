# SARTHI Agent

SARTHI is a branded distribution of [Hermes Agent](https://github.com/NousResearch/hermes-agent).

This repository is **not a fork**. It contains no application source code. It
contains a pinned upstream commit and the branding that turns Hermes into
SARTHI, and the build regenerates everything from those two inputs.

## Why it is built this way

The previous approach forked the whole upstream repository and rewrote every
file. That inherited far more than the product: NousResearch's internal CI
(including runners this account cannot use), their contributor registry, their
docs-site deploy, their governance files. Every sync became an archaeology
session, and a blind find-and-replace silently overwrote branded artwork and
left NousResearch URLs inside the shipping app.

Treating upstream as a dependency fixes that at the root. A sync is now a
one-line change.

## Layout

```
sync/
  hermes.lock      the upstream commit this build is pinned to
  identity.json    every branding rule, in one declarative file
  build.py         fetch upstream -> rebrand -> patch -> overlay -> verify
overlay/           files copied verbatim over the generated tree, last word
brand/             source artwork
.github/workflows/
  sarthi-sync.yml    one-click sync: bump the pin, open a PR
  build-desktop.yml  tag -> build installers -> attach to a release
```

## Building locally

```bash
python sync/build.py --out build
cd build && npm ci && npm install --workspace apps/desktop
cd apps/desktop && npm run dist:win     # or dist:mac / dist:linux
```

`build/` is generated and git-ignored. Never edit it; edits are discarded on
the next build. Change `sync/identity.json` or `overlay/` instead.

## Syncing with upstream

Click **Sync from Hermes** on the admin panel at
[sarthi-agent.vercel.app/admin](https://sarthi-agent.vercel.app/admin), or run
the *Sarthi Sync* workflow from the Actions tab.

It resolves the latest upstream commit, runs the full branded build against it
to prove it works, and opens a pull request whose diff is a single line in
`sync/hermes.lock`. If the build fails verification, no PR is opened.

Merging a sync PR changes nothing for existing users. Installers are only
rebuilt when a release tag is pushed:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

## Changing the branding

Everything lives in `sync/identity.json`.

- **Artwork** — drop the file into `overlay/` at the same path it occupies in
  the generated tree. Overlay always wins.
- **Names, URLs, IDs** — add an entry under `patches`.
- **Upstream files to delete** — add the path under `drop`.

`patches` fails the build loudly when a pattern stops matching. That is
deliberate: if upstream refactors around a branding field, the build stops
instead of quietly shipping a NousResearch URL inside the app.

## User data is never touched

The installed app keeps memory, profiles, bots, MCP servers, and skills in
`~/.sarthi` (or `$SARTHI_HOME`) on the user's own machine — outside this
repository entirely. Rebuilding, syncing, and reinstalling do not touch it.

The one change that *would* orphan every existing user's setup is renaming that
directory, because the app would start reading an empty folder and their
configuration would appear wiped. `sync/build.py` therefore refuses to produce
a build where `SARTHI_HOME` is missing or `HERMES_HOME` has crept back in.
