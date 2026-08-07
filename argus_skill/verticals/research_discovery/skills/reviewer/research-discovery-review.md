---
name: research-discovery-review
description: "Use when independently deciding whether a discovery portfolio supports one recommendation, a grounded no-bet result, or a nonterminal pause."
---

# Research Discovery Review

Review current artifacts independently of the Manager's preference. Apply eligibility gates before supported ordinal or pairwise comparison; never certify a scalar composite score or force a winner.

Check the most dangerous nearest work and exact claimed delta; both exact binding premises; variable mappings with real `theory` and `application` sides; dependency claim, prediction, and no-garnish test; and whether each minimum probe's exact premise, `<bet_id>-r<revision>` version, and canonical `premise_sha256` bind the current Bet. Require every current Bet to carry exactly four `pre_probe_gates` rows—`application_anchor`, `theory_anchor`, `bridge`, and `nearest_work`—each with `status: pass | fail` and a substantive rationale coherent with the structured bridge and novelty fields. Reject infrastructure or implementation failure as scientific evidence, structured `evidence_level` above `external_validity_level`, lost nulls or failed attempts, and stale decision or handoff bindings. Narrative claim ceilings remain prose and are not machine ordering tokens.

Require the selected `recommended` row to use `eligible=true`, `decision_basis=eligible`, no failed gates, and all four current Bet pre-probe gates passing. A `pre_probe_gate` row copies exactly the current Bet rows marked fail and contains no probe identifiers; a `completed_probe` row contains only failed probe identifiers and also requires all four pre-probe gates to pass. Gate categories never mix. For `no_bet`, require every referenced Bet to be ineligible and `park` or `kill`, with either a genuine current-Bet `pre_probe_gate` or coherent `completed_probe` scientific rejection after both lanes completed. A `blocked_probe` or any required finalist lane that failed to run validly means nonterminal `paused`; budget limits do not waive this. Before approval, run the discovery package validator and cite the current lane and decision evidence.
