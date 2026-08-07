---
name: "Verify Compute Run"
description: "Independently verify compute artifacts, episode coverage, and frozen-evidence provenance."
---

# Verify Compute Run

Use this role mirror after provider work finishes. Run `argus-compute verify --project-root <root> --plan <plan.json> --manifest <manifest.json>` and accept evidence only when the JSON report has `accepted:true`.

A zero exit code alone is insufficient. Verify output containment and SHA-256 digests, exact planned-output coverage, complete episode coverage, zero duplicate `(query, branch, seed)` keys, matching provider/job/frozen fields, and actor fingerprints for frozen Katana runs. Reject any Tinker result that claims frozen or main-table evidence.

Verification exit code `3` means the inputs were readable but the evidence failed acceptance. Do not promote a failed report into research claims.
