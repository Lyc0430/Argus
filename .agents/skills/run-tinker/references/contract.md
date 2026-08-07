# Tinker standard-phase contract

Legal task kinds are `prompt_sanity`, `sampling`, and `lora_prototype`.

Required workload fields:

| Field | Contract |
|---|---|
| `prompt_file` | Project-relative JSONL path |
| `prompt_count` | Positive number of distinct prompt requests |
| `num_samples` | Positive completions per prompt; do not expand into duplicate calls |
| `max_tokens` | Positive generation cap |
| `temperature` | Finite, non-negative number |
| `training_recipe` | Required project-relative recipe for `lora_prototype` |

Forbidden fields are `sequential:true`, `client_timeout_seconds`, and `retry_count`.

Before a future live submission, the provider adapter must:

1. Load its own provider-scoped key outside the model process.
2. Call `ServiceClient.get_server_capabilities_async()` and confirm the exact model identifier.
3. Create the sampling client asynchronously; after new LoRA weights, create a new sampling client.
4. Submit distinct prompts concurrently and use `num_samples` for same-prompt groups.
5. Archive raw responses append-only and reconcile delayed billing without changing the original reservation history.

The current broker intentionally has no live-submit switch.
