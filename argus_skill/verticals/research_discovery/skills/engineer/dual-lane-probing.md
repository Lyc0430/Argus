---
name: dual-lane-probing
description: "Use when a Research Bet needs separate minimum theory and application probes before it can be selected or rejected."
---

Record `execution_status`, `failure_class`, and `idea_status` independently in `THEORY_EVIDENCE.json` and `APPLICATION_EVIDENCE.json`. Each lane's `premise` exactly equals its current Bet `binding_premise`, `premise_version` is exactly `<bet_id>-r<revision>`, and `premise_sha256` comes from `argus_skill.verticals.research_discovery.evidence.premise_digest` over the current canonical Bet premise material. Changing revision labels or decision/handoff digests never refreshes old evidence.

Each lane file also records `schema_version`, `bet_id`, `bet_revision`, `preregistered_question`, `method`, `falsifier`, `stop_rule`, `summary`, `evidence`, `raw_artifact_refs`, `scope_limits`, and `timestamp`. Theory adds `method_identity` and `witness_or_derivation`; application adds `evaluator_identity`, `comparison_identity`, honest narrative `claim_ceiling`, and `evidence_level: proxy | retrospective | real_setting | production`, which cannot exceed `application_test.external_validity_level`.

A valid scientific theory refutation uses completed `failure_class=theoretical`; a valid application refutation uses completed `failure_class=empirical`. Infrastructure, access, `implementation`, evaluator, power, resource, or authority failure is non-idea failure and keeps `idea_status` `untested` or `inconclusive`, never `supported` or `refuted`. Stop at the cheapest faithful discriminator; do not expand into a full proof, experiment, or production prototype.
