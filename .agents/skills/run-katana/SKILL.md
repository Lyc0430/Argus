---
name: run-katana
description: Use when a routed workload needs UNSW Katana PBS GPUs, frozen or replayable evidence, model internals, custom CUDA, or private no-egress execution.
---

# Run Katana

## Overview

Render auditable PBS work as one recoverable job per shard. In the standard phase, stop after dry-run scripts and tickets; do not SSH, upload, or submit.

## Preconditions

- Read `references/contract.md`.
- Require a Katana decision from `route-compute`.
- Keep all experiment state under `/srv/scratch/nemesis/`, never home or the login node.
- For frozen work, require the container digest, model snapshot digest, sampling-config digest, and post-run actual GPU identity.

## Workflow

1. Define one typed command argument list, runtime (`container` or `conda`), shards, scratch/log paths, and actor inputs.
2. Require checkpoint mode `episode_append_only` with exact idempotency fields `query, branch, seed`. Every invocation resumes instead of recomputing completed episodes.
3. Use `smoke:true` for `02:00:00`; normal segments use `12:00:00`. Chain later segments with `afterok_job_id`.
4. Leave queue and GPU model absent. Add a supported `min_gpu_memory_gb` resource only with a concrete scientific reason.
5. Render the plan:

   ```bash
   argus-compute plan --project-root . \
     --ledger .argus_compute/budget.jsonl \
     --request request.json
   ```

6. Inspect every generated script and argv. Each shard must have its own `/opt/pbs/bin/qsub` argv. Monitoring uses `/opt/pbs/bin/qstat -u z5614191`.
7. Return the dry-run ticket and stop. The generated `.argus_external_work` record describes liveness only, never scientific success.

## Scheduler contract

- No `#PBS -q` and no GPU model/type constraint by default.
- Default select: one node, 18 CPUs, one GPU, 120 GB RAM.
- Logs use `#PBS -j oe` under `/srv/scratch/nemesis/logs/`.
- vLLM runs with Apptainer and the declared `.sif`; non-container jobs activate the declared scratch conda environment.
- Capture `nvidia-smi` name and UUID at runtime. Scheduling without a GPU pin does not remove the need to record the actual architecture.

## Stop conditions

Never use `screen` or `nohup` on the login node, never accept raw shell text, never combine shards into one opaque job, and never call qsub during this phase.
