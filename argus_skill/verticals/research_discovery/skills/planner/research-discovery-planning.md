---
name: research-discovery-planning
description: "Use when planning an early theory-application discovery mission whose next method must be chosen under evidence, access, time, or budget constraints."
---

# Research Discovery Planning

Plan adaptively around the next highest-information move; do not require every discovery method for every Bet. Keep candidate generation separate from selection, and freeze eligibility plus ordinal or pairwise comparison criteria before observing finalist outcomes.

For each finalist, choose the cheapest faithful theory probe and application probe that could change the decision. Freeze each exact `binding_premise` in `BET.json` before probing. Lane records use `premise_version=<bet_id>-r<revision>` and the current canonical `premise_sha256`; an old result cannot be relabelled after premise material changes. Parallelize only genuinely independent searches or probes.

Record blocked access, infrastructure, implementation, evaluator, power, resource, or authority as `untested` or `inconclusive`, never as negative evidence about the idea. If a required finalist lane cannot validly complete, plan a nonterminal `paused` decision. Budget exhaustion does not convert blockage into `no_bet`.
