# Balanced evaluation of Skill Quality Builder

**A public, reproducible evaluation package; not a claim that the builder passed 108 model trials.**
The September 18, 2026 run exercised deterministic validators, packet preparation,
mutation/regression checks, and an eight-case nonblind current-session artifact
pilot. Fresh Codex/Claude sessions, natural host selection, independent graders
and matched child-skill comparisons were not available. See [results](RESULTS.md).

## What is being evaluated?

A skill-authoring skill has several different outputs. Do not confuse these layers:

| Group | Cases | Evaluation target and evidence |
|---|---:|---|
| `trigger` | 48 | Actual natural host selection: 24 positive and 24 near-negative requests; eight minimal-contrast pairs; Korean/English coverage. Explicit invocation is excluded. |
| `builder` | 30 | Creation, editing, auditing, scope, source grounding, clarification, preservation, progressive disclosure, missing tools, failure diagnosis, stopping and safety. Inspect actual artifacts, diffs and actions. |
| `adaptation` | 6 | Model/host adaptation, authorized versus reserved actions, proportional verification, retrieval and preference scope. Do not attribute host failures to the model. |
| `child_csv` | 7 | Execute the **generated child**, not the builder: confirmed actions, empty output, unaccepted ownership and embedded instructions. |
| `child_analysis` | 2 | Counterfactual process facts: substantial waiting versus substantial work; preserve approval, allow valid alternative interventions. |
| `child_action` | 2 | Actual local state and action traces: already authorized edit versus reserved decision. No real external service is needed. |
| `child_codebook` | 5 | Adapted manufacturing codebook data: English, Chinese, unknown product, equivalent duplicate codes and injection. |
| `calibration` | 8 | Test the **grader**, not downstream skill performance: wrong owners, valid alternatives, forbidden attempts, empty output, crashes, late selection, equivalent CSV and missing evidence. |

There are **108 scenarios**, not 108 independent statistical samples. The existing
repository supplies 67 adapted cases, SkillsBench supplies data for 5 adapted
cases, and 36 cases fill gaps. Translation/contrast siblings retain family IDs.
Report dimensions and groups separately; do not let 48 routing questions drown
out safety or child-task failures. Repeated observations are not independent
new scenarios. Nineteen prompts are Korean; one codebook input is Chinese.

The generated [catalog](catalog.json) records prompts, selected inputs, criteria,
severity, dimensions, public family IDs, provenance and file hashes. It is judge
material. The [generator](build_catalog.py) imports pinned source bytes rather
than inventing all cases from scratch. Sources and licenses: [SOURCES.md](SOURCES.md).

## Running the checks that need no model

Run from the repository root with Python 3.10+; no dependencies or MCP are needed:

```sh
python -B evaluation/build_catalog.py --check
python -B evaluation/harness.py check
python -B -m unittest discover -s tests -v
```

A successful exit here means **catalog/tool correctness**, not skill effectiveness.
Source JSON and fixture bytes are fixed to LF on Windows as well as Linux. Do not
regenerate against changed imports while leaving their old revision label: review
and update `BASE` and `PINNED_IMPORTS` deliberately.

## Preparing an actual host experiment

Copy [bindings.example.json](bindings.example.json) outside the repository and
replace every placeholder with the actual executor/host/effort/settings and an
absolute skill path. No API model ID, subscription entitlement or CLI syntax is
assumed. The existing runner accepts a reviewed, caller-supplied adapter.

```sh
python -B evaluation/harness.py prepare trigger /absolute/bindings.json --output /absolute/new-experiment
```

Default repetitions are three. Natural trigger uses candidate only. Builder,
adaptation and child groups use baseline and candidate. Calibration uses candidate
only and requires `evaluation_target: "grader"` rather than builder or child. A baseline may be no skill (`skill_dir: null`) or an immutable original.
Never interpret a no-skill trigger baseline as a useful precision comparison.
Each group is prepared separately: the native runner has a 200-packet limit.
An excessive repetition request is rejected, not silently truncated.

The native output contains independently copied actor packets plus a separate
judge directory. Only prompts and explicitly selected inputs reach each packet;
case labels, rubrics, answer keys and condition labels are withheld. Targets are
actually materialized as `target/<name>/SKILL.md`. `child-inputs.json`, which
contains answers, is **never** an actor input. Distinct inline records receive
case-specific paths so that one record cannot silently overwrite another.

**Execution identity and contamination:** the canonical builder already bundles
public examples resembling these cases. The wrapper therefore creates a separate
execution view that excludes `evals/` and rewrites only documentation links to those
withheld files. The canonical source is not modified. Both source and effective
content digests, excluded files and rewritten links are recorded under `judge/`.
This is an explicit projection, not a byte-identical evaluation of the canonical
bundle. Do not claim otherwise. Public regression examples and this session's
pilot cannot demonstrate unseen generalization even after that projection.
A stronger future claim needs newly collected private families sealed before tuning.

A directory boundary is **not** a sandbox. The adapter must expose only its actor
packet, withhold the repository and judge directory, remove unrelated skills and
credentials from the actor's context, enforce permissions, and create a fresh
session. Natural-trigger acceptance assumes only this builder is an eligible
skill-authoring capability. Competitor-installed profiles are separate diagnostics:
choosing another appropriate authoring skill is not necessarily a user-task error.
Record the actual installed skill inventory and profile; do not pool profiles.

Execute one packet only after reviewing the adapter and authorizing any model usage:

```sh
python -B .agents/skills/skill-quality-builder/scripts/run_eval.py /absolute/new-experiment/actors/RUN_ID --output /absolute/new-result --execute --expected-packet-sha SHA_FROM_JUDGE_INDEX -- /absolute/adapter-executable
```

Without `--execute` the native runner is a dry run. A result status `completed`
means transport completed, **not** that any criterion passed. The adapter's stdout
is a JSON object containing `output` and `events`; diagnostics go to stderr.
For natural-selection grading it must also set `trace_complete: true` and
`trace_source: "host_event_stream"` based on actual retained host telemetry.
Normalize a real selection as:

```json
{"source":"host","type":"skill_selected","skill":"skill-quality-builder"}
```

A model saying it selected the skill, a generic file read, or a guessed choice is
not that event. Selection may legitimately occur after other tool calls. Timeout,
crash, invalid output, missing trace or explicit activation returns unknown, never
a free pass on a negative case. The normalizer is trusted infrastructure: arbitrary
JSON cannot authenticate itself. Retain and review the actual raw host trace.

The progressive-layout request includes a `follow_up` field for a separate fresh
child validation session after refactoring. The wrapper rehashes the changed
request/packet and judge index. An adapter must explicitly support this follow-up;
otherwise its conditional-read criterion remains `not_run`, not passed by inspection.
Do not quietly ignore that field. The native process runner does not itself create
model sessions or conduct follow-ups.

## Builder-to-child protocol

For each `child_*` group, first ask each builder condition to create a child using
the corresponding `child_build_contracts` entry in the catalog and domain inputs
only. Hide child test prompts, expected outputs and graders. Freeze each resulting
child, retain the build transcript, and **then** execute those children in fresh
sessions on the downstream cases. Do not regenerate a child separately for each
known answer. A no-skill baseline is also useful but answers a different question
from old-builder versus new-builder comparison.

Set `evaluation_target: "child"`; provide a child path for each non-null condition
and `child_build_records[condition]` containing `builder_model`,
`builder_skill_sha256`, `child_skill_sha256`, and a `build_record` reference. The
wrapper checks the child digest against the actual included files and refuses a
builder directory used as a child. Build-record references require reviewer
verification; a hash is an integrity binding, not proof of truthful authorship.
The child digest uses the native canonical format: SHA-256 of sorted compact JSON
mapping included relative paths to their SHA-256 byte digests.

## Grading and release gates

Use native `judge/suite.json` and `judge/observations.json`. Before accepting a result,
verify run ID, request hash, packet hash and response digest using
`harness.verify_result_binding`; review actual artifacts and retained traces.
Populate only observed criteria. Do not copy hypothetical expectations into the
evidence field. The native summarizer is the final reporting path:

```sh
python -B .agents/skills/skill-quality-builder/scripts/summarize_evals.py /absolute/new-experiment/judge/suite.json /absolute/new-experiment/judge/observations.json
```

`trigger_observation` grades normalized host telemetry as true/false/unknown.
`csv_verdict` accepts legal CSV quoting and CRLF but checks exact row/column values,
order, empty results and the required final newline. `codebook_verdict` accepts
both indistinguishable U202 codebook codes, checks product/station/label/source
span and rejects duplicate JSON keys. These output graders do **not** certify
absence of attempted side effects. Missing safety telemetry remains `not_run`.
Open-ended criteria need a calibrated human/model reviewer; do not replace them
with keyword matching or a required sequence of fashionable reasoning steps.

A safety/mandatory-contract failure blocks a favorable release judgment. Missing
required checks keep the result unverified. Show coverage denominators, failures,
unknowns, per-dimension results and matched transitions. Do not pool cost, model,
host or effort cohorts. Token/latency figures must come from measurements, not
estimates. Independent blind grading and random A/B label order are recommended
for substantive comparisons but have not been performed in the recorded pilot.

## Review process and limitations

[REVIEW.md](REVIEW.md) records concrete adversarial findings, fixes and reruns.
Reviews here were self-reviews with independent hard-coded regression oracles,
not an independent reviewer/model. Zero remaining **known** P0/P1 findings in this
bounded review is not a guarantee that all defects have been discovered.

No extra service is installed, no credentials are requested or stored, and no
model bill is incurred by catalog preparation or deterministic tests. The recorded
GitHub Models probe failed with HTTP 410; it is an infrastructure observation, not
an evaluation score. The failed probe is not evidence for the cause of the ChatGPT
"Thinking failed" UI interruption.
