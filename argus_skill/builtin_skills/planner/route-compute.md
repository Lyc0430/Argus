---
name: "Route Compute"
description: "Route research compute through the dry-run Tinker and Katana safety boundary."
---

# Route Compute

Use this role mirror when a task may require Tinker or Katana. Create a version-1 `ComputeRequest` and run `argus-compute plan`; do not call either provider directly.

Route to Katana whenever the work needs hidden states, full-vocabulary logits, pinned/replayable model state, CRN, critic training, custom CUDA, private no-egress data, or evidence for a main table. Tinker is allowed only for exploratory prompt sanity checks, sampling, or standard LoRA prototypes and must remain `frozen:false`.

Treat an explicit Tinker request that conflicts with a Katana-only requirement as an error. Preserve the request's evidence class; selecting Katana does not automatically make exploratory evidence frozen. Planning is dry-run only.
