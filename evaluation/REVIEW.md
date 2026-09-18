# Adversarial review record

Scope: evaluation design, grading oracles, packet preparation and evidence claims.
The builder itself was not rewritten. Reviewer: the same assistant, using concrete
counterexamples and separately hard-coded executable assertions. This is **not**
an independent-agent review and does not establish exhaustive defect absence.

P0: potentially destructive or fabricated release evidence on a broad scale.
P1: a material false pass/false fail, lost required scenario, or integrity/scope
violation that invalidates a meaningful part of the evaluation. P2: narrower
clarity/coverage issues that do not invalidate an asserted result.

## Round 1 — construction and initial evaluation

Imported all 67 existing cases before writing new scenarios. Inspected source
material and incorporated five external-data cases; wrote 36 gap cases. Initial
34 new unittest methods passed, including mutation subcases. Corrected during
construction: legacy fixture materialization, removal of answer-bearing child
input files from actor inputs, public-family labeling, equivalent CSV quoting,
duplicate codebook labels, and crash-versus-nonselection separation.

These construction decisions are not claimed to be failures observed in a real
host trial. Initial executable log: `results/review-round1-tests.txt`.

## Round 2 — four executable failures, then targeted fixes

The expanded 38-test evaluation produced **four failing tests**. Evidence is
retained in `results/review-round2-before.txt`; the corrected rerun is
`results/review-round2-after.txt`.

| Finding | Severity | Counterexample | Fix / regression |
|---|---|---|---|
| R2-01: child provenance not bound to actual bytes | P1 | A build record with an all-zero child digest still prepared child trials. | Require a real 64-hex builder digest and an exact generated-child content digest; reject the builder used as a child. `test_child_build_record_binds_generated_bytes`. |
| R2-02: execution view overwrote an existing destination | P1 | An existing output directory containing a sentinel accepted view writes. | Require a new non-symlink destination outside the source. `test_execution_view_never_overwrites_an_existing_destination`. |
| R2-03: progressive follow-up disappeared in transport | P1 | The catalog required a child validation follow-up but request.json did not carry it. | Preserve follow_up in actor requests and recompute request, manifest and judge-index hashes. `test_progressive_case_followup_reaches_the_actual_actor_request`. Missing adapter support still leaves the criterion not_run. |
| R2-04: self-declared trace could count as nonselection | P1 | A response with trace_complete=true but no host-origin declaration returned false rather than unknown. | Require normalized host_event_stream provenance, plus complete successful execution. `test_self_declared_trace_without_host_origin_is_unknown`. The adapter remains a trusted recorder; JSON cannot authenticate itself. |

Additional hardening: pin imported source bytes to the declared revision; preserve
LF for source JSON and external fixtures on Windows; localize selected builder and
adaptation cases without creating fake independent holdouts; promote preservation
of the work-package's mandatory contract to a critical criterion.

## Round 3 — full integration, artifact pilot and source recheck

The full suite has 184 tests: 142 pre-existing plus 42 new test methods (several
methods contain multiple mutations). Every evaluation group is actually exported
through the native preparation tool. Tests verify all request/packet digests,
separate child/grader/builder roles, repetition-budget failures, no observation
promotion, and the nonblind pilot's honest status.

A direct line count confirmed that the supplied work-package fixture really has
900 lines. An unsupported draft comment that described it as shorter was removed,
and a source-count regression was added. The correct original prompt was retained.
This is recorded to avoid turning a mistaken review assumption into a claimed bug.

Eight current-session builder tasks produced actual edits/replies; 16 mechanical
artifact checks passed. They were not independent model calls and were not used
to populate natural-trigger or child-performance observations. The complete pilot
retains original/final manifests and actual text artifacts.

Final bounded-review finding state: **no unresolved known P0/P1 evaluation-design
or harness defects identified**. The missing authorized fresh host/model runner,
independent grading, private holdout and fresh child execution remain explicit
coverage limitations, not passes. This statement applies to the reviewed code and
recorded checks; it is not a certification or evidence that all skill behavior is
correct. See RESULTS.md and the final exact-revision CI checks.

## Round 4 — actual CPU execution and evidence review

Scope: real Qwen responses, host traces, generated files, condition isolation and
claims. The reviewer remains the orchestrating ChatGPT, not a blind independent
semantic judge. The 8-case calibration gate failed (5/8 correct), so open-ended
semantic scoring was withheld. See RESULTS.md and the artifact registry.

| Finding | Severity / disposition | Correction and evidence |
|---|---|---|
| Inline actor filenames exposed case identity | P1, fixed before scored CPU trials | Opaque input aliases matched across conditions; privacy regression retained. |
| Inference failure discarded prior responses | P1, fixed | Retain prior raw calls and actions; failures before/after the first response have separate tests. V2 journal preserves the affected earlier response. |
| Truncated tool batch replay caused HTTP 500 | P1, fixed | Stop before executing/replaying a partial batch. Three new tests fail on the older host, pass on corrected host; rerun only the diagnosis pair. Candidate generation-limit behavior remains observed. |
| Child driver skipped a real interrupted draft | P1 evidence-coverage issue, corrected as diagnostic | Freeze verified final child bytes, allow singleton preparation, execute without repairing the bundle. Never claim that an interrupted builder completed. |
| Local write treated as injection failure | P1 in draft offline analysis, corrected before publication | Catalog prohibits source-directed/external actions, not every local write. Regrade retained outputs; record writes as facts and leave causal safety unknown. Output failures remain independent. |
| Invalid baseline and no-child control could imply uplift | P1 claim risk, excluded | No valid baseline child exists. Label the no-child control separately, including its installed-child wording limitation. No 3-versus-4-failure uplift claim. |
| Short budget confounds delivery | Limitation, measured separately | One fresh 12-call CSV build per arm. Baseline used 2 and candidate 11 calls, neither delivered a loadable child. Preserve earlier failures; do not select best results. |
| Old evaluation plan auto-triggered by host edit | Operational fault, corrected | Cancel exact superseded run 35300006737 before outcome review. Retain excluded-run metadata. Set CPU workflows to explicit manual dispatch. |

The public 108-case catalog and installed builder bytes remain unchanged. All
54 scored-cohort attempt bindings were checked; 52 have preserved actual model
responses. Cases, attempts, calls, contrast siblings and repeated use of one
child are reported separately. Safety unsupported by a capable external-action
host remains unknown. Hashes prove recorded byte consistency, not independent
authorship, absence of training contamination or independent reviewer identity.

Final bounded review: no known unresolved P0/P1 defect in the narrowed evaluation
claims above. This is not exhaustive assurance or a successful skill release
gate. Failed calibration, native-host coverage, weak/invalid child baseline and
79 not-run catalog cases remain explicit limitations. Full deterministic checks
and exact final-revision CI must pass before merge.
