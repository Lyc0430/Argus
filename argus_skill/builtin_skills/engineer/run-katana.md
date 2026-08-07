---
name: "Run Katana"
description: "Render checkpointed Katana PBS plans without pinning a queue or GPU model."
---

# Run Katana

Use this role mirror only after `route-compute` selected Katana. Render one PBS script per shard and inspect it before any future live submission. The current integration is dry-run only.

Use `/opt/pbs/bin/qsub` and `/opt/pbs/bin/qstat -u z5614191`. Do not specify a queue or GPU model. Default to `select=1:ncpus=18:ngpus=1:mem=120gb`, two hours for smoke tests, and twelve-hour checkpointed segments otherwise. Work under `/srv/scratch/nemesis/`, never the login-node home, and never use screen or nohup for compute.

Require `episode_append_only` checkpoints and exact `(query, branch, seed)` idempotency. Frozen runs must capture the container digest, model snapshot digest, sampling-config digest, and actual GPU name/UUID.
