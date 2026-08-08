---
name: idea-discovery
description: "Use when generating source-grounded theory-application Research Bets before a direction has earned downstream research investment."
---

# Research Discovery Engineer Contract

Discovery produces `research/discovery/PORTFOLIO.json` plus one `research/discovery/bets/<bet_id>/BET.json` per retained Bet. Do not write the common `IDEA_CANDIDATES.md`, add a scalar `rank_score`, write `EXPERIMENT_PLAN.md`, force a winner, or treat prior art as a scientific refutation.

Generate structurally different Bets from real application failures, theoretical mechanisms, explicit paper gaps, or landscape disagreements. For every Bet, preserve its problem anchor; `theory_anchor.binding_premise`; `application_test.binding_premise`; variable mappings with non-placeholder `theory` and `application` entries; dependency claim; observable prediction; no-garnish counterfactual; null explanation; nearest-work search; and unresolved scope limits. Record narrative `external_validity_ceiling` separately from structured `external_validity_level: proxy | retrospective | real_setting | production`. An unsuccessful search does not establish novelty.

Every `BET.json` includes an exact `pre_probe_gates` object with the four keys `application_anchor`, `theory_anchor`, `bridge`, and `nearest_work`; each key maps to `{"status": "pass | fail", "rationale": "..."}` grounded in that current Bet. Do not put probe, evidence-separation, safety, or review gates in this object. Bridge `supported` maps to pass, `weak | broken` maps to fail, and `untested` cannot terminate; nearest-work `distinct_on_searched_axis` maps to pass and `unresolved` maps to fail, while reviewed `overlap` may pass or fail for its explicit remaining delta.

Candidate generation is not selection. Retain raw sources, failed searches, rejected candidates, and nulls. End discovery with a grounded portfolio that may support zero or one later recommendation, never with an automatic paper, proof, experiment, or implementation commitment.

For a controller-owned expansion request, first write the exact typed Rejection Capsule: killed premise, survivors, forbidden region, open tension, mutation demand, structure tags, and current artifact references. Preserve the application problem anchor and all live siblings. Create exactly one `near` and one `far` child with validated `lineage`; each child changes at least one of mechanism, estimand, or prediction rather than merely relabeling the parent. The far child also writes `theory_transfer` with source domain and mechanism, target-role mappings, a new target prediction, a negative-transfer boundary, and a discriminating target-domain probe. Keep no more than five active Bets; extra children remain parked.
