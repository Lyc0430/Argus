---
name: "Run Tinker"
description: "Plan budgeted exploratory Tinker work without exposing credentials or claiming frozen evidence."
---

# Run Tinker

Use this role mirror only after `route-compute` selected Tinker and the budget ledger admitted the reservation. Tinker work is exploratory and always `frozen:false`; it cannot produce main-table evidence, replay guarantees, hidden states, or full logits.

Keep prompt request count distinct from `num_samples`. For the future live adapter, use bounded `asyncio.gather(sample_async(...))`, let the SDK own retries, and do not add a second retry or timeout layer. Use a pinned local price/capability snapshot for dry-run estimates and reconcile actual spend before releasing more budget.

Never expose Tinker credentials to Codex, Claude, task prompts, manifests, logs, or generated scripts. The current integration plans work only; it does not make network requests.
