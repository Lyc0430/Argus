# Research Discovery Gate Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every terminal `no_bet` rejection machine-bound to the current Bet and prevent mixed pre-probe/probe gate rows from hiding blocked finalist probes.

**Architecture:** Add an exact four-row `BET.json.pre_probe_gates` assessment whose status and rationale are covered by the existing Bet digest. Validate decision bases as mutually exclusive shapes: eligible and completed-probe candidates require all pre-probe gates to pass, while pre-probe rejection must equal the Bet's exact failed pre-probe set. Preserve the existing lane evidence, completion-hook, stable error-family, and empty-portfolio contracts.

**Tech Stack:** Python 3.11+, pytest, Argus role Skill Markdown, canonical release builder, Git.

## Global Constraints

- The approved addendum is `docs/superpowers/specs/2026-08-08-research-discovery-gate-grounding-design.md` and governs exact field names and relationships.
- `pre_probe_gates` has exactly `application_anchor`, `theory_anchor`, `bridge`, and `nearest_work`; each row has `status: pass | fail` and a non-placeholder `rationale`.
- A `pre_probe_gate` decision contains only pre-probe identifiers and its `failed_gates` equals exactly the current Bet rows marked `fail`.
- `eligible` and `completed_probe` require every current Bet pre-probe gate to pass. `completed_probe` contains only `theory_probe | application_probe` and retains the existing dual-lane scientific grounding rules.
- `blocked_probe` remains nonterminal and can never complete as `no_bet`.
- `bridge` and `nearest_work` gate results must be coherent with current structured Bet fields as specified by the addendum.
- Infrastructure, access, dependency, toolchain, evaluator, statistical-power, implementation, resource, or authority failure remains non-idea evidence.
- Preserve the grounded empty-portfolio `no_bet`, zero-or-one selection, exact premise bindings, safe canonical paths, narrative/structured evidence-level split, and optional handoff semantics.
- Do not repair or change the accepted 23 same-machine environment/platform full-suite failures.

---

### Task 1: Bind terminal eligibility gates to the current Bet

**Files:**
- Modify: `argus_skill/verticals/research_discovery/evidence.py`
- Modify: `argus_skill/verticals/research_discovery/skills/engineer/idea-creator.md`
- Modify: `argus_skill/verticals/research_discovery/skills/engineer/idea-discovery.md`
- Modify: `argus_skill/verticals/research_discovery/skills/reviewer/research-discovery-review.md`
- Modify only if the fresh Skill test proves necessary: `argus_skill/verticals/research_discovery/skills/manager/research-discovery-manager.md`
- Modify: `docs/superpowers/specs/2026-08-08-research-discovery-vertical-design.md`
- Test: `tests/skills/test_research_discovery_evidence.py`
- Test only if needed for behavior, not source-text checks: `tests/skills/test_research_discovery_vertical.py`

**Interfaces:**
- Consumes: existing `BET.json`, `DECISION.json.eligibility`, `_validate_bet`, `_validate_decision`, `_completed_probe_basis_issue`, `premise_digest`, and digest freshness helpers.
- Produces: an exact validated `BET.json.pre_probe_gates` mapping and mutually exclusive, current-Bet-grounded decision-basis validation under existing stable error families.
- Preserves: public `validate_package`, `completion_issue`, `content_digest`, `premise_digest`, `THEORY_EVIDENCE`, and `APPLICATION_EVIDENCE` signatures.

- [ ] **Step 1: Run a fresh Skill baseline before editing any role Skill**

Use a fresh-context subagent without the amended role Skill text. Give it a Bet whose `novelty.status` is `distinct_on_searched_axis`, whose theory probe is blocked by a dependency, and pressure to finish within an exhausted budget. Ask for exact `BET.json` gate fields and the `DECISION.json` eligibility row. Record whether it omits current-Bet gate results, mixes `nearest_work` with `theory_probe`, or incorrectly emits terminal `no_bet`.

- [ ] **Step 2: Write behavioral failing tests**

Add fixtures with a hand-written canonical `pre_probe_gates` mapping:

```python
def valid_pre_probe_gates(*, failed: str | None = None) -> dict:
    rationales = {
        "application_anchor": "The real decision and baseline are concrete.",
        "theory_anchor": "The binding theory premise is precise enough to probe.",
        "bridge": "The supported bridge changes the application decision.",
        "nearest_work": "The searched delta remains distinct on its stated axis.",
    }
    return {
        gate: {
            "status": "fail" if gate == failed else "pass",
            "rationale": rationales[gate],
        }
        for gate in (
            "application_anchor",
            "theory_anchor",
            "bridge",
            "nearest_work",
        )
    }
```

Write tests that prove these exact breaks. Use the real package writer and
literal expected error fragments; for example:

```python
def test_pre_probe_basis_cannot_mix_probe_gate_to_hide_blocked_lane(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["novelty"]["status"] = "overlap"
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="nearest_work")
    _write_json(bet_path, bet)

    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        decision_basis="pre_probe_gate",
        failed_gates=["nearest_work", "theory_probe"],
    )
    _write_json(decision_path, decision)

    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory.update(
        execution_status="blocked",
        failure_class="dependency",
        idea_status="untested",
    )
    _write_json(theory_path, theory)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "cannot mix" in error
        for error in validate_package(root)
    )


def test_pre_probe_failed_gates_must_equal_current_bet_failures(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["novelty"]["status"] = "overlap"
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="nearest_work")
    _write_json(bet_path, bet)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0]["failed_gates"] = ["bridge"]
    _write_json(decision_path, decision)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "current Bet" in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize(
    ("mutation", "error_fragment"),
    [
        ({"nearest_work": {"status": "fail", "rationale": "Distinct work."}}, "nearest_work"),
        ({"bridge": {"status": "fail", "rationale": "Bridge failed."}}, "bridge"),
        ({"application_anchor": {"status": "maybe", "rationale": "Unknown."}}, "status"),
        ({"theory_anchor": {"status": "pass", "rationale": "REPLACE"}}, "rationale"),
    ],
)
def test_pre_probe_gate_rows_are_current_and_well_formed(
    tmp_path: Path,
    mutation: dict,
    error_fragment: str,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["pre_probe_gates"] = valid_pre_probe_gates()
    bet["pre_probe_gates"].update(mutation)
    _write_json(bet_path, bet)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_bet:B1:") and error_fragment in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize("decision", ["recommended", "no_bet"])
def test_eligible_or_completed_probe_requires_all_pre_probe_gates_to_pass(
    tmp_path: Path,
    decision: str,
) -> None:
    root = _valid_project(tmp_path, decision=decision)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["bridge"]["status"] = "broken"
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="bridge")
    _write_json(bet_path, bet)
    decision_path = root / "research/discovery/DECISION.json"
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision == "no_bet":
        payload["eligibility"][0].update(
            decision_basis="completed_probe",
            failed_gates=["theory_probe"],
        )
    _write_json(decision_path, payload)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "pre-probe gates" in error
        for error in validate_package(root)
    )
```

The first test must reproduce the independently confirmed exploit: decision
`pre_probe_gate`, `failed_gates=["nearest_work", "theory_probe"]`, a dependency-
blocked theory lane, current decision digests, and prior validator result `[]`.

- [ ] **Step 3: Run RED and verify the expected failures**

Run:

```bash
.venv/bin/pytest -q \
  tests/skills/test_research_discovery_evidence.py \
  -k 'pre_probe or completed_probe_requires_all or recommendation_requires_all or bridge_gate_result or distinct_nearest_work'
```

Expected: the new tests fail because `pre_probe_gates` is not validated, mixed categories pass, and decisions are not compared with current Bet gate results. Existing passing tests in the selection may stay green.

- [ ] **Step 4: Implement the minimal Bet gate validator**

In `evidence.py`, add exact constants and focused helpers:

```python
PRE_PROBE_GATE_ORDER = (
    "application_anchor",
    "theory_anchor",
    "bridge",
    "nearest_work",
)
PRE_PROBE_GATES = frozenset(PRE_PROBE_GATE_ORDER)

def _pre_probe_gate_statuses(
    bet: Mapping[str, Any], errors: list[str] | None = None
) -> dict[str, str] | None:
    findings = errors if errors is not None else []
    gates = _mapping(bet.get("pre_probe_gates"))
    if gates is None or set(gates) != PRE_PROBE_GATES:
        findings.append("pre_probe_gates must contain exactly the four required gates")
        return None
    statuses: dict[str, str] = {}
    for gate in PRE_PROBE_GATE_ORDER:
        row = _mapping(gates.get(gate))
        if row is None or row.get("status") not in {"pass", "fail"}:
            findings.append(f"pre_probe_gates.{gate}.status must be pass or fail")
            continue
        if not _text(row.get("rationale")):
            findings.append(f"pre_probe_gates.{gate}.rationale is empty")
            continue
        statuses[gate] = str(row["status"])
    return statuses if len(statuses) == len(PRE_PROBE_GATE_ORDER) else None

def _failed_pre_probe_gates(bet: Mapping[str, Any]) -> frozenset[str] | None:
    statuses = _pre_probe_gate_statuses(bet)
    if statuses is None:
        return None
    return frozenset(gate for gate, status in statuses.items() if status == "fail")
```

The helper requires an object with exactly the four keys. Each row is an object
with exact or minimally sufficient `status` and `rationale` fields; status is
`pass | fail`, and rationale is non-placeholder. Add `_validate_bet` findings
under `invalid_bet` when malformed.

Enforce structured consistency:

```python
bridge_gate = statuses["bridge"]
bridge_status = bridge.get("status")
# pass iff supported; fail iff weak or broken; untested cannot certify a terminal package

nearest_gate = statuses["nearest_work"]
novelty_status = novelty.get("status")
# distinct_on_searched_axis requires pass
# unresolved requires fail
# overlap may pass or fail because the current explicit delta may or may not survive
```

- [ ] **Step 5: Make decision bases mutually exclusive and Bet-bound**

In `_validate_decision`:

```python
current_failed = _failed_pre_probe_gates(bets[bet_id])
gate_set = set(gates)
if basis == "eligible" and current_failed:
    errors.append(f"eligibility {bet_id} eligible requires all pre-probe gates to pass")
elif basis == "pre_probe_gate":
    if not gate_set or not gate_set <= PRE_PROBE_GATES:
        errors.append(f"eligibility {bet_id} pre_probe_gate cannot mix probe gates")
    elif current_failed is None or gate_set != set(current_failed):
        errors.append(f"eligibility {bet_id} failed_gates do not match the current Bet")
elif basis == "completed_probe":
    if not gate_set or not gate_set <= PROBE_GATES:
        errors.append(f"eligibility {bet_id} completed_probe accepts only probe gates")
    if current_failed:
        errors.append(f"eligibility {bet_id} completed_probe requires all pre-probe gates to pass")
    issue = _completed_probe_basis_issue(row, records.get(bet_id))
    if issue:
        errors.append(f"eligibility {bet_id} {issue}")
```

Keep `blocked_probe` validation and the explicit `no_bet` rejection. Do not
permit a mixed pre-probe/probe list to pass through any terminal basis. Treat a
missing/malformed gate map as already invalid Bet data and also prevent it from
grounding a decision.

Update fixtures so:

- valid recommendation has all four gates passing;
- valid pre-probe `no_bet` uses a current Bet with
  `novelty.status=overlap`, `nearest_work.status=fail`, and exact
  `failed_gates=["nearest_work"]`;
- completed scientific-refutation `no_bet` has all pre-probe gates passing;
- empty portfolio remains unchanged.

- [ ] **Step 6: Run GREEN and the complete evidence suite**

Run:

```bash
.venv/bin/pytest -q tests/skills/test_research_discovery_evidence.py
```

Expected: 100% pass with no unexpected warnings.

- [ ] **Step 7: Amend only the role Skills needed to shape the canonical output**

Use the baseline failure to add the minimal positive recipe: every Bet writes
the four `pre_probe_gates` rows; pre-probe `failed_gates` copies the exact failed
set; eligible/completed-probe rows require all four pass; gate categories never
mix. Preserve existing frontmatter and keep each Skill concise.

Run the same fresh-context scenario with the amended Skill text and require the
canonical gate map plus a nonterminal `blocked_probe`/`paused` decision for the
blocked finalist. Do not accept a prose-only answer as GREEN.

- [ ] **Step 8: Align the primary design and run focused/adjacent checks**

Add the exact `pre_probe_gates` schema and invariants to
`docs/superpowers/specs/2026-08-08-research-discovery-vertical-design.md`.

Run:

```bash
.venv/bin/pytest -q \
  tests/skills/test_research_discovery_evidence.py \
  tests/skills/test_research_discovery_vertical.py \
  tests/core/test_completion_gate.py \
  tests/manager/test_domain_author.py \
  tests/manager/test_stage_decider.py \
  tests/skills/test_builtins_seeding.py
```

Then run the adjacent group recorded in the existing implementation plan:

```bash
.venv/bin/pytest -q \
  tests/skills/test_math_vertical.py \
  tests/skills/test_verticals.py \
  tests/life/test_goal_gate_completion_livelock.py \
  tests/life/test_planner_terminal_empty_output.py \
  tests/test_reviewer_completion_contract.py
```

- [ ] **Step 9: Run static, release, and differential verification**

Run Ruff on changed Python/tests, compileall, validator CLI help, a generated
valid-package CLI check, and `git diff --check`. Then run the canonical release
builder:

```bash
.venv/bin/python -m argus_skill.release_tools.build_release
```

Run the nine release/deployment tests:

```bash
.venv/bin/pytest -q \
  tests/core/test_release.py \
  tests/deployment/test_multi_process_contract.py
```

Run exactly one final feature-branch full suite:

```bash
.venv/bin/pytest -q
```

Compare its named failures with `/tmp/argus-task4-full-post-release.txt`.
Acceptance is exactly the same 23 named environment/platform failures, with no
added or missing names.

- [ ] **Step 10: Self-review, report, and commit**

Review the mutation cases: remove exact-key validation, allow a mixed gate,
change a current Bet gate result after decision binding, or let a failed
pre-probe Bet use `completed_probe`; a behavioral test must fail for each.

Write the SDD report with RED/GREEN, Skill baseline/GREEN, release identity,
and full-suite differential evidence. Commit tracked source, tests, design,
Skills, and regenerated release artifacts with:

```bash
git commit -m "fix: ground research discovery eligibility gates"
```
