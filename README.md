# Skill Quality Builder

Create, improve, and audit reusable Agent Skills with built-in validation, packaging, evaluation templates, and adversarial review guidance.

## Install in 30 seconds

Requires Node.js 22.20 or later; `npx` is included with npm. Run this command in the project where you want to use the skill:

```bash
npx skills@latest add idnotbe/skill-quality-builder
```

The installer detects supported coding agents and asks you to choose agents and installation scope when a choice is needed.

For a non-interactive, global Codex installation:

```bash
npx skills@latest add idnotbe/skill-quality-builder --skill skill-quality-builder --agent codex --global --copy --yes
```

No plugin setup or separate npm package is required. The [`skills`](https://github.com/vercel-labs/skills) CLI discovers the existing `.agents/skills/skill-quality-builder/SKILL.md` file directly from this repository.

Want to inspect what the installer finds before installing?

```bash
npx skills@latest add idnotbe/skill-quality-builder --list
```

After installation, confirm that the installer recorded the skill for Codex at the scope you selected:

```bash
# Project installation
npx skills@latest list --agent codex

# Global installation
npx skills@latest list --global --agent codex
```

## Use the skill

Ask your agent to create, improve, audit, or tune an Agent Skill. In Codex, you can invoke it explicitly:

```text
$skill-quality-builder audit the skill in .agents/skills/my-skill
```

The skill can also be selected automatically when your request clearly asks for a reusable skill or a review of one.

## Update

Update a project installation:

```bash
npx skills@latest update skill-quality-builder --project
```

Update a global installation:

```bash
npx skills@latest update skill-quality-builder --global
```

## What is included

The installable bundle lives in [`.agents/skills/skill-quality-builder/`](.agents/skills/skill-quality-builder/). It includes:

- instructions for skill design, refactoring, evaluation, safety, and adversarial review;
- Python 3.10+ standard-library helpers for initialization, structural linting, packaging, and evaluation summaries;
- reusable contract, preservation, evaluation, observation, and report templates.

The helpers do not call a model, install packages, publish files, or run scripts from a skill being reviewed. Review third-party skill contents before executing any included code.

## Development

Run these commands from the repository root with Python 3.10 or newer:

```bash
python -m unittest discover -s tests -v
python .agents/skills/skill-quality-builder/scripts/lint_skill.py .agents/skills/skill-quality-builder --format json
python .agents/skills/skill-quality-builder/scripts/summarize_evals.py .agents/skills/skill-quality-builder/evals/trigger-suite.json .agents/skills/skill-quality-builder/evals/observations.empty.json
```

The structural linter and evaluation summarizer do not run an agent model or certify task quality. Empty observation files intentionally produce `not_run` results.

## Packaging

Review every file in the skill directory before packaging. Then write the archive outside that directory:

```bash
python .agents/skills/skill-quality-builder/scripts/package_skill.py .agents/skills/skill-quality-builder --output ./skill-quality-builder.zip
```

Packaging creates an archive; it does not install or publish the skill.
