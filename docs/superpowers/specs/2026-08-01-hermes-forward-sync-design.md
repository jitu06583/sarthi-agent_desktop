# Hermes Forward-Synchronization Design

## Context

Sarthi was created from a Hermes snapshot, but its initial repository commit did not preserve Hermes Git ancestry. The current Sarthi repository and `NousResearch/hermes-agent` therefore have unrelated histories. Directly merging the current Hermes branch would attempt to replay thousands of historical commits across a broad rebrand and is not safe.

The approved strategy is forward synchronization: treat a fixed current Hermes commit as the baseline, preserve the current Sarthi tree, and review only later Hermes changes.

## Goals

- Record the exact Hermes commit from which forward tracking begins.
- Detect new commits on `NousResearch/hermes-agent/main` automatically.
- Create a reviewable draft pull request when Hermes advances.
- Include enough evidence for a maintainer or Sarthi agent to port changes deliberately.
- Never auto-merge raw Hermes code into Sarthi.
- Keep installed Sarthi updates on the existing `sarthi update` path through the Sarthi repository.

## Non-goals

- Port the historical backlog between the original Sarthi snapshot and the forward-sync baseline.
- Automatically rename Hermes symbols or branding to Sarthi.
- Automatically merge generated synchronization pull requests.
- Modify the live installed Sarthi checkout.

## Architecture

### Baseline state

`.github/hermes-sync/baseline` contains one full Hermes commit SHA followed by a newline. It identifies the latest upstream commit that has been reviewed or intentionally accepted as the synchronization baseline.

### Sync generator

`scripts/hermes_sync.py` is a deterministic command-line tool. Given a repository, baseline file, upstream remote URL, and output directory, it:

1. validates the baseline as a 40-character hexadecimal commit ID;
2. fetches `NousResearch/hermes-agent/main` into an isolated remote-tracking ref;
3. exits without changing tracked output when the baseline equals upstream;
4. verifies that the baseline is an ancestor of upstream;
5. writes a synchronization report, commit list, changed-file list, and binary patch bundle for the range `baseline..upstream`;
6. updates the generated candidate-baseline file to the upstream commit without replacing the accepted baseline automatically.

The generated artifacts live under `.github/hermes-sync/pending/`. A reviewer ports applicable changes into Sarthi, runs validation, and updates `.github/hermes-sync/baseline` only when accepting the new upstream point.

### GitHub Actions workflow

`.github/workflows/hermes-forward-sync.yml` runs daily and through `workflow_dispatch`. It grants only `contents: write` and `pull-requests: write`, executes the generator, and creates one draft PR from `automation/hermes-forward-sync`. While that PR remains open, later scheduled runs exit without rewriting the branch, so reviewer changes cannot be overwritten. After the PR is merged or closed, the next run can create a fresh synchronization PR.

If no upstream change exists, the workflow makes no commit and creates no PR. If an open synchronization PR already exists, the workflow performs a successful no-op. If generation or ancestry validation fails, the workflow fails visibly and does not advance the baseline.

### Pull-request review flow

The draft PR contains generated upstream evidence rather than silently merging code. The reviewer or Sarthi agent:

1. reads the commit and changed-file reports;
2. applies or ports relevant patches with Sarthi naming and architecture preserved;
3. adds tests for behavior changes;
4. runs repository validation;
5. updates the accepted baseline to the candidate SHA;
6. marks the PR ready and merges only after review.

## Error handling and safety

- Invalid or missing baseline: fail with a clear error.
- Rewritten/non-descendant upstream history: fail and require manual review.
- Network/fetch failure: fail without modifying the baseline.
- No update: successful no-op.
- Concurrent scheduled/manual runs: GitHub Actions concurrency allows only one sync run at a time.
- Generated PRs are drafts and cannot merge themselves.
- The workflow uses the repository-scoped `GITHUB_TOKEN`; no personal token is required.

## Testing

Automated tests cover:

- invalid baseline rejection;
- no-op when baseline equals upstream;
- update artifact generation for a small local Git fixture;
- rejection when the baseline is not an ancestor of upstream;
- report contents and candidate-baseline correctness.

Workflow verification includes YAML parsing, script syntax checking, the focused test suite, and a local end-to-end run against temporary repositories. Existing broad project tests are not required for documentation-only generated artifacts, but any subsequently ported Hermes code must run its relevant Sarthi tests before merge.

## Rollout

1. Merge this automation PR into Sarthi `main`.
2. The next daily run compares against the recorded forward baseline.
3. Future Hermes changes appear in a draft sync PR.
4. Reviewed and ported changes merge into Sarthi `main`.
5. Installed agents obtain released Sarthi changes through `sarthi update`.
