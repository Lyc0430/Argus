# Completion manifest contract

Required top-level fields:

- `version: 1`, `job_key`, `provider`, `status`, and `exit_code`;
- `evidence_class` plus matching boolean `frozen`;
- `outputs`: project-relative path and lowercase SHA-256 for every planned output;
- `coverage`: expected/completed/unique/duplicate episode counts and exact idempotency fields;
- `actor` for frozen Katana evidence.

Frozen Katana actor fields:

`container_sha256`, `model_snapshot_sha256`, `sampling_config_sha256`, `actual_gpu_name`, and `actual_gpu_uuid`. The first three must match the plan. Recording the actual GPU is required even when scheduling deliberately did not pin a GPU model.

Tinker may include model and price/capability provenance but cannot claim `frozen:true` or `evidence_class:frozen`.

The verifier reads only paths contained by the project root after symlink resolution. Scheduler logs and `.argus_external_work` records may support diagnosis but do not replace output artifacts.
