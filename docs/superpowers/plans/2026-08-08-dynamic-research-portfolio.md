# Dynamic Research Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a live `research_discovery` Seed Project automatically preserve siblings, classify grounded research outcomes, and derive one near-domain plus one distant-domain continuation after a scientific/novelty failure or two information-free probes.

**Architecture:** Add a fail-soft optional Vertical post-mission hook over the existing supervisor and a project-local automatic-expansion controller. The controller validates canonical discovery artifacts, persists deterministic events/requests, idempotently ensures continuation backlog items, and imports typed Rejection Capsules into a host-global advisory experience graph. Existing Backlog DAG, role slots, budgets, evidence validation, and zero-or-one recommendation remain authoritative.

**Tech Stack:** Python 3.11+, dataclasses/JSONL/file locks, Argus Backlog and Vertical hooks, pytest, Ruff, Markdown role Skills, canonical release builder.

## Global Constraints

- The approved design is `docs/superpowers/specs/2026-08-08-dynamic-research-portfolio-design.md`.
- Projects are dynamic Seed Projects; the Memory-as-Control five-project portfolio is an example, never a fixed project topology.
- Each project has one initialization point and at most five active `probe|select` Bets.
- Scientific rejection, novelty collision, and two-strike stagnation derive exactly one `near` and one `far` route.
- Raw task, dependency, access, implementation, evaluator, resource, authority, or infrastructure failure never creates a new Idea.
- Automation is full only inside existing Argus authority and budget gates; no new credential, remote-write, deployment, or cross-Vertical authority is inferred.
- Recommended decisions retain zero-or-one semantics and explicit handoff; no automatic Vertical switch.
- Existing discovery packages remain valid when automatic-expansion state is absent.
- No unsafe/symlink/malformed/stale artifact may enqueue work.
- Do not repair or change the accepted 23 same-machine environment/platform full-suite failures.

---

### Task 1: Idempotent backlog ensure and optional Vertical settlement hook

**Files:**
- Modify: `argus_skill/life/memory.py`
- Modify: `argus_skill/verticals/_base.py`
- Modify: `argus_skill/life/supervisor/_planner_orchestration.py`
- Create: `tests/life/test_memory_backlog.py`
- Create: `tests/life/test_supervisor_vertical_hook.py`

**Interfaces:**
- Produces: `Backlog.ensure_many(new_items: Iterable[BacklogItem]) -> list[BacklogItem]`.
- Produces: `vertical_after_mission(mod, **context) -> dict[str, Any]`.
- Consumes: existing `BacklogItem`, `load_vertical`, `resolve_vertical`, supervisor artifact/global/project roots, and the settled outcome dict.
- Preserves: host `post_mission_hook` stop semantics and every existing Vertical with no hook.

- [ ] **Step 1: Write backlog RED tests**

Add tests using deterministic IDs:

```python
def test_ensure_many_is_idempotent_and_keeps_existing_siblings(tmp_path: Path) -> None:
    backlog = Backlog(tmp_path / "backlog.jsonl")
    sibling = backlog.add(BacklogItem.new(item_id="sibling", title="Sibling", objective="keep"))
    derived = BacklogItem.new(item_id="derived", title="Derived", objective="expand")

    first = backlog.ensure_many([derived])
    second = backlog.ensure_many([derived])

    assert [item.id for item in first] == ["derived"]
    assert [item.id for item in second] == ["derived"]
    assert [item.id for item in backlog.all()] == [sibling.id, "derived"]
```

Also assert that an existing ID with a different title/objective raises
`ValueError`, and that one batch cannot introduce a dependency cycle.

- [ ] **Step 2: Run backlog RED**

Run:

```bash
.venv/bin/pytest -q tests/life/test_memory_backlog.py -k ensure_many
```

Expected: collection or assertion failure because `ensure_many` does not exist.

- [ ] **Step 3: Implement minimal idempotent ensure**

Under the existing backlog file lock, load all rows, reject duplicate IDs
inside the requested batch, compare any already-present row's stable authored
fields (`id`, `title`, `objective`, `tags`, `node_key`, `context_refs`), append
only missing rows, validate dependency cycles, save once, and return the rows in
request order.

- [ ] **Step 4: Write and run Vertical-hook RED**

Create a fake module exposing:

```python
def after_mission(**context):
    calls.append(context)
    return {"status": "reconciled"}
```

Assert the accessor returns a normalized dict, absent hooks return `{}`, hook
exceptions return `{"status": "hook_error", "error": "RuntimeError"}`, and the
supervisor calls the Vertical hook after a non-maintenance mission without
changing a non-empty host-hook stop reason.

Run:

```bash
.venv/bin/pytest -q tests/life/test_supervisor_vertical_hook.py
```

Expected: failure because the accessor/integration does not exist.

- [ ] **Step 5: Implement and verify the hook**

Add `vertical_after_mission` to `_base.py` with a fail-soft normalized result.
In `PlannerOrchestrationMixin._post_mission_hook`, run the configured host hook
first; when it returns no stop reason, resolve the active Vertical and call the
Vertical hook with `project_root`, `state_root`, `global_root`, `backlog`, and
`outcome`. Log hook errors and never turn them into a scientific result or a
mission-settlement failure.

Run the two Task 1 test files and Ruff on the touched Python files.

- [ ] **Step 6: Commit Task 1**

```bash
git add argus_skill/life/memory.py argus_skill/verticals/_base.py \
  argus_skill/life/supervisor/_planner_orchestration.py \
  tests/life/test_memory_backlog.py tests/life/test_supervisor_vertical_hook.py
git commit -m "feat: add idempotent vertical continuations"
```

---

### Task 2: Typed cross-project Rejection Capsule graph

**Files:**
- Create: `argus_skill/verticals/research_discovery/experience_graph.py`
- Test: `tests/skills/test_research_discovery_experience_graph.py`

**Interfaces:**
- Produces: `validate_capsule(payload: object, *, expected_event_id: str = "") -> tuple[str, ...]`.
- Produces: `ResearchExperienceGraph(path: Path)` with `append`, `import_capsule`, `recent`, and `retrieve`.
- Produces: retrieval rows with `channel` equal to `near`, `structural`, or `far`.
- Preserves: capsule contents as advisory and source-bound; never opens `artifact_refs`.

- [ ] **Step 1: Write capsule/graph RED tests**

Cover exact required fields, malformed/unhashable values, source-event mismatch,
symlink rejection, idempotent append, corrupt JSONL rows, bounded reads, lazy
artifact references, near-domain retrieval, structural retrieval, and a far
row that prefers another project with lower domain overlap.

Use a valid capsule shaped as:

```python
{
    "schema_version": 1,
    "event_id": "evt-a",
    "source_bet_ids": ["B1"],
    "source_decision_sha256": "a" * 64,
    "failure_class": "scientific_rejection",
    "killed_premise": "The local policy shift identifies utility.",
    "survivors": ["The application needs safe memory control."],
    "forbidden_region": ["unidentified action-shift heuristic"],
    "open_tension": "Normative value and realized influence can diverge.",
    "mutation_demand": "Change the estimand or identification design.",
    "structure_tags": ["identifiability", "policy-transport"],
    "artifact_refs": ["research/discovery/DECISION.json"],
}
```

- [ ] **Step 2: Run RED**

```bash
.venv/bin/pytest -q tests/skills/test_research_discovery_experience_graph.py
```

Expected: import failure because the module does not exist.

- [ ] **Step 3: Implement minimal graph**

Use a POSIX file lock with a thread fallback, append-only JSONL records, stable
capsule IDs derived from project/event/decision digest, and bounded corrupt-row-
tolerant reads. Retrieval scoring uses lexical domain overlap separately from
structural overlap (`open_tension`, `mutation_demand`, `structure_tags`), so the
far channel is low-domain-overlap but still structurally grounded.

- [ ] **Step 4: Verify and commit Task 2**

Run the new suite, `tests/life/test_failure_experience.py`, Ruff, and compileall.

```bash
git add argus_skill/verticals/research_discovery/experience_graph.py \
  tests/skills/test_research_discovery_experience_graph.py
git commit -m "feat: add research rejection experience graph"
```

---

### Task 3: Seed Project automatic-expansion controller

**Files:**
- Create: `argus_skill/verticals/research_discovery/expansion.py`
- Modify: `argus_skill/verticals/research_discovery/stages.py`
- Modify: `argus_skill/verticals/research_discovery/__init__.py`
- Test: `tests/skills/test_research_discovery_expansion.py`

**Interfaces:**
- Produces: `initialize_seed_project(project_root: Path, *, project_id: str) -> dict[str, Any]`.
- Produces: `classify_current_outcome(project_root: Path, state: Mapping[str, Any]) -> ResearchOutcome`.
- Produces: `reconcile_after_mission(*, project_root, state_root, global_root, backlog, outcome) -> dict[str, Any]`.
- Produces: `automatic_expansion_issue(project_root: Path) -> str`.
- Consumes: public `validate_package`, canonical Portfolio/Bet/Evidence/Decision files, `Backlog.ensure_many`, and `ResearchExperienceGraph`.

- [ ] **Step 1: Write initialization and classification RED tests**

Use real canonical package fixtures. Prove:

- initialization is idempotent, preserves the first objective, and writes the
  approved `automation=full`, active limit 5, stagnation threshold 2,
  `[near, far]`, expansion ceiling 8, and repair ceiling 2;
- valid `recommended` is `eligible` and enqueues nothing;
- valid pre-probe `no_bet` with `nearest_work` failure is
  `novelty_collision`;
- valid completed scientific rejection is `scientific_rejection`;
- blocked non-idea probe is `execution_blocked` and never scientific;
- malformed, stale, unsafe, or symlinked packages are `invalid` and enqueue
  nothing.

- [ ] **Step 2: Run classification RED**

```bash
.venv/bin/pytest -q tests/skills/test_research_discovery_expansion.py \
  -k 'initialize or classify or malformed or symlink'
```

Expected: import failure because `expansion.py` does not exist.

- [ ] **Step 3: Implement fail-closed state and classifier**

Use exact regular-file reads under the supplied project root. Accept a paused
package only when the sole validator blocker is `terminal_paused`; all other
validator errors are invalid. Compute decision and premise-family digests from
canonical bytes/decision bindings, not display prose or raw task status.

- [ ] **Step 4: Write automatic-continuation RED tests**

Prove these behaviors against a real `Backlog`:

1. one no-bet decision creates exactly one immutable request and one
   deterministic continuation task;
2. the request contains branch modes `near` and `far`, current decision digest,
   source Bets, available slots, and advisory graph hits;
3. reconciliation twice and reconciliation after a simulated restart create no
   duplicate task;
4. an unrelated sibling backlog item remains unchanged;
5. the first completed inconclusive paused decision schedules probe redesign,
   while a second distinct result for the same premise family schedules near +
   far derivation;
6. blocked-probe decisions create bounded repair tasks and never derivation;
7. active Bet count over five blocks derivation;
8. eight derivation events mark bounded frontier exhaustion instead of creating
   a ninth;
9. a failed/materially incomplete continuation receives at most two repair
   attempts;
10. a changed decision digest completes the prior request and imports its exact
    capsule into the global graph.

- [ ] **Step 5: Run continuation RED**

```bash
.venv/bin/pytest -q tests/skills/test_research_discovery_expansion.py \
  -k 'enqueue or restart or sibling or stagnat or blocked or frontier or repair or import'
```

Expected: the new behavioral tests fail because reconciliation is absent.

- [ ] **Step 6: Implement controller GREEN**

Under `research/discovery/expansion.lock`:

- atomically load/write `AUTO_EXPANSION.json`;
- reconcile existing request task states before classifying a new decision;
- import only expected `rejections/<event_id>.json` capsules;
- compute deterministic `event_id`/task IDs;
- atomically write `expansion/requests/<event_id>.json` before backlog ensure;
- call `Backlog.ensure_many` before marking the decision processed;
- render a bounded objective that requires the exact request, one near and one
  far child, anti-relabel dimensions, R2 mapping, capsule, minimum probes, and
  updated canonical decision;
- keep derivation tasks dependency-free so a failed parent cannot cascade-skip
  them and siblings continue;
- persist a computed graph snapshot from Portfolio Bet lineage/status.

Expose `after_mission` from `stages.py` and public lazy exports from
`research_discovery.__init__`.

- [ ] **Step 7: Verify and commit Task 3**

Run the full new expansion suite, existing discovery evidence/Vertical suites,
Backlog tests, Ruff, compileall, and diff-check.

```bash
git add argus_skill/verticals/research_discovery/expansion.py \
  argus_skill/verticals/research_discovery/stages.py \
  argus_skill/verticals/research_discovery/__init__.py \
  tests/skills/test_research_discovery_expansion.py
git commit -m "feat: automate research portfolio expansion"
```

---

### Task 4: Lineage, completion, and role Skill contracts

**Files:**
- Modify: `argus_skill/verticals/research_discovery/evidence.py`
- Modify: `argus_skill/verticals/research_discovery/skills/manager/research-discovery-manager.md`
- Modify: `argus_skill/verticals/research_discovery/skills/planner/research-discovery-planning.md`
- Modify: `argus_skill/verticals/research_discovery/skills/engineer/idea-discovery.md`
- Modify: `argus_skill/verticals/research_discovery/skills/engineer/idea-creator.md`
- Modify: `argus_skill/verticals/research_discovery/skills/reviewer/research-discovery-review.md`
- Modify: `argus_skill/verticals/research_discovery/stages.py`
- Test: `tests/skills/test_research_discovery_evidence.py`
- Test: `tests/skills/test_research_discovery_vertical.py`

**Interfaces:**
- Produces: optional validated `BET.json.lineage` and required R2 `theory_transfer` shape.
- Produces: completion blocker while an automatic request is pending/blocked or the active frontier exceeds five.
- Preserves: every legacy package without lineage/automatic state and existing stable validator error families.

- [ ] **Step 1: Record Skill RED from the real pilot**

Record the already-observed baseline: the old Manager Skill says terminal
grounded no-bet and “Never ... enqueue ... automatically”; the Memory-as-
Control no-bet/stage-hold created no successor despite surviving application
value and theoretical tensions. This is the behavior-shaping failure the Skill
edits must correct.

- [ ] **Step 2: Write lineage/completion RED tests**

Cover:

- malformed lineage, invalid parent IDs, generation/radius mismatch, empty
  `changed_dimensions`, and dimensions outside
  `mechanism|estimand|prediction`;
- `radius=far` without exact theory-transfer source mechanism, role mapping,
  new prediction, negative-transfer boundary, and target-domain probe;
- a pending/repair-blocked expansion state prevents completion even when the
  underlying decision is valid no-bet;
- an exhausted bounded state permits the grounded no-bet;
- recommended decisions remain terminal and do not require lineage.

- [ ] **Step 3: Run RED and implement validator/completion GREEN**

```bash
.venv/bin/pytest -q tests/skills/test_research_discovery_evidence.py \
  -k 'lineage or theory_transfer or automatic_expansion'
```

Add optional lineage validation in `_validate_bet`. In `completion_issue`, keep
existing validation precedence, then call `automatic_expansion_issue` only for
an otherwise terminal-valid package.

- [ ] **Step 4: Update Skills using the approved positive contract**

Write the smallest behavior-shaping additions:

- Manager identifies the project as a dynamic Seed Project and treats
  controller-managed derivation as nonterminal while preserving explicit
  downstream handoff.
- Planner consumes the exact request, keeps siblings live, and separates repair
  from pivoting.
- Engineer/Idea Creator writes the exact capsule/lineage/theory-transfer shapes
  and one near plus one far child without changing the application anchor.
- Reviewer requires a target-domain prediction/probe, rejects theory-name-only
  analogies, and checks frontier/processed-event freshness.

Do not add project histories or candidate identities to Skills.

- [ ] **Step 5: Verify Skill GREEN and commit Task 4**

Run the exact scenario through the integrated role banners/controller fixture:
the output contract must keep surviving siblings, classify the source failure,
and request near/far children rather than terminalize or relabel the same Idea.
Then run all discovery suites and Ruff.

```bash
git add argus_skill/verticals/research_discovery/evidence.py \
  argus_skill/verticals/research_discovery/stages.py \
  argus_skill/verticals/research_discovery/skills \
  tests/skills/test_research_discovery_evidence.py \
  tests/skills/test_research_discovery_vertical.py
git commit -m "feat: teach failure-driven research pivots"
```

---

### Task 5: Documentation, release, differential verification, and integration

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: generated release artifacts only through the canonical builder
- Test: focused/adjacent suites listed below

**Interfaces:**
- Documents: dynamic Seed Projects, active frontier five, near/far derivation,
  full budget-bound automation, execution/scientific failure separation, and
  the `AUTO_EXPANSION.json`/request/capsule artifacts.
- Preserves: the disclaimer that discovery completion is not theorem proof,
  production readiness, or paper readiness.

- [ ] **Step 1: Update English and Chinese docs**

Add a compact section after the existing `research_discovery` documentation.
Keep the two languages semantically aligned and state that the current five
Memory-as-Control projects are examples, not fixed roles.

- [ ] **Step 2: Run focused and adjacent verification**

```bash
.venv/bin/pytest -q \
  tests/skills/test_research_discovery_vertical.py \
  tests/skills/test_research_discovery_evidence.py \
  tests/skills/test_research_discovery_expansion.py \
  tests/skills/test_research_discovery_experience_graph.py \
  tests/life/test_failure_experience.py \
  tests/life/test_memory_backlog.py \
  tests/life/test_supervisor_vertical_hook.py \
  tests/core/test_completion_gate.py \
  tests/manager/test_domain_author.py

.venv/bin/ruff check argus_skill tests
.venv/bin/python -m compileall -q argus_skill
git diff --check
```

- [ ] **Step 3: Run canonical release builder and release/deployment checks**

```bash
.venv/bin/python -m argus_skill.release_tools.build_release
.venv/bin/pytest -q tests/core/test_release.py tests/deployment/test_multi_process_contract.py
```

- [ ] **Step 4: Run one final full-suite differential**

Run `.venv/bin/pytest -q` once, save the transcript, and compare exact failing
node IDs with the accepted 23-node baseline. Zero added or missing node IDs is
required; do not repair unrelated environment/platform failures.

- [ ] **Step 5: Commit documentation/release artifacts**

```bash
git add README.md README.zh-CN.md argus_skill frontend docs/superpowers
git commit -m "docs: describe dynamic research portfolios"
```

- [ ] **Step 6: Finish, merge, and restart**

Use `superpowers:finishing-a-development-branch`. Merge
`codex/dynamic-research-portfolio` into local `main`, rebuild release artifacts
if the merge commit changes release identity, restart the integrated WebAPI on
the existing LAN/loopback configuration, and verify release, PID ownership,
HTTP health, and the five existing project daemons without changing their
research artifacts.
