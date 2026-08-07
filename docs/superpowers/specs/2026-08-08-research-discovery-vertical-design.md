# Research Discovery Vertical Design

Status: approved in conversation on 2026-08-08; awaiting written-spec review.

## Summary

Add one built-in Argus vertical named `research_discovery` for finding and
screening research directions whose theoretical and application value are both
load-bearing. The vertical ends with a trustworthy research decision package:
a ranked portfolio and either zero or one recommended Research Bet. It does not
automatically prove a theorem, launch a full experiment, build a production
prototype, write a paper, or switch the project's persisted vertical.

The implementation reuses Argus's existing idea-generation, literature-search,
and four-state evidence foundations. It adds the missing theory-application
bridge contract, dual-lane evidence model, fail-closed completion validator,
role-specific Skills, and explicit downstream handoff.

## Decision

Implement `research_discovery` as a new built-in vertical instead of:

1. adding discovery stages to `research`, whose lifecycle and completion gate
   are intentionally paper-oriented;
2. splitting theory discovery and application discovery into separate
   verticals, which would destroy the bridge as the unit of evaluation; or
3. copying the supplied Theory Research Workflow plugin wholesale, which would
   duplicate Argus roles and import unrelated publication, author-style, and
   mathematical-audit machinery.

The vertical is domain-neutral in v1. A domain is captured as project context,
not as a new vertical. Built-in domain overlays remain restricted to the
existing `research` vertical in v1; generalizing that cross-cutting contract is
out of scope until a concrete discovery domain needs distinct tools or safety
floors.

## Goals

- Discover research opportunities from an application problem, theoretical
  tool, paper, observed anomaly, or broad research direction.
- Require a precise theoretical anchor, a real application anchor, and an
  explicit mechanism connecting them.
- Screen finalists with the cheapest faithful theory-side and application-side
  probes that fit the operator's budget and authority.
- Keep execution failure, scientific evidence, novelty, bridge validity, and
  selection decisions separate.
- Allow a successful `NO-BET` outcome when no candidate survives.
- Produce one evidence-bound handoff when a candidate is recommended.
- Reuse existing Argus infrastructure and preserve all current vertical
  behavior.

## Non-goals

- Full mathematical proof or machine-audited claim certification.
- Full empirical research, benchmark execution, or paper production.
- Production implementation or deployment.
- Human-subject, clinical, physical, or other real-world intervention without
  an independently authorized downstream task and its domain safety contract.
- Automatic cross-vertical execution.
- Numeric rarity, venue, or composite quality scores.
- Importing author-style Skills, LaTeX templates, plugin manifests, Claude
  hooks, or the supplied plugin's publication pipeline.
- Adding multiple field-specific discovery verticals.

## Core terminology

**Research Bet**
: A falsifiable candidate direction with a real application problem, a precise
  theoretical abstraction, a non-decorative bridge, nearest-work evidence,
  bounded probes, kill criteria, and an explicit next uncertainty.

**Theory lane**
: The candidate's formal objects, assumptions, mechanism, prediction or claim,
  and a probe capable of exposing a counterexample, degeneracy, inconsistency,
  or useful support.

**Application lane**
: The real decision context, intervention or design choice, baseline, metric,
  evaluator, data or access conditions, and an honest external-validity ceiling.

**Bridge**
: The dependency that makes the theoretical model change an application
  design, prediction, boundary, or decision, and makes application evidence
  capable of revising the theoretical account. Shared vocabulary alone is not
  a bridge.

**Decision-ready**
: Sufficiently grounded to choose the next bounded research investment. It does
  not mean proved, deployed, publication-ready, or known to work in the real
  world.

## Architecture

The vertical has four coarse stages:

```text
frame -> discover -> probe -> decide
```

It declares:

```python
WORKFLOW_MODE = "proportional"
completion_gate = "none"
REQUIRE_INDEPENDENT_REVIEW = True
COMPLETION_CONTRACT_VERSION = 1
```

It does not declare `RESEARCH_TARGET_LEVELS`. The existing generic research
target contract describes theorem/result outcomes and would incorrectly block
a discovery decision package.

Methods such as literature mining, counterexample search, derivation, data
inspection, simulation, and micro-prototyping are dynamic Skills or Planner
tasks inside these stages. They are not mandatory stages and not separate
verticals.

### Stage 1: `frame`

Purpose: define the two sides of the search before generating candidates.

Required outcome:

- the application context names the decision-maker or stakeholder, actual
  workflow or setting, present baseline, observed failure or unmet need, and
  consequence of resolving it;
- the theoretical aperture names plausible objects, mechanisms, quantities,
  assumptions, or boundaries without prematurely locking one answer;
- the operator's resource, time, data, access, and safety constraints are
  explicit;
- the stop condition is a decision-ready portfolio, not a paper or product.

The canonical human-readable artifact is
`research/discovery/BRIEF.md`.

### Stage 2: `discover`

Purpose: generate structurally different theory-application Research Bets.

Candidate sources may include:

- application-first: a real pain point, failure, constraint, or anomaly;
- theory-first: a theorem, abstraction, mechanism, or technique that may
  change an application decision;
- paper-first: an explicit gap, limitation, negative result, or open question;
- landscape-first: disagreement, missing comparison, or unstable evaluation
  across a research area.

Generation must steel-man the null and may return no viable candidates. It may
reuse Argus's existing ideation patterns, live literature search, and nearest
work methods. It must not infer novelty from an unsuccessful search.

The canonical portfolio index is
`research/discovery/PORTFOLIO.json`. Per-bet source material lives below
`research/discovery/bets/<bet_id>/`.

### Stage 3: `probe`

Purpose: cheaply discriminate among a small finalist set without turning the
mission into full research execution.

Each finalist receives two separately preregistered probes:

- a theory probe targeting the binding theoretical premise; and
- an application probe targeting the binding application premise against a
  credible baseline or reference.

A probe may be a counterexample search, boundary calculation, small derivation,
finite check, data audit, faithful benchmark slice, simulation, or bounded
prototype. It must be the smallest probe that can change the decision, not a
ceremonial smoke test.

Infrastructure, access, dependency, toolchain, or implementation failure cannot
support or refute a premise. These cases use Argus's shared four-state evidence
vocabulary and remain `untested` or `inconclusive`.

### Stage 4: `decide`

Purpose: independently decide whether any candidate deserves the next research
investment.

The Reviewer applies eligibility gates first, then evidence-backed ordinal or
pairwise comparison. The Reviewer must not use or request a pseudo-precise
composite score.

The final decision is one of:

- `recommended`: exactly one primary Research Bet;
- `no_bet`: no candidate is eligible and every material rejection is grounded;
- `paused`: a faithful decision is blocked by missing data, access, resources,
  authority, or a probe that could not validly run.

`recommended` and `no_bet` may complete the vertical. `paused` may not.

## Canonical artifacts

```text
research/discovery/
  BRIEF.md
  PORTFOLIO.json
  DECISION.json
  HANDOFF.json                       # recommended only
  bets/
    <bet_id>/
      BET.json
      THEORY_EVIDENCE.json
      APPLICATION_EVIDENCE.json
```

`bet_id` must match `[A-Za-z0-9_-]+`. User-controlled IDs are resolved as exact
paths, never interpolated into a glob. Every referenced artifact path is
project-relative, remains under the project root, and points to a regular file.

The design deliberately avoids `research/ideas/**/EVIDENCE.json`. The existing
research-paper idea-evidence scanner owns that namespace and applies an
empirical paper contract that is not the dual-lane discovery contract.

## Data contracts

The implementation uses strict JSON validators rather than treating Markdown
presence as evidence. Examples below describe required semantics, not optional
templates.

### `PORTFOLIO.json`

Required fields:

```json
{
  "schema_version": 1,
  "objective": "...",
  "focus_domain": "...",
  "budget": {"summary": "...", "stop_condition": "..."},
  "bet_refs": ["research/discovery/bets/B1/BET.json"],
  "search_summary": {
    "as_of": "YYYY-MM-DD",
    "sources": ["..."],
    "queries": ["..."]
  }
}
```

`bet_refs` may be empty only when the discover stage records a grounded null
result. Candidate count is not otherwise fixed; the system must not pad the
portfolio to satisfy a quota.

### `BET.json`

Required top-level fields:

- `schema_version`, `id`, and positive integer `revision`;
- `title`, `candidate_state`, and `candidate_premise`;
- `problem_anchor`;
- `theory_anchor`;
- `bridge`;
- `novelty`;
- `application_test`;
- `kill_criteria`, `limitations`, `estimated_cost`, and `next_uncertainty`.

`problem_anchor` requires:

- stakeholder or decision-maker;
- real setting and decision;
- current baseline or practice;
- observed failure or unmet need;
- provenance for the problem claim.

`theory_anchor` requires:

- a `binding_premise` stating the exact premise the theory probe tests;
- formal or operational objects;
- assumptions and scope;
- candidate mechanism;
- prediction, claim, or boundary;
- theory falsifier;
- theory status: `conjectured | sketched | proved | verified`.

The status is descriptive input to discovery. This vertical does not promote a
claim to `proved` or `verified` without the appropriate downstream evidence.

`bridge` requires:

- direction: `theory_to_application | application_to_theory | bidirectional`;
- explicit variable or concept mappings whose every row has non-placeholder
  `theory` and `application` entries;
- a dependency claim describing what application choice, prediction, or
  boundary changes because of the theory;
- an observable prediction generated by the mechanism;
- a no-garnish counterfactual answering whether the application decision would
  remain unchanged if the theory were removed;
- bridge status: `untested | weak | supported | broken`.

`novelty` requires:

- status: `distinct_on_searched_axis | overlap | unresolved`;
- search date and query summary;
- nearest verified work with source locators;
- the precise delta axis;
- the most dangerous overlap or uncertainty.

`overlap` is a reframe or selection signal, not empirical refutation. It may
still leave a new application context, boundary, integration, or decision
contribution, but that delta must be restated before selection.

`application_test` requires:

- a `binding_premise` stating the exact premise the application probe tests;
- intervention, design choice, or phenomenon;
- strongest feasible simple or standard baseline;
- decision metric and evaluator identity;
- data, task, population, or system scope;
- application falsifier;
- proxy-to-real-setting fidelity and an honest narrative
  `external_validity_ceiling`;
- a structured `external_validity_level` using exactly
  `proxy | retrospective | real_setting | production`;
- relevant ethics, safety, access, deployment, and adoption risks.

### Lane evidence files

`THEORY_EVIDENCE.json` and `APPLICATION_EVIDENCE.json` each require:

- `schema_version`, `bet_id`, and `bet_revision`;
- `premise` exactly equal to the lane's current `binding_premise`;
- `premise_version` exactly equal to `<bet_id>-r<bet_revision>`;
- `premise_sha256` equal to the deterministic digest returned by
  `argus_skill.verticals.research_discovery.evidence.premise_digest` for that
  lane;
- preregistered question, method, falsifier, and stop rule;
- `execution_status: completed | blocked | failed`;
- a lane-appropriate `failure_class`;
- `idea_status: untested | inconclusive | supported | refuted`;
- summary, evidence, raw artifact references, scope limits, and timestamp.

Both validators reuse `argus_skill.core.evidence_status.validate_evidence`.
Discovery-specific contracts add lane grounding fields and failure classes.

The theory lane adds `theoretical`, `prior_art`, and `scope_change` to the
shared failure vocabulary. Only `theoretical` may carry a refutation;
`prior_art` and `scope_change` are advisory replanning signals. A conclusive
theory record requires the exact premise, method identity, and a checkable
witness, derivation, or raw finite-check artifact.

The canonical premise digest uses UTF-8 JSON with sorted keys and compact
separators over the Bet ID and revision, top-level `candidate_premise`, lane
name, the complete current lane anchor (`theory_anchor` or `application_test`),
and the complete load-bearing `bridge`. Editing any of this material requires
fresh lane evidence; changing only revision fields or decision/handoff digests
cannot make an old probe current.

The application lane reuses the research evidence vocabulary. Only a completed
`empirical` result may carry a refutation; data access, evaluator
infrastructure, statistical power, implementation, prior art, and scope change
retain their existing non-idea or advisory meanings. A conclusive application
record requires the exact premise, evaluator identity, and comparison identity.
It also carries honest narrative `claim_ceiling` prose plus structured
`evidence_level: proxy | retrospective | real_setting | production`; the
structured evidence level may not exceed the Bet's
`application_test.external_validity_level`.

For both lanes, `failure_class=implementation` is a non-idea failure and cannot
carry `supported` or `refuted`.

The central invariant is unchanged: non-evidentiary execution failures cannot
produce conclusive scientific status.

### `DECISION.json`

Required fields:

```json
{
  "schema_version": 1,
  "decision": "recommended | no_bet | paused",
  "recommended_bet_id": "B1 or null",
  "eligibility": [],
  "ordering": [],
  "selection_rationale": "...",
  "residual_risks": ["..."],
  "limited_by_budget": false,
  "bindings": []
}
```

Each binding records a bet ID and revision plus content digests for `BET.json`,
`THEORY_EVIDENCE.json`, and `APPLICATION_EVIDENCE.json`. Any edit invalidates
the decision until independent review runs again.

Every eligibility row has `bet_id`, boolean `eligible`, `failed_gates`, and
`decision_basis`. `decision_basis` is exactly one of `eligible`,
`pre_probe_gate`, `completed_probe`, or `blocked_probe`. `failed_gates` contains
only these stable identifiers: `application_anchor`, `theory_anchor`, `bridge`,
`nearest_work`, `theory_probe`, `application_probe`, `evidence_separation`,
`safety_authority`, and `fresh_review`; it never contains prose.

For `recommended`:

- `recommended_bet_id` names exactly one portfolio member;
- the selected eligibility row has `eligible=true`,
  `decision_basis=eligible`, and no failed gates;
- every eligibility gate passes;
- both lane probes completed validly and support the current candidate premise;
  a refuted or inconclusive binding premise requires revision, parking, or
  rejection before recommendation;
- the bridge is supported rather than merely asserted;
- novelty is not unresolved; an `overlap` result is eligible only after the
  candidate premise and delta axis are revised to the contribution that remains;
- `HANDOFF.json` exists and binds the same revision and evidence digests.

For `no_bet`:

- `recommended_bet_id` is null;
- every referenced candidate is `eligible=false`, is `park` or `kill`, and has
  nonempty stable failed gates;
- each row uses `pre_probe_gate`, grounded by `application_anchor`,
  `theory_anchor`, `bridge`, or `nearest_work`, or `completed_probe`, grounded by
  a scientifically negative or inconclusive theory/application probe after
  both required lanes completed coherently;
- no infrastructure or access failure is presented as a scientific rejection;
- the result may be budget-limited only when the completed search and probes
  support a genuine bounded decision. If a faithful finalist probe never ran,
  the decision is `paused`, not `no_bet`.

`blocked_probe` explains a nonterminal `paused` decision and can never terminate
as `no_bet`. A failed, blocked, invalid, under-powered, inaccessible, or
implementation-broken required finalist lane is a blocked probe, not a
scientific refutation. A grounded empty-portfolio `no_bet` remains valid.

### `HANDOFF.json`

Generated only for `recommended`. It contains:

- `bet_id`, `bet_revision`, and the same evidence bindings as the decision;
- exactly one `next_vertical`: `math`, `research`, or `software`;
- the binding uncertainty that the next vertical must address;
- a bounded objective, acceptance check, non-goals, evidence references, and
  return condition;
- an honest claim ceiling describing what discovery established and did not
  establish.

The handoff never mutates `research/PIPELINE_STATE.json` to another vertical and
never automatically enqueues downstream work.

## Selection gates

A candidate is eligible for recommendation only when all of these hold:

1. **Application anchoring:** the real problem, decision, baseline, and source
   are concrete.
2. **Theory anchoring:** the objects, assumptions, mechanism, prediction, and
   falsifier are precise enough to probe.
3. **Non-decorative bridge:** the dependency and no-garnish tests show that the
   theory changes a design, prediction, or boundary.
4. **Nearest-work differentiation:** the searched axis and most dangerous prior
   work are explicit; absence of search results is not a novelty claim.
5. **Theory probe:** a faithful theory-side premise was validly exercised.
6. **Application probe:** a faithful application-side premise was validly
   exercised against a credible reference or baseline.
7. **Evidence separation:** one successful lane does not stand in for the other,
   and proxy results respect their evidence ceiling.
8. **Safety and authority:** the bounded probes stayed inside authorized access
   and did not perform an unapproved real-world intervention.
9. **Fresh independent review:** the final decision and optional handoff bind the
   current bet revision and lane evidence digests.

After eligibility, the Reviewer compares candidates using supported ordinal
judgments such as stronger/weaker theoretical leverage, application value,
discriminability, feasibility, and residual risk. A scalar total is forbidden
because it hides fatal gates and creates false precision.

## Role design

### Manager

The Manager:

- routes early theory-application research ideation to
  `research_discovery`;
- distinguishes it from `math` proof work, full-paper `research`, and
  `software` implementation;
- preserves the operator's direction, budget, authority, and stop condition;
- refuses automatic escalation to downstream execution or publication;
- treats `recommended`, `no_bet`, and `paused` according to the completion
  semantics above.

### Planner

The Planner:

- selects the next highest-information move rather than requiring every
  discovery method;
- separates candidate generation from candidate selection;
- preregisters ordering criteria before observing finalist probe outcomes;
- designs the cheapest faithful theory and application probes;
- decomposes only genuinely independent searches or probes;
- never converts a blocked run into a negative idea verdict.

### Engineer

The Engineer:

- performs real source retrieval, paper absorption, application problem mining,
  theoretical abstraction, bridge construction, counterexample search, and
  bounded probes;
- writes the canonical artifacts through exact paths;
- records raw evidence, nulls, failed attempts, and scope limits;
- does not write a paper plan, full experiment plan, or production prototype as
  a side effect of discovery.

Vertical-specific Engineer Skills replace the research-paper output contracts
of common `idea-discovery`, `idea-creator`, and `novelty-check` when this
vertical is active. They may reuse the existing methods and reference material,
but their outputs are the discovery artifacts in this specification.

### Reviewer

The Reviewer independently checks:

- the most dangerous nearest work and claimed delta;
- whether the theory is load-bearing or decorative;
- whether each probe tests the stated premise;
- execution-versus-evidence invariants;
- proxy drift and external-validity ceilings;
- selection integrity, failed/null preservation, and stale bindings;
- final completion through the machine validator.

### Scientist

The Scientist may distill or adapt project-local reusable discovery procedures
only after a concrete method gap or durable learning appears. It does not store
project history, a specific candidate, or generic brainstorming advice.

## Skill layout

The new vertical owns concise role Skills under:

```text
argus_skill/verticals/research_discovery/skills/
  manager/research-discovery-manager.md
  planner/research-discovery-planning.md
  engineer/idea-discovery.md
  engineer/idea-creator.md
  engineer/novelty-check.md
  engineer/theory-application-bridge.md
  engineer/dual-lane-probing.md
  reviewer/research-discovery-review.md
  scientist/research-discovery-distillation.md
  scientist/research-discovery-adaptation.md
```

The three same-path Engineer Skills intentionally override the common
research-paper versions only inside this vertical. This prevents common output
contracts from writing `IDEA_CANDIDATES.md`, committing an experiment plan, or
requiring a winner.

The supplied Theory Research Workflow is used as design input, not copied
wholesale. The directory has no license or notice and contains version drift
between 6.2 and 6.3. New Argus Skills will therefore be written in Argus-native
language. They retain only general research-integrity principles such as
source-grounded search, null-first ideation, cheap falsification, most-dangerous
prior-work review, and no automatic paper escalation.

## Routing

Register `research_discovery` in `VERTICALS` and add a purpose that explicitly
targets early research direction finding where theory and application must both
matter.

Manager routing guidance must separate these examples:

- "find research ideas connecting a theoretical mechanism to a real problem"
  -> `research_discovery`;
- "prove or refute this theorem" -> `math`;
- "run experiments and produce a submission-ready paper" -> `research`;
- "implement this selected method in the repository" -> `software`.

The route remains model-decided and fail-hard. No keyword classifier is added.
`domain` remains null for `research_discovery` in v1.

## Fail-closed completion

Checklist-only completion is insufficient for a machine-readable decision
package. Add an optional vertical hook:

```python
completion_issue(project_root: object) -> str
```

and a safe accessor in `argus_skill.verticals._base`:

```python
vertical_completion_issue(mod, project_root) -> str
```

The default result is an empty string, preserving all existing verticals.

For `research_discovery`, the hook invokes the discovery evidence validator and
returns a stable issue code when artifacts are missing, invalid, stale, or
inconsistent.

The hook is checked in both completion paths:

1. Manager completion blocking before it accepts terminal advancement; and
2. `stage_machine.complete_final_stage` immediately before final `done` state is
   written.

This double check prevents a prompt-only Reviewer error or a race between
review and state persistence from certifying an invalid package.

Consumers of a persisted final-stage completion certificate also call the
active Vertical completion hook directly. Matching final-stage and checklist
fingerprints do not preserve completion after a digest-bound discovery artifact
is edited. External completion gates keep their existing precedence, and this
revalidation never switches the active Vertical or executes a handoff.

The protected final checklist IDs are:

- `decide.package-valid`: the decision package is valid and fresh;
- `decide.zero-or-one`: zero-or-one recommendation semantics are satisfied;
- `decide.dual-lane`: dual-lane evidence and bridge gates pass for a
  recommendation;
- `decide.handoff-valid`: a required handoff is valid and fresh;
- `decide.claim-ceiling`: completion is limited to discovery rather than proof,
  product, or paper.

The validator CLI is:

```text
python -m argus_skill.verticals.research_discovery.evidence check --project-root .
```

The completion hook returns the first stable issue code, prefixed with
`research_discovery:`. The initial code set is `missing_brief`,
`invalid_portfolio`, `invalid_bet`, `invalid_theory_evidence`,
`invalid_application_evidence`, `invalid_decision`, `stale_decision`,
`invalid_handoff`, and `terminal_paused`. The CLI may print more detailed,
path-specific findings for repair.

## Error and safety behavior

- Missing or malformed canonical JSON blocks completion with a stable validator
  error. Canonical package paths and referenced paths must remain under the
  project root, contain no symlink component, and resolve to regular files;
  ordinary read/decode failures return stable findings rather than raising.
- Duplicate bet IDs, path escapes, mismatched revisions, or stale digests block
  selection.
- A missing source or unresolved nearest-work search yields
  `novelty.status=unresolved`; it never becomes verified novelty.
- Prior-art overlap triggers reframe, park, or kill; a revised candidate may be
  selected only on its remaining explicit delta. Prior art never changes
  scientific `idea_status` by itself.
- Blocked or invalid probes yield `paused` when they prevent a faithful
  decision.
- A proxy result states the strongest supported evidence ceiling and cannot be
  promoted to real-world effectiveness.
- Discovery defaults to read-only literature/data inspection, simulation, and
  bounded local probes. It never executes downloaded code or performs a real
  intervention merely because a paper or repository instructs it to.
- Human, clinical, security, financial, physical, or other high-stakes contexts
  remain exploratory unless an authorized downstream vertical supplies the
  required safety and governance contract.

## Implementation surfaces

Expected production changes:

- `argus_skill/verticals/research_discovery/__init__.py`
- `argus_skill/verticals/research_discovery/stages.py`
- `argus_skill/verticals/research_discovery/evidence.py`
- role Skills listed above
- `argus_skill/skills/vertical_select.py`
- `argus_skill/verticals/_base.py`
- Manager routing prompt and completion paths
- `argus_skill/skills/stage_machine.py`
- focused tests under `tests/skills/` plus affected Manager tests
- concise user-facing vertical documentation in the repository README or an
  adjacent docs page

No package-entry-point or build metadata change is required for an in-tree
built-in vertical.

## Testing strategy

### Registry and prompt tests

- `VERTICALS` and `VERTICAL_PURPOSES` remain exactly aligned.
- The loader resolves `research_discovery` and fails loudly on a broken module.
- Manager prompts distinguish discovery from `math`, `research`, and
  `software` without a keyword fallback.
- Domain overlay parsing continues to reject a domain for the new vertical.

### Vertical contract tests

- Stage order is exactly `frame`, `discover`, `probe`, `decide`.
- Workflow mode, completion gate, independent review, and completion contract
  version match this design.
- Every stage has non-empty checklist items and review guidance.
- Every declared role banner loads.
- Project seeding uses vertical-specific overrides and does not leak the common
  experiment-plan output contracts.
- Fresh vertical persistence seeds `frame` without changing existing
  seed-only/reset semantics.

### Evidence validator tests

Accept:

- a complete `recommended` package with one fresh handoff;
- a grounded `no_bet` package;
- supported, refuted, null, and inconclusive lane evidence when their execution
  status and failure class are coherent.

Reject:

- one-sided or decorative candidates;
- a recommendation with zero or multiple selected bets;
- unresolved or ungrounded nearest work presented as novelty;
- a recommendation with missing, blocked, or invalid lane probes;
- an infrastructure failure recorded as scientific refutation;
- prior art recorded as scientific refutation;
- mismatched IDs or revisions;
- stale decision or handoff digests;
- proxy evidence promoted above its declared ceiling;
- missing handoff for a recommendation or handoff for `no_bet`;
- `paused` presented as terminal completion;
- unsafe or escaping evidence paths.

### Completion and regression tests

- The optional completion hook defaults to no issue for every existing
  vertical.
- Manager and final-stage persistence both reject an invalid discovery package.
- The final completion fingerprint becomes stale when the contract version or
  protected checklist changes.
- Existing math, research, software, domain, direct, and proportional workflows
  remain unchanged.
- Existing goal-gate and completion-livelock parameterized tests include the new
  vertical and pass.

## Success criteria

The feature is complete when:

1. Manager can route a theory-application Idea search to
   `research_discovery` and distinguish the adjacent verticals.
2. A project can progress through all four stages using Argus's normal
   Planner/Engineer/Reviewer lifecycle.
3. The validator accepts only coherent `recommended` or `no_bet` decision
   packages and blocks stale or one-sided packages.
4. Recommended decisions emit one valid, evidence-bound handoff without
   changing verticals or launching downstream work.
5. Common Idea Skills are reused or safely overridden without entering the
   paper pipeline.
6. Focused and full regression tests pass.
7. User documentation explains when to choose this vertical, its artifacts,
   and what its completion does and does not mean.

## Rollout and compatibility

This is an additive built-in vertical with no migration of existing projects.
Existing persisted projects retain their current vertical and stages. A plugin
or project data domain named `research_discovery` would be shadowed by the new
built-in name; the built-in name is intentionally reserved by registration.

If the feature later demonstrates a real need for field-specific tools or
safety floors, add domain-overlay compatibility as a separate design. Do not
preemptively generalize that contract in v1.
