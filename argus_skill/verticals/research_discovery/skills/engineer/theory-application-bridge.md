---
name: theory-application-bridge
description: "Use when a candidate direction claims that a precise theoretical mechanism changes a real application decision or prediction."
---

Require a problem anchor, theory anchor, and the exact `bridge` fields `direction`, `variable_mappings`, `dependency_claim`, `observable_prediction`, `no_garnish_counterfactual`, and `status`. Every `variable_mappings` row has non-placeholder `theory` and `application` entries; explanatory extras cannot replace either side. If removing the theory leaves the application design and prediction unchanged, set `status=weak` and do not recommend the Bet.
