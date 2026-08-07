---
name: route-compute
description: Use when a research or engineering task may require Tinker inference, LoRA prototyping, Katana PBS GPU execution, frozen evidence, or remote compute budget allocation.
---

# Route Compute

## Overview

Turn one bounded workload into a versioned `ComputeRequest`. The skill chooses an evidence-capable provider; it never launches work. Provider preference cannot weaken evidence requirements.

## Workflow

1. Read `references/contract.md` and classify the requested evidence before choosing infrastructure.
2. Set every requirement flag explicitly. Use `evidence_class: frozen` only when the result is intended for confirmatory evidence.
3. Apply the hard route:

   | Observable requirement | Route |
   |---|---|
   | hidden states, full-vocabulary logits, model revision pin, replay, CRN, critic training, main table, custom CUDA, or private no-egress data | Katana |
   | prompt sanity, sampling, or standard LoRA prototype with all hard flags false | Tinker eligible |
   | anything else or an unpriced Tinker request | Katana |

4. Write the JSON request to a project-relative file. Use a stable `job_key`; replaying it means the same request.
5. Validate without execution:

   ```bash
   argus-compute plan --project-root . --ledger .argus_compute/budget.jsonl --request request.json
   ```

   Add `--price-snapshot` for Tinker. A rejected request is not permission to change its evidence class or hide a requirement.
6. Return the JSON ticket and exact reason codes. Hand Tinker tickets to `run-tinker`, Katana tickets to `run-katana`, and completed manifests to `verify-compute-run`.

## Stop conditions

- Never request, read, print, or place API keys in the request.
- Never mark Tinker work frozen.
- Never replace a hard Katana route with Tinker to save time or budget.
- A changed workload gets a new `job_key`; do not overwrite an existing ticket.

## Examples

Executable examples live in `examples/tinker-request.json` and `examples/katana-request.json`.
