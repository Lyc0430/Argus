# Katana PBS request contract

Required workload fields:

| Field | Contract |
|---|---|
| `scratch_dir` | Absolute project path below `/srv/scratch/nemesis/` |
| `log_dir` | Absolute path below `/srv/scratch/nemesis/` |
| `shards` | Unique safe identifiers; one script and qsub call per item |
| `smoke` | Boolean; `true` gives 2h, otherwise 12h |
| `runtime` | `container` with `.sif` path/digest/argv, or `conda` with environment/argv |
| `checkpoint.mode` | `episode_append_only` |
| `checkpoint.path` | Absolute scratch path |
| `checkpoint.idempotency_fields` | Exactly `query`, `branch`, `seed` |

Frozen requests additionally require:

- `actor.model_snapshot_path` and `model_snapshot_sha256`;
- `actor.sampling_config_path` and `sampling_config_sha256`;
- container digest when using Apptainer;
- post-run GPU name and UUID in the completion manifest.

Allowed resource fields are `ncpus`, `ngpus`, `memory_gb`, and optionally `min_gpu_memory_gb` plus `memory_requirement_reason`. Supported memory floors are 45, 62, 93, 120, 124, 180, 240, 250, and 500 GB. `queue`, `gpu_model`, and `gpu_type` are rejected.

The broker returns argument arrays; an executor must never pass them through `shell=True`. The current broker cannot submit.
