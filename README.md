# Skill Quality Builder

This repository contains a project-scoped Codex skill for creating, improving, auditing, and tuning reusable Agent Skill bundles.

The installable skill lives at [`.agents/skills/skill-quality-builder/`](.agents/skills/skill-quality-builder/). Codex can discover it from this repository and it can be invoked explicitly as `$skill-quality-builder`.

## Local validation

Run these commands from the repository root with Python 3.10 or newer:

```powershell
python -m unittest discover -s tests -v
python .agents/skills/skill-quality-builder/scripts/lint_skill.py .agents/skills/skill-quality-builder --format json
python .agents/skills/skill-quality-builder/scripts/summarize_evals.py .agents/skills/skill-quality-builder/evals/trigger-suite.json .agents/skills/skill-quality-builder/evals/observations.empty.json
```

The structural linter and evaluation summarizer do not run an agent model or certify task quality. Empty observation files intentionally produce `not_run` results.

## Packaging

Review every file in the skill directory before packaging. Then write the archive outside that directory:

```powershell
python .agents/skills/skill-quality-builder/scripts/package_skill.py .agents/skills/skill-quality-builder --output ./skill-quality-builder.zip
```

Packaging creates an archive; it does not install or publish the skill.
