# ComputeRequest contract

Required fields:

| Field | Contract |
|---|---|
| `version` | `1` |
| `job_key` | Stable 1-128 character idempotency key; letters, digits, `. _ : -` only |
| `mission_id`, `project`, `model` | Non-empty identifiers |
| `task_kind` | `prompt_sanity`, `sampling`, `lora_prototype`, `training`, `evaluation`, `renderer`, `embedding`, or `custom` |
| `evidence_class` | `exploratory` or `frozen` |
| `provider_hint` | `auto`, `tinker`, or `katana` |
| `estimated_cost_usd` | Non-negative; Tinker requires a positive estimate |
| `expected_outputs` | Project-relative paths |
| `workload`, `resources` | JSON objects consumed by the selected adapter |

Requirement flags default false but must be set true when applicable:

`requires_hidden_states`, `requires_full_vocab_logits`, `requires_model_revision_pin`, `requires_replay`, `requires_crn`, `requires_critic_training`, `requires_main_table`, `requires_custom_cuda`, `requires_private_no_egress`.

The broker rejects unknown fields so misspelled policy fields cannot fail open. It derives `frozen` from `evidence_class`; a workload field named `frozen` has no authority.

`plan` is dry-run-only in the standard phase. It may reserve Tinker budget and write a terminal `planned_dry_run` external-work record, but it cannot contact Tinker or submit PBS.
