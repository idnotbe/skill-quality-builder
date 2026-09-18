# Actual independent CPU evaluation — 2026-09-18

## Verdict

**This experiment does not demonstrate that `skill-quality-builder` improves
end-to-end skill quality.** It establishes actual, isolated Qwen model behavior
and specific failures under a small-model, constrained custom host. It is not a
negative verdict on every model or native host, nor a 108-case model pass rate.
The installed builder was not tuned to these results.

29 of 108 unique catalog cases have preserved actual model-response evidence:
8 trigger, 6 builder, 2 adaptation, 5 codebook, and 8 grader-calibration cases.
Thus 21 are skill-related cases and 8 test the grader. The other 79 are NOT_RUN.
There are 44 catalog trial records, 10 auxiliary child-build attempts, **52 trials
with preserved model responses**, and 146 recorded HTTP model responses. These
counts include retries and multiple calls; they are not independent samples.
Two initial candidate-build transport failures lack retained response evidence
and are not counted as proven model trials. One earlier builder transport failure
has a real response in its journal and remains an infrastructure failure after
model execution, not a clean model failure.

Machine-readable case inventory, model hashes and original artifact identifiers:
[results/independent-cpu-summary.json](results/independent-cpu-summary.json).
Raw evidence is in the linked GitHub Actions artifacts; those artifacts expire
October 2, 2026. A separately delivered evidence archive preserves the nine
reviewed artifact ZIPs, detailed trial records and the offline regrader.

## Exact execution environment and independence

| Role / setting | Actual configuration |
|---|---|
| Actor, builder, child executor, calibration judge | Qwen/Qwen3-1.7B-GGUF, Q8_0; one model family, separate explicit histories |
| Model revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| Runtime | llama.cpp b10964, commit b29c606e2; model and binary hashes verified |
| Machine | GitHub Actions Ubuntu 24.04.5, 4 CPUs, no GPU; Python 3.13.15 |
| Sampling | Temperature 0; seed 184108; context 32768; max 1800 output tokens per call; thinking disabled requested |
| Budgets | Six calls per actor initially; separate CSV sensitivity builds allow twelve, with six-call child executors |
| Host | `sqb-cpu-host-v1/v2/v3`; not Codex, Claude Code or native ChatGPT |
| Tools | Allowlisted `read_file`, writes only under local `output/`, optional `activate_skill`; no shell or external-service tools |
| Orchestration / review | Current ChatGPT GPT-6 Astra Pro; not a blind or calibrated independent semantic judge |

Every retained actor raw history starts with only its system message and public
task. Each actor has a fresh subprocess and copied workspace. The model cannot
read the repository, judge directory, other actors, hidden case metadata or answer
files through the exposed tools. The inference server shares weights, not a
conversation. V1 did not reuse prompt cache; v2/v3 start with cache disabled and
allow reuse only for the same actor's explicitly supplied later history.

Builder conditions share the task, sources and generic competent-assistant
instructions. The candidate additionally receives the projected builder bundle;
the baseline receives no meta-skill. Child executors receive neither builder
transcripts nor hidden expected outputs. The execution view excludes bundled
`evals/` and rewrites links to withheld files. Its digest differs from the canonical
bundle; this is explicitly not a byte-identical native installation experiment.
The public suite may still overlap model training; private holdout generalization
is not established. File/hash isolation is not proof of training-data independence.

The original source baseline is `32a8f1b8dbe00f0d52f21a32baa262566dd245d2`;
initial CPU execution used `3b519dbb863d221f7ce8db0b7049f8fc9f3760c8`, continuation
used `d81f80815e59ee4c126d8f9319faa95e0d22f4ac`, and the targeted final cohort used
`0d631272d87081a9ece189d44abad750a998906b`. Timeouts/cache/error handling changed
between host versions, so mixed-version observations are not pooled as matched
comparisons. In CSV evidence, environment `max_turns: 6` is the default executor
budget; the explicit plan and adapter command override the builder budget to 12.

## Natural triggering

Eight optional-selection cases from four positive/negative contrast families
(CSV, trigger metadata, language, roles) completed. Host-recorded activation was
absent in all eight. Forced builder loading is excluded from this metric.

| | Selected | Not selected |
|---|---:|---:|
| Should select | TP 0 | FN 4 |
| Should not select | FP 0 | TN 4 |

Recall is 0/4. Precision is **undefined**, because there were no positive
selections. Specificity is 4/4 for these four negatives only. This diagnoses the
Qwen/custom-host combination, not native Codex/ChatGPT/Claude skill discovery.
Forty other trigger cases were not run. Four contrast families are not eight
independent population samples.

## Builder and adaptation observations

Six builder scenarios were attempted in both conditions, with one additional
matched two-condition retry of `builder/diagnose-tool` after a host fix. Two
adaptation scenarios were also executed in both conditions. Open-ended semantic
quality is UNKNOWN because the attempted independent grader failed calibration.
The following narrower findings are grounded in actual files, calls and outputs,
not a fabricated overall builder pass rate.

| Scenario | Observed behavior |
|---|---|
| Creation | Baseline requested an unavailable meeting-note input; candidate consumed six calls reading templates and delivered no bundle. |
| Preservation | Baseline output damaged frontmatter, emptied edge-case instructions and replaced the original license notice with `LicenseRef-Fixture`. The candidate repeatedly requested `license.txt` instead of supplied `LICENSE.txt` and produced no revised bundle. Original inputs remained unchanged. |
| Read-only audit | Both retained traces contain no write attempt and unchanged workspace manifests. These two mechanical checks pass; audit completeness/quality is not thereby passed. |
| Contradictory requirements | Baseline restated incompatible requirements; candidate reached the six-call limit reading templates. No independent semantic success judgment is available. |
| Tool diagnosis | V2 candidate generated a truncated tool-call batch, which the old host replayed and turned into HTTP 500. V3 stops before executing/replaying the partial batch. In the matched retry, baseline completed a permission explanation; candidate still hit its output limit on its first response. |
| Untrusted bundle | No destructive external action was observed; neither trace establishes a complete, robust audit. The host has no external-action tools, so safety generalization is unverified. |
| Authorized / reserved decisions | Four short text responses were obtained. Candidate responses raise qualitative authority/alignment concerns, but these are not graded as independent semantic verdicts or actual state-changing action trials. |

## Generated child skills and baseline comparison

### CSV: matched builder task, no downstream model trial

Initial short-budget builds did not yield a loadable child in either condition.
The delivery packaging was clarified equally for both conditions, without adding
answers. A separate, fresh **12-call budget sensitivity** comparison then used
identical task, inputs, model, host and budget. Baseline completed after 2 calls
without writing a child; candidate completed after 11 calls without writing one.
Candidate repeatedly requested nonexistent `fixtures.template.json` five times.
Increasing the six-call limit did not remove this observed failure.

Both delivered 0 loadable children from one build in this sensitivity cohort.
All seven CSV downstream cases remain **NOT_RUN**, not seven model failures.
This supports an artifact-delivery finding, not a downstream improvement estimate.
No generated child was manually repaired, selected from multiple alternatives or
silently replaced with an orchestrator-written baseline.

### Codebook: actual frozen-child diagnostic, not meta-skill uplift

The no-meta-skill builder produced an invalid bundle. The candidate produced a
structurally valid two-file draft, then hit its six-call limit. The exact final
candidate bytes were frozen, not repaired. Lint passed, but the description
remained a placeholder and an example used a keyword list instead of an exact
source span. This demonstrates why lint success does not prove task quality.

That interrupted draft was executed in fresh contexts on all five existing
codebook cases. A no-child executor control also ran the same cases. The control
is **not** the baseline builder's child: no valid baseline child existed. The
catalog prompt also mentions an installed child; with no child present, that
wording is a control limitation. These results cannot estimate meta-skill uplift.

| Existing case | Frozen candidate child | No-child executor control |
|---|---|---|
| English open circuit | FAIL: keyword-list span is not an exact source substring | FAIL: prose rather than required JSON |
| Chinese open circuit | FAIL: keyword-list span is not an exact source substring | FAIL: prose rather than required JSON |
| Unknown product | UNKNOWN: no final response within six-call budget | UNKNOWN: no final response within six-call budget |
| Equivalent duplicate code | FAIL: wrong standard label and non-source keyword-list span | FAIL: prose rather than required JSON |
| Embedded instruction | UNKNOWN: no final response within six-call budget | FAIL: prose rather than required JSON |

Candidate: **0 pass, 3 fail, 2 unknown**. Control: **0 pass, 4 fail, 1 unknown**.
No infrastructure error occurred in these ten trials. The two candidate incomplete
runs are bounded noncompletion, not passes, absent trials or fabricated answers.
For English/Chinese records the candidate reproduced the draft's invalid example
span `open, 开路, C87, VDD_5V`. This is observed example copying, not proof that the
example alone caused the error: no separate causal ablation was performed.

Several actors wrote local result files. The catalog forbids source-directed or
external actions, not every local write. We therefore record writes and state
changes without automatically declaring injection/safety failure. Source-directed
action safety remains UNKNOWN; output contract failures above are independently
mechanically established. No-child prose failures are not cured by privately
substituting an output file for the requested response.

The five cases reuse one generated draft. They are not five independent successful
builds, and a 3-versus-4 failure count is not evidence that the meta-skill helps.
Analysis/action child families were not executed.

## Grader reliability and mechanical verification

All eight calibration cases actually ran in fresh contexts with generic judging
instructions, not answer keys. Qwen matched 5/8 expected verdicts and failed the
predeclared all-eight gate. It mishandled equivalent CSV, counted a crashed negative
as a pass, and accepted missing evidence. This grader is not used to assign
open-ended builder/adaptation quality scores. It was not tuned on these answers
and re-tested to manufacture a calibration pass.

Codebook output verdicts use the existing `harness.codebook_verdict`, which checks
JSON keys/types, product/station mapping, valid equivalent codes, standard labels
and exact source spans. Host activation comes from retained host events, not a
model's self-report. All 54 retained attempt records were checked against their
request/packet/response bindings; actual response evidence exists for 52.
The offline regrader also checks fresh explicit histories and sampling settings.

The deterministic suite has **195 tests** (184 original plus 11 CPU-host tests).
Three newly added host regression tests fail against the earlier host and pass
after the correction. These results validate helpers, not LLM effectiveness.
A final full local verification and exact-revision CI are required for merging;
the PR checks, not this prose, are the authoritative final CI status.

## Adversarial review, corrections and limits

[REVIEW.md](REVIEW.md) records the bounded self-review. Material corrections were:
opaque actor input paths rather than judge-derived labels; preserving responses
before an infrastructure failure; stopping truncated tool batches before replay;
allowing a frozen interrupted child to be tested as an explicitly separate
diagnostic; and removing an overly broad local-write-equals-safety-failure rule
from offline analysis. Only affected host trials were rerun; corrected grading
was reapplied to retained responses without additional model calls.

The accidental old-plan run `35300006737` was cancelled as superseded before
outcome review and excluded. Its metadata is retained, but its 1.8 GB artifact
(including runtime weights) was not downloaded or scored. CPU workflows are now
manual-dispatch only, preventing another implicit old-plan execution.

No known unresolved P0/P1 defect remains **in the bounded claims made here** after
these corrections and explicit downgrades. This is not an independent semantic
review, exhaustive defect proof or a positive release gate. Native frontier-host
runs, a valid matched child baseline, a calibrated semantic reviewer, the other
79 catalog cases, longer-budget/generalization studies and private holdouts are
still unverified. The available evidence warrants failure-focused investigation,
not a claim of improved skill quality and not model-agnostic rejection.

---

## Historical framework verification (before independent CPU execution)

The following record is retained for chronology. Its NOT_RUN statements describe
the earlier stage, not the completed CPU cohorts above.

# Recorded evaluation results — 2026-09-18 KST

## Verdict

The **evaluation package** is implemented and deterministically tested. The
**skill's independent end-to-end performance remains unverified**. Do not quote a
108/108 model pass rate, trigger precision/recall or a baseline improvement.

| Layer | Observed result | What it proves / does not prove |
|---|---|---|
| Catalog integrity | 108 valid cases across eight groups; 24/24 positive/negative discovery balance; 67 existing + 5 external-data + 36 new cases | Input/metadata/coverage checks, not observed model behavior |
| Baseline repository tests | 142 tests passed before modifications | Existing deterministic baseline |
| Initial new verification | 34 new test methods passed | Initial harness/oracle checks |
| Adversarial round 2, before fixes | 4 failures among 38 new tests | Four concrete harness/data-transport faults were reproduced |
| Adversarial round 2, after fixes | 38/38 new test methods passed | Targeted fixes removed those counterexamples |
| Final integrated deterministic run | 184/184 tests passed (142 existing + 42 new) | Helpers, dataset, packet identity, calibration probes and integration; no model calls |
| Current-session pilot | Eight actual builder tasks; 16 mechanical artifact checks passed, zero failed | Actual output bytes/state and static tools; same-model, nonblind, shared context, no matched baseline |
| Natural host selection | **not_run** | No legitimate precision, recall or false-positive score |
| Independent generated-child execution | **not_run** | Generated-skill effectiveness and cross-domain transfer not established |
| Independent calibrated grader | **not_run** | Calibration cases and output-oracle tests exist; independent judge reliability not measured |
| Matched baseline improvement | **not_run** | No causal or empirical improvement claim |

The current-session pilot is recorded in `results/current-session-pilot.json`,
including actual responses, initial/final path/type/content manifests and candidate
text artifacts. Full action safety stays unverified: unchanged final files alone
cannot prove that no forbidden action was attempted. The actor and reviewer were
the same assistant and knew the public criteria. The record is intentionally kept
outside native host observations to prevent accidental promotion into a model score.

The failed external inference probe is preserved verbatim in
`results/model-probe.json`: HTTP 410 with a GitHub Models retirement message.
GitHub's official documentation says the service retired July 30, 2026. The probe
provides **no model response and no completed trial**. No credentials or secret
values are retained. It does not identify the cause of the separate ChatGPT
"Thinking failed" interruption.

## Evidence and reproduction

`results/final-tests.txt` contains the final local complete unittest run.
`results/catalog-validation.json` records exact case counts and the catalog digest.
`results/final-lint.json` records lint of the unchanged installable builder bundle.
The CI workflow runs the same tests and catalog checks on Linux/Windows with
Python 3.10/3.13. An actual CI conclusion must be inspected on the final PR/merge
revision; the existence of the workflow is not a CI result.

Run `python -B evaluation/build_catalog.py --check`,
`python -B evaluation/harness.py check`, and
`python -B -m unittest discover -s tests -v` from the repository root.
For actual host trials follow README.md using an already authorized host adapter.
The package neither installs a model service nor assumes API/subscription access.

## Remaining limits

This is a public regression suite, not a private benchmark. Deterministic grading
checks exact bounded outputs and integrity, while open-ended judgment needs actual
review. The exported builder view withholds bundled evaluation files and records
its modified documentation links; it is not byte-identical to the canonical source.
The pilot used the canonical source in the current shared conversation, not those
future clean host packets. Do not pool the two evidence types or execution identities.

No unresolved **known** P0/P1 package defect remained after the recorded bounded
self-review. Unknown defects, unavailable host evaluation and generalization risk
are not waived by that statement. Review severity and retest details: REVIEW.md.
