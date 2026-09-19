# Installation and distribution

This repository ships **skill-quality-builder** as one canonical Agent Skill and as a skills-only
plugin for Claude and ChatGPT/Codex. Choose one installation mode per host and
scope to avoid duplicate activation. Review executable files before installation.

## Standalone skill: Windows and Linux

Use a supported Node.js LTS release (CI uses Node.js 24), npm and Git. From the
project that will receive the skill, not from this source checkout:

```sh
npx skills@latest add idnotbe/skill-quality-builder --list
npx skills@latest add idnotbe/skill-quality-builder --skill skill-quality-builder --agent codex claude-code --copy
```

Select only `codex` or `claude-code` when installing for one host. Add `--global`
for user-wide installation. `--copy` avoids Windows symlink privileges. In
PowerShell, `npx.cmd` is an alternative when execution policy blocks `npx.ps1`;
there is no need to weaken execution policy. Quote local paths containing spaces.
These are local-host commands, not installation into a remote ChatGPT web account.

Invoke `$skill-quality-builder` in Codex or `/skill-quality-builder` in Claude Code. The host chooses when to
load skills; host-specific invocation policy is not silently changed by packaging.
Copy the whole skill folder, including references, scripts and host metadata,
when using a host's manual skill-import UI. Do not upload only `SKILL.md`.
Python 3.10+ is needed for repository checks and skill-quality-builder's optional
helpers; deep-inquiry and vibe-check are instruction-only at runtime.

## Claude plugin

```sh
claude plugin marketplace add idnotbe/claude-plugins
claude plugin install skill-quality-builder@idnotbe
```

Inside Claude Code the corresponding commands are `/plugin marketplace add`
and `/plugin install`. Invoke the plugin skill as `/skill-quality-builder:skill-quality-builder`.
The marketplace already includes other plugins; this installation selects only
this plugin. Claude desktop/workspace surfaces must expose their own plugin
installation controls; a local CLI install does not change a remote account.

## ChatGPT/Codex plugin

```sh
codex plugin marketplace add idnotbe/chatgpt-plugins
codex plugin marketplace list
```

In a compatible ChatGPT desktop plugin UI, select the `idnotbe-chatgpt-plugins`
marketplace and install **skill-quality-builder**. The CLI commands register a catalog; they are
not a claim that GUI installation or a model invocation has occurred. For a
ChatGPT web/workspace deployment, an authorized workspace administrator imports
or syncs the GitHub marketplace through the available plugin-management UI.
Account, workspace policy and host-version availability still apply. There is no
universal-public-directory publication or automatic account installation here.

## One source, two manifests

```text
.agents/skills/skill-quality-builder/       Canonical runtime bundle (standalone installation)
.claude-plugin/plugin.json   Claude compatibility manifest
.codex-plugin/plugin.json    OpenAI compatibility manifest
```

Both manifests point `skills` to `./.agents/skills/` and carry the same identity
and release version. This deliberately uses the supported compatibility layout:
a root portable `plugin.json` would impose the fixed `skills/` layout and take
precedence. Do not add it, duplicate the skill, or replace the folder with a
symlink. No MCP server, automatic hooks, credentials or background process is
introduced. Marketplace repositories contain references, not skill copies.

For a reproducible installation, review a checkout at a full commit SHA and
install its quoted absolute path with a pinned `skills` CLI version. `@latest`
and the short GitHub source command float. Back up local modifications before
updating; installers may replace existing files. Keep the previous reviewed
revision for rollback. Do not install project and global copies unintentionally.
For plugin releases, bump both manifest versions together and update the full
source SHA in each marketplace after the source commit has passed review and
merged. Updating a marketplace does not approve unreviewed source changes.

## Verification boundaries

```sh
python -B -m unittest discover -s tests -p test_distribution.py -v
python -B tools/distribution.py
```

After installing the current official Claude Code and Codex CLIs, run the explicit
networked integration evaluation in a disposable environment:

```sh
python -B tools/distribution.py --smoke --report distribution-report.json
```

The same workflow runs on native Windows and Linux. It checks actual `skills`
discovery, project/global copy installation and repeated installation, compares
all installed bytes, validates and installs a Claude plugin through a temporary
marketplace, and verifies Codex marketplace registration. It records exact CLI
versions and keeps all installation state in a temporary home with spaces in its
path. Existing repository regression/evaluation checks remain in place.

Inspect the actual report and CI conclusion for the exact commit. A configured
workflow is not a passing run. GUI installation, ChatGPT workspace import,
natural triggering, authenticated model execution and quality improvements are
separate checks and are explicitly `not_run` here. Existing model-evaluation
results are not relabeled as packaging evidence or newly executed trials.

## Upstream contracts

Verified September 19, 2026:

- [Skills CLI](https://github.com/vercel-labs/skills)
- [Claude plugin reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [OpenAI plugin build and marketplace reference](https://developers.openai.com/plugins/build/plugins)
- [ChatGPT plugins](https://learn.chatgpt.com/docs/plugins)
