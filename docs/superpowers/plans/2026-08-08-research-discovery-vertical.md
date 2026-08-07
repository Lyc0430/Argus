# Research Discovery Vertical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed `research_discovery` Vertical that finds and screens theory-application Research Bets, ending with either one evidence-bound recommendation or a grounded `no_bet` decision.

**Architecture:** Add an in-tree proportional four-stage Vertical (`frame → discover → probe → decide`) with a strict package validator built on Argus's shared four-state evidence model. Register it with Manager routing, supply vertical-owned role Skills, and add a generic optional completion hook checked both before Manager completion and immediately before final stage persistence.

**Tech Stack:** Python 3.11+, pytest, stdlib `json`/`hashlib`/`pathlib`/`argparse`, Argus `ChecklistItem`, `EvidenceContract`, vertical registry, Manager stage decision, and layered Skill seeding.

## Global Constraints

- Work only on branch `codex/research-discovery-vertical`; preserve unrelated user changes.
- Use test-driven development: write each failing test, run it red, implement the minimum behavior, and rerun it green.
- The final outcomes are exactly `recommended`, `no_bet`, and non-terminal `paused`; never force a recommendation.
- A `recommended` package names exactly one bet and binds current `BET.json`, theory evidence, and application evidence digests.
- Infrastructure, dependency, access, toolchain, evaluator, statistical-power, or implementation failures cannot support or refute an idea.
- Prior art and scope changes are replanning signals, not scientific refutations.
- Selection uses eligibility gates plus ordinal evidence, never a composite numeric score.
- `research_discovery` never automatically writes a full experiment plan, switches Vertical, builds a production artifact, or enters publication.
- Domain overlays remain restricted to `research` in v1; `research_discovery` persists `domain=null`.
- Do not copy unlicensed text from `/Users/landon/Downloads/theory-research-workflow 3/`; write Argus-native Skills using only general research principles.
- All bet IDs match `[A-Za-z0-9_-]+`; all artifact references are exact project-relative regular-file paths under the project root.
- Existing Vertical behavior and existing flat Skill ownership invariants must remain green; any same-path Skill override must be explicitly allowlisted and tested.
- The macOS baseline has 23 unrelated environment/platform failures; completion requires no new full-suite failures plus a fully green focused and adjacent suite, not repairs outside this feature.
- Every new role Skill uses a hyphenated `name`, a third-person `description` beginning with `Use when...`, and is pressure-tested individually before the next Skill is authored.

---

## File map

### New production files

- `argus_skill/verticals/research_discovery/__init__.py` — public Vertical exports.
- `argus_skill/verticals/research_discovery/stages.py` — stage order, checklists, protected items, role banners, and `completion_issue` hook.
- `argus_skill/verticals/research_discovery/evidence.py` — artifact loading, schema validation, dual-lane evidence contracts, freshness bindings, completion issue codes, and CLI.
- `argus_skill/verticals/research_discovery/skills/manager/research-discovery-manager.md` — routing and stop boundary.
- `argus_skill/verticals/research_discovery/skills/planner/research-discovery-planning.md` — adaptive discovery and preregistered probe planning.
- `argus_skill/verticals/research_discovery/skills/engineer/idea-discovery.md` — discovery-specific replacement for the paper-oriented common Skill.
- `argus_skill/verticals/research_discovery/skills/engineer/idea-creator.md` — zero-or-one selection and bounded probes, without experiment-plan commitment.
- `argus_skill/verticals/research_discovery/skills/engineer/novelty-check.md` — searched-axis differentiation without treating prior art as refutation.
- `argus_skill/verticals/research_discovery/skills/engineer/theory-application-bridge.md` — dual anchors, variable mapping, dependency, and no-garnish test.
- `argus_skill/verticals/research_discovery/skills/engineer/dual-lane-probing.md` — separate preregistration and evidence recording.
- `argus_skill/verticals/research_discovery/skills/reviewer/research-discovery-review.md` — independent eligibility, freshness, and claim-ceiling review.
- `argus_skill/verticals/research_discovery/skills/scientist/research-discovery-distillation.md` — reusable method distillation.
- `argus_skill/verticals/research_discovery/skills/scientist/research-discovery-adaptation.md` — method adaptation after a concrete gap.
- `argus_skill/core/completion_gate.py` — combined external and active-Vertical completion issue resolver.

### Modified production files

- `argus_skill/skills/vertical_select.py` — register the Vertical and purpose.
- `argus_skill/skills/builtins.py` — declare the three intentional same-path Skill overrides.
- `argus_skill/verticals/_base.py` — expose fail-closed `vertical_completion_issue`.
- `argus_skill/roles/prompts/manager.py` — distinguish discovery from proof, paper, and implementation routing.
- `argus_skill/manager/_stage_ops.py` — use the combined completion issue in both final-decision paths.
- `argus_skill/skills/stage_machine.py` — recheck the combined issue before writing final `done`.
- `README.md` and `README.zh-CN.md` — document the built-in Vertical and completion meaning.

### New and modified tests

- `tests/skills/test_research_discovery_evidence.py` — package and lane validator tests.
- `tests/skills/test_research_discovery_vertical.py` — registry, stages, checklists, roles, Skill ownership, and routing tests.
- `tests/core/test_completion_gate.py` — optional hook and combined gate tests.
- `tests/skills/test_builtins_seeding.py` — exact intentional override allowlist and seeded-body assertions.
- `tests/manager/test_domain_author.py` — Manager prompt routing boundary.
- `tests/skills/test_verticals.py` — persistence/evidence-mode regression for the new Vertical if not fully covered in the dedicated test.

---

### Task 1: Build the dual-lane discovery package validator

**Files:**
- Create: `argus_skill/verticals/research_discovery/__init__.py`
- Create: `argus_skill/verticals/research_discovery/evidence.py`
- Create: `tests/skills/test_research_discovery_evidence.py`

**Interfaces:**
- Consumes: `argus_skill.core.evidence_status.EvidenceContract`, `validate_evidence`, `BASE_FAILURE_CLASSES`, and `BASE_NON_IDEA_FAILURES`.
- Produces: `validate_package(project_root: Path | str) -> list[str]`, `completion_issue(project_root: Path | str) -> str`, `content_digest(path: Path) -> str`, `main(argv: list[str] | None = None) -> int`, `THEORY_EVIDENCE`, and `APPLICATION_EVIDENCE`.
- Stable completion issue prefix: `research_discovery:`.
- Stable first-error codes: `missing_brief`, `invalid_portfolio`, `invalid_bet`, `invalid_theory_evidence`, `invalid_application_evidence`, `invalid_decision`, `stale_decision`, `invalid_handoff`, and `terminal_paused`.

- [ ] **Step 1: Write package fixtures and the first failing happy-path tests**

Create a fixture writer in `tests/skills/test_research_discovery_evidence.py` that writes a complete package under `tmp_path / "research/discovery"`. Use exact canonical files and bind SHA-256 digests:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from argus_skill.verticals.research_discovery.evidence import (
    completion_issue,
    validate_package,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_project(root: Path, *, decision: str = "recommended") -> Path:
    discovery = root / "research" / "discovery"
    discovery.mkdir(parents=True)
    (discovery / "BRIEF.md").write_text(
        "# Discovery brief\n\nFind a theory-application mechanism inside the stated budget.\n",
        encoding="utf-8",
    )
    bet_path = discovery / "bets" / "B1" / "BET.json"
    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    application_path = bet_path.with_name("APPLICATION_EVIDENCE.json")
    _write_json(bet_path, valid_bet())
    _write_json(theory_path, valid_theory_evidence())
    _write_json(application_path, valid_application_evidence())
    _write_json(discovery / "PORTFOLIO.json", valid_portfolio())
    bindings = [{
        "bet_id": "B1",
        "bet_revision": 1,
        "bet_sha256": _sha(bet_path),
        "theory_evidence_sha256": _sha(theory_path),
        "application_evidence_sha256": _sha(application_path),
    }]
    _write_json(discovery / "DECISION.json", valid_decision(decision, bindings))
    if decision == "recommended":
        _write_json(discovery / "HANDOFF.json", valid_handoff(bindings[0]))
    return root


def test_valid_recommended_package_passes(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    assert validate_package(root) == []
    assert completion_issue(root) == ""


def test_valid_no_bet_package_passes_without_handoff(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    assert not (root / "research/discovery/HANDOFF.json").exists()
    assert validate_package(root) == []
```

The helper payloads must include every required field from the approved spec; do not use empty placeholders.

- [ ] **Step 2: Run the happy-path tests and confirm the module is missing**

Run:

```bash
pytest -q tests/skills/test_research_discovery_evidence.py -k 'valid_recommended or valid_no_bet'
```

Expected: collection fails with `ModuleNotFoundError: argus_skill.verticals.research_discovery`.

- [ ] **Step 3: Add the evidence contracts, safe loaders, and package validator**

Implement these public constants and contracts in `evidence.py`:

```python
SCHEMA_VERSION = 1
BET_ID = re.compile(r"^[A-Za-z0-9_-]+$")
DECISIONS = frozenset({"recommended", "no_bet", "paused"})
CANDIDATE_STATES = frozenset({"probe", "park", "select", "kill"})
NEXT_VERTICALS = frozenset({"math", "research", "software"})

THEORY_FAILURES = BASE_FAILURE_CLASSES | frozenset({
    "theoretical", "prior_art", "scope_change",
})
THEORY_EVIDENCE = EvidenceContract(
    domain="research_discovery_theory",
    failure_classes=THEORY_FAILURES,
    non_idea_failures=BASE_NON_IDEA_FAILURES,
    grounding_fields=("premise", "method_identity", "witness_or_derivation"),
    refuting_failures=frozenset({"theoretical"}),
    advisory_failures=frozenset({"prior_art", "scope_change"}),
)

APPLICATION_FAILURES = BASE_FAILURE_CLASSES | frozenset({
    "data_access", "evaluator_infrastructure", "statistical_power",
    "empirical", "prior_art", "scope_change",
})
APPLICATION_EVIDENCE = EvidenceContract(
    domain="research_discovery_application",
    failure_classes=APPLICATION_FAILURES,
    non_idea_failures=BASE_NON_IDEA_FAILURES | frozenset({
        "data_access", "evaluator_infrastructure", "statistical_power",
    }),
    grounding_fields=("premise", "evaluator_identity", "comparison_identity"),
    refuting_failures=frozenset({"empirical"}),
    advisory_failures=frozenset({"prior_art", "scope_change"}),
)
```

Implement exact-path and validation helpers:

```python
def content_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_ref(root: Path, value: object, *, suffix: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != suffix:
        return None
    candidate = (root / relative).resolve()
    if root != candidate and root not in candidate.parents:
        return None
    return candidate if candidate.is_file() and not candidate.is_symlink() else None
```

`validate_package` must validate in stable order: brief, portfolio, each exact bet reference, both lane records, decision, digest freshness, and conditional handoff. Prefix detailed findings with their stable code, for example `invalid_bet:B1:bridge.dependency_claim is empty`.

`completion_issue` returns `""` for a valid `recommended` or `no_bet` package, otherwise returns `research_discovery:<first stable code>`.

Add a CLI with only `check --project-root`:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    errors = validate_package(args.project_root)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 2
    print("research discovery package: valid")
    return 0
```

Export the public evidence functions from `research_discovery/__init__.py` without importing `stages.py` yet.

- [ ] **Step 4: Run happy-path tests and make them pass**

Run:

```bash
pytest -q tests/skills/test_research_discovery_evidence.py -k 'valid_recommended or valid_no_bet'
```

Expected: both tests pass.

- [ ] **Step 5: Add failing invariant tests**

Add focused tests that mutate one valid package at a time:

```python
def test_stale_bet_digest_blocks_recommendation(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    bet = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(bet.read_text(encoding="utf-8"))
    payload["revision"] = 2
    _write_json(bet, payload)
    assert "stale_decision" in completion_issue(root)


def test_infrastructure_failure_cannot_refute_theory(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/THEORY_EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(execution_status="blocked", failure_class="dependency", idea_status="refuted")
    _write_json(path, payload)
    errors = validate_package(root)
    assert any("dependency" in error and "untested or inconclusive" in error for error in errors)


def test_prior_art_cannot_refute_application_premise(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/APPLICATION_EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(execution_status="completed", failure_class="prior_art", idea_status="refuted")
    _write_json(path, payload)
    assert any("prior_art" in error and "replanning" in error for error in validate_package(root))


def test_recommendation_rejects_decorative_bridge(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bridge"]["no_garnish_counterfactual"] = "Removing the theory changes nothing."
    payload["bridge"]["status"] = "weak"
    _write_json(path, payload)
    assert any("bridge" in error for error in validate_package(root))


def test_paused_decision_is_non_terminal(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="paused")
    assert completion_issue(root) == "research_discovery:terminal_paused"


def test_no_bet_rejects_stray_handoff(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    _write_json(root / "research/discovery/HANDOFF.json", valid_handoff({}))
    assert any("invalid_handoff" in error for error in validate_package(root))
```

Also cover invalid IDs, absolute/path-escaping refs, duplicate bet IDs, mismatched evidence revisions, unresolved novelty on a recommendation, unsupported lane status on a recommendation, multiple selected candidates, missing handoff, invalid next Vertical, and proxy evidence exceeding its declared ceiling.

- [ ] **Step 6: Run invariant tests and confirm they fail for the intended reasons**

Run:

```bash
pytest -q tests/skills/test_research_discovery_evidence.py
```

Expected: the newly added mutations fail because the validator does not yet enforce every invariant, not because fixture JSON is malformed.

- [ ] **Step 7: Complete the minimal invariant implementation**

Add stable validation helpers for required strings/lists/maps, bet schema, lane schema, decision eligibility, and digest bindings. For a recommendation require:

`DECISION.json.eligibility` is an ordered list with one row per referenced Bet:
`{"bet_id": str, "eligible": bool, "failed_gates": list[str]}`. `ordering` is an
ordinal list of unique Bet IDs and contains no score. Every Bet disposition is one
of `probe`, `park`, `select`, or `kill`; exactly the recommended Bet is `select`.

```python
if decision == "recommended":
    require(recommended_id in bets, "invalid_decision:recommended bet is not in portfolio")
    require(len(selected_ids) == 1, "invalid_decision:recommended requires exactly one selected bet")
    require(theory["execution_status"] == "completed" and theory["idea_status"] == "supported",
            "invalid_theory_evidence:recommended premise is not supported")
    require(application["execution_status"] == "completed" and application["idea_status"] == "supported",
            "invalid_application_evidence:recommended premise is not supported")
    require(bet["bridge"]["status"] == "supported",
            "invalid_bet:recommended bridge is not supported")
    require(bet["novelty"]["status"] != "unresolved",
            "invalid_bet:recommended novelty delta is unresolved")
```

For `no_bet`, require null recommendation, no handoff, and a non-empty grounded disposition for every referenced bet. For `paused`, return `terminal_paused` after structural validation.

- [ ] **Step 8: Run the validator tests and CLI smoke test**

Run:

```bash
pytest -q tests/skills/test_research_discovery_evidence.py
python -m argus_skill.verticals.research_discovery.evidence --help
```

Expected: all tests pass; help lists the `check` subcommand.

- [ ] **Step 9: Commit Task 1**

```bash
git add argus_skill/verticals/research_discovery/__init__.py \
  argus_skill/verticals/research_discovery/evidence.py \
  tests/skills/test_research_discovery_evidence.py
git commit -m "feat: validate research discovery decisions"
```

---

### Task 2: Add the Vertical contract, routing, and role Skills

**Files:**
- Create: `argus_skill/verticals/research_discovery/stages.py`
- Create: all ten role Skill files listed in the file map
- Modify: `argus_skill/verticals/research_discovery/__init__.py`
- Modify: `argus_skill/skills/vertical_select.py`
- Modify: `argus_skill/skills/builtins.py`
- Modify: `argus_skill/roles/prompts/manager.py`
- Create: `tests/skills/test_research_discovery_vertical.py`
- Modify: `tests/skills/test_builtins_seeding.py`
- Modify: `tests/manager/test_domain_author.py`

**Interfaces:**
- Consumes: Task 1 `evidence.completion_issue` and existing Vertical optional-hook API.
- Produces: `STAGE_ORDER`, `CHECKLIST_STAGE_ORDER`, `CHECKLIST_ITEMS`, `REVIEWER_CHECKLISTS`, `STAGE_CHECKS`, `PROTECTED_ITEM_IDS`, `WORKFLOW_MODE`, `REQUIRE_INDEPENDENT_REVIEW`, `COMPLETION_CONTRACT_VERSION`, `completion_gate`, `completion_issue`, and `role_banner`.
- Registers: `research_discovery` in `VERTICALS` and `VERTICAL_PURPOSES`.

- [ ] **Step 1: Write failing Vertical contract tests**

Create `tests/skills/test_research_discovery_vertical.py`:

```python
from pathlib import Path

from argus_skill.skills.builtins import iter_vertical_skill_texts
from argus_skill.skills.vertical_select import VERTICAL_PURPOSES, VERTICALS, persist_vertical
from argus_skill.verticals._base import (
    load_vertical,
    vertical_checklist_items,
    vertical_checklist_stage_order,
    vertical_completion_contract_version,
    vertical_completion_gate,
    vertical_requires_independent_review,
    vertical_role_banner,
    vertical_workflow_mode,
)


EXPECTED_SKILLS = {
    "manager/research-discovery-manager.md",
    "planner/research-discovery-planning.md",
    "engineer/idea-discovery.md",
    "engineer/idea-creator.md",
    "engineer/novelty-check.md",
    "engineer/theory-application-bridge.md",
    "engineer/dual-lane-probing.md",
    "reviewer/research-discovery-review.md",
    "scientist/research-discovery-distillation.md",
    "scientist/research-discovery-adaptation.md",
}


def test_research_discovery_vertical_contract() -> None:
    assert "research_discovery" in VERTICALS
    assert set(VERTICAL_PURPOSES) == set(VERTICALS)
    module = load_vertical("research_discovery")
    assert vertical_checklist_stage_order(module) == ("frame", "discover", "probe", "decide")
    assert vertical_workflow_mode(module) == "proportional"
    assert vertical_completion_gate(module) == "none"
    assert vertical_requires_independent_review(module) is True
    assert vertical_completion_contract_version(module) == 1


def test_research_discovery_final_protected_floor_is_exact() -> None:
    module = load_vertical("research_discovery")
    assert module.PROTECTED_ITEM_IDS == frozenset({
        "decide.package-valid",
        "decide.zero-or-one",
        "decide.dual-lane",
        "decide.handoff-valid",
        "decide.claim-ceiling",
    })
    declared = {item.id for items in vertical_checklist_items(module).values() for item in items}
    assert module.PROTECTED_ITEM_IDS <= declared


def test_research_discovery_roles_and_skills_are_complete() -> None:
    module = load_vertical("research_discovery")
    for role in ("manager", "planner", "engineer", "reviewer", "scientist_create", "scientist"):
        assert "discovery" in vertical_role_banner(module, role).lower()
    assert set(dict(iter_vertical_skill_texts("research_discovery"))) == EXPECTED_SKILLS


def test_research_discovery_persistence_seeds_frame(tmp_path: Path) -> None:
    persist_vertical(tmp_path, "research_discovery")
    assert (tmp_path / "research/PIPELINE_STATE.json").read_text(encoding="utf-8").find('"current_stage": "frame"') >= 0
```

- [ ] **Step 2: Run the Vertical tests and confirm registration/import failures**

Run:

```bash
pytest -q tests/skills/test_research_discovery_vertical.py
```

Expected: failures show the Vertical is unregistered and `stages.py`/Skills are missing.

- [ ] **Step 3: Implement `stages.py` and public exports**

Use this exact skeleton:

```python
STAGE_ORDER = ("frame", "discover", "probe", "decide")
CHECKLIST_STAGE_ORDER = STAGE_ORDER
WORKFLOW_MODE = "proportional"
REQUIRE_INDEPENDENT_REVIEW = True
completion_gate = "none"
COMPLETION_CONTRACT_VERSION = 1
PROTECTED_ITEM_IDS = frozenset({
    "decide.package-valid",
    "decide.zero-or-one",
    "decide.dual-lane",
    "decide.handoff-valid",
    "decide.claim-ceiling",
})


def completion_issue(project_root: object) -> str:
    from .evidence import completion_issue as validate_completion
    return validate_completion(project_root)
```

Each stage gets at least two `ChecklistItem`s. The `decide` stage declares all five protected IDs with evidence hints pointing to `DECISION.json`, lane files, and conditional `HANDOFF.json`. `STAGE_CHECKS` remains structural and only checks `research/PIPELINE_STATE.json`; scientific validity belongs to the Reviewer and completion hook.

`role_banner` maps the six Argus banner roles to the ten role Skill files. For Engineer, load `engineer/idea-discovery.md` as the always-on role contract; the remaining Engineer Skills stay matchable methods. Export all public hooks from `__init__.py`.

- [ ] **Step 4: Pressure-test and write Argus-native role Skills one at a time**

For each of the ten Skills, run a fresh-context scenario without that Skill and
record the concrete contract violation, then author only that Skill, rerun the
same scenario with it, and verify the required behavior before moving to the
next file. Store the scenarios and observed results in the SDD task report;
do not batch-create untested Skills.

Every Skill has exactly `name` and `description` frontmatter. Names use only
letters, numbers, and hyphens; descriptions begin with `Use when...` and state
triggering conditions rather than summarizing the procedure. Use these
non-negotiable bodies:

```markdown
---
name: research-discovery-manager
description: "Use when governing early theory-application direction search before a proof, full experiment, implementation, or publication task has been selected."
---

This Vertical ends with a decision-ready portfolio, not a proved theorem, validated product, or paper. Preserve zero-or-one recommendation semantics. Never switch Vertical or enqueue the handoff automatically.
```

```markdown
---
name: theory-application-bridge
description: "Use when a candidate direction claims that a precise theoretical mechanism changes a real application decision or prediction."
---

Require a problem anchor, theory anchor, explicit variable mapping, dependency claim, observable prediction, and no-garnish counterfactual. If removing the theory leaves the application design and prediction unchanged, mark the bridge weak and do not recommend the Bet.
```

```markdown
---
name: dual-lane-probing
description: "Use when a Research Bet needs separate minimum theory and application probes before it can be selected or rejected."
---

Record execution_status, failure_class, and idea_status independently in each lane. Infrastructure or access failure is not negative scientific evidence. Stop at the cheapest faithful discriminator; do not expand into a full proof, experiment, or production prototype.
```

The discovery-specific `idea-discovery`, `idea-creator`, and `novelty-check` files must be complete replacements, not pointer stubs. They must explicitly prohibit the common files' `IDEA_CANDIDATES.md`, scalar `rank_score`, `EXPERIMENT_PLAN.md`, forced winner, and “prior art means refuted” output contracts.

- [ ] **Step 5: Register the Vertical and routing purpose**

Add `research_discovery` adjacent to `research` and `math` in `VERTICALS`. Add this purpose:

```python
"research_discovery": (
    "early research-direction discovery that must connect a precise theoretical "
    "mechanism to a real application problem; produces an evidence-screened "
    "portfolio and zero or one recommended Research Bet, not a paper, proof, or implementation"
),
```

In both fast and grounded Manager prompts, add a routing boundary stating:

```text
Use research_discovery for finding and screening theory-application research directions. Use math when the requested outcome is a proof or counterexample, research when the requested outcome is a full empirical paper pipeline, and software when the method is already selected and the requested outcome is repository implementation.
```

Do not add keyword routing code.

- [ ] **Step 6: Add the explicit same-path Skill override allowlist**

In `argus_skill/skills/builtins.py`, declare:

```python
_VERTICAL_SKILL_OVERRIDES = {
    "research_discovery": frozenset({
        "engineer/idea-discovery.md",
        "engineer/idea-creator.md",
        "engineer/novelty-check.md",
    }),
}
```

Export a read-only helper for tests:

```python
def vertical_skill_overrides(vertical: str) -> frozenset[str]:
    return _VERTICAL_SKILL_OVERRIDES.get(vertical, frozenset())
```

Seeding already gives vertical files precedence; do not add a second copy path.

Update `test_vertical_owned_skills_are_not_also_flat_builtins` so overlap is legal only when it equals the explicit allowlist:

```python
for vertical in VERTICALS:
    vertical_names = {name for name, _ in iter_vertical_skill_texts(vertical)}
    assert vertical_names & flat == vertical_skill_overrides(vertical)
```

Add a seed test asserting the new vertical's `idea-creator.md` contains `zero or one` and does not contain `rank_score` or an instruction to write `EXPERIMENT_PLAN.md`.

- [ ] **Step 7: Add routing and domain-boundary tests**

In `tests/manager/test_domain_author.py`, add:

```python
def test_vertical_prompt_distinguishes_research_discovery_neighbors() -> None:
    prompt = build_vertical_decision_prompt(
        "Find research ideas that connect a theoretical mechanism to an application problem",
        verticals_with_purpose=VERTICAL_PURPOSES,
        domains_with_purpose=DOMAIN_PURPOSES,
    )
    assert "research_discovery" in prompt
    assert "finding and screening theory-application research directions" in prompt
    assert "Use math" in prompt
    assert "Use research" in prompt
    assert "Use software" in prompt


def test_parser_rejects_domain_on_research_discovery() -> None:
    decision = parse_vertical_decision(
        json.dumps({
            "choice": "existing",
            "vertical": "research_discovery",
            "domain": "chemistry",
            "workflow_mode": "staged",
            "execution_task": "find a chemistry research bet",
        }),
        known_verticals=VERTICALS,
        known_domains=BUILTIN_DOMAINS,
        default_execution_task="find a chemistry research bet",
    )
    assert decision is None
```

- [ ] **Step 8: Run focused Vertical, Skill, routing, and global guards**

Run:

```bash
pytest -q \
  tests/skills/test_research_discovery_vertical.py \
  tests/skills/test_builtins_seeding.py \
  tests/manager/test_domain_author.py \
  tests/skills/test_final_stage_gate.py \
  tests/skills/test_stage_checks_no_content_scanners.py
```

Expected: all pass, including exact Vertical-purpose alignment and protected-floor checks.

- [ ] **Step 9: Commit Task 2**

```bash
git add argus_skill/verticals/research_discovery \
  argus_skill/skills/vertical_select.py \
  argus_skill/skills/builtins.py \
  argus_skill/roles/prompts/manager.py \
  tests/skills/test_research_discovery_vertical.py \
  tests/skills/test_builtins_seeding.py \
  tests/manager/test_domain_author.py
git commit -m "feat: add research discovery vertical"
```

---

### Task 3: Enforce the active Vertical completion hook fail-closed

**Files:**
- Create: `argus_skill/core/completion_gate.py`
- Modify: `argus_skill/verticals/_base.py`
- Modify: `argus_skill/manager/_stage_ops.py`
- Modify: `argus_skill/skills/stage_machine.py`
- Create: `tests/core/test_completion_gate.py`
- Modify: `tests/manager/test_stage_decider.py`

**Interfaces:**
- Consumes: Task 2 active Vertical `completion_issue(project_root)` hook.
- Produces: `vertical_completion_issue(mod, project_root) -> str` and `project_completion_issue(project_root) -> str`.
- Guarantees: missing hooks preserve existing behavior; a declared hook exception fails closed; external completion issues retain precedence; final-stage disk mutation rechecks the combined issue.

- [ ] **Step 1: Write failing optional-hook and combined-gate tests**

Create `tests/core/test_completion_gate.py`:

```python
from types import SimpleNamespace

from argus_skill.core.completion_gate import project_completion_issue
from argus_skill.verticals._base import vertical_completion_issue


def test_missing_vertical_completion_hook_is_satisfied(tmp_path) -> None:
    assert vertical_completion_issue(SimpleNamespace(), tmp_path) == ""


def test_vertical_completion_hook_result_is_returned(tmp_path) -> None:
    module = SimpleNamespace(completion_issue=lambda root: "research_discovery:invalid_decision")
    assert vertical_completion_issue(module, tmp_path) == "research_discovery:invalid_decision"


def test_vertical_completion_hook_exception_fails_closed(tmp_path) -> None:
    def broken(_root):
        raise RuntimeError("boom")
    issue = vertical_completion_issue(SimpleNamespace(completion_issue=broken), tmp_path)
    assert issue == "vertical completion check unavailable: RuntimeError"


def test_external_gate_has_precedence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_SKILL_EXTERNAL_COMPLETION_GATE", "controller.json:satisfied")
    assert "external completion gate is missing" in project_completion_issue(tmp_path)
```

Add an integration test that persists `research_discovery`, writes an invalid package, monkeypatches the current stage to `decide`, and verifies `complete_final_stage` raises `ValueError` containing `research_discovery:invalid_` without writing `stages.decide.status=done`.

- [ ] **Step 2: Run completion tests and confirm missing interfaces**

Run:

```bash
pytest -q tests/core/test_completion_gate.py
```

Expected: import failures for `completion_gate` and `vertical_completion_issue`.

- [ ] **Step 3: Implement the fail-closed accessor and combined resolver**

In `argus_skill/verticals/_base.py`:

```python
def vertical_completion_issue(mod: VerticalDefinition, project_root: object) -> str:
    fn = getattr(mod, "completion_issue", None)
    if not callable(fn):
        return ""
    try:
        result = fn(project_root)
    except Exception as exc:  # completion must fail closed
        return f"vertical completion check unavailable: {type(exc).__name__}"
    return result.strip() if isinstance(result, str) else "vertical completion check returned invalid result"
```

In new `argus_skill/core/completion_gate.py`:

```python
def project_completion_issue(project_root: Path | str) -> str:
    external = external_completion_gate_issue(project_root)
    if external:
        return external
    try:
        vertical = resolve_vertical(project_root)
        module = load_vertical(vertical, project_root=project_root)
    except Exception as exc:
        return f"vertical completion check unavailable: {type(exc).__name__}"
    return vertical_completion_issue(module, project_root)
```

Export both functions in their module `__all__` lists.

- [ ] **Step 4: Replace the two Manager completion blocker calls**

In both branches of `_StageDecisionMixin._finalize_stage_decision`, replace only:

```python
completion_blocker=external_completion_gate_issue(root)
```

with:

```python
from ..core.completion_gate import project_completion_issue

completion_blocker=project_completion_issue(root)
```

Keep external rework and stage-ceiling functions unchanged; a Vertical issue holds at the final stage rather than inventing a rollback target.

- [ ] **Step 5: Recheck immediately before final-stage mutation**

In `complete_final_stage`, after resolving the active module and before computing/storing the completion fingerprint:

```python
from ..core.completion_gate import project_completion_issue

issue = project_completion_issue(project_root)
if issue:
    raise ValueError(issue)
```

This must happen before `_set_stage` so invalid packages cannot receive a `done` stamp.

- [ ] **Step 6: Add Manager completion-blocker coverage**

Extend `tests/manager/test_stage_decider.py` with a direct blocker test:

```python
def test_vertical_completion_blocker_prevents_final_complete() -> None:
    decision = final_stage_completion_decision(
        _review(),
        current_stage="decide",
        stage_order=("frame", "discover", "probe", "decide"),
        vertical="research_discovery",
        completion_blocker="research_discovery:invalid_decision",
    )
    assert decision is None
```

- [ ] **Step 7: Run focused completion and regression tests**

Run:

```bash
pytest -q \
  tests/core/test_completion_gate.py \
  tests/core/test_external_completion_gate.py \
  tests/manager/test_stage_decider.py \
  tests/skills/test_research_discovery_evidence.py \
  tests/skills/test_research_discovery_vertical.py
```

Expected: all pass.

- [ ] **Step 8: Commit Task 3**

```bash
git add argus_skill/core/completion_gate.py \
  argus_skill/verticals/_base.py \
  argus_skill/manager/_stage_ops.py \
  argus_skill/skills/stage_machine.py \
  tests/core/test_completion_gate.py \
  tests/manager/test_stage_decider.py
git commit -m "feat: enforce vertical completion checks"
```

---

### Task 4: Document, integrate, and verify the complete feature

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `tests/skills/test_verticals.py` only if the dedicated tests do not already cover persisted evidence mode.
- Verify: every production and test file from Tasks 1–3.

**Interfaces:**
- Consumes: complete registered Vertical and validator.
- Produces: user-facing usage guidance and clean full-suite verification.

- [ ] **Step 1: Add concise English and Chinese documentation**

After “Build your own Vertical” / “创建自己的 Vertical”, add a built-in example that states:

```markdown
#### Built-in Research Discovery

`research_discovery` is for early research-direction search where a theoretical mechanism and a real application problem must both matter. It progresses through `frame → discover → probe → decide` and finishes with a ranked portfolio plus either one evidence-bound Research Bet or a grounded `no_bet` result. Completion does not mean the theorem is proved, the application works in production, or a paper is ready; the optional handoff names the next bounded `math`, `research`, or `software` task.
```

Add the equivalent Chinese paragraph, preserving the same completion ceiling.

- [ ] **Step 2: Run the focused feature suite**

Run:

```bash
pytest -q \
  tests/skills/test_research_discovery_evidence.py \
  tests/skills/test_research_discovery_vertical.py \
  tests/core/test_completion_gate.py \
  tests/skills/test_builtins_seeding.py \
  tests/manager/test_domain_author.py \
  tests/manager/test_stage_decider.py \
  tests/skills/test_final_stage_gate.py \
  tests/skills/test_stage_checks_no_content_scanners.py
```

Expected: all pass.

- [ ] **Step 3: Run adjacent Vertical, lifecycle, and completion regressions**

Run:

```bash
pytest -q \
  tests/skills/test_math_vertical.py \
  tests/skills/test_verticals.py \
  tests/life/test_goal_gate_completion_livelock.py \
  tests/life/test_planner_terminal_empty_output.py \
  tests/test_reviewer_completion_contract.py
```

Expected: all pass, including parameterized coverage over every registered Vertical.

- [ ] **Step 4: Run the complete test suite and compare with the recorded baseline**

Run:

```bash
pytest -q
```

Expected: the focused and adjacent suites are green and the full run introduces
no failures beyond the 23 recorded macOS environment/platform baseline failures.
Do not modify unrelated production code merely to make those baseline tests pass.

- [ ] **Step 5: Run static repository hygiene checks**

Run:

```bash
git diff --check
python -m argus_skill.verticals.research_discovery.evidence --help
git status --short
```

Expected: no whitespace errors; CLI help succeeds; status shows only intended feature files before the documentation commit.

- [ ] **Step 6: Commit Task 4**

```bash
git add README.md README.zh-CN.md
git commit -m "docs: explain research discovery workflow"
```

- [ ] **Step 7: Review the final branch delta**

Run:

```bash
git log --oneline main..HEAD
git diff --stat main...HEAD
git status --short
```

Expected: the branch contains the approved design, this implementation plan, validator, Vertical, role Skills, completion hook, focused tests, and docs; the worktree is clean.
