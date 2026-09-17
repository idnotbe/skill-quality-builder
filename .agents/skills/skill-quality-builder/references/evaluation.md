# Evaluate evidence, not confidence

Read when creating a test plan, tuning discovery, or reporting improvement. Use clean runs where available. This package has no model runner; its scripts validate structure and aggregate supplied observations only.

## Four evaluation layers

| Layer | Method | Does not prove |
|---|---|---|
| Static | File names, supported frontmatter, local paths, bundle checks | Correct semantics or host selection |
| Trigger | Natural requests, no forced skill mention; observe selection/read | Quality after activation |
| Outcome | Explicit skill run on real task; inspect artifact and actions | Reliable implicit selection |
| Safety/regression | Missing inputs, conflicting instructions, permissions, old successes | Complete resistance to arbitrary attacks |

For a small change, use the layers it can affect. Mark skipped or inapplicable layers rather than calling them passed. The package's suggested sample sizes and iteration caps are engineering defaults, not validated universal thresholds.

## Experimental contract

Record task inputs, skill version/hash, model, host, tools, permissions, context policy, and budget. For create use a no-skill baseline; for improve use the unchanged original. Separate sessions avoid leakage of previous solutions. If there are no subagents, use fresh manual sessions; never invent parallel runs.

Define expected results before optimizing. Keep judges' expected answers out of execution prompts. Separate development cases from private final-check cases; public “held-out” examples are only split examples, not genuinely unseen evidence. To change a bad assertion, document why and regrade both versions.

For ambiguous subjective outcomes, blind and randomize the order of outputs where feasible. Use human judgment or a separately instructed evaluator. Self-review is useful but not independent replication. Never request hidden chain-of-thought; record observable actions and concise reasons.

## Trigger testing

Use realistic positive prompts and near-miss negatives, including language variation. Near-miss cases should exercise adjacent requested contracts, such as all proposed actions versus confirmed actions only, rather than only unrelated tasks. Test implicit matching separately from explicit invocation. A description-only classifier simulation may help refine language, but is not a host-level triggering result. Unobservable invocation is unknown.

For observed binary results, precision = TP/(TP+FP), recall = TP/(TP+FN). When a denominator is zero, the metric is undefined, not 100%. Report observation coverage with both metrics. Missing observations must not disappear from the denominator of coverage.

## Observation format for the supplied summarizer

The suite has `schema_version: 1`, `suite_id`, `conditions`, positive integer `repetitions`, and `cases`. Each case has a unique `id`, `kind` (`trigger` or `outcome`), prompt, `critical` flag, and optional split. Trigger cases also have a Boolean `should_trigger`. Outcome cases have named `checks`, each with a unique `id`, text, and a `critical` flag. A split is organizational only; the script does not conceal cases.

Observations have `schema_version: 1`, matching `suite_id`, `metadata`, and `observations`. Metadata has `model`, `host`, `skill_version`, `run_context`, and `evidence_kind` (`host_run`, `manual_artifact_review`, or `simulation`). Unfilled metadata is allowed for an empty template, but it is not runtime evidence.

Each observation identifies `case_id`, `condition`, and a 1-based `repetition`.

```json
{
  "case_id": "trigger-01", "condition": "candidate", "repetition": 1,
  "triggered": true, "evidence": "Run log path and selection event location"
}
```

For outcome observations, provide all expected checks. Repeat global format and permission checks in every case where they apply; include empty-result behavior when the contract defines it. For skills that consume untrusted content, include a critical case with an embedded instruction that attempts to change permissions or output. Do not use aggregate confidence in place of an assertion result.

```json
{
  "case_id": "outcome-01", "condition": "candidate", "repetition": 1,
  "checks": [
    {"id": "artifact", "status": "pass", "evidence": "artifact path and what was checked"}
  ]
}
```

Check statuses are `pass`, `fail`, `not_run`, or `not_applicable`. Evidence is required for pass, fail, and an inapplicability judgment. A missing check becomes not_run. A missing case or repetition remains missing. N/A never supplies positive evidence and never waives a critical check. Critical N/A therefore blocks complete validation until applicability is resolved.

Run:

```text
python -B <THIS_SKILL_DIR>/scripts/summarize_evals.py <suite.json> <observations.json>
```

The script rejects unknown IDs, duplicate observations/checks, invalid types, and inconsistent suite IDs. It reports each condition separately, coverage, trigger confusion counts, outcome counts, and critical blockers. Its exit code 0 means the JSON was valid, not that the skill passed. It does not verify the truth of evidence strings, judge semantic quality, establish statistical significance, or authorize deployment.

## Shared checks, fixed fixtures, and condition identity

Optional `common_checks` expands into every outcome case and must not duplicate case-local IDs. Include its checks in each observation. New shipped suites set `require_provenance: true`: nonempty records must bind the exact suite, fixed fixture manifest and each condition's skill digest, with matched model/host/tools/permissions/budget. Legacy unbound suites remain readable but are explicitly labeled unbound.

Read [reuse verification](reuse-verification.md) when using those fields, preparing cross-project reuse, or testing a generated child skill. It defines the digest format, fixed-fixture materialization and the two-stage builder-to-child experiment. The CLI verifies declared fixture bytes; it does not authenticate observation claims. Empty records remain unverified without invented hashes.

## Decision gates

A critical failure blocks a release recommendation. Incomplete required observations keep the status unverified. All-static or simulation evidence cannot establish host performance. Better wording, shorter files, and successful packaging are not a substitute for baseline improvement.

Review regression per case and by risk class. A higher average can hide a lost critical constraint. Capture time and tokens only when measured; never fill missing values with estimates presented as observations. Repeat important cases to expose variability and qualify small samples.
