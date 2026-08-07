---
name: run-tinker
description: Use when an exploratory prompt-sampling, behavior-sanity, evaluation probe, or standard LoRA prototype has been routed to Tinker and must be budgeted and prepared safely.
---

# Run Tinker

## Overview

Prepare high-throughput exploratory Tinker work behind a predictive budget reservation. In the standard phase, “run” ends at a validated dry-run ticket; no network request is authorized.

## Preconditions

- Read `references/contract.md`.
- Require a `route-compute` decision for Tinker.
- Require `evidence_class: exploratory`, `frozen:false`, a positive cost estimate, and a captured price-snapshot SHA.
- Confirm the task does not need hidden states, full logits, revision pinning, replay, CRN, critic training, or main-table evidence.

## Workflow

1. Put different prompts in a project-relative JSONL file. Set `prompt_count`, `num_samples`, `max_tokens`, and temperature in the request.
2. Use `num_samples` for repeated generations of the same prompt. Across different prompts, the future live adapter must submit all `sample_async` calls together with `asyncio.gather`.
3. Do not add client-side timeout or retry wrappers. The Tinker SDK owns transient retries and slow requests may still be healthy.
4. Initialize the deployment ledger once, never to reset spend:

   ```bash
   argus-compute init-budget --ledger .argus_compute/budget.jsonl
   ```

5. Create the reserved dry-run plan:

   ```bash
   argus-compute plan --project-root . \
     --ledger .argus_compute/budget.jsonl \
     --request request.json \
     --price-snapshot price-snapshot.json
   ```

6. Return the ticket, reservation amount, capability-check requirement, and plan path. Stop before external execution.

## Budget gates

- Prompt sanity or sampling: raw estimate at most $50 per job.
- LoRA prototype: raw estimate at most $200 per job.
- The ledger reserves estimate × 1.25, holds a $250 billing-lag buffer, freezes new admissions above the $2,250 reconciliation threshold, and hard-stops at $2,500.
- Replaying the same `job_key` must reuse the same reservation. A changed request needs a new key.

## Stop conditions

Never request or inspect a key, never label Tinker output frozen, never invent capability support, and never release a reservation while work could still settle.
