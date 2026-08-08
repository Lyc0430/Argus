# Dynamic Research Portfolio Design

Status: approved in conversation on 2026-08-08; implementation authorized.

## Summary

Extend the built-in `research_discovery` Vertical from a terminal, linear
portfolio decision into a bounded, event-driven Seed Project DAG. Every Argus
project begins from one initialization point and may grow an independent graph
of Research Bets. A rejected or twice-stagnated Bet releases only its own
frontier slot; sibling Bets continue. The controller persists the outcome,
creates one near-domain and one distant-domain continuation, and schedules the
next bounded research mission automatically.

The system does not contain five fixed project types. The five projects used by
the Memory-as-Control pilot are one concrete portfolio. Theory, ideation,
novelty, application, and experiment are reusable lenses/Skills within any
Seed Project, not a hard-coded project count.

## Approved decisions

- Use an Evidence-Guided Portfolio DAG, not a linear retry chain or an
  unconstrained evolutionary search.
- Projects are dynamically created Seed Projects. Each has one immutable
  initialization point and one independently evolving Bet DAG.
- A project may have at most five active Bets. Extra valid candidates remain
  pending rather than being discarded.
- Actual simultaneous execution is bounded separately by Argus's host-wide
  worker/concurrency and monetary/token/transition budgets.
- A scientific rejection, a novelty collision, or two consecutive
  information-free probes may derive two candidates.
- Each derivation contains one near-domain route (`R0` or `R1`) and one
  distant-domain route (`R2`).
- Automation is full within configured budgets. Candidate generation,
  low-cost probes, distant theory transfer, and eligible compute jobs do not
  require a per-branch operator click.
- Execution failure never counts as scientific rejection and never creates a
  new research Idea. It creates a bounded repair/retry continuation.
- A project reaches terminal `no_bet` only after its derivation budget or
  explicitly grounded frontier is exhausted. Another project's terminal state
  is unaffected.

## Goals

- Continue useful sibling research when one Bet fails.
- Turn a failed Bet into auditable, reusable negative knowledge.
- Escape local conceptual neighborhoods using theory from other domains while
  requiring a target-domain prediction and probe.
- Resume correctly after process restart without duplicate child missions.
- Keep the application problem anchor stable while allowing the mechanism,
  estimand, or falsifiable prediction to change.
- Reuse Argus's existing Backlog DAG, mission settlement, budgets, role slots,
  and `research_discovery` evidence validator.
- Preserve legacy discovery packages unless a live mission initializes the new
  controller state.

## Non-goals

- Automatic paper writing, theorem certification, production deployment, or
  cross-Vertical handoff.
- Treating an analogy, attention signal, literature absence, timeout, or tool
  failure as evidence that a research premise is false.
- A fixed list of five research projects or five mandatory research stages.
- Unlimited branching or hidden compute spend.
- Machine-judging whether a cross-domain analogy is scientifically true. The
  machine validates its structure; a bounded probe supplies the evidence.

## Runtime entities

### Seed Project

An ordinary Argus session selected into `research_discovery`. Its initialization
point is the first grounded portfolio objective. It owns one project-local DAG,
frontier policy, requests, and terminal state.

### Research Bet node

An existing canonical `BET.json`, optionally extended with `lineage`:

```json
{
  "lineage": {
    "source_event_id": "evt-...",
    "parent_bet_ids": ["B1"],
    "generation": 1,
    "radius": "near",
    "changed_dimensions": ["mechanism", "prediction"]
  }
}
```

Derived Bets preserve the application anchor and change at least one of
`mechanism`, `estimand`, or `prediction`. An R2 Bet also records a theory
transfer mapping: source domain, source mechanism, target-role mapping, new
prediction, negative-transfer boundary, and a discriminating target-domain
probe.

### Rejection Capsule

One bounded record of what a rejected branch taught:

```json
{
  "schema_version": 1,
  "event_id": "evt-...",
  "source_bet_ids": ["B1"],
  "source_decision_sha256": "...",
  "failure_class": "scientific_rejection",
  "killed_premise": "...",
  "survivors": ["..."],
  "forbidden_region": ["..."],
  "open_tension": "...",
  "mutation_demand": "...",
  "structure_tags": ["partial-observability", "value-of-information"],
  "artifact_refs": ["..."]
}
```

The five semantic fields are mandatory. A capsule is not a general
impossibility claim and cannot block a materially changed approach.

### Global Experience Graph

An append-only JSONL store under the Argus runtime root imports valid project
capsules with source project and digest provenance. Retrieval mixes:

1. direct or near-domain matches;
2. structural transfer matches over tensions and mechanism tags; and
3. a low-domain-overlap, structurally grounded exploratory analogy.

Cross-project records are advisory. They enter a new project through an
explicit expansion request and never silently satisfy its evidence gates.

## Project-local controller state

The controller owns `research/discovery/AUTO_EXPANSION.json`:

```json
{
  "schema_version": 1,
  "project_id": "s-example",
  "initialization_point": "Find a bounded post-retrieval memory policy.",
  "policy": {
    "enabled": true,
    "automation": "full",
    "max_active_bets": 5,
    "stagnation_threshold": 2,
    "branch_modes": ["near", "far"],
    "max_expansion_events": 8,
    "max_repair_attempts": 2
  },
  "processed_decisions": [],
  "stagnation": {},
  "requests": {}
}
```

The eight-event default is a configurable runaway-search ceiling, not a claim
that eight attempts exhaust science. Hitting it yields a bounded
`portfolio_no_bet`/budget ceiling with the remaining tensions preserved.

Each derivation writes an immutable
`research/discovery/expansion/requests/<event_id>.json`. The request binds the
current decision digest, source Bets, trigger class, near/far branch contract,
available frontier slots, relevant prior capsules, and required outputs.

## Outcome classification

The controller reads the current canonical discovery package after every
settled mission. Raw mission status is diagnostic only.

| Canonical condition | Outcome | Automatic action |
| --- | --- | --- |
| Valid `recommended` | `eligible` | No derivation; keep zero-or-one recommendation |
| Valid `no_bet` with pre-probe failure | `novelty_collision` or grounded rejection | Queue near + far derivation |
| Valid `no_bet` with completed scientific probe failure | `scientific_rejection` | Queue near + far derivation |
| `paused` with blocked/failed non-idea lane | `execution_blocked` | Queue bounded repair, never a new Idea |
| Distinct `paused` completed-probe inconclusive package, first occurrence | `stagnating` | Preserve branch and request a better probe |
| Same premise family reaches a second information-free result | `stagnated_twice` | Preserve paused parent; queue near + far derivation |
| Missing, malformed, stale, or unsafe package | `invalid` | Do not derive; leave fail-closed diagnostics |

## Automatic control loop

1. A mission settles and its backlog row is persisted.
2. The generic Vertical post-mission hook resolves `research_discovery`.
3. Under a project controller lock, the controller validates and classifies
   the current package.
4. A deterministic event ID binds project, decision digest, trigger, premise
   family, and policy version.
5. The controller writes the immutable request, ensures a deterministic
   continuation backlog item, and only then marks the decision processed.
6. The continuation creates the Rejection Capsule, one near Bet, one far Bet,
   the minimum discriminating probes, and an updated canonical decision.
7. The next settlement imports valid capsules to the global graph and repeats
   reconciliation.

The Backlog gains an idempotent batch-ensure operation. A crash after enqueue
but before controller-state update is therefore safe: restart recomputes the
same IDs, observes them already present, and commits the processed event
without duplicating work.

## Scheduling and limits

- `candidate_state=probe|select` counts as active; `park|kill` does not.
- A project never promotes more than five active Bet nodes.
- Derived candidates may be generated while the frontier is full, but remain
  pending/parked until a slot is released.
- Existing host-wide role slots, daemon admission, daily budget, token budget,
  and compute-broker gates remain the execution authority.
- The controller does not bypass Tinker/Katana/paid-API authorization. “Full
  automation” means no idea-level click; it does not create new credentials or
  authority.

## Skill behavior

The role Skills shape judgment while code enforces mechanical invariants:

- Manager: a local branch failure is not project completion; terminal no-bet
  requires exhausted derivation policy.
- Planner: keep siblings live, separate repair from scientific pivoting, and
  schedule the exact controller request.
- Engineer/Idea Creator: write Rejection Capsules, preserve the application
  anchor, generate one near and one far Bet, and satisfy the anti-relabel and
  R2 transfer contracts.
- Reviewer: reject prose-only analogy, stale lineage, mixed failure classes,
  more than five active Bets, or a child that changes only its name.
- Scientist distillation remains unchanged: project identities and outcomes
  stay in artifacts/experience records, not reusable Skills.

## Compatibility and failure handling

- Existing discovery packages remain valid when `AUTO_EXPANSION.json` is
  absent. A live research-discovery mission initializes it idempotently from
  `PORTFOLIO.json.objective`.
- A Vertical hook exception is logged and cannot corrupt mission settlement.
- Unsafe paths, symlinks, malformed JSON, stale digests, and invalid decision
  packages never generate continuation tasks.
- Existing siblings, decisions, raw evidence, nulls, and rejected Bet files are
  append-only/auditable; the controller does not delete them.
- Recommended handoff remains explicit and is never auto-switched into another
  Vertical.

## Verification strategy

- RED/GREEN tests for idempotent backlog ensure, initialization, classification,
  no-bet derivation, blocked-probe repair, two-strike stagnation, restart
  recovery, active-frontier limits, capsule import/retrieval, and completion
  blocking while an expansion is pending.
- Existing `research_discovery` validator and failure-experience suites remain
  green.
- Skill behavior is checked against the observed baseline failure from the
  Memory-as-Control pilot: terminal no-bet/stage-hold with no continuation.
- Focused supervisor, Manager routing, WebAPI snapshot, release, compile, Ruff,
  and canonical build checks run before merge.
