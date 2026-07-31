# Hermes forward synchronization

Sarthi intentionally starts forward tracking from the commit stored in `baseline`. Earlier Hermes history is not imported because Sarthi's initial rebrand did not retain upstream Git ancestry.

## Automated behavior

The daily/manual workflow compares the accepted baseline with `NousResearch/hermes-agent/main`. When upstream advances and no sync PR is already open, it creates a draft PR containing:

- `pending/REPORT.md` — baseline, candidate, and review warning;
- `pending/commits.tsv` — ordered upstream commit inventory;
- `pending/changed-files.tsv` — rename-aware changed-file inventory;
- `pending/upstream.patch` — binary-capable patch for the exact range, capped at 90 MiB;
- `pending/candidate-baseline` — proposed next accepted commit.

The generator streams the patch to disk rather than buffering it in memory. It fails visibly before committing if the patch exceeds 90 MiB, if the recorded baseline is no longer an ancestor of upstream, or if GitHub/upstream access fails. Its output directory must be a `pending` directory inside the repository; a no-update run preserves any existing output.

The workflow never merges the PR, applies the patch to Sarthi, or replaces `baseline`.

## Reviewer procedure

1. Read `pending/REPORT.md`, the commit inventory, and changed-file inventory.
2. Port applicable behavior into Sarthi deliberately. Preserve Sarthi naming, desktop integration, ACP behavior, Multica integration, and project-specific architecture.
3. Add or update tests for every ported behavior.
4. Run focused tests plus the repository checks relevant to the changed code.
5. Replace the contents of `baseline` with the exact SHA in `pending/candidate-baseline` only after all applicable upstream changes have been reviewed.
6. Remove `pending/`, mark the PR ready, and merge only after review and CI approval.

If a sync PR is open, later scheduled runs stop without rewriting its branch. After that PR is merged or closed, the next run can create a new sync PR.
