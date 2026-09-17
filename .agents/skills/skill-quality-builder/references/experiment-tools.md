# Prepare, run and compare an experiment

Read when actual execution evidence is available or requested. All scripts use Python 3.10+ standard library. They never install software or purchase model access. A model runtime is optional, not bundled.

## Prepare reproducible actor packets

Copy the [bindings template](../assets/experiment-bindings.template.json) outside the installed skill and fill actual paths/settings. Select the applicable cases from an existing suite or the [evaluation template](../assets/evaluation-suite.template.json). Keep the suite and declared fixed fixtures together. `input_files` explicitly selects the fixture files an actor needs; do not select answer keys. A legacy case's `fixture` description is manual setup metadata, NOT an automatic file mapping. Materialize such a fixture and add explicit input_files before using this tool. Fixtures must match their declared hashes.

Run from any working directory, quoting real paths:

```text
python -B <THIS_SKILL_DIR>/scripts/prepare_evals.py <suite.json> <bindings.json> --output <new-external-directory>
```

Bindings contain common environment and execution_context, plus a skill_dir and builder_model per condition. Relative skill paths resolve beside the bindings file. Only baseline may use null for no skill. Use baseline/original/minimal/candidate conditions where useful; all must exist in the suite. Each target is structurally checked and copied, not executed. Use an inspected execution-only snapshot: bundled private tests/answers can otherwise contaminate results. Source bundles remain untouched.

The output contains randomly named, randomly ordered `actors/<id>/` packets and a separate `judge/` area with suite, expectations, mappings and empty observations. Each repetition has its own copy of the skill and selected inputs. Actor request.json contains only the task, activation mode, local skill path and input paths. Read only one packet into each fresh execution session. Never mount the judge directory into that session. Filesystem separation alone is NOT isolation; adapters must restrict access. Target skill names may still reveal identities; this is procedural blinding, not a guarantee.

Record the actual execution model, host version, effort, thinking mode, output budget, instruction-stack and shared runtime-profile digests. Use canonical_digest on a recorded representation to compute those digests, including an empty profile where no shared profile applies. Candidate-specific rules belong in its bundle hash; profile_sha256 identifies common runtime guidance, NOT the changing candidate rules. builder_model may vary between conditions. Executor settings must match within a cohort. Compare different effort/model/host combinations in separate experiments, without interpreting label equality as compute equality. Unknown values do not support controlled-comparison claims.

## Optional trusted adapter protocol

```text
python -B <THIS_SKILL_DIR>/scripts/run_eval.py <actor-packet> --output <new-result-directory> -- <absolute-executable> <adapter-arguments>
```

This is a dry run. For execution supply `--expected-packet-sha <digest-from-judge-index>` and `--execute` before `--`, only after inspecting the adapter and authorizing its side effects and model usage. `--timeout` is bounded to one hour. The executable must be an absolute real path, not a shell batch file. Commands are never read from the suite or target skill. No built-in Codex/Claude CLI flags or subscription capabilities are assumed; your adapter maps this protocol to the actual installed host.

The adapter receives request.json on stdin and runs with that packet as cwd. It must create a fresh host session, register only the intended skill, expose only the packet inputs, enforce stated permissions, capture actual tool calls/selection and final artifacts, and wait for all its own work. Never reuse a session across cases or run background descendants. Return one JSON object on stdout: `{"output": "actual final text", "events": []}`. Events are observable calls/selection/state, not hidden reasoning. Put diagnostics on stderr. Preserve actual identity/usage fields as additional data only when observed. An empty events list does not prove no side effects if tracing is unavailable.

The runner verifies every packet file/type (including ignored additions) against the frozen manifest and the independently supplied digest in judge/index.json. Changed inputs or a self-rewritten manifest cannot silently pass as the original packet. This assumes a stable snapshot; it is not protection against concurrent hostile filesystem races. The runner uses no shell, records packet/request/response hashes, exit code and measured elapsed time, and returns timeout/error states without grading them. It limits captured output and stops the adapter process tree where supported. Polling is not a hard filesystem quota, and the runner is not a sandbox. The adapter inherits the caller's environment to support already-authorized hosts; do not expose credentials to the actor or put secrets in argv/logs. Use a restricted external environment for untrusted inputs. Review retained logs before sharing them. Dry runs create no files.

## Grade without turning transport success into quality proof

Match result.run_id and request_sha256 to judge/index.json. Verify original/candidate snapshots, final state and traces; a JSON reply claiming success is insufficient. Fill judge/observations.json only after actual grading, set evidence_kind to the method actually used, and replace prepared metadata with real session context. Missing runtime or graders stay not_run. Record lost tracing explicitly; do not mark permission checks passed just because nothing was logged.

```text
python -B <THIS_SKILL_DIR>/scripts/summarize_evals.py <experiment>/judge/suite.json <experiment>/judge/observations.json
```

The summarizer reports each dimension and capability/regression checks separately, plus matched baseline transitions (`improved`, `regressed`, `both_pass`, `both_fail`, `not_comparable`). Missing/N/A checks do not become wins. Paired assertion counts are descriptive and correlated; they are not a causal estimate or an independent-sample significance test. Existing critical blockers still apply; no automatic release decision or performance claim is generated. New suites may require execution_context; legacy schema_version 1 records remain compatible.

For open-ended outputs use source checks and blind human/model comparison, calibrated with defect mutations and valid alternative solutions. For generated skills first build/freeze a child under each builder condition, then execute those children in fresh sessions on unseen tasks. Preserve builder identities separately from executor identities. Keep observations, raw traces, human corrections and rejected candidates outside the installed bundle.
