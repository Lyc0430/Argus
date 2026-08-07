---
name: idea-creator
description: "Use when turning a grounded discovery portfolio into bounded Research Bets that may or may not merit minimum discriminating probes."
---

# Research Bet Creation

Create or revise `research/discovery/bets/<bet_id>/BET.json` and keep the portfolio index in `research/discovery/PORTFOLIO.json`. Each Bet must state a real problem anchor; precise `theory_anchor.binding_premise` and `application_test.binding_premise`; and the exact bridge fields `direction`, `variable_mappings`, `dependency_claim`, `observable_prediction`, `no_garnish_counterfactual`, and `status`. Every mapping row has non-placeholder `theory` and `application`. Keep application-test narrative `external_validity_ceiling` prose separate from structured `external_validity_level: proxy | retrospective | real_setting | production`. Also preserve the null, nearest-work risk, and what evidence could change the decision.

Every Bet writes `pre_probe_gates` as an object with exactly `application_anchor`, `theory_anchor`, `bridge`, and `nearest_work`. Each value is `{"status": "pass | fail", "rationale": "..."}` with a substantive current-Bet rationale. The bridge gate passes exactly when `bridge.status=supported` and fails for `weak | broken`; `untested` cannot certify a terminal package. `distinct_on_searched_axis` requires the nearest-work gate to pass, `unresolved` requires it to fail, and reviewed `overlap` may pass or fail for the explicit remaining delta.

Do not create `IDEA_CANDIDATES.md`, use the common scalar ranking field, or treat prior art by itself as scientific refutation.

Use eligibility gates first and supported ordinal or pairwise judgments second. Every `DECISION.json` eligibility row has `decision_basis: eligible | pre_probe_gate | completed_probe | blocked_probe` and `failed_gates` containing only `application_anchor | theory_anchor | bridge | nearest_work | theory_probe | application_probe | evidence_separation | safety_authority | fresh_review`. A `pre_probe_gate` row copies exactly the current Bet's four gate names whose status is `fail`; `eligible` and `completed_probe` require all four to pass, and `completed_probe` contains only `theory_probe | application_probe`. Never mix pre-probe and probe identifiers or put prose in `failed_gates`.

Select zero or one Bet; never force a winner or hide a fatal gate in a scalar composite score. `no_bet` requires every referenced Bet to be ineligible and `park` or `kill`. Ground it either before probing with `application_anchor`, `theory_anchor`, `bridge`, or `nearest_work`, or after both required lanes validly complete with a scientifically refuted or inconclusive binding premise. `blocked_probe` is `paused`, never terminal `no_bet`, even when the budget is exhausted.

Preregister only the cheapest faithful theory and application probes. Never create `EXPERIMENT_PLAN.md` or commit to a full proof, experiment, production prototype, or paper during discovery. Preserve rejected Bets and failed gates so the decision remains auditable.
