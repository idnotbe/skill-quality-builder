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
