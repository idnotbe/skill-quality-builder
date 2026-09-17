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
