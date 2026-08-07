# Research Discovery Gate Grounding Design

## Context

The first `research_discovery` implementation made eligibility gate names and
decision bases machine-readable, but a terminal `no_bet` could still combine a
`pre_probe_gate` basis with both a nominal pre-probe token and a blocked probe
token. The validator checked token membership, not whether the current Bet
actually recorded that pre-probe gate as failed. This allowed a blocked
finalist to be hidden behind an unrelated token.

This addendum closes that terminal-path gap without changing the approved
`frame → discover → probe → decide` workflow, zero-or-one recommendation rule,
dual-lane evidence model, or downstream handoff boundary.

## Chosen design

Each referenced `BET.json` adds an exact `pre_probe_gates` object:

```json
{
  "pre_probe_gates": {
    "application_anchor": {"status": "pass | fail", "rationale": "..."},
    "theory_anchor": {"status": "pass | fail", "rationale": "..."},
    "bridge": {"status": "pass | fail", "rationale": "..."},
    "nearest_work": {"status": "pass | fail", "rationale": "..."}
  }
}
```

The four keys are exact. Every row requires a non-placeholder rationale. The
gate results live inside the Bet, so the existing Bet digest in
`DECISION.json.bindings` binds them to the independently reviewed decision.

Two existing structured fields provide additional consistency checks:

- `pre_probe_gates.bridge.status=pass` requires `bridge.status=supported`;
  `fail` requires `bridge.status=weak | broken`.
- `novelty.status=distinct_on_searched_axis` requires
  `pre_probe_gates.nearest_work.status=pass`. `overlap` may pass only when the
  current Bet's explicit remaining `delta_axis` is the reviewed contribution;
  `overlap` or `unresolved` may fail with a grounded rationale.

Application- and theory-anchor gate rows are the current Bet's explicit
eligibility assessment. Their underlying anchor schemas remain fully required,
so a failed gate is a substantive judgment with a rationale rather than a
missing-field shortcut.

## Decision invariants

The four `decision_basis` values have mutually exclusive shapes:

- `eligible`: `eligible=true`, no `failed_gates`, and all four current Bet
  pre-probe gates pass.
- `pre_probe_gate`: `eligible=false`; `failed_gates` is nonempty, contains only
  the four pre-probe gate identifiers, and equals exactly the current Bet's
  `pre_probe_gates` rows whose status is `fail`.
- `completed_probe`: `eligible=false`; all current Bet pre-probe gates pass;
  `failed_gates` contains only `theory_probe | application_probe`; both lanes
  completed validly, and every named failed probe is grounded by a refuted or
  inconclusive lane result.
- `blocked_probe`: may describe only a nonterminal `paused` decision. It cannot
  terminate as `no_bet`; any named probe gate must be grounded by a blocked,
  failed, non-idea, or otherwise invalid required lane.

For terminal `no_bet`, every referenced Bet remains `park | kill` and must use
either the exact current pre-probe failure set or coherent completed-probe
evidence. A row cannot mix pre-probe and probe gate categories. Budget limits
do not relax these invariants. The grounded empty-portfolio `no_bet` remains
valid.

For `recommended`, the selected Bet must have all four pre-probe gates passing
in addition to the already enforced bridge, novelty, dual-lane, eligibility,
freshness, and handoff checks.

## Error behavior

Gate-shape or gate-grounding contradictions return the existing
`invalid_decision` stable error family. Missing or malformed
`BET.json.pre_probe_gates` returns `invalid_bet`. No new completion error family
is introduced.

## Skill behavior

The Bet-authoring and Reviewer Skills must teach the positive artifact shape:
write all four `pre_probe_gates` rows with status and rationale, copy the exact
failed set into a `pre_probe_gate` decision, and never mix pre-probe and probe
gate identifiers in one basis. A fresh-context pressure scenario must fail
without the amended Skill guidance and produce the canonical grounded shape
with it.

## Test design

Behavioral RED tests must first reproduce:

- the independently confirmed mixed `nearest_work + theory_probe` bypass with a
  dependency-blocked theory lane;
- a `nearest_work` failure contradicting
  `novelty.status=distinct_on_searched_axis`;
- decision failed gates that do not equal the current Bet's failed pre-probe
  rows;
- a completed-probe decision whose Bet still has a failed pre-probe gate; and
- a recommendation whose Bet has any failed pre-probe gate.

GREEN coverage must retain valid recommendation, grounded pre-probe `no_bet`,
completed scientific-refutation `no_bet`, blocked nonterminal `paused`, empty
portfolio, stale binding, and all earlier adversarial cases. After the focused
suite, refresh canonical release artifacts and prove the same accepted
same-machine 23-failure differential before merging.
