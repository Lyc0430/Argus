---
name: verify-compute-run
description: Use when a Tinker or Katana compute job reports completion and its outputs, coverage, provenance, budget state, or evidence class must be independently accepted or rejected.
---

# Verify Compute Run

## Overview

Judge evidence, not process liveness. A zero exit code, terminal scheduler state, or attractive metric is insufficient without complete artifacts, hashes, coverage, and provider-appropriate provenance.

## Workflow

1. Read `references/contract.md` and obtain the original immutable plan plus the completion manifest.
2. Verify the manifest matches `job_key`, provider, evidence class, and every planned output.
3. Recompute each output SHA-256 from a project-contained path. Reject missing, unsafe, unplanned, or mismatched files.
4. Verify episode accounting: expected equals completed equals unique keys, duplicates are zero, and idempotency fields are exactly `query, branch, seed`.
5. Apply provider gates:

   - Tinker must remain `exploratory` and `frozen:false`.
   - Frozen Katana must match container, model-snapshot, and sampling-config digests and record the actual GPU name and UUID.

6. Run deterministic verification:

   ```bash
   argus-compute verify --project-root . --plan plan.json --manifest manifest.json
   ```

7. Return `accepted`, provider, evidence class, and every finding. Do not smooth failures into a conditional pass.
8. After acceptance, reconcile Tinker billing before settlement. Release a reservation only when the provider can no longer settle work against it.

## Decision rules

| Observation | Verdict |
|---|---|
| Exit code zero but no output hashes or coverage | Reject |
| Tinker manifest claims frozen/main-table evidence | Reject |
| Katana frozen actor omits actual GPU identity | Reject |
| Partial or duplicate episode keys | Reject |
| All plan, hash, coverage, actor, and evidence checks pass | Accept |

External-work records describe whether to wait; they never grant scientific acceptance.

## Stop conditions

Never edit the plan or manifest to make verification pass. Never settle from an estimate when actual billing is still delayed. Escalate an evidence-class conflict instead of rerouting it after completion.
