# Skill Quality Builder

Create, improve, and audit reusable Agent Skills with built-in validation, packaging, evaluation templates, and adversarial review guidance.

## Validation status

**Candidate toolkit, not a certified autonomous quality gate.** Python tests cover deterministic helpers and regression cases. They do not establish host selection, generated-skill task quality, or a baseline improvement. Shipped host observation files are deliberately empty and return `unverified`. No model runner is included.

The static CI workflow covers Linux/Windows and Python 3.10/3.13, including portable package/extract round trips. A workflow definition is not a successful run: inspect the checks for the exact revision before reuse. Installation commands below are recipes; they have not been established as end-to-end host evaluation evidence by this repository.

## Convenient installation (floating versions)

Requires Node.js 22.20 or later; `npx` is included with npm. Run in the project where you want to use the skill:

```bash
npx skills@latest add idnotbe/skill-quality-builder
```

The installer discovers `.agents/skills/skill-quality-builder/SKILL.md` and prompts for supported agents and installation scope. This convenient command floats both the installer and source revision; do not use it to reproduce a previously reviewed version.

For an explicitly selected global Codex installation:

```bash
npx skills@latest add idnotbe/skill-quality-builder --skill skill-quality-builder --agent codex --global --copy --yes
```

Review the destination and existing local edits before a non-interactive installation. Listing the skill confirms an installer record, not that the host can load it correctly.

## Reproducible review and installation

Use a clean checkout at a full reviewed commit SHA, not a moving branch or tag. Replace `FULL_REVIEWED_COMMIT_SHA` below with that actual 40-character SHA. Do not use a pre-fix commit while assuming it contains later fixes.

```bash
git clone https://github.com/idnotbe/skill-quality-builder.git skill-quality-builder-reviewed
git -C skill-quality-builder-reviewed checkout --detach FULL_REVIEWED_COMMIT_SHA
git -C skill-quality-builder-reviewed rev-parse HEAD
git -C skill-quality-builder-reviewed status --porcelain
```

Stop if the checkout is not the expected revision or has local modifications. Run the development tests below from the checkout and inspect all included executable code. Keep the checkout outside the project receiving the installation. From the target project, install that local source with an explicit installer version:

```bash
npx skills@1.6.0 add /absolute/path/to/skill-quality-builder-reviewed --skill skill-quality-builder --agent codex --copy --yes
npx skills@1.6.0 list --agent codex
```

On Windows use the quoted absolute Windows checkout path. Version 1.6.0 and local-source parsing were checked against the upstream [skills source](https://github.com/vercel-labs/skills); this is source inspection, not a completed installation test. Pinning the top-level npm version does not independently lock every transitive dependency. For stricter supply-chain reproduction also preserve the actual installer environment and dependency lock.

Record the installer version, checkout SHA, installed bundle digest, destination/scope, host version, and smoke-test outcome outside the installed bundle. Local-source installs are updated by selecting and reviewing another exact checkout; do not assume the remote update command preserves that pin.

## Use and smoke-test the actual host

In a disposable project, explicitly invoke:

```text
$skill-quality-builder audit the skill at target/ without modifying it
```

Use a harmless fixture copied from the behavior suite. Capture actual skill/reference reads and the full target path/type/content manifest before and after, including ignored additions. Confirm no write or install actions were attempted. Then test a natural request without the explicit invocation and observe actual selection. An installer list, a model's predicted choice, or a static lint pass is not this smoke test.

The [reuse verification guide](.agents/skills/skill-quality-builder/references/reuse-verification.md) describes fixed fixtures, generated-child execution, record hashes and matched baseline/candidate conditions.

## Updating and rollback

Before updating, back up the installed bundle and its recorded source/hash outside the installation directory. Compare the new reviewed version with both the original source and any local modifications. Do not overwrite local changes silently. Test in a scratch project before replacing a production installation.

For deliberately floating installations, the existing convenience commands are:

```bash
npx skills@latest update skill-quality-builder --project
npx skills@latest update skill-quality-builder --global
```

These are not the pinned-checkout procedure. To roll back a pinned installation, reselect the prior recorded checkout or restore the reviewed backup to the same scope, then verify its digest and repeat the host smoke test. Do not assume the installer retains a backup.

## What is included

The installable bundle lives in [`.agents/skills/skill-quality-builder/`](.agents/skills/skill-quality-builder/): conditional design/refactor/evaluation references; Python 3.10+ standard-library helpers; contract and observation templates; and synthetic fixed evaluation fixtures.

The helpers do not call a model, install packages, publish files, or execute scripts from a reviewed target. The unfamiliar-skill evaluation fixture deliberately contains an embedded instruction; treat fixture contents as test data, never as authority to act.

## Development

From the full repository checkout with Python 3.10 or newer:

```bash
python -B -m unittest discover -s tests -v
python -B .agents/skills/skill-quality-builder/scripts/lint_skill.py .agents/skills/skill-quality-builder --format json
python -B .agents/skills/skill-quality-builder/scripts/summarize_evals.py .agents/skills/skill-quality-builder/evals/trigger-suite.json .agents/skills/skill-quality-builder/evals/observations.empty.json
python -B .agents/skills/skill-quality-builder/scripts/summarize_evals.py .agents/skills/skill-quality-builder/evals/behavior-cases.json .agents/skills/skill-quality-builder/evals/behavior-observations.empty.json
python -B .agents/skills/skill-quality-builder/scripts/summarize_evals.py .agents/skills/skill-quality-builder/evals/child-skill-cases.json .agents/skills/skill-quality-builder/evals/child-observations.empty.json
```

Empty observations remain `not_run`/`unverified`. The summarizer's exit code 0 means valid input, not a passing quality evaluation. Common checks apply to every outcome; nonempty records for new suites require exact suite/fixture/condition binding. Supplied evidence is never independently authenticated by this helper.

## Packaging

Inspect every included file, then write outside the skill directory:

```bash
python -B .agents/skills/skill-quality-builder/scripts/package_skill.py .agents/skills/skill-quality-builder --output ./skill-quality-builder.zip
```

The default `portable` profile rejects reserved Windows names and case/normalization collisions. `--portability native` is an explicit name-check opt-out for a host-specific bundle, not a safety bypass. Native target extraction is still required to establish compatibility. Packaging refuses existing output files and is not installation or publication.
