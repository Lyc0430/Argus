# Dynamic Memory Research Program and Pre-Gate GPU Validation

**Status:** proposed for written review

**Date:** 2026-08-08

**Scope:** Research Discovery orchestration, project isolation, and bounded GPU evaluation before K0/K3

## 1. Decision

Argus will treat memory research as one dynamic Research Program containing any
number of independent Seed Projects. The initial program contains:

1. the existing Causal Memory / Memory as Control project;
2. an Emotion-Conditioned Memory Policy Learning project; and
3. an Affect-Preserving Memory Compression project.

The number of projects is not fixed. A future research direction receives a new
Seed Project when it has a distinct problem anchor, primary endpoint, evidence
contract, or compute gate. Research Bets remain project-local. Cross-project
reuse happens through typed experience references, never by copying a result or
treating one project's failure as another project's scientific evidence.

K0 and K3 prohibit training before the pilot gates pass. They do not prohibit
bounded GPU inference needed to measure the gates. Research Discovery must
therefore distinguish:

- **validation compute:** allowed before K0/K3 when a reviewed executable
  harness requires model inference;
- **training compute:** forbidden before K0 and K3 both pass; and
- **scale-up compute:** 144/2400 expansion, latent intervention, critic work,
  LoRA, PPO/GRPO, or broad hyperparameter search, also forbidden before both
  gates pass.

## 2. Alternatives Considered

### A. One project containing every memory direction

This minimizes orchestration work but mixes problem anchors, reward semantics,
test splits, and failure meanings. A successful compression probe could be
mistaken for evidence about an RL policy. Rejected.

### B. Fully independent projects without a program layer

This preserves scientific isolation but loses explicit shared budgets,
cross-project experience provenance, and a place to add future directions.
Useful as an implementation fallback, but not the target design.

### C. Dynamic program with independent Seed Projects

Recommended and approved. Projects keep separate stages, Bets, evidence,
datasets, budgets, and decisions. A lightweight program registry coordinates
membership, typed experience references, and compute admission without owning
scientific conclusions.

## 3. Program and Project Boundaries

The program registry is coordination metadata. It records:

- program id and initialization statement;
- project ids, titles, state, and problem anchors;
- project-local budget references;
- allowed typed experience edges;
- aggregate concurrency ceilings; and
- no scientific status stronger than the referenced project artifacts.

Each Seed Project continues to own its canonical:

```text
research/PIPELINE_STATE.json
research/discovery/BRIEF.md
research/discovery/PORTFOLIO.json
research/discovery/bets/<bet_id>/...
research/discovery/DECISION.json
research/discovery/AUTO_EXPANSION.json
```

The initial project contracts are:

| Project | Primary question | Pre-training gate |
|---|---|---|
| Causal Memory Control | Does a memory intervention change structured action, and is the change valuable? | K0 signal non-degeneracy and K3 oracle headroom |
| Emotion-Conditioned Memory Policy Learning | Can a policy learn when to write, retrieve, update, or forget emotion-tagged memory without reward hacking or harmful affect loops? | stable labels, reward audit, offline oracle headroom, safety ceiling |
| Affect-Preserving Memory Compression | Under an equal token budget, which affective and causal details must survive compression to preserve safe downstream action? | decision-utility headroom over ordinary summaries and safety-field retention |

## 4. Cross-Project Experience Contract

An experience edge may transfer only:

- a source artifact reference;
- source problem and assumptions;
- killed premise and surviving observations;
- forbidden transfer region;
- proposed target-role mapping;
- negative-transfer boundary; and
- a target-project discriminator.

It may not transfer:

- a scientific status;
- an eligibility result;
- a test split;
- a reward calibration;
- a K0/K3 verdict; or
- a model result without target-project verification.

Execution failures schedule bounded repair only. Scientific or novelty failure
preserves live siblings and creates one near and one far branch when the
project-local expansion policy permits it.

## 5. Causal-Memory Data Gate

The current self-authored scenario sketches are proxy design artifacts, not K0
or K3 data. Before GPU validation, the project must produce 12 executable gold
scenarios: two each for Helpful-tool, Helpful-argument, Irrelevant,
Stale/conflicting, Authority mismatch, and Verify-required.

Each gold scenario must contain:

- a deterministic, restorable environment snapshot;
- a fixed observation, tool schema, and trajectory prefix;
- natural memory-present and counterfactual-twin conditions;
- matched placebo and no-memory conditions;
- legal USE, IGNORE, and VERIFY action classes;
- forced first-action branches;
- programmatic reward vectors and a preregistered ordering rule;
- shortcut and executability checks; and
- reviewer-independent gold fields.

The readiness certificate requires 100% twin executability, deterministic
snapshot replay, valid action serialization, no result labels derived from the
evaluated model, and no unresolved evaluator ambiguity. Failing readiness does
not say the Idea is false and cannot authorize GPU work.

## 6. Pre-K0/K3 GPU Evaluation

Once the readiness certificate is independently approved, the Planner may
create a version-1 `ComputeRequest` with:

```text
task_kind: evaluation
evidence_class: frozen
provider_hint: auto
requires_model_revision_pin: true
requires_replay: true
requires_crn: true
requires_main_table: true
requires_full_vocab_logits: true when canonical action probabilities require it
requires_critic_training: false
requires_custom_cuda: false
```

These requirements route the formal K0/K3 pilot to Katana. The request is an
evaluation request, never a training request. It freezes the 12-scenario
manifest, model snapshot, candidate-action serializer, sampling configuration,
branch policy, seeds, and evaluator.

The pilot executes:

- two preregistered open-weight model families;
- memory, counterfactual twin, placebo, and no-memory arms;
- USE, IGNORE, and VERIFY action scoring;
- H=1 for every eligible pivot;
- a preregistered subset at H=3;
- common random numbers where environment stochasticity permits; and
- immutable per-arm outputs plus failure records.

GPU or provider failure is `blocked` or `inconclusive`, never a null scientific
result. Outputs become evidence only after `verify-compute-run` accepts the
manifest and an independent Research Reviewer checks the readable scientific
contract.

## 7. Parallel GPU Budgets

GPU budgets are project-local and may run in parallel. Parallelism is admitted
only when every job has a distinct project budget reservation and a distinct
compute lease or scheduler allocation.

The program maintains both:

- **project budgets:** reserved GPU-hours, provider spend, retry allowance, and
  evidence purpose for each Seed Project; and
- **global ceilings:** maximum aggregate spend, maximum active jobs, and
  protected reserve across the program.

Default pilot policy:

- each project receives its own bounded evaluation allocation;
- projects may submit concurrently;
- a project cannot borrow another project's unused allocation automatically;
- retries consume the same project's repair allowance;
- training allocation remains zero until that project's gates pass; and
- future projects can be added without changing existing budgets or evidence.

For Katana, PBS owns placement and jobs do not pin a queue or GPU model. Each
job records the actual GPU name and UUID. Conditions whose numerical comparison
depends on identical hardware must run within one isolated comparison block or
be stratified by recorded architecture. Independent projects may run on
different GPU architectures because their results are not compared directly.

For Tinker, reservations remain project-scoped while the existing global
protected reserve and reconciliation threshold continue to apply. Tinker is
not eligible for frozen K0/K3 evidence.

## 8. K0 and K3 Decisions

K0 asks whether memory produces a non-degenerate structured-action signal. It
must compare paired treatment effects with placebo variation and report
clustered uncertainty. Model self-description, rationale changes, or
self-authored labels are not K0 evidence.

K3 asks whether an oracle USE/IGNORE/VERIFY policy has material headroom over
the best non-oracle baseline at the same memory budget. It uses the forced
branches and programmatic reward contract, not a language-model judge.

Only `K0=pass` and `K3=pass` together may authorize:

- expansion to 144 pivots;
- controller or critic training;
- LoRA, PPO, GRPO, or other policy optimization;
- latent-interface work; or
- larger project-specific GPU budgets.

The authorization is project-local. Passing gates in Causal Memory Control does
not authorize training in the two emotion-memory projects.

## 9. Stage Behavior

During `discover`, a Bet may preregister the cheapest faithful GPU-dependent
evaluation but cannot submit it.

During `probe`, after the executable-harness readiness certificate passes, the
Planner may route and submit bounded evaluation compute within the project's
preauthorized budget. A completed job does not advance the stage until compute
verification and independent scientific review both accept it.

During `decide`, a missing, rejected, stale, or failed required compute result
causes `paused` and rollback to `probe`. It never becomes `no_bet` merely because
GPU access failed or the budget was exhausted.

## 10. Reviewer Requirements

The Reviewer must reject:

- scenarios and supporting labels created by the same actor in one pass when
  those labels are presented as empirical support;
- `completed/supported` evidence with no actual model or environment outputs;
- a GPU exit code used as scientific evidence;
- a K0/K3 verdict without accepted compute provenance;
- cross-project result transfer without target-project validation;
- parallel jobs that share an unisolated comparison resource; and
- any pre-gate training or scale-up request.

The Reviewer may accept self-authored scenarios only as design/proxy artifacts,
with `idea_status=untested` or `inconclusive` until independent execution.

## 11. Failure and Recovery

The system distinguishes:

1. **design defect:** repair the harness or evaluator, then re-review readiness;
2. **execution defect:** bounded retry under the same immutable request;
3. **information-free result:** redesign the discriminator once;
4. **scientific or novelty failure:** retain siblings and derive one near and
   one mapped far branch; and
5. **valid null with no oracle headroom:** stop training for that project while
   leaving the Research Program and other projects active.

No individual project failure completes the program.

## 12. Acceptance Criteria

The implementation is acceptable when:

- multiple Seed Projects can be grouped without sharing scientific state;
- per-project GPU reservations can coexist and run concurrently under a global
  ceiling;
- Research Discovery explicitly permits bounded evaluation but forbids
  pre-gate training and scale-up;
- a reviewed readiness artifact is required before a ComputeRequest;
- K0/K3 evidence requires accepted Katana provenance;
- self-generated labels cannot satisfy empirical lane support;
- failed compute remains non-scientific;
- current project behavior migrates from unrun proxy-only probes toward an
  executable 12-scenario evaluation; and
- no compute is submitted merely by installing or upgrading the design.

## 13. Rollout

Implementation is deliberately split into three independently reviewable
increments:

### Increment A: validation-compute boundary

1. Amend Research Discovery Manager, Planner, Engineer, and Reviewer Skills.
2. Add a project-local readiness and compute-binding contract to canonical
   probe evidence.
3. Extend automatic expansion so a ready blocked probe requests evaluation
   compute instead of repeatedly redesigning static metadata.
4. Migrate the current causal-memory project without upgrading its proxy
   evidence; it remains paused until real evaluation is accepted.

### Increment B: dynamic program and parallel budgets

1. Add the lightweight program registry and typed project membership.
2. Add per-project compute budget references and parallel admission under the
   global ceiling.
3. Preserve hardware-isolation rules for directly compared conditions.

### Increment C: project initialization and adoption

1. Initialize the two emotion-memory Seed Projects with distinct briefs and
   zero training allocation.
2. Build and refresh release artifacts.
3. Restart the integrated main service so the daemon and WebAPI share the new
   release identity.

Increment A is implemented first because it fixes the current scientific
validation gap without depending on the new program registry.
